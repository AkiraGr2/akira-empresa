"""Autopruebas de Fase 4/5/6/7/8/9. Cada resultado: PASS, FAIL, PENDING o N/A. Nada se da por bueno sin comprobarlo.

- run_logic_tests: pruebas de comportamiento (validacion, idempotencia, versiones, privacidad, rollback, agentes+tareas).
- run_restart_probe: prueba REAL de reinicio. Un proceso escribe una sonda; otro proceso distinto la relee.

Fase 1.6 (2026-10-01): la limpieza de memorias de prueba ahora hace HARD DELETE (repo.delete),
no archive_memory. Antes se acumulaban ~6 filas selftest por cada corrida del selftest,
contaminando la tabla memories. Ahora no queda rastro.
"""
from __future__ import annotations

import uuid

from .core import (ConflictError, PersistenceError, ValidationError, new_id,
                   validate_memory, validate_learning_event)

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


def _guard(name, fn):
    try:
        return fn()
    except Exception as e:  # un fallo de la prueba es un FAIL, no un crash
        return _res(name, False, f"excepcion {type(e).__name__}: {str(e)[:120]}")


def _ensure_tools(service):
    """Registra las tools que los tests de agentes necesitan. Idempotente por nombre."""
    tools = [
        {"name": "memory_save", "description": "Guarda memoria (test).", "category": "memory",
         "permissions": ["auth"], "inputs_schema": {"content": "str", "memory_type": "str"},
         "outputs_schema": {"id": "str"}, "limits_json": {}, "risks": []},
        {"name": "memory_search", "description": "Busca memorias (test).", "category": "memory",
         "permissions": ["auth"], "inputs_schema": {"query": "str"},
         "outputs_schema": {"results": "list"}, "limits_json": {}, "risks": []},
    ]
    for t in tools:
        try:
            service.register_tool(t, actor="selftest")
        except Exception:
            pass


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

    def t_agent_task_mission_filter():
        name = "TEST_AGENT_TASK_MISSION_FILTER"
        _ensure_tools(service)
        _ensure_test_agent(service)
        mission_id = f"test_mission_{uuid.uuid4().hex[:8]}"
        ids = []
        for i in range(3):
            r = service.create_task(_TEST_AGENT_NAME, "memory_save",
                                    inputs={"content": f"selftest m{i}", "memory_type": "system"},
                                    mission_id=mission_id, actor="selftest")
            tid = r["record"]["id"]
            ids.append(tid)
            created_task_ids.append(tid)
            service.complete_task(tid, outputs={}, duration_ms=1, actor="selftest")
        # Filtrar por mission_id
        rows = service.list_tasks(mission_id=mission_id, limit=10)
        filtered = [r for r in rows if r.get("mission_id") == mission_id]
        ok = len(filtered) == 3 and all(r["id"] in ids for r in filtered)
        return _res(name, ok, f"3 tasks con mission_id, filtradas: {len(filtered)}")

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

    for name, fn in (
        ("TEST_MEMORY_PERSISTENCE (reinicio suave)", t_memory_persistence),
        ("TEST_IDEMPOTENT_SYNC", t_idempotent),
        ("TEST_PRIVATE_MEMORY", t_private),
        ("TEST_VERSIONING_CONFLICT", t_versioning),
        ("TEST_ARCHIVE_SOFT_DELETE", t_archive),
        ("TEST_VALIDATION_REJECTS", t_validation),
        ("TEST_TRANSACTION_ROLLBACK", t_rollback),
        ("TEST_AGENT_TASK_PERSISTENCE", t_agent_task_persistence),
        ("TEST_AGENT_TASK_VALIDATION", t_agent_task_validation),
        ("TEST_AGENT_TASK_MISSION_FILTER", t_agent_task_mission_filter),
        ("TEST_AGENT_STATE_TRANSITION", t_agent_state_transition),
        ("TEST_LEARNING_STATE_CONTRACT", t_learning_state_contract),
    ):
        results.append(_guard(name, fn))

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
