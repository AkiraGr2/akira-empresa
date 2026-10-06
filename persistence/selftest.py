"""Autopruebas de Fase 4/5/6/7/8/9. Cada resultado: PASS, FAIL, PENDING o N/A. Nada se da por bueno sin comprobarlo.

- run_logic_tests: pruebas de comportamiento (validacion, idempotencia, versiones, privacidad, rollback, agentes+tareas).
- run_restart_probe: prueba REAL de reinicio. Un proceso escribe una sonda; otro proceso distinto la relee.

Fase 1.6 (2026-10-01): la limpieza de memorias de prueba ahora hace HARD DELETE (repo.delete),
no archive_memory. Antes se acumulaban ~6 filas selftest por cada corrida del selftest,
contaminando la tabla memories. Ahora no queda rastro.
"""
from __future__ import annotations

import hashlib
import json
import inspect
import time
import uuid

import akira_auth

from .core import (ConflictError, GRAPH_EDGE_SCHEMA_VERSION, GRAPH_NODE_SCHEMA_VERSION,
                   LEARNING_SCHEMA_VERSION, NotFoundError, PersistenceError, ValidationError, new_id,
                   _SELF_MODEL_DERIVED_FIELDS,
                   validate_graph_edge, validate_graph_node, validate_memory, validate_learning_event)
from .memory_recall import recall_memories
from .model_registry import model_registry_snapshot, PRIMARY_CHAT_MODEL, GEMINI_REASONING_MODEL, GEMINI_CHAT_FALLBACK_VARIANT, GROQ_FALLBACK_MODELS, OPENROUTER_MODEL_ROUTE, MISTRAL_MODEL_ROUTE, MEMORY_EMBEDDING_MODEL
from .capability import (
    CapabilityContractError,
    derive_effective_state,
    validate_capability,
    validate_capability_state,
    validate_capability_transition,
)

PROBE_KEY = "selftest:restart-probe:v1"
PROBE_CONTENT = "AKIRA selftest restart probe v1: si puedes leer esto tras un reinicio, la persistencia funciona."

# V8-Fase9: agente de prueba aislado. Se crea al vuelo y se deshabilita al terminar.
_TEST_AGENT_NAME = "selftest_agent"


class _Abort(Exception):
    pass


def _res(name, ok, detail):
    return {"test": name, "status": "PASS" if ok else "FAIL", "detail": detail}


def _mem(marker, **over):
    base = {"content": f"selftest {marker}", "memory_type": "system", "importance": 1, "confidence": 1.0,
            "source": "selftest", "tags": ["selftest"], "privacy_level": "PRIVATE"}
    base.update(over)
    return base


def _guard(name, fn, service, created_ids):
    before_memory_ids = set(created_ids)
    try:
        result = fn()
        if result.get("status") == "FAIL":
            print(
                f"[persistence] selftest {name} FAIL: "
                f"{str(result.get('detail') or '')[:500]}",
                flush=True,
            )
        return result
    except Exception as e:  # un fallo de la prueba es un FAIL, no un crash
        detail = f"excepcion {type(e).__name__}: {str(e)[:120]}"
        print(f"[persistence] selftest {name} FAIL: {detail}", flush=True)
        return _res(name, False, detail)
    finally:
        new_memory_ids = [mid for mid in created_ids if mid not in before_memory_ids]
        for mid in new_memory_ids:
            try:
                service.repo.delete("memories", mid)
            except Exception as cleanup_error:
                print(
                    f"[persistence] selftest memory cleanup warning: "
                    f"{mid}: {type(cleanup_error).__name__}",
                    flush=True,
                )
        if new_memory_ids:
            created_ids[:] = [mid for mid in created_ids if mid not in new_memory_ids]


def _ensure_tools(service):
    """Verifica el contrato de las tools reales sin modificar el registry de producción."""
    expected = ("memory_save", "memory_search")
    problems = []
    for name in expected:
        tool = service.get_tool_by_name(name)
        if tool is None:
            problems.append(f"{name}:missing")
            continue
        permissions = {str(p).strip() for p in (tool.get("permissions") or [])}
        if permissions != {"owner"}:
            problems.append(f"{name}:permissions={sorted(permissions)}")
        if tool.get("status") != "available":
            problems.append(f"{name}:status={tool.get('status')}")
    if problems:
        raise ValidationError("tool contract invalid: " + ", ".join(problems))


def _ensure_test_agent(service):
    """Crea o reutiliza el agente de prueba. Idempotente por name."""
    existing = service.get_agent_by_name(_TEST_AGENT_NAME)
    if existing is not None:
        # Re-habilitar por si quedo disabled de una corrida anterior
        if existing.get("status") == "disabled":
            try:
                service.update_agent(_TEST_AGENT_NAME, {"status": "idle"}, actor="selftest")
            except Exception:
                pass
        return existing
    r = service.register_agent({
        "name": _TEST_AGENT_NAME,
        "role": "generic",
        "description": "Agente de autopruebas. Se deshabilita al final.",
        "allowed_tools": ["memory_save", "memory_search"],
    }, actor="selftest")
    return r["record"]


def _disable_test_agent(service):
    try:
        service.update_agent(_TEST_AGENT_NAME, {"status": "disabled"}, actor="selftest")
    except Exception:
        pass


def run_logic_tests(service, fresh_service_factory=None):
    """fresh_service_factory: opcional, devuelve un servicio con conexiones nuevas ('reinicio suave')."""
    created_ids = []
    created_task_ids = []
    created_mission_ids = []
    results = []

    # ---------- MEMORIA (Fase 4/5) ----------
    def t_memory_persistence():
        name = "TEST_MEMORY_PERSISTENCE (reinicio suave)"
        r = service.save_memory(_mem(uuid.uuid4().hex), actor="selftest")
        rec = r["record"]
        created_ids.append(rec["id"])
        if r["outcome"] != "created" or not rec["id"].startswith("mem_"):
            return _res(name, False, "no se creo con ID valido")
        if not service.exists_memory(rec["id"]):
            return _res(name, False, "exists devolvio falso")
        if service.get_memory(rec["id"])["content"] != rec["content"]:
            return _res(name, False, "contenido distinto al releer")
        other = fresh_service_factory() if fresh_service_factory else service
        again = other.get_memory(rec["id"])
        ok = again is not None and again["content"] == rec["content"] and again["version"] == 1
        return _res(name, ok, "releido con servicio/conexiones nuevas" if fresh_service_factory
                    else "releido con el mismo servicio (no prueba reinicio)")

    def t_idempotent():
        name = "TEST_IDEMPOTENT_SYNC"
        key = f"selftest:idem:{uuid.uuid4().hex}"
        a = service.save_memory(_mem("idem"), actor="selftest", idempotency_key=key)
        b = service.save_memory(_mem("idem"), actor="selftest", idempotency_key=key)
        created_ids.append(a["record"]["id"])
        n = service.count_memory({"idempotency_key": key})
        ok = (a["outcome"] == "created" and b["outcome"] == "already_synced"
              and a["record"]["id"] == b["record"]["id"] and n == 1)
        return _res(name, ok, f"registros con la misma clave: {n}")

    def t_private():
        name = "TEST_PRIVATE_MEMORY"
        marker = f"priv-{uuid.uuid4().hex}"
        p = service.save_memory(_mem(marker, content=f"selftest {marker}", privacy_level="PRIVATE"), actor="selftest")
        s = service.save_memory(_mem(marker, content=f"selftest {marker}", privacy_level="SHAREABLE"), actor="selftest")
        created_ids.extend([p["record"]["id"], s["record"]["id"]])
        hive_ids = {r["id"] for r in service.search_memory({"text_contains": marker}, hive=True)}
        ok = p["record"]["id"] not in hive_ids and s["record"]["id"] in hive_ids
        return _res(name, ok, "PRIVATE fuera del Hive y SHAREABLE dentro (control positivo)")

    def t_versioning():
        name = "TEST_VERSIONING_CONFLICT"
        r = service.save_memory(_mem("ver"), actor="selftest")
        mid = r["record"]["id"]
        created_ids.append(mid)
        v2 = service.update_memory(mid, {"importance": 2}, expected_version=1, actor="selftest")
        try:
            service.update_memory(mid, {"importance": 3}, expected_version=1, actor="selftest")
            return _res(name, False, "la segunda actualizacion con version vieja NO dio conflicto")
        except ConflictError:
            pass
        final = service.get_memory(mid)
        return _res(name, v2["version"] == 2 and final["version"] == 2 and final["importance"] == 2,
                    "version 1->2 y conflicto detectado")

    def t_archive():
        name = "TEST_ARCHIVE_SOFT_DELETE"
        marker = f"arch-{uuid.uuid4().hex}"
        r = service.save_memory(_mem(marker), actor="selftest")
        mid = r["record"]["id"]
        created_ids.append(mid)
        a = service.archive_memory(mid, actor="selftest")
        hidden = mid not in {x["id"] for x in service.search_memory({"text_contains": marker})}
        return _res(name, a["status"] == "archived" and hidden and service.exists_memory(mid),
                    "archivada, oculta en busqueda normal y aun recuperable")

    def t_validation():
        name = "TEST_VALIDATION_REJECTS"
        before = service.count_memory({"status__in": ["active", "archived", "deleted"]})
        bad = [
            _mem("x", content="   "),
            _mem("x", privacy_level="PUBLIC"),
            _mem("x", importance=99),
            dict(_mem("x"), id="mem_forzado"),
        ]
        rejected = 0
        for b in bad:
            try:
                service.save_memory(b, actor="selftest")
            except ValidationError:
                rejected += 1
        after = service.count_memory({"status__in": ["active", "archived", "deleted"]})
        return _res(name, rejected == len(bad) and before == after, f"rechazados {rejected}/{len(bad)}, sin escrituras")

    def t_rollback():
        name = "TEST_TRANSACTION_ROLLBACK"
        rec = dict(validate_memory(_mem("rb")), id=new_id("mem"), status="active", schema_version="memory.v1")
        try:
            with service.repo.transaction() as tx:
                tx.create("memories", rec)
                raise _Abort()
        except _Abort:
            pass
        return _res(name, not service.exists_memory(rec["id"]), "el registro no existe tras el rollback")

    # ---------- AGENTES + TAREAS (Fase 9) ----------
    def t_agent_task_persistence():
        name = "TEST_AGENT_TASK_PERSISTENCE"
        _ensure_tools(service)
        _ensure_test_agent(service)
        # Crear task
        cr = service.create_task(_TEST_AGENT_NAME, "memory_search",
                                 inputs={"query": "selftest"}, actor="selftest")
        task_id = cr["record"]["id"]
        created_task_ids.append(task_id)
        if not task_id.startswith("task_"):
            return _res(name, False, "task_id no empieza con task_")
        # Start y complete
        service.start_task(task_id, actor="selftest")
        service.complete_task(task_id, outputs={"found": 0}, duration_ms=42, actor="selftest")
        # Releer con servicio fresco si esta disponible
        other = fresh_service_factory() if fresh_service_factory else service
        again = other.get_task(task_id)
        ok = (again is not None and again["status"] == "completed"
              and again["duration_ms"] == 42)
        return _res(name, ok, "task persistida, completada y releida" if ok else "task no coincide al releer")

    def t_agent_task_validation():
        name = "TEST_AGENT_TASK_VALIDATION"
        _ensure_tools(service)
        _ensure_test_agent(service)
        # Agente no puede usar tool que no esta en allowed_tools
        try:
            service.create_task(_TEST_AGENT_NAME, "web_search",
                                inputs={"query": "x"}, actor="selftest")
            return _res(name, False, "acepto tool no permitida (web_search)")
        except ValidationError:
            pass
        # Tool inexistente
        try:
            service.create_task(_TEST_AGENT_NAME, "tool_que_no_existe",
                                inputs={}, actor="selftest")
            return _res(name, False, "acepto tool inexistente")
        except (ValidationError, Exception) as e:
            # create_task lanza NotFoundError si el tool no existe
            if "no existe" not in str(e) and type(e).__name__ not in ("NotFoundError", "ValidationError"):
                return _res(name, False, f"excepcion inesperada: {type(e).__name__}")
        # Agente inexistente
        try:
            service.create_task("agente_que_no_existe", "memory_save",
                                inputs={"content": "x"}, actor="selftest")
            return _res(name, False, "acepto agente inexistente")
        except (ValidationError, Exception) as e:
            if "no existe" not in str(e) and type(e).__name__ not in ("NotFoundError", "ValidationError"):
                return _res(name, False, f"excepcion inesperada: {type(e).__name__}")
        return _res(name, True, "rechazo tool no permitida, tool inexistente y agente inexistente")

    def t_tool_permission_contract():
        name = "TEST_TOOL_PERMISSION_CONTRACT"
        _ensure_tools(service)
        return _res(
            name,
            True,
            "memory_save y memory_search existen, estan disponibles y tienen permissions=[owner]",
        )

    def t_identity_root_contract():
        name = "TEST_IDENTITY_ROOT_CONTRACT"
        root = service.get_identity_root()
        db_root = service.repo.get("identity_root", "akira_primary")
        ok = (
            root.get("name") == "Akira"
            and root.get("creator") == "Jhon Grimm"
            and root.get("language") == "es-CO"
            and root.get("root_schema_version") == "identity_root.v1"
            and isinstance(db_root, dict)
            and db_root.get("canonical_name") == "Akira"
            and db_root.get("creator") == "Jhon Grimm"
            and db_root.get("language") == "es-CO"
            and db_root.get("root_schema_version") == "identity_root.v1"
        )
        return _res(name, ok, "Identity Root de codigo y espejo persistente son consistentes")

    def t_self_model_identity_protected():
        name = "TEST_SELF_MODEL_IDENTITY_PROTECTED"
        current = service.get_self_model()
        before = dict(current.get("identity") or {})
        try:
            service.update_self_model(
                {"identity": {"name": "Otra identidad"}},
                current["version"],
                actor="selftest",
            )
        except ValidationError:
            after = dict(service.get_self_model().get("identity") or {})
            return _res(name, after == before, "identity rechazada y no modificada")
        except Exception as e:
            return _res(name, False, f"error inesperado: {type(e).__name__}")
        return _res(name, False, "identity fue aceptada por update_self_model")

    def t_model_route_registry_contract():
        name = "TEST_MODEL_ROUTE_REGISTRY_CONTRACT"
        snapshot = model_registry_snapshot()
        routes = {(row.get("provider"), row.get("model"), row.get("role")) for row in snapshot.get("routes") or []}
        expected = {
            ("gemini", PRIMARY_CHAT_MODEL, "primary_chat"),
            ("gemini", GEMINI_REASONING_MODEL, "reasoning"),
            ("gemini", GEMINI_CHAT_FALLBACK_VARIANT, "chat_fallback_variant"),
            ("groq", GROQ_FALLBACK_MODELS[0], "fallback"),
            ("groq", GROQ_FALLBACK_MODELS[1], "fallback"),
            ("groq", GROQ_FALLBACK_MODELS[2], "fallback"),
            ("openrouter", OPENROUTER_MODEL_ROUTE, "fallback_dynamic"),
            ("mistral", MISTRAL_MODEL_ROUTE, "fallback"),
            ("gemini", MEMORY_EMBEDDING_MODEL, "memory_embedding"),
        }
        missing = sorted(expected - routes)
        duplicate_keys = []
        seen = set()
        for row in snapshot.get("routes") or []:
            key = (row.get("provider"), row.get("model"), row.get("role"))
            if key in seen:
                duplicate_keys.append(key)
            seen.add(key)
        ok = snapshot.get("schema_version") == "model_route.v1" and not missing and not duplicate_keys
        return _res(
            name,
            ok,
            "registro de rutas activo, completo y sin duplicados"
            if ok else f"faltantes={missing}; duplicados={duplicate_keys}; schema={snapshot.get('schema_version')}",
        )

    def t_self_model_derived_fields_protected():
        name = "TEST_SELF_MODEL_DERIVED_FIELDS_PROTECTED"
        current = service.get_self_model()
        failures = []
        for field in sorted(_SELF_MODEL_DERIVED_FIELDS):
            try:
                service.update_self_model({field: []}, current["version"], actor="selftest")
            except ValidationError:
                continue
            except Exception as e:
                failures.append(f"{field}:unexpected_{type(e).__name__}")
                continue
            failures.append(f"{field}:accepted")
        return _res(
            name,
            not failures,
            "campos derivados protegidos: " + ", ".join(sorted(_SELF_MODEL_DERIVED_FIELDS))
            if not failures else "; ".join(failures),
        )

    def t_agent_task_mission_filter():
        name = "TEST_AGENT_TASK_MISSION_FILTER"
        _ensure_tools(service)
        _ensure_test_agent(service)
        mission = service.create_mission(
            {
                "title": f"selftest mission {uuid.uuid4().hex[:8]}",
                "objective": "fixture temporal para probar mission_id en agent_tasks",
                "status": "created",
                "priority": 1,
                "flow_type": "generic",
            },
            actor="selftest",
        )
        mission_id = mission["record"]["id"]
        created_mission_ids.append(mission_id)
        ids = []
        for i in range(3):
            r = service.create_task(
                _TEST_AGENT_NAME,
                "memory_save",
                inputs={"content": f"selftest m{i}", "memory_type": "system"},
                mission_id=mission_id,
                actor="selftest",
            )
            tid = r["record"]["id"]
            ids.append(tid)
            created_task_ids.append(tid)
            service.complete_task(tid, outputs={}, duration_ms=1, actor="selftest")
        rows = service.list_tasks(mission_id=mission_id, limit=10)
        filtered = [r for r in rows if r.get("mission_id") == mission_id]
        ok = len(filtered) == 3 and all(r["id"] in ids for r in filtered)
        return _res(name, ok, f"3 tasks con mission_id, filtradas: {len(filtered)}")

    def t_agent_task_owner_scope_filter():
        name = "TEST_AGENT_TASK_OWNER_SCOPE_FILTER"
        _ensure_tools(service)
        _ensure_test_agent(service)
        scope_a = "selftest_scope_a"
        scope_b = "selftest_scope_b"
        ids = []
        for scope in (scope_a, scope_b):
            r = service.create_task(
                _TEST_AGENT_NAME,
                "memory_search",
                inputs={"query": "selftest"},
                actor="selftest",
                owner_scope=scope,
            )
            ids.append((r["record"]["id"], scope))
            created_task_ids.append(r["record"]["id"])
        rows_a = service.list_tasks(owner_scope=scope_a, limit=20)
        rows_b = service.list_tasks(owner_scope=scope_b, limit=20)
        ids_a = {r["id"] for r in rows_a}
        ids_b = {r["id"] for r in rows_b}
        ok = (
            ids[0][0] in ids_a
            and ids[1][0] not in ids_a
            and ids[1][0] in ids_b
            and ids[0][0] not in ids_b
        )
        return _res(name, ok, "cada owner_scope solo recupera sus agent_tasks")

    def t_specialized_agents_persistence():
        name = "TEST_SPECIALIZED_AGENTS_PERSISTENCE"
        expected_tools = {
            "developer_propose": {"permissions": {"owner"}, "status": "available"},
            "python_test": {"permissions": {"owner"}, "status": "available"},
            "code_review": {"permissions": {"owner"}, "status": "available"},
        }
        expected_agents = {
            "developer": {"role": "developer", "allowed_tools": ["github_repo_read", "developer_propose"]},
            "tester": {"role": "tester", "allowed_tools": ["github_repo_read", "python_test"]},
            "reviewer": {"role": "reviewer", "allowed_tools": ["github_repo_read", "python_test", "code_review"]},
        }
        problems = []
        for tool_name, expected in expected_tools.items():
            tool = service.get_tool_by_name(tool_name)
            if tool is None:
                problems.append(f"tool_missing:{tool_name}")
                continue
            permissions = {str(p).strip() for p in (tool.get("permissions") or [])}
            if permissions != expected["permissions"]:
                problems.append(f"tool_permissions:{tool_name}:{sorted(permissions)}")
            if tool.get("status") != expected["status"]:
                problems.append(f"tool_status:{tool_name}:{tool.get('status')}")
        for agent_name, expected in expected_agents.items():
            agent = service.get_agent_by_name(agent_name)
            if agent is None:
                problems.append(f"agent_missing:{agent_name}")
                continue
            if agent.get("role") != expected["role"]:
                problems.append(f"agent_role:{agent_name}:{agent.get('role')}")
            if list(agent.get("allowed_tools") or []) != expected["allowed_tools"]:
                problems.append(f"agent_tools:{agent_name}:{agent.get('allowed_tools')}")
        return _res(name, not problems, "specialized tools/agents persisted" if not problems else "; ".join(problems))

    def t_repair_engine_v1_capability():
        name = "TEST_REPAIR_ENGINE_V1_CAPABILITY"
        rows = service.list_capabilities(filters={"name": "repair_engine_v1"}, limit=1)
        if not rows:
            return _res(name, False, "capacidad repair_engine_v1 no registrada por la migracion")
        capability = rows[0]
        try:
            from .repair import REPAIR_ACTIONS, REPAIR_STAGES, REPAIR_STAGE_TRANSITIONS
            required_methods = (
                "create_repair", "get_repair", "list_repairs", "advance_repair",
                "sandbox_repair", "test_repair", "evaluate_repair",
                "approve_repair", "discard_repair", "apply_repair",
            )
            checks = {
                "capability_declared": capability.get("implementation_state") == "implemented",
                "action_catalog_allowlisted": (
                    set(REPAIR_ACTIONS)
                    == {
                        "disable_selftest_agent",
                        "detach_orphan_selftest_task",
                        "recover_stale_selftest_task",
                    }
                    and all(v.get("safe_scope") == "system" for v in REPAIR_ACTIONS.values())
                ),
                "full_stage_contract": (
                    tuple(REPAIR_STAGES)
                    == (
                        "detected", "diagnosed", "isolated", "proposed", "sandboxed",
                        "tested", "evaluated", "approved", "applied", "discarded", "failed",
                    )
                    and REPAIR_STAGE_TRANSITIONS["approved"] == {"applied", "discarded", "failed"}
                ),
                "service_contract": all(hasattr(service, method) for method in required_methods),
            }
            ok = all(checks.values())
            source_digest = hashlib.sha256(
                inspect.getsource(service.create_repair).encode("utf-8")
                + inspect.getsource(service.apply_repair).encode("utf-8")
            ).hexdigest()[:16]
            event = {
                "event_type": "verification",
                "test_key": "repair_engine_v1_contract",
                "test_version": "v1",
                "result": "pass" if ok else "fail",
                "evidence": [{
                    "type": "selftest",
                    "title": "Repair Engine v1 controlled lifecycle",
                    "reference": "selftest:repair-engine-v1",
                    "note": (
                        "Lifecycle persistente con acciones allowlisted, sandbox, tests, "
                        "evaluacion, aprobacion explicita, apply controlado y learn."
                    ),
                    "hash": source_digest,
                }],
                "environment": {"runtime": "selftest"},
                "dependency_snapshot": [
                    {"kind": "state", "id": "SelfModel.repairs", "version": "runtime"},
                    {"kind": "service", "id": "PersistenceService.repair", "version": source_digest},
                    {"kind": "security", "id": "owner_scope", "version": "runtime"},
                ],
                "runtime_version": "selftest",
                "build_ref": source_digest,
                "actor": "selftest",
                "executor": "selftest",
                "evaluator": "system",
                "error": None if ok else {"checks": checks},
            }
            verification = service.record_capability_verification(
                capability["id"],
                event,
                actor="selftest",
                idempotency_key="selftest:repair_engine_v1:v1:" + source_digest,
            )
            effective = verification.get("effective_state")
            verified = effective == "verified" if ok else effective in ("failed", "stale")
            return _res(
                name,
                bool(ok and verified),
                f"resultado={verification.get('outcome')}; effective_state={effective}; checks={checks}",
            )
        except Exception as exc:
            return _res(name, False, f"excepcion {type(exc).__name__}: {str(exc)[:300]}")

    def t_self_knowledge_snapshot():
        name = "TEST_SELF_KNOWLEDGE_SNAPSHOT"
        snapshot = service.self_knowledge_snapshot(owner_scope="selftest")
        identity = snapshot.get("identity") or {}
        capabilities = {row.get("name"): row for row in (snapshot.get("capabilities") or [])}
        agents = {row.get("name"): row for row in (snapshot.get("agents") or [])}
        tools = {row.get("name"): row for row in (snapshot.get("tools") or [])}
        specialized = {
            "developer": ["github_repo_read", "developer_propose"],
            "tester": ["github_repo_read", "python_test"],
            "reviewer": ["github_repo_read", "python_test", "code_review"],
        }
        problems = []
        if identity.get("name") != "Akira" or identity.get("root_schema_version") != "identity_root.v1":
            problems.append("identity_root_incorrecto")
        for required in (
            "session_auth", "persistent_memory", "memory_recall",
            "learning_persistent", "graph_persistent", "selftest_capability",
        ):
            if required not in capabilities:
                problems.append(f"capability_missing:{required}")
            elif capabilities[required].get("effective_state") != "verified":
                problems.append(f"capability_not_verified:{required}")
        for agent_name, allowed_tools in specialized.items():
            agent = agents.get(agent_name)
            if agent is None:
                problems.append(f"agent_missing:{agent_name}")
                continue
            if list(agent.get("allowed_tools") or []) != allowed_tools:
                problems.append(f"agent_tools:{agent_name}")
            for tool_name in allowed_tools:
                if tool_name not in tools:
                    problems.append(f"tool_missing:{tool_name}")
        ok = not problems
        return _res(
            name,
            ok,
            "snapshot autoritativo consistente" if ok else "; ".join(problems),
        )

    def t_self_knowledge_runtime_capability():
        name = "TEST_SELF_KNOWLEDGE_RUNTIME_CAPABILITY"
        rows = service.list_capabilities(filters={"name": "self_knowledge_runtime"}, limit=1)
        if not rows:
            return _res(name, False, "capacidad self_knowledge_runtime no fue registrada por la migracion")
        capability = rows[0]
        scope = "selftest:self-knowledge-runtime"
        checks = {}
        before_counts = {}
        after_counts = {}
        try:
            for entity in ("capabilities", "agents", "tools"):
                before_counts[entity] = len(service.repo.search(
                    entity, {}, limit=500, order_by="name", descending=False
                ))

            snapshot = service.self_knowledge_snapshot(owner_scope=scope, limit=200)
            identity = snapshot.get("identity") or {}
            capabilities = {
                row.get("name"): row
                for row in (snapshot.get("capabilities") or [])
                if row.get("name")
            }
            agents = {
                row.get("name"): row
                for row in (snapshot.get("agents") or [])
                if row.get("name")
            }
            tools = {
                row.get("name"): row
                for row in (snapshot.get("tools") or [])
                if row.get("name")
            }

            required_capabilities = (
                "session_auth",
                "persistent_memory",
                "memory_recall",
                "learning_persistent",
                "graph_persistent",
                "selftest_capability",
            )
            checks["authoritative_source"] = (
                snapshot.get("source") == "runtime_authoritative_registry"
                and snapshot.get("identity_authority") == "identity_root"
            )
            checks["identity_authority"] = (
                identity.get("name") == "Akira"
                and identity.get("root_schema_version") == "identity_root.v1"
            )
            checks["capability_states_truthful"] = all(
                capabilities.get(required, {}).get("effective_state") == "verified"
                for required in required_capabilities
            )
            checks["agent_registry_present"] = bool(agents)
            checks["tool_registry_present"] = bool(tools)
            checks["agent_tool_references_resolve"] = all(
                tool_name in tools
                for agent in agents.values()
                for tool_name in (agent.get("allowed_tools") or [])
            )
            checks["owner_scoped_memory_count"] = (
                isinstance(snapshot.get("memory_active_count"), int)
                and snapshot.get("memory_active_count") >= 0
            )

            for entity in ("capabilities", "agents", "tools"):
                after_counts[entity] = len(service.repo.search(
                    entity, {}, limit=500, order_by="name", descending=False
                ))
            checks["snapshot_non_mutating"] = before_counts == after_counts

            fresh_service = fresh_service_factory() if fresh_service_factory else service
            fresh_snapshot = fresh_service.self_knowledge_snapshot(owner_scope=scope, limit=200)
            checks["fresh_connection_reproducible"] = fresh_snapshot == snapshot

            ok = all(checks.values())
            snapshot_digest = hashlib.sha256(
                json.dumps(
                    snapshot,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                ).encode("utf-8")
            ).hexdigest()[:16]
            source_digest = hashlib.sha256(
                inspect.getsource(service.self_knowledge_snapshot).encode("utf-8")
            ).hexdigest()[:16]
            evidence = [{
                "type": "selftest",
                "title": "Self-knowledge runtime contract",
                "reference": "selftest:self-knowledge-runtime/v1",
                "summary": (
                    "Snapshot autoritativo reproducible, no mutante y con referencias agent->tool integras."
                    if ok else "El contrato de autoconocimiento runtime no supero todos los controles."
                ),
                "hash": snapshot_digest,
            }]
            event = {
                "event_type": "verification",
                "test_key": "self_knowledge_runtime_contract",
                "test_version": "v1",
                "result": "pass" if ok else "fail",
                "evidence": evidence,
                "environment": {
                    "runtime": "selftest",
                    "snapshot_source": snapshot.get("source"),
                },
                "dependency_snapshot": [
                    {"kind": "authority", "id": "IdentityRoot", "version": identity.get("root_schema_version", "unknown")},
                    {"kind": "registry", "id": "CapabilityEngine", "version": source_digest},
                    {"kind": "storage", "id": "PostgreSQL.capabilities", "version": "runtime"},
                    {"kind": "storage", "id": "PostgreSQL.agents", "version": "runtime"},
                    {"kind": "storage", "id": "PostgreSQL.tools", "version": "runtime"},
                    {"kind": "security", "id": "owner_scope", "version": "runtime"},
                ],
                "runtime_version": "selftest",
                "build_ref": source_digest,
                "actor": "selftest",
                "executor": "selftest",
                "evaluator": "system",
                "error": None if ok else {"checks": checks},
            }
            idem = "selftest:self_knowledge_runtime:v1:" + source_digest + ":" + snapshot_digest
            verification = service.record_capability_verification(
                capability["id"],
                event,
                actor="selftest",
                idempotency_key=idem,
            )
            effective = verification.get("effective_state")
            verified = effective == "verified" if ok else effective in ("failed", "stale")
            return _res(
                name,
                bool(ok and verified),
                f"resultado={verification.get('outcome')}; effective_state={effective}; checks={checks}",
            )
        except Exception as exc:
            try:
                service.record_audit(
                    "selftest",
                    "selftest.self_knowledge_runtime",
                    "capabilities",
                    capability.get("id"),
                    "failure",
                    {
                        "phase": "exception",
                        "error_type": type(exc).__name__,
                        "error": str(exc)[:500],
                        "checks": checks,
                    },
                )
            except Exception:
                pass
            return _res(name, False, f"excepcion {type(exc).__name__}: {str(exc)[:300]}")

    def t_agent_tool_reference_integrity():
        name = "TEST_AGENT_TOOL_REFERENCE_INTEGRITY"
        tools = {
            row.get("name")
            for row in service.repo.search("tools", {}, limit=500, order_by="name", descending=False)
        }
        problems = []
        for agent in service.repo.search("agents", {}, limit=500, order_by="name", descending=False):
            for tool_name in (agent.get("allowed_tools") or []):
                if tool_name not in tools:
                    problems.append(
                        f"agent={agent.get('name')}:missing_tool={tool_name}"
                    )
        return _res(
            name,
            not problems,
            "todas las referencias agent.allowed_tools apuntan a tools existentes"
            if not problems else "; ".join(problems),
        )

    def t_agent_state_transition():
        name = "TEST_AGENT_STATE_TRANSITION"
        _ensure_tools(service)
        _ensure_test_agent(service)
        # Asegurar idle
        try:
            service.update_agent(_TEST_AGENT_NAME, {"status": "idle"}, actor="selftest")
        except Exception:
            pass
        a0 = service.get_agent_by_name(_TEST_AGENT_NAME)
        if a0 is None or a0.get("status") != "idle":
            return _res(name, False, f"no arranca en idle: {a0 and a0.get('status')}")
        # Crear task y start -> debe pasar a busy
        cr = service.create_task(_TEST_AGENT_NAME, "memory_save",
                                 inputs={"content": "selftest transition", "memory_type": "system"},
                                 actor="selftest")
        tid = cr["record"]["id"]
        created_task_ids.append(tid)
        service.start_task(tid, actor="selftest")
        a1 = service.get_agent_by_name(_TEST_AGENT_NAME)
        if a1.get("status") != "busy":
            return _res(name, False, f"no paso a busy: {a1.get('status')}")
        if not a1.get("current_task_id") == tid:
            return _res(name, False, "current_task_id no apunta a la task")
        # Completar -> debe volver a idle
        service.complete_task(tid, outputs={}, duration_ms=1, actor="selftest")
        a2 = service.get_agent_by_name(_TEST_AGENT_NAME)
        ok = a2.get("status") == "idle" and a2.get("current_task_id") is None
        return _res(name, ok, "idle -> busy -> idle correcto" if ok else f"estado final: {a2.get('status')}")

    def t_learning_state_contract():
        name = "TEST_LEARNING_STATE_CONTRACT"
        valid = validate_learning_event({
            "source": "selftest",
            "event": "explicit teaching",
            "lesson": "learning state contract",
            "status": "candidate",
            "confidence": 0.9,
            "outcome": "unknown",
        })
        invalid = False
        try:
            validate_learning_event({
                "source": "selftest",
                "event": "bad",
                "lesson": "bad",
                "status": "not_a_learning_state",
            })
        except ValidationError:
            invalid = True
        ok = valid["status"] == "candidate" and invalid
        return _res(name, ok, "candidate valido y estados desconocidos rechazados" if ok else "fallo del contrato de estados")



    def t_graph_persistent_capability():
        name = "TEST_GRAPH_PERSISTENT_CAPABILITY"
        rows = service.list_capabilities(filters={"name": "graph_persistent"}, limit=1)
        if not rows:
            return _res(name, False, "capacidad graph_persistent no fue registrada por el bootstrap")
        capability = rows[0]

        # Limpia únicamente fixtures V12 anteriores creados por este selftest.
        # El owner_scope dedicado evita tocar datos productivos aunque compartan
        # una etiqueta parecida.
        stale_nodes = []
        for stale in service.repo.search("graph_nodes", {"status": "active"}, limit=2000):
            label = str(stale.get("label") or "")
            scope = str(stale.get("owner_scope") or "")
            if label.startswith("V12 Graph Node ") and scope.startswith("selftest:graph-persistent:"):
                stale_nodes.append(stale["id"])
        for stale_node_id in stale_nodes:
            stale_edges = {}
            for field in ("from_node", "to_node"):
                for edge in service.repo.search("graph_edges", {field: stale_node_id}, limit=5000):
                    if edge.get("id"):
                        stale_edges[edge["id"]] = edge
            for edge in stale_edges.values():
                try:
                    service.repo.delete("graph_edges", edge["id"])
                except Exception:
                    pass
            try:
                service.repo.delete("graph_nodes", stale_node_id)
            except Exception:
                pass

        scope_a = "selftest:graph-persistent:A:" + uuid.uuid4().hex[:8]
        scope_b = "selftest:graph-persistent:B:" + uuid.uuid4().hex[:8]
        created_node_ids = []
        created_edge_ids = []
        cleanup_failures = []
        checks = {}

        labels = [
            "V12 Graph Node A1 " + uuid.uuid4().hex[:8],
            "V12 Graph Node A2 " + uuid.uuid4().hex[:8],
            "V12 Graph Node B1 " + uuid.uuid4().hex[:8],
            "V12 Graph Node B2 " + uuid.uuid4().hex[:8],
        ]
        idem_node = "selftest:graph_persistent:node:" + uuid.uuid4().hex
        idem_edge = "selftest:graph_persistent:edge:" + uuid.uuid4().hex

        def _cleanup():
            edge_ids = set(created_edge_ids)
            for node_id in created_node_ids:
                for field in ("from_node", "to_node"):
                    try:
                        for edge in service.repo.search("graph_edges", {field: node_id}, limit=5000):
                            if edge.get("id"):
                                edge_ids.add(edge["id"])
                    except Exception as exc:
                        cleanup_failures.append({
                            "node_id": node_id,
                            "field": field,
                            "error": type(exc).__name__,
                        })
            for edge_id in sorted(edge_ids):
                try:
                    service.repo.delete("graph_edges", edge_id)
                except Exception as exc:
                    cleanup_failures.append({"edge_id": edge_id, "error": type(exc).__name__})
            for node_id in created_node_ids:
                try:
                    service.repo.delete("graph_nodes", node_id)
                except Exception as exc:
                    cleanup_failures.append({"node_id": node_id, "error": type(exc).__name__})

        try:
            common = {
                "node_type": "concept",
                "tags": [],
                "privacy_level": "PRIVATE",
                "node_metadata": {"suppress_tag_auto_connect": True},
            }
            a1 = service.create_node(
                {**common, "label": labels[0], "description": "V12 node A1", "owner_scope": scope_a},
                actor="selftest", idempotency_key=idem_node,
            )
            a1_repeat = service.create_node(
                {**common, "label": labels[0], "description": "V12 node A1", "owner_scope": scope_a},
                actor="selftest", idempotency_key=idem_node,
            )
            a2 = service.create_node(
                {**common, "label": labels[1], "description": "V12 node A2", "owner_scope": scope_a},
                actor="selftest",
            )
            b1 = service.create_node(
                {**common, "label": labels[2], "description": "V12 node B1", "owner_scope": scope_b},
                actor="selftest",
            )
            b2 = service.create_node(
                {**common, "label": labels[3], "description": "V12 node B2", "owner_scope": scope_b},
                actor="selftest",
            )
            created_node_ids.extend([
                a1["record"]["id"], a2["record"]["id"], b1["record"]["id"], b2["record"]["id"]
            ])

            reread_a1 = service.get_node(a1["record"]["id"], owner_scope=scope_a)
            foreign_a1 = service.get_node(a1["record"]["id"], owner_scope=scope_b)
            fresh_service = fresh_service_factory() if fresh_service_factory else service
            fresh_a1 = fresh_service.get_node(a1["record"]["id"], owner_scope=scope_a)

            updated_a1 = service.update_node(
                a1["record"]["id"],
                {"description": "V12 node A1 updated"},
                expected_version=a1["record"]["version"],
                actor="selftest", owner_scope=scope_a,
            )
            stale_blocked = False
            try:
                service.update_node(
                    a1["record"]["id"],
                    {"description": "stale update"},
                    expected_version=a1["record"]["version"],
                    actor="selftest", owner_scope=scope_a,
                )
            except ConflictError:
                stale_blocked = True

            foreign_update_blocked = False
            try:
                service.update_node(
                    a1["record"]["id"],
                    {"description": "foreign update"},
                    expected_version=updated_a1["version"],
                    actor="selftest", owner_scope=scope_b,
                )
            except NotFoundError:
                foreign_update_blocked = True

            edge_a = service.create_edge(
                {"from_node": a1["record"]["id"], "to_node": a2["record"]["id"], "relation_type": "related_to"},
                actor="selftest", owner_scope=scope_a, idempotency_key=idem_edge,
            )
            edge_a_repeat = service.create_edge(
                {"from_node": a1["record"]["id"], "to_node": a2["record"]["id"], "relation_type": "related_to"},
                actor="selftest", owner_scope=scope_a, idempotency_key=idem_edge,
            )
            edge_b = service.create_edge(
                {"from_node": b1["record"]["id"], "to_node": b2["record"]["id"], "relation_type": "related_to"},
                actor="selftest", owner_scope=scope_b,
            )
            created_edge_ids.extend([edge_a["record"]["id"], edge_b["record"]["id"]])

            edge_a_read_a = service.get_edge(edge_a["record"]["id"], owner_scope=scope_a)
            edge_a_read_b = service.get_edge(edge_a["record"]["id"], owner_scope=scope_b)
            foreign_edge_blocked = False
            try:
                service.create_edge(
                    {"from_node": a1["record"]["id"], "to_node": b1["record"]["id"], "relation_type": "related_to"},
                    actor="selftest", owner_scope=scope_a,
                )
            except (NotFoundError, ValidationError):
                foreign_edge_blocked = True

            missing_endpoint_blocked = False
            try:
                service.create_edge(
                    {"from_node": a1["record"]["id"], "to_node": "node_does_not_exist_v12", "relation_type": "related_to"},
                    actor="selftest", owner_scope=scope_a,
                )
            except NotFoundError:
                missing_endpoint_blocked = True

            related_before = service.related_nodes(a1["record"]["id"], owner_scope=scope_a)
            # La persistencia de nodos ya queda demostrada por get_node,
            # owner isolation, fresh connection y versionado. Evitamos una
            # enumeración amplia de graph_nodes durante el selftest de arranque.
            listed_a_edges = service.list_graph_edges(
                limit=50, owner_scope=scope_a,
                filters={"from_node": a1["record"]["id"]},
            )
            listed_b_edges = service.list_graph_edges(
                limit=50, owner_scope=scope_b,
                filters={"from_node": b1["record"]["id"]},
            )

            archived = service.archive_edge(
                edge_a["record"]["id"],
                expected_version=edge_a["record"]["version"],
                actor="selftest", owner_scope=scope_a,
            )
            related_after = service.related_nodes(a1["record"]["id"], owner_scope=scope_a)
            fresh_edge_b = fresh_service.get_edge(edge_b["record"]["id"], owner_scope=scope_b)

            checks["node_created"] = (
                a1["outcome"] == "created"
                and a2["outcome"] == "created"
                and b1["outcome"] == "created"
                and b2["outcome"] == "created"
                and a1["record"].get("schema_version") == GRAPH_NODE_SCHEMA_VERSION
            )
            checks["node_idempotent"] = (
                a1_repeat["outcome"] == "already_synced"
                and a1_repeat["record"]["id"] == a1["record"]["id"]
            )
            checks["node_reread"] = bool(reread_a1 and reread_a1["id"] == a1["record"]["id"])
            checks["node_foreign_read_blocked"] = foreign_a1 is None
            checks["node_fresh_connection"] = bool(fresh_a1 and fresh_a1["id"] == a1["record"]["id"])
            checks["node_versioned_update"] = (
                updated_a1["version"] == a1["record"]["version"] + 1
                and updated_a1["description"] == "V12 node A1 updated"
            )
            checks["node_stale_update_blocked"] = stale_blocked
            checks["node_foreign_update_blocked"] = foreign_update_blocked
            checks["edge_created"] = (
                edge_a["outcome"] == "created"
                and edge_b["outcome"] == "created"
                and edge_a["record"].get("schema_version") == GRAPH_EDGE_SCHEMA_VERSION
            )
            checks["edge_idempotent"] = (
                edge_a_repeat["outcome"] == "already_synced"
                and edge_a_repeat["record"]["id"] == edge_a["record"]["id"]
            )
            checks["edge_owner_isolated"] = edge_a_read_a is not None and edge_a_read_b is None
            checks["edge_foreign_create_blocked"] = foreign_edge_blocked
            checks["missing_endpoint_blocked"] = missing_endpoint_blocked
            checks["listed_a_edges_contains"] = any(
                e.get("id") == edge_a["record"]["id"] for e in listed_a_edges
            )
            checks["listed_b_edges_contains"] = any(
                e.get("id") == edge_b["record"]["id"] for e in listed_b_edges
            )
            checks["related_before_archive"] = any(
                e.get("id") == edge_a["record"]["id"] for e in related_before
            )
            checks["edge_archived"] = (
                archived.get("status") == "archived"
                and archived.get("version") == edge_a["record"]["version"] + 1
            )
            checks["archived_edge_hidden_from_related"] = not any(
                e.get("id") == edge_a["record"]["id"] for e in related_after
            )
            checks["fresh_connection_edge"] = bool(
                fresh_edge_b and fresh_edge_b["id"] == edge_b["record"]["id"]
            )

            _cleanup()
            checks["cleanup"] = not cleanup_failures
            ok = all(checks.values())

            source_digest = hashlib.sha256(
                inspect.getsource(service.__class__).encode("utf-8")
                + inspect.getsource(validate_graph_node).encode("utf-8")
                + inspect.getsource(validate_graph_edge).encode("utf-8")
            ).hexdigest()[:16]
            verification_event = {
                "event_type": "verification",
                "test_key": "graph_persistent_contract",
                "test_version": "v1",
                "result": "pass" if ok else "fail",
                "evidence": [{
                    "type": "selftest",
                    "title": "Graph persistent lifecycle and ownership",
                    "reference": "selftest:graph_persistent:v1",
                    "summary": (
                        "Nodos y aristas persistidos, relectura, reinicio suave, versionado, "
                        "idempotencia, aislamiento owner_scope, integridad de extremos y archivado."
                        if ok else
                        "El contrato de graph_persistent no supero todos los controles."
                    ),
                    "hash": source_digest,
                }],
                "environment": {
                    "runtime": "selftest",
                    "graph_node_schema": GRAPH_NODE_SCHEMA_VERSION,
                    "graph_edge_schema": GRAPH_EDGE_SCHEMA_VERSION,
                },
                "dependency_snapshot": [
                    {"kind": "service", "id": "PersistenceService.graph", "version": source_digest},
                    {"kind": "storage", "id": "PostgreSQL.graph_nodes", "version": "runtime"},
                    {"kind": "storage", "id": "PostgreSQL.graph_edges", "version": "runtime"},
                    {"kind": "security", "id": "owner_scope", "version": "runtime"},
                ],
                "runtime_version": "selftest",
                "build_ref": source_digest,
                "actor": "selftest",
                "executor": "selftest",
                "evaluator": "system",
                "error": None if ok else {
                    "checks": checks,
                    "cleanup_failures": cleanup_failures,
                },
            }
            verification = service.record_capability_verification(
                capability["id"],
                verification_event,
                actor="selftest",
                idempotency_key="selftest:graph_persistent:verification:v1:" + source_digest,
            )
            verification_ok = (
                verification.get("effective_state") == "verified"
                if ok else
                verification.get("effective_state") in ("failed", "stale")
            )
            detail = (
                f"resultado={verification.get('outcome')}; "
                f"effective_state={verification.get('effective_state')}; "
                f"checks={checks}"
            )
            return _res(name, bool(ok and verification_ok), detail)
        except Exception as exc:
            _cleanup()
            return _res(name, False, f"excepcion {type(exc).__name__}: {str(exc)[:240]}")

    def t_learning_persistent_capability():
        name = "TEST_LEARNING_PERSISTENT_CAPABILITY"
        rows = service.list_capabilities(filters={"name": "learning_persistent"}, limit=1)
        if not rows:
            return _res(name, False, "capacidad learning_persistent no fue registrada por el bootstrap")
        capability = rows[0]
        scope_a = "selftest:learning-persistent:A"
        scope_b = "selftest:learning-persistent:B"
        created_ids_local = []
        checks = {}
        cleanup_failures = []
        idem = "selftest:learning_persistent:v1:" + uuid.uuid4().hex
        try:
            a = service.save_learning({
                "source": "learning_persistent_selftest",
                "event": "selftest lifecycle",
                "lesson": "learning persistence contract probe " + uuid.uuid4().hex,
                "knowledge_nodes": [],
                "relationships": [],
                "confidence": 0.9,
                "outcome": "success",
                "status": "candidate",
                "evidence": [],
                "learning_context": {"origin": "selftest", "scope": scope_a},
            }, actor="selftest", owner_scope=scope_a, idempotency_key=idem)
            b = service.save_learning({
                "source": "learning_persistent_selftest",
                "event": "selftest isolation",
                "lesson": "learning persistence scope B " + uuid.uuid4().hex,
                "knowledge_nodes": [],
                "relationships": [],
                "confidence": 0.8,
                "outcome": "unknown",
                "status": "candidate",
                "evidence": [],
                "learning_context": {"origin": "selftest", "scope": scope_b},
            }, actor="selftest", owner_scope=scope_b)
            created_ids_local.extend([a["record"]["id"], b["record"]["id"]])

            reread = service.get_learning(a["record"]["id"], owner_scope=scope_a)
            foreign = service.get_learning(a["record"]["id"], owner_scope=scope_b)
            rows_b = service.search_learning({"id": a["record"]["id"]}, owner_scope=scope_b, limit=10)
            fresh_service = fresh_service_factory() if fresh_service_factory else service
            fresh = fresh_service.get_learning(a["record"]["id"], owner_scope=scope_a)
            repeat = service.save_learning({
                "source": "learning_persistent_selftest",
                "event": "selftest lifecycle",
                "lesson": a["record"]["lesson"],
                "knowledge_nodes": [],
                "relationships": [],
                "confidence": 0.9,
                "outcome": "success",
                "status": "candidate",
                "evidence": [],
                "learning_context": {"origin": "selftest", "scope": scope_a},
            }, actor="selftest", owner_scope=scope_a, idempotency_key=idem)

            checks["created_v3"] = (
                a["outcome"] == "created"
                and a["record"].get("schema_version") == LEARNING_SCHEMA_VERSION
                and a["record"].get("status") == "candidate"
            )
            checks["reread"] = bool(reread and reread["id"] == a["record"]["id"])
            checks["foreign_read_blocked"] = foreign is None and not rows_b
            checks["fresh_connection_reread"] = bool(fresh and fresh["id"] == a["record"]["id"])
            checks["idempotent"] = (
                repeat["outcome"] == "already_synced"
                and repeat["record"]["id"] == a["record"]["id"]
            )

            evidence = [{
                "type": "selftest",
                "title": "Learning persistent evidence",
                "reference": "selftest://learning-persistent/v1",
                "note": "Evidencia controlada para verificar el ciclo candidate -> verified -> consolidated.",
            }]
            with_evidence = service.add_learning_evidence(
                a["record"]["id"], evidence,
                expected_version=a["record"]["version"],
                actor="selftest", owner_scope=scope_a,
            )
            verified = service.update_learning_status(
                a["record"]["id"], "verified",
                expected_version=with_evidence["version"],
                actor="selftest", owner_scope=scope_a,
            )
            gate_blocked = False
            try:
                service.update_learning_status(
                    a["record"]["id"], "consolidated",
                    expected_version=verified["version"],
                    actor="selftest", owner_scope=scope_a,
                )
            except ValidationError:
                gate_blocked = True

            analyzed = service.update_learning(
                a["record"]["id"],
                {"verification_analysis": {
                    "verdict": "supported",
                    "confidence": 0.90,
                    "evaluated_by": "selftest",
                }},
                expected_version=verified["version"],
                actor="selftest", owner_scope=scope_a,
            )
            consolidated = service.update_learning_status(
                a["record"]["id"], "consolidated",
                expected_version=analyzed["version"],
                actor="selftest", owner_scope=scope_a,
            )
            reused = service.record_reuse(
                a["record"]["id"], actor="selftest", owner_scope=scope_a
            )

            checks["evidence_persisted"] = len(with_evidence.get("evidence") or []) == 1
            checks["verified_transition"] = verified.get("status") == "verified"
            checks["consolidation_gate"] = gate_blocked
            checks["consolidated_with_supported_analysis"] = consolidated.get("status") == "consolidated"
            checks["reuse_persisted"] = reused.get("reuse_count") == 1 and reused.get("last_reused_at") is not None

            for learning_id in created_ids_local:
                try:
                    deleted = service.repo.delete("learning_events", learning_id)
                    if service.repo.exists("learning_events", learning_id):
                        cleanup_failures.append({
                            "learning_id": learning_id,
                            "delete_returned": bool(deleted),
                        })
                except Exception as cleanup_exc:
                    cleanup_failures.append({
                        "learning_id": learning_id,
                        "error_type": type(cleanup_exc).__name__,
                    })
            checks["cleanup"] = not cleanup_failures

            ok = all(checks.values())
            source_digest = hashlib.sha256(
                inspect.getsource(service.__class__).encode("utf-8")
                + inspect.getsource(validate_learning_event).encode("utf-8")
            ).hexdigest()[:16]
            verification_event = {
                "event_type": "verification",
                "test_key": "learning_persistent_contract",
                "test_version": "v1",
                "result": "pass" if ok else "fail",
                "evidence": [{
                    "type": "selftest",
                    "title": "Learning persistent lifecycle and ownership",
                    "reference": "selftest:learning_persistent:v1",
                    "summary": (
                        "Persistencia, owner_scope, reinicio suave, idempotencia, "
                        "evidencia, transiciones, gate de consolidacion, reuse y cleanup."
                        if ok else
                        "El contrato de learning persistente no supero todos los controles."
                    ),
                    "hash": source_digest,
                }],
                "environment": {
                    "runtime": "selftest",
                    "learning_schema": LEARNING_SCHEMA_VERSION,
                },
                "dependency_snapshot": [
                    {
                        "kind": "service",
                        "id": "PersistenceService.learning",
                        "version": source_digest,
                    },
                    {
                        "kind": "storage",
                        "id": "PostgreSQL.learning_events",
                        "version": "runtime",
                    },
                    {
                        "kind": "security",
                        "id": "owner_scope",
                        "version": "runtime",
                    },
                ],
                "runtime_version": "selftest",
                "build_ref": source_digest,
                "actor": "selftest",
                "executor": "selftest",
                "evaluator": "system",
                "error": None if ok else {
                    "checks": checks,
                    "cleanup_failures": cleanup_failures,
                },
            }
            verification = service.record_capability_verification(
                capability["id"],
                verification_event,
                actor="selftest",
                idempotency_key="selftest:learning_persistent:verification:v1:" + source_digest,
            )
            verification_ok = (
                verification.get("effective_state") == "verified"
                if ok else
                verification.get("effective_state") in ("failed", "stale")
            )
            detail = (
                f"resultado={verification.get('outcome')}; "
                f"effective_state={verification.get('effective_state')}; "
                f"checks={checks}"
            )
            if cleanup_failures:
                detail += f"; cleanup_failures={cleanup_failures}"
            return _res(name, bool(ok and verification_ok), detail)
        except Exception as exc:
            for learning_id in created_ids_local:
                try:
                    service.repo.delete("learning_events", learning_id)
                except Exception:
                    pass
            return _res(name, False, f"excepcion {type(exc).__name__}: {str(exc)[:240]}")

    def t_capability_engine_contract():
        name = "TEST_CAPABILITY_ENGINE_CONTRACT"
        valid = validate_capability({
            "name": "selftest_capability_contract",
            "description": "Prueba estable del contrato Capability Engine.",
            "category": "general",
            "kind": "composite",
            "implementation_state": "implemented",
            "verification_state": "unverified",
            "availability_state": "available",
            "maturity": "experimental",
            "cost_compatibility": "unknown",
            "dependencies": [{"kind": "runtime", "id": "selftest", "required": True}],
            "limitations": [],
            "verification_spec": {
                "method": "selftest",
                "test_key": "capability_contract",
                "freshness_policy": {
                    "mode": "on_change",
                    "max_age_seconds": None,
                    "invalidate_on": ["build_change"],
                },
            },
            "provenance": {"source": "selftest", "created_by": "selftest"},
        })
        impossible = False
        try:
            validate_capability_state({
                "implementation_state": "not_implemented",
                "verification_state": "verified",
                "availability_state": "unavailable",
                "maturity": "experimental",
                "cost_compatibility": "unknown",
            })
        except CapabilityContractError:
            impossible = True
        effective = derive_effective_state(valid)
        try:
            validate_capability_transition(
                validate_capability_state({
                    "implementation_state": "implemented",
                    "verification_state": "unverified",
                    "availability_state": "available",
                    "maturity": "experimental",
                    "cost_compatibility": "unknown",
                }),
                validate_capability_state({
                    "implementation_state": "implemented",
                    "verification_state": "verified",
                    "availability_state": "available",
                    "maturity": "experimental",
                    "cost_compatibility": "unknown",
                }),
            )
            transition_ok = True
        except CapabilityContractError:
            transition_ok = False
        ok = (
            valid["verification_state"] == "unverified"
            and effective == "implemented_unverified_available"
            and impossible
            and transition_ok
        )
        return _res(name, ok, "estados validos, estado imposible rechazado y transicion valida aceptada")

    def t_persistent_memory_capability():
        name = "TEST_PERSISTENT_MEMORY_CAPABILITY"
        rows = service.list_capabilities(filters={"name": "persistent_memory"}, limit=1)
        if not rows:
            return _res(name, False, "capacidad persistent_memory no fue registrada por el bootstrap")
        capability = rows[0]
        scope_a = "selftest:persistent-memory:A"
        scope_b = "selftest:persistent-memory:B"
        created_ids_local = []
        checks = {}
        key = "selftest:persistent_memory:v1:" + uuid.uuid4().hex
        detail = ""
        try:
            a = service.save_memory({
                "content": "persistent memory probe A " + uuid.uuid4().hex,
                "memory_type": "semantic",
                "importance": 7,
                "confidence": 0.9,
                "source": "persistent_memory_selftest",
                "source_reference": "selftest://persistent-memory/v1",
                "privacy_level": "PRIVATE",
                "tags": ["persistent_memory_selftest"],
            }, actor="selftest", owner_scope=scope_a, idempotency_key=key)
            created_ids_local.append(a["record"]["id"])
            same = service.get_memory(a["record"]["id"], owner_scope=scope_a)
            foreign = service.get_memory(a["record"]["id"], owner_scope=scope_b)
            checks["created"] = a["outcome"] == "created"
            checks["reread"] = bool(
                same
                and same.get("content") == a["record"].get("content")
                and same.get("version") == 1
            )
            checks["foreign_read_blocked"] = foreign is None
            other = fresh_service_factory() if fresh_service_factory else service
            after_restart = other.get_memory(a["record"]["id"], owner_scope=scope_a)
            checks["fresh_connection_reread"] = bool(
                after_restart and after_restart.get("id") == a["record"]["id"]
            )
            repeat = service.save_memory({
                "content": a["record"]["content"],
                "memory_type": "semantic",
                "importance": 7,
                "confidence": 0.9,
                "source": "persistent_memory_selftest",
                "source_reference": "selftest://persistent-memory/v1",
                "privacy_level": "PRIVATE",
                "tags": ["persistent_memory_selftest"],
            }, actor="selftest", owner_scope=scope_a, idempotency_key=key)
            checks["idempotent"] = (
                repeat["outcome"] == "already_synced"
                and repeat["record"]["id"] == a["record"]["id"]
            )
            b = service.save_memory({
                "content": "persistent memory probe B " + uuid.uuid4().hex,
                "memory_type": "episodic",
                "importance": 5,
                "confidence": 0.7,
                "source": "persistent_memory_selftest",
                "source_reference": "selftest://persistent-memory/v1",
                "privacy_level": "SHAREABLE",
                "tags": ["persistent_memory_selftest"],
            }, actor="selftest", owner_scope=scope_b)
            created_ids_local.append(b["record"]["id"])
            ids_a = {
                x["id"]
                for x in service.search_memory(
                    {"text_contains": "persistent memory probe"},
                    owner_scope=scope_a,
                    limit=20,
                )
            }
            ids_b = {
                x["id"]
                for x in service.search_memory(
                    {"text_contains": "persistent memory probe"},
                    owner_scope=scope_b,
                    limit=20,
                )
            }
            checks["scope_isolated"] = (
                a["record"]["id"] in ids_a
                and b["record"]["id"] not in ids_a
                and b["record"]["id"] in ids_b
                and a["record"]["id"] not in ids_b
            )
            updated = service.update_memory(
                a["record"]["id"],
                {"importance": 8},
                expected_version=1,
                actor="selftest",
            )
            checks["versioned_update"] = (
                updated.get("version") == 2 and updated.get("importance") == 8
            )
            try:
                service.update_memory(
                    a["record"]["id"],
                    {"importance": 9},
                    expected_version=1,
                    actor="selftest",
                )
                checks["stale_version_rejected"] = False
            except ConflictError:
                checks["stale_version_rejected"] = True
            archived = service.archive_memory(
                a["record"]["id"],
                expected_version=2,
                actor="selftest",
            )
            hidden = service.search_memory(
                {"text_contains": "persistent memory probe A"},
                owner_scope=scope_a,
                limit=20,
            )
            checks["archive"] = (
                archived.get("status") == "archived"
                and all(x.get("id") != a["record"]["id"] for x in hidden)
            )
        except Exception as exc:
            checks["exception_free"] = False
            detail = "excepcion " + type(exc).__name__ + ": " + str(exc)[:240]
        else:
            checks["exception_free"] = True
        finally:
            for mid in created_ids_local:
                try:
                    service.repo.delete("memories", mid)
                except Exception:
                    pass
        ok = all(checks.values())
        source_digest = hashlib.sha256(
            inspect.getsource(service.__class__).encode("utf-8")
        ).hexdigest()[:16]
        evidence = [{
            "type": "selftest",
            "title": "Persistent memory lifecycle and ownership",
            "reference": "selftest:persistent_memory:v1",
            "summary": (
                "Creacion, relectura, reinicio suave, idempotencia, aislamiento, "
                "versionado y archivado."
                if ok else
                "El contrato de memoria persistente no supero todos los controles."
            ),
            "hash": source_digest,
        }]
        event = {
            "event_type": "verification",
            "test_key": "persistent_memory_contract",
            "test_version": "v1",
            "result": "pass" if ok else "fail",
            "evidence": evidence,
            "environment": {"runtime": "selftest"},
            "dependency_snapshot": [
                {
                    "kind": "service",
                    "id": "PersistenceService",
                    "version": source_digest,
                },
                {
                    "kind": "storage",
                    "id": "PostgreSQL.memories",
                    "version": "runtime",
                },
            ],
            "runtime_version": "selftest",
            "build_ref": source_digest,
            "actor": "selftest",
            "executor": "selftest",
            "evaluator": "system",
            "error": None if ok else {"checks": checks, "detail": detail},
        }
        try:
            result = service.record_capability_verification(
                capability["id"],
                event,
                actor="selftest",
                idempotency_key=(
                    "selftest:persistent_memory:verification:v1:" + source_digest
                ),
            )
        except Exception as exc:
            return _res(
                name,
                False,
                "verification persistence fallo: "
                + type(exc).__name__ + ": " + str(exc)[:240],
            )
        return _res(
            name,
            bool(ok and result.get("effective_state") == "verified"),
            "resultado=" + str(result.get("outcome"))
            + "; effective_state=" + str(result.get("effective_state"))
            + "; checks=" + str(checks),
        )


    def t_memory_recall_capability():
        name = "TEST_MEMORY_RECALL_CAPABILITY"
        rows = service.list_capabilities(filters={"name": "memory_recall"}, limit=1)
        if not rows:
            return _res(name, False, "capacidad memory_recall no fue registrada por el bootstrap")
        capability = rows[0]
        scope_a = "selftest:memory-recall:A"
        scope_b = "selftest:memory-recall:B"
        created_ids_local = []
        checks = {}
        detail = ""
        model = "gemini-embedding-2"
        vector_a = [1.0] + [0.0] * 767
        vector_b = [0.0, 1.0] + [0.0] * 766
        try:
            a = service.save_memory({
                "content": "recuerdo alpino controlado A " + uuid.uuid4().hex,
                "memory_type": "semantic",
                "importance": 7,
                "confidence": 0.9,
                "source": "memory_recall_selftest",
                "source_reference": "selftest://memory-recall/v1/A",
                "privacy_level": "PRIVATE",
            }, actor="selftest", owner_scope=scope_a)
            b = service.save_memory({
                "content": "recuerdo marino controlado B " + uuid.uuid4().hex,
                "memory_type": "semantic",
                "importance": 7,
                "confidence": 0.9,
                "source": "memory_recall_selftest",
                "source_reference": "selftest://memory-recall/v1/B",
                "privacy_level": "PRIVATE",
            }, actor="selftest", owner_scope=scope_b)
            created_ids_local.extend([a["record"]["id"], b["record"]["id"]])

            service.upsert_memory_embedding(
                a["record"]["id"],
                model,
                vector_a,
                "selftest:memory-recall:A",
                owner_scope=scope_a,
            )
            service.upsert_memory_embedding(
                b["record"]["id"],
                model,
                vector_b,
                "selftest:memory-recall:B",
                owner_scope=scope_b,
            )

            recalled_a = recall_memories(
                service,
                "consulta semantica controlada sin coincidencia lexical",
                limit=5,
                include_semantic=True,
                owner_scope=scope_a,
                extract_keywords=lambda _q: [],
                generate_embedding=lambda _q: vector_a,
                embedding_model=model,
            )
            recalled_b = recall_memories(
                service,
                "consulta semantica controlada sin coincidencia lexical",
                limit=5,
                include_semantic=True,
                owner_scope=scope_b,
                extract_keywords=lambda _q: [],
                generate_embedding=lambda _q: vector_b,
                embedding_model=model,
            )

            ids_a = {row.get("id") for row in recalled_a}
            ids_b = {row.get("id") for row in recalled_b}
            checks["semantic_scope_a"] = (
                a["record"]["id"] in ids_a
                and b["record"]["id"] not in ids_a
            )
            checks["semantic_scope_b"] = (
                b["record"]["id"] in ids_b
                and a["record"]["id"] not in ids_b
            )

            lexical = recall_memories(
                service,
                "marino",
                limit=5,
                include_semantic=False,
                owner_scope=scope_b,
                extract_keywords=lambda _q: ["marino"],
                generate_embedding=None,
                embedding_model=model,
            )
            checks["lexical_fallback"] = b["record"]["id"] in {
                row.get("id") for row in lexical
            }

            other = fresh_service_factory() if fresh_service_factory else service
            fresh = recall_memories(
                other,
                "consulta semantica controlada sin coincidencia lexical",
                limit=5,
                include_semantic=True,
                owner_scope=scope_a,
                extract_keywords=lambda _q: [],
                generate_embedding=lambda _q: vector_a,
                embedding_model=model,
            )
            checks["fresh_connection_semantic_recall"] = a["record"]["id"] in {
                row.get("id") for row in fresh
            }

            archived = service.archive_memory(
                b["record"]["id"],
                expected_version=b["record"]["version"],
                actor="selftest",
            )
            after_archive = recall_memories(
                service,
                "marino",
                limit=5,
                include_semantic=False,
                owner_scope=scope_b,
                extract_keywords=lambda _q: ["marino"],
                generate_embedding=None,
                embedding_model=model,
            )
            checks["archived_hidden"] = (
                archived.get("status") == "archived"
                and b["record"]["id"] not in {row.get("id") for row in after_archive}
            )
        except Exception as exc:
            checks["exception_free"] = False
            detail = "excepcion " + type(exc).__name__ + ": " + str(exc)[:240]
        else:
            checks["exception_free"] = True
        finally:
            for mid in created_ids_local:
                try:
                    service.repo.delete("memories", mid)
                except Exception:
                    pass

        ok = all(checks.values())
        recall_source = inspect.getsource(recall_memories).encode("utf-8")
        vector_search = inspect.getsource(service.repo.search_memory_embeddings).encode("utf-8")
        source_digest = hashlib.sha256(
            recall_source + b"\\n" + vector_search
        ).hexdigest()[:16]
        evidence = [{
            "type": "selftest",
            "title": "Hybrid memory recall and ownership",
            "reference": "selftest:memory_recall:v1",
            "summary": (
                "Recuperacion semantica vectorial, aislamiento por owner_scope, "
                "degradacion lexical, reinicio suave y exclusion de memorias archivadas."
                if ok else
                "El contrato de recuperacion de memoria no supero todos los controles."
            ),
            "hash": source_digest,
        }]
        event = {
            "event_type": "verification",
            "test_key": "memory_recall_contract",
            "test_version": "v1",
            "result": "pass" if ok else "fail",
            "evidence": evidence,
            "environment": {
                "runtime": "selftest",
                "semantic_provider_call": False,
            },
            "dependency_snapshot": [
                {
                    "kind": "module",
                    "id": "persistence.memory_recall",
                    "version": source_digest,
                },
                {
                    "kind": "storage",
                    "id": "PostgreSQL.memory_embeddings",
                    "version": "runtime",
                },
                {
                    "kind": "provider",
                    "id": model,
                    "version": "external",
                },
            ],
            "runtime_version": "selftest",
            "build_ref": source_digest,
            "actor": "selftest",
            "executor": "selftest",
            "evaluator": "system",
            "error": None if ok else {"checks": checks, "detail": detail},
        }
        try:
            verification = service.record_capability_verification(
                capability["id"],
                event,
                actor="selftest",
                idempotency_key="selftest:memory_recall:verification:v1:" + source_digest,
            )
        except Exception as exc:
            return _res(
                name,
                False,
                "verification persistence fallo: "
                + type(exc).__name__ + ": " + str(exc)[:240],
            )
        return _res(
            name,
            bool(ok and verification.get("effective_state") == "verified"),
            "resultado=" + str(verification.get("outcome"))
            + "; effective_state=" + str(verification.get("effective_state"))
            + "; checks=" + str(checks),
        )

    def t_session_auth_capability():
        name = "TEST_SESSION_AUTH_CAPABILITY"
        rows = service.list_capabilities(filters={"name": "session_auth"}, limit=1)
        if not rows:
            return _res(name, False, "capacidad session_auth no fue registrada por el bootstrap")
        capability = rows[0]
        configured = akira_auth._secret() is not None
        probe_sub = "selftest-session-auth-v1"
        probe_email = "selftest-session-auth@example.invalid"
        token, exp, issue_reason = akira_auth.issue_session(probe_sub, probe_email)
        checks = {
            "secret_configured": configured,
            "issued": bool(token),
            "issue_reason": issue_reason,
        }
        if token:
            session = akira_auth.verify_session(token, default_owner_emails=(), now=time.time())
            tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
            tampered_session = akira_auth.verify_session(tampered, default_owner_emails=(), now=time.time())
            expired_session = akira_auth.verify_session(token, default_owner_emails=(), now=exp)
            header_session = akira_auth.session_from_header("Bearer " + token, default_owner_emails=(), now=time.time())
            checks.update({
                "session_valid": session is not None,
                "identity_preserved": bool(session and session.get("sub") == probe_sub and session.get("email") == probe_email),
                "owner_scope_server_derived": bool(session and session.get("owner_scope") == "g:" + probe_sub),
                "tampered_rejected": tampered_session is None,
                "expired_rejected": expired_session is None,
                "bearer_parsed": header_session is not None,
            })
        else:
            checks.update({
                "session_valid": False,
                "identity_preserved": False,
                "owner_scope_server_derived": False,
                "tampered_rejected": False,
                "expired_rejected": False,
                "bearer_parsed": False,
            })
        ok = all(bool(checks[k]) for k in (
            "secret_configured", "issued", "session_valid", "identity_preserved",
            "owner_scope_server_derived", "tampered_rejected", "expired_rejected", "bearer_parsed",
        ))
        source_digest = hashlib.sha256(inspect.getsource(akira_auth).encode("utf-8")).hexdigest()[:16]
        idem = "selftest:session_auth:v1:" + source_digest + (":configured" if configured else ":missing")
        evidence = [{
            "type": "selftest",
            "title": "Session auth runtime contract",
            "reference": "selftest:session_auth:v1",
            "summary": "Sesion HMAC emitida, validada, delimitada por Bearer y rechaza manipulacion/caducidad." if ok else "El contrato de sesion no supero la autoprueba.",
            "hash": source_digest,
        }]
        event = {
            "event_type": "verification",
            "test_key": "session_auth_contract",
            "test_version": "v1",
            "result": "pass" if ok else "fail",
            "evidence": evidence,
            "environment": {"runtime": "selftest", "secret_configured": configured},
            "dependency_snapshot": [{"kind": "module", "id": "akira_auth.py", "version": source_digest}],
            "runtime_version": "selftest",
            "build_ref": source_digest,
            "actor": "selftest",
            "executor": "selftest",
            "evaluator": "system",
            "error": None if ok else {"checks": checks, "issue_reason": issue_reason},
        }
        try:
            result = service.record_capability_verification(
                capability["id"],
                event,
                actor="selftest",
                idempotency_key=idem,
            )
        except Exception as exc:
            return _res(name, False, f"verification persistence fallo: {type(exc).__name__}: {str(exc)[:240]}")
        effective = result.get("effective_state")
        outcome = result.get("outcome")
        verified = effective == "verified" if ok else effective in ("failed", "stale")
        return _res(name, bool(ok and verified), f"resultado={outcome}; effective_state={effective}; configured={configured}")

    def t_capability_persistence():
        name = "TEST_CAPABILITY_PERSISTENCE"

        # El registry canonico ya contiene esta capability. El selftest debe
        # comprobar su roundtrip sin intentar redefinir ni duplicar la entrada.
        rows = service.list_capabilities(filters={"name": "selftest_capability"}, limit=1)
        if not rows:
            return _res(name, False, "capability canonica selftest_capability no existe")
        cap = rows[0]
        evidence = [{
            "type": "selftest",
            "title": "Capability persistence roundtrip",
            "reference": "selftest:capability:v1",
            "summary": "Capability y verification persistidas y releidas.",
            "hash": "",
        }]
        event = {
            "event_type": "verification",
            "test_key": "capability_persistence",
            "test_version": "v1",
            "result": "pass",
            "evidence": evidence,
            "environment": {"runtime": "selftest"},
            "dependency_snapshot": [],
            "runtime_version": "selftest",
            "build_ref": "selftest",
            "actor": "selftest",
            "executor": "selftest",
            "evaluator": "system",
        }
        try:
            vr = service.record_capability_verification(
                cap["id"], event, actor="selftest",
                idempotency_key="selftest:capability:verification:v1",
            )
        except Exception as e:
            return _res(
                name,
                False,
                f"record_capability_verification fallo: {type(e).__name__}: {str(e)[:300]}",
            )
        cap2 = service.get_capability(cap["id"])
        rows = service.get_capability_verifications(cap["id"], limit=10)
        try:
            repeat = service.record_capability_verification(
                cap["id"], event, actor="selftest",
                idempotency_key="selftest:capability:verification:v1",
            )
        except Exception as e:
            return _res(name, False, f"reintento idempotente fallo: {type(e).__name__}: {str(e)[:300]}")
        ok = (
            cap2 is not None
            and cap2["verification_state"] == "verified"
            and bool(rows)
            and rows[0]["state_after"]["verification_state"] == "verified"
            and repeat["outcome"] == "already_synced"
            and vr["effective_state"] == "verified"
        )
        detail = (
            f"verificationes persistidas={len(rows)}; "
            f"repeticion={repeat['outcome']}; estado={cap2 and cap2.get('verification_state')}"
        )
        return _res(name, ok, detail)

    def t_capability_verification_append_only():
        name = "TEST_CAPABILITY_VERIFICATION_APPEND_ONLY"
        rows = service.list_capabilities(filters={"name": "selftest_capability"}, limit=1)
        if not rows:
            return _res(name, False, "fixture selftest_capability no existe")
        cap = rows[0]
        verifications = service.get_capability_verifications(cap["id"], limit=10)
        if not verifications:
            return _res(name, False, "fixture no tiene verification")
        event = verifications[0]
        original = service.repo.get("capability_verifications", event["id"])
        update_blocked = False
        try:
            service.repo.update(
                "capability_verifications",
                event["id"],
                {"result": "fail"},
                original["version"],
            )
        except PersistenceError:
            update_blocked = True
        delete_result = service.repo.delete("capability_verifications", event["id"])
        current = service.repo.get("capability_verifications", event["id"])
        ok = (
            update_blocked
            and delete_result is False
            and current is not None
            and current["result"] == original["result"]
            and current["version"] == original["version"]
        )
        return _res(name, ok, "UPDATE y DELETE bloqueados; historial permanece intacto")

    for name, fn in (
        ("TEST_MEMORY_PERSISTENCE (reinicio suave)", t_memory_persistence),
        ("TEST_IDEMPOTENT_SYNC", t_idempotent),
        ("TEST_PRIVATE_MEMORY", t_private),
        ("TEST_VERSIONING_CONFLICT", t_versioning),
        ("TEST_ARCHIVE_SOFT_DELETE", t_archive),
        ("TEST_VALIDATION_REJECTS", t_validation),
        ("TEST_TOOL_PERMISSION_CONTRACT", t_tool_permission_contract),
        ("TEST_IDENTITY_ROOT_CONTRACT", t_identity_root_contract),
        ("TEST_SELF_MODEL_IDENTITY_PROTECTED", t_self_model_identity_protected),
        ("TEST_SELF_MODEL_DERIVED_FIELDS_PROTECTED", t_self_model_derived_fields_protected),
        ("TEST_MODEL_ROUTE_REGISTRY_CONTRACT", t_model_route_registry_contract),
        ("TEST_TRANSACTION_ROLLBACK", t_rollback),
        ("TEST_AGENT_TASK_PERSISTENCE", t_agent_task_persistence),
        ("TEST_AGENT_TASK_VALIDATION", t_agent_task_validation),
        ("TEST_AGENT_TASK_MISSION_FILTER", t_agent_task_mission_filter),
        ("TEST_AGENT_TASK_OWNER_SCOPE_FILTER", t_agent_task_owner_scope_filter),
        ("TEST_SPECIALIZED_AGENTS_PERSISTENCE", t_specialized_agents_persistence),
        ("TEST_REPAIR_ENGINE_V1_CAPABILITY", t_repair_engine_v1_capability),
        ("TEST_SELF_KNOWLEDGE_SNAPSHOT", t_self_knowledge_snapshot),
        ("TEST_SELF_KNOWLEDGE_RUNTIME_CAPABILITY", t_self_knowledge_runtime_capability),
        ("TEST_AGENT_TOOL_REFERENCE_INTEGRITY", t_agent_tool_reference_integrity),
        ("TEST_AGENT_STATE_TRANSITION", t_agent_state_transition),
        ("TEST_LEARNING_STATE_CONTRACT", t_learning_state_contract),
        ("TEST_CAPABILITY_ENGINE_CONTRACT", t_capability_engine_contract),
        ("TEST_SESSION_AUTH_CAPABILITY", t_session_auth_capability),
        ("TEST_PERSISTENT_MEMORY_CAPABILITY", t_persistent_memory_capability),
        ("TEST_MEMORY_RECALL_CAPABILITY", t_memory_recall_capability),
        ("TEST_LEARNING_PERSISTENT_CAPABILITY", t_learning_persistent_capability),
        ("TEST_GRAPH_PERSISTENT_CAPABILITY", t_graph_persistent_capability),
        ("TEST_CAPABILITY_PERSISTENCE", t_capability_persistence),
        ("TEST_CAPABILITY_VERIFICATION_APPEND_ONLY", t_capability_verification_append_only),
    ):
        results.append(_guard(name, fn, service, created_ids))

    results.append({"test": "TEST_RELATION_INTEGRITY", "status": "N/A",
                    "detail": "Experiencia/Learning/Knowledge enlazados: pendiente de pruebas cruzadas."})

    # Limpieza (Fase 1.6, 2026-10-01): BORRAR de verdad las memorias de prueba.
    # La limpieza también se valida: un selftest NO puede reportar PASS si dejó
    # una memoria de prueba detrás.
    cleanup_failures = []
    cleanup_deleted = 0
    for mid in created_ids:
        try:
            deleted = service.repo.delete("memories", mid)
            still_exists = service.exists_memory(mid)
            if still_exists:
                cleanup_failures.append({
                    "memory_id": mid,
                    "reason": "memory_still_exists_after_delete",
                    "delete_returned": bool(deleted),
                })
            else:
                cleanup_deleted += 1
        except Exception as e:
            cleanup_failures.append({
                "memory_id": mid,
                "reason": "delete_error",
                "error_type": type(e).__name__,
            })

    results.append(
        _res(
            "TEST_MEMORY_CLEANUP",
            not cleanup_failures,
            f"creadas={len(created_ids)} eliminadas={cleanup_deleted} "
            f"fallos={len(cleanup_failures)}",
        )
    )
    if cleanup_failures:
        print(
            f"[persistence] selftest cleanup FAIL: "
            f"{len(cleanup_failures)} memory(s) remain or could not be deleted",
            flush=True,
        )
    for tid in created_task_ids:
        try:
            service.repo.delete("agent_tasks", tid)
        except Exception:
            pass

    mission_cleanup_failures = []
    mission_cleanup_deleted = 0
    for mid in created_mission_ids:
        try:
            with service.repo.transaction() as tx:
                deleted = tx.delete("missions", mid)
                tx.append_audit({
                    "actor": "selftest",
                    "action": "mission.fixture.delete",
                    "resource": "missions",
                    "resource_id": mid,
                    "status": "success" if deleted else "failure",
                    "detail": {"fixture": True},
                })
            if service.get_mission(mid) is not None:
                mission_cleanup_failures.append({
                    "mission_id": mid,
                    "reason": "mission_still_exists_after_delete",
                    "delete_returned": bool(deleted),
                })
            else:
                mission_cleanup_deleted += 1
        except Exception as e:
            mission_cleanup_failures.append({
                "mission_id": mid,
                "reason": "delete_error",
                "error_type": type(e).__name__,
            })

    results.append(
        _res(
            "TEST_MISSION_FIXTURE_CLEANUP",
            not mission_cleanup_failures,
            f"creadas={len(created_mission_ids)} eliminadas={mission_cleanup_deleted} "
            f"fallos={len(mission_cleanup_failures)}",
        )
    )

    _disable_test_agent(service)
    return results


def run_restart_probe(service, boot_id):
    """Sonda de reinicio real. Primera vez: la escribe. Tras reiniciar el servicio: la relee y compara."""
    found = service.search_memory({"idempotency_key": PROBE_KEY, "status__in": ["active", "archived", "deleted"]},
                                  limit=1)
    if not found:
        r = service.save_memory(
            {"content": PROBE_CONTENT, "memory_type": "system", "importance": 1, "confidence": 1.0,
             "source": "selftest", "source_reference": boot_id, "privacy_level": "PRIVATE",
             "tags": ["selftest", "restart-probe"]},
            actor="selftest", idempotency_key=PROBE_KEY)
        service.record_audit("selftest", "selftest.restart_probe.written", "memories", r["record"]["id"],
                             "success", {"boot_id": boot_id})
        return {"test": "TEST_RESTART_PROBE", "status": "PENDING",
                "detail": "Sonda escrita. Reinicia el servicio en Render y revisa /api/v8/persistence/status."}
    rec = found[0]
    same_content = rec["content"] == PROBE_CONTENT
    other_process = rec.get("source_reference") != boot_id
    if same_content and not other_process:
        return {"test": "TEST_RESTART_PROBE", "status": "PENDING",
                "detail": "La sonda existe pero la escribio este mismo proceso. Falta reiniciar."}
    ok = same_content and other_process
    service.record_audit("selftest", "selftest.restart_probe.verified", "memories", rec["id"],
                         "success" if ok else "failure",
                         {"written_by_boot": rec.get("source_reference"), "verified_by_boot": boot_id,
                          "same_content": same_content})
    return _res("TEST_RESTART_PROBE", ok,
                "sonda escrita por otro proceso y releida intacta" if ok else "el contenido de la sonda cambio")


def summarize(results):
    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return counts
