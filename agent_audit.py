"""Auditoría E2E de agentes de AKIRA (F9).

Cada agente activo debe demostrar una capacidad real y trazable. El auditor
ejecuta las mismas rutas de herramientas que usa el runtime, persiste tareas
de agente y verifica semántica; no considera suficiente el registro en DB.
No borra tareas ni invocaciones de auditoría: solo limpia fixtures.
"""
from __future__ import annotations

import json
import time
from typing import Any, Callable

from agent_contracts import (
    AGENT_CONTRACTS,
    PRODUCTION_AGENT_ORDER,
    validate_agent_definition,
    validate_agent_result,
)
from persistence.autonomy import AutonomyService
from persistence.core import ValidationError, validate_tool_inputs


def _matches_type(value: Any, expected: str) -> bool:
    expected = str(expected or "").strip().lower()
    if expected == "str":
        return isinstance(value, str)
    if expected == "dict":
        return isinstance(value, dict)
    if expected == "list":
        return isinstance(value, list)
    if expected == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "bool":
        return isinstance(value, bool)
    return True


def _schema_ok(outputs: Any, schema: dict[str, Any]) -> tuple[bool, list[str]]:
    if not isinstance(outputs, dict):
        return False, ["outputs_not_object"]
    failures: list[str] = []
    for key, expected in (schema or {}).items():
        if key not in outputs:
            failures.append(f"missing_output:{key}")
        elif not _matches_type(outputs[key], expected):
            failures.append(f"wrong_type:{key}:expected={expected}")
    return not failures, failures


def _audit_task(
    service,
    invoke_registered: Callable[..., dict[str, Any]],
    actor: str,
    owner_scope: str,
    run_id: str,
    agent_name: str,
    tool_name: str,
    inputs: dict[str, Any],
    fixture: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    started = time.time()
    key = f"f9-audit:{run_id}:{agent_name}:{tool_name}:{index}"
    report: dict[str, Any] = {
        "agent": agent_name,
        "tool": tool_name,
        "verdict": "FAILED",
        "checks": {},
        "evidence": {},
    }
    agent = service.get_agent_by_name(agent_name)
    tool = service.get_tool_by_name(tool_name)

    definition_ok, definition_failures = validate_agent_definition(agent or {})
    report["checks"]["agent_definition"] = definition_ok
    report["evidence"]["agent_definition_failures"] = definition_failures
    if tool is None:
        report["error"] = "tool_not_registered"
        report["elapsed_ms"] = int((time.time() - started) * 1000)
        return report

    report["checks"]["tool_available"] = tool.get("status") == "available"
    try:
        validate_tool_inputs(tool, inputs)
        report["checks"]["inputs_valid"] = True
    except ValidationError as exc:
        report["checks"]["inputs_valid"] = False
        report["error"] = f"tool_inputs_invalid:{str(exc)[:220]}"
        report["elapsed_ms"] = int((time.time() - started) * 1000)
        return report

    try:
        created = service.create_task(
            agent_name,
            tool_name,
            inputs=inputs,
            actor=actor,
            owner_scope=owner_scope,
            idempotency_key=key,
        )
        task = created["record"]
        report["evidence"]["task_id"] = task["id"]
        if created.get("outcome") != "created":
            report["error"] = "unexpected_task_replay_on_first_run"
            report["elapsed_ms"] = int((time.time() - started) * 1000)
            return report
        service.start_task(task["id"], actor=actor, owner_scope=owner_scope)
        report["checks"]["task_persisted_and_started"] = True
    except Exception as exc:
        report["checks"]["task_persisted_and_started"] = False
        report["error"] = {"type": type(exc).__name__, "message": str(exc)[:240]}
        report["elapsed_ms"] = int((time.time() - started) * 1000)
        return report

    invocation_key = f"{key}:invoke"
    invocation = invoke_registered(
        service,
        tool_name,
        inputs,
        actor=f"agent:{agent_name}",
        owner_scope=owner_scope,
        idempotency_key=invocation_key,
    )
    report["checks"]["tool_executed"] = bool(invocation.get("ok"))
    report["checks"]["tool_invocation_persisted"] = bool(
        invocation.get("persisted") is True and invocation.get("invocation_id")
    )
    report["evidence"]["invocation_id"] = invocation.get("invocation_id")
    report["evidence"]["invocation_idempotency_key"] = invocation_key
    report["evidence"]["tool_error"] = invocation.get("error")

    outputs = invocation.get("outputs") or {}
    semantic_ok, semantic_detail = validate_agent_result(
        agent_name,
        tool_name,
        outputs,
        invocation.get("error"),
    )
    report["checks"]["semantic_result"] = semantic_ok
    report["evidence"]["semantic"] = semantic_detail

    schema_ok, schema_failures = _schema_ok(outputs, tool.get("outputs_schema") or {})
    report["checks"]["output_schema"] = schema_ok
    report["evidence"]["output_schema_failures"] = schema_failures

    if invocation.get("ok") and semantic_ok and schema_ok:
        try:
            service.complete_task(
                task["id"],
                outputs=outputs,
                duration_ms=int(invocation.get("duration_ms") or 0),
                actor=actor,
                owner_scope=owner_scope,
            )
            stored = service.get_task(task["id"], owner_scope=owner_scope)
            report["checks"]["task_completed_and_persisted"] = bool(
                stored and stored.get("status") == "completed"
            )
        except Exception as exc:
            report["checks"]["task_completed_and_persisted"] = False
            report["error"] = {
                "type": type(exc).__name__,
                "message": f"task completion persistence failed: {str(exc)[:220]}",
            }
    else:
        try:
            service.fail_task(
                task["id"],
                invocation.get("error") or {"type": "AgentSemanticContractError"},
                duration_ms=int(invocation.get("duration_ms") or 0),
                actor=actor,
                owner_scope=owner_scope,
            )
        except Exception:
            pass
        report["checks"]["task_completed_and_persisted"] = False

    report["verdict"] = "VERIFIED" if all(report["checks"].values()) else "FAILED"

    if agent_name in {"memorizer", "learner"} and tool_name == "memory_save" and outputs.get("id"):
        fixture.setdefault("memory_ids", []).append(outputs.get("id"))
        try:
            memory_record = service.get_memory(outputs.get("id"), owner_scope=owner_scope)
            report["checks"]["memory_persisted_in_owner_scope"] = bool(
                memory_record
                and memory_record.get("status") == "active"
                and memory_record.get("privacy_level") == "PRIVATE"
                and memory_record.get("owner_scope") == owner_scope
            )
            if not report["checks"]["memory_persisted_in_owner_scope"]:
                report["verdict"] = "FAILED"
        except Exception as exc:
            report["checks"]["memory_persisted_in_owner_scope"] = False
            report["error"] = {"type": type(exc).__name__, "message": "memory persistence verification failed"}
    if agent_name == "learner" and tool_name == "learning_save" and outputs.get("id"):
        try:
            learning_record = service.get_learning(outputs.get("id"), owner_scope=owner_scope)
            report["checks"]["learning_stays_candidate"] = bool(
                learning_record
                and learning_record.get("status") == "candidate"
                and not learning_record.get("verified_at")
            )
            if not report["checks"]["learning_stays_candidate"]:
                report["verdict"] = "FAILED"
        except Exception as exc:
            report["checks"]["learning_stays_candidate"] = False
            report["error"] = {"type": type(exc).__name__, "message": "learning persistence verification failed"}
    if agent_name == "graph_builder" and tool_name == "graph_create_node" and outputs.get("id"):
        fixture.setdefault("graph_node_ids", []).append(outputs.get("id"))
    if agent_name == "graph_builder" and tool_name == "graph_create_edge" and outputs.get("id"):
        fixture["graph_edge_id"] = outputs.get("id")
    if agent_name == "learner" and tool_name == "learning_save" and outputs.get("id"):
        fixture["learning_id"] = outputs.get("id")
    if agent_name == "autonomy_orchestrator" and isinstance(outputs.get("autonomy"), dict):
        fixture["autonomy_run_id"] = outputs["autonomy"].get("id")

    report["elapsed_ms"] = int((time.time() - started) * 1000)
    return report


def _cleanup_fixture(service, fixture: dict[str, Any], actor: str, owner_scope: str, run_id: str) -> dict[str, Any]:
    cleanup = {"ok": True, "actions": []}

    node_ids = list(dict.fromkeys(fixture.get("graph_node_ids") or []))
    memory_ids = list(dict.fromkeys(fixture.get("memory_ids") or []))
    for memory_id in memory_ids:
        memory_nodes = service.repo.search(
            "graph_nodes",
            {"label": f"memory:{memory_id}"},
            limit=20,
            order_by="created_at",
            descending=False,
        )
        node_ids.extend(node.get("id") for node in memory_nodes if node.get("id"))
    node_ids = [x for x in dict.fromkeys(node_ids) if x]

    edge_ids = set()
    for node_id in node_ids:
        for e in service.repo.search("graph_edges", {"from_node": node_id}, limit=200):
            if e.get("id"):
                edge_ids.add(e["id"])
        for e in service.repo.search("graph_edges", {"to_node": node_id}, limit=200):
            if e.get("id"):
                edge_ids.add(e["id"])
    if fixture.get("graph_edge_id"):
        edge_ids.add(fixture["graph_edge_id"])

    for edge_id in sorted(edge_ids):
        try:
            deleted = service.repo.delete("graph_edges", edge_id)
            absent = service.repo.get("graph_edges", edge_id) is None
            cleanup["actions"].append({
                "entity": "graph_edges",
                "id": edge_id,
                "deleted": bool(deleted),
                "confirmed_absent": absent,
            })
            cleanup["ok"] &= absent
        except Exception as exc:
            cleanup["ok"] = False
            cleanup["actions"].append({
                "entity": "graph_edges",
                "id": edge_id,
                "error_type": type(exc).__name__,
            })

    for node_id in node_ids:
        try:
            deleted = service.repo.delete("graph_nodes", node_id)
            absent = service.repo.get("graph_nodes", node_id) is None
            cleanup["actions"].append({
                "entity": "graph_nodes",
                "id": node_id,
                "deleted": bool(deleted),
                "confirmed_absent": absent,
            })
            cleanup["ok"] &= absent
        except Exception as exc:
            cleanup["ok"] = False
            cleanup["actions"].append({
                "entity": "graph_nodes",
                "id": node_id,
                "error_type": type(exc).__name__,
            })

    for entity, record_id in (
        ("learning_events", fixture.get("learning_id")),
    ):
        if not record_id:
            continue
        try:
            deleted = service.repo.delete(entity, record_id)
            absent = service.repo.get(entity, record_id) is None
            cleanup["actions"].append({
                "entity": entity,
                "id": record_id,
                "deleted": bool(deleted),
                "confirmed_absent": absent,
            })
            cleanup["ok"] &= absent
        except Exception as exc:
            cleanup["ok"] = False
            cleanup["actions"].append({
                "entity": entity,
                "id": record_id,
                "error_type": type(exc).__name__,
            })

    for memory_id in memory_ids:
        try:
            deleted = service.repo.delete("memories", memory_id)
            absent = service.repo.get("memories", memory_id) is None
            cleanup["actions"].append({
                "entity": "memories",
                "id": memory_id,
                "deleted": bool(deleted),
                "confirmed_absent": absent,
            })
            cleanup["ok"] &= absent
        except Exception as exc:
            cleanup["ok"] = False
            cleanup["actions"].append({
                "entity": "memories",
                "id": memory_id,
                "error_type": type(exc).__name__,
            })

    autonomy_id = fixture.get("autonomy_run_id")
    if autonomy_id:
        try:
            autonomy = AutonomyService(service)
            run = autonomy.get_run(autonomy_id, owner_scope=owner_scope)
            if run and run.get("status") not in {"completed", "rejected", "failed", "cancelled"}:
                run = autonomy.cancel(
                    autonomy_id,
                    actor=actor,
                    owner_scope=owner_scope,
                    reason="f9_agent_audit_cleanup",
                )
            cleanup["actions"].append({
                "entity": "autonomy_runs",
                "id": autonomy_id,
                "status_after": (run or {}).get("status"),
            })
            cleanup["ok"] &= not run or run.get("status") in {"completed", "rejected", "failed", "cancelled"}
        except Exception as exc:
            cleanup["ok"] = False
            cleanup["actions"].append({
                "entity": "autonomy_runs",
                "id": autonomy_id,
                "error_type": type(exc).__name__,
            })

    service.record_audit(
        "agent_audit",
        "agent_audit.cleanup",
        "agent_audit_runs",
        run_id,
        "success" if cleanup["ok"] else "failure",
        {"run_id": run_id, "requested_by": actor, "cleanup": cleanup},
    )
    return cleanup


def run_agent_audit(
    service,
    invoke_registered: Callable[..., dict[str, Any]],
    actor: str,
    owner_scope: str,
    run_id: str,
    repo_name: str = "AkiraGr2/akira-empresa",
) -> dict[str, Any]:
    """Run the complete F9 audit over every active production agent."""
    fixture: dict[str, Any] = {"memory_ids": []}
    developer_output: dict[str, Any] = {}
    tester_output: dict[str, Any] = {}
    reports: list[dict[str, Any]] = []

    service.record_audit(
        "agent_audit",
        "agent_audit.started",
        "agent_audit_runs",
        run_id,
        "success",
        {
            "run_id": run_id,
            "requested_by": actor,
            "owner_scope": owner_scope,
            "agent_order": PRODUCTION_AGENT_ORDER,
        },
    )

    agents = {
        a.get("name"): a
        for a in service.list_agents(limit=200)
        if a.get("status") != "disabled"
    }

    missing = [name for name in PRODUCTION_AGENT_ORDER if name not in agents]
    unexpected = sorted(name for name in agents if name not in PRODUCTION_AGENT_ORDER)
    if missing or unexpected:
        report = {
            "agent": "_registry",
            "verdict": "FAILED",
            "checks": {
                "all_production_agents_registered": not missing,
                "no_uncontracted_active_agents": not unexpected,
            },
            "evidence": {
                "missing_agents": missing,
                "unexpected_active_agents": unexpected,
            },
        }
        service.record_audit(
            "agent_audit",
            "agent_audit.case",
            "agents",
            run_id,
            "failure",
            {"run_id": run_id, "report": report},
        )
        reports.append(report)
    else:
        cases = [
            ("memorizer", "memory_save", {"content": f"AKIRA F9 AGENT AUDIT {run_id}", "memory_type": "system"}),
            ("memorizer", "memory_search", {"query": f"AKIRA F9 AGENT AUDIT {run_id}"}),
            ("researcher", "web_search", {"query": "documentación oficial de FastAPI"}),
            ("researcher", "github_repo_read", {
                "repo": repo_name, "path": "", "paths": ["test_specialized_agents_contract.py"],
                "queries": ["SpecializedAgentsContractTests"], "max_files": 2,
            }),
            ("researcher", "memory_search", {"query": f"AKIRA F9 AGENT AUDIT {run_id}"}),
            ("graph_builder", "graph_create_node", {
                "node_type": "error", "label": f"AKIRA F9 AGENT AUDIT A {run_id}",
            }),
            ("graph_builder", "graph_create_node", {
                "node_type": "solution", "label": f"AKIRA F9 AGENT AUDIT B {run_id}",
            }),
            ("graph_builder", "graph_create_edge", {
                "from_node": "__replace_after_first_node__", "to_node": "__replace_after_second_node__",
                "relation_type": "related_to",
            }),
            ("graph_builder", "graph_related", {"node_id": "__replace_after_first_node__"}),
            ("learner", "learning_save", {
                "source": "agent_audit",
                "event": f"f9_agent_audit_{run_id}",
                "lesson": "Auditoría E2E controlada de agente learner.",
            }),
            ("internal", "self_model_read", {}),
            ("developer", "developer_propose", {
                "repo": repo_name,
                "paths": ["test_specialized_agents_contract.py"],
                "queries": ["valid_unified_diff_with_stale_hunk_coordinates_is_recovered_before_acceptance"],
                "instruction": "Revisa el contrato de agentes y propone como máximo una mejora de prueba. No escribas ni apliques cambios.",
            }),
            ("tester", "python_test", {
                "tests": ["test_specialized_agents_contract.SpecializedAgentsContractTests.test_developer_proposal_is_explicitly_non_mutating"],
                "compile_paths": ["nexus.py"],
            }),
            ("reviewer", "code_review", {
                "repo": repo_name,
                "paths": ["test_specialized_agents_contract.py"],
                "proposal": {},
                "test_results": {},
            }),
            ("autonomy_orchestrator", "controlled_autonomy_start", {
                "goal": "Auditoría F9 segura y sin escritura externa",
                "repository": repo_name,
                "base_branch": "main",
                "paths": ["test_specialized_agents_contract.py"],
                "instruction": "Propón únicamente una mejora de prueba documental mínima. No escribas en GitHub. Debes detenerte esperando aprobación humana.",
                "queries": ["test_developer_proposal_is_explicitly_non_mutating"],
                "tests": ["test_specialized_agents_contract.SpecializedAgentsContractTests.test_developer_proposal_is_explicitly_non_mutating"],
                "idempotency_key": f"f9-agent-audit-autonomy:{run_id}",
            }),
        ]

        for index, (agent_name, tool_name, raw_inputs) in enumerate(cases, start=1):
            inputs = dict(raw_inputs)
            if tool_name == "graph_create_edge":
                ids = fixture.get("graph_node_ids") or []
                if len(ids) != 2:
                    inputs["from_node"] = ""
                    inputs["to_node"] = ""
                else:
                    inputs["from_node"], inputs["to_node"] = ids[0], ids[1]
            elif tool_name == "graph_related":
                ids = fixture.get("graph_node_ids") or []
                inputs["node_id"] = ids[0] if ids else ""
            elif agent_name == "reviewer":
                inputs["proposal"] = developer_output
                inputs["test_results"] = tester_output

            report = _audit_task(
                service, invoke_registered, actor, owner_scope, run_id,
                agent_name, tool_name, inputs, fixture, index,
            )
            if agent_name == "developer" and tool_name == "developer_propose":
                developer_output = (report.get("evidence") or {}).get("semantic_output") or {}
            if agent_name == "tester" and tool_name == "python_test":
                tester_output = (report.get("evidence") or {}).get("semantic_output") or {}

            if tool_name == "developer_propose":
                invocation = service.get_invocation_by_idempotency_key(
                    tool_name, f"agent:{agent_name}", owner_scope, f"f9-audit:{run_id}:{agent_name}:{tool_name}:{index}:invoke"
                )
                if invocation:
                    developer_output = invocation.get("outputs") or {}
                    report["evidence"]["semantic_output"] = developer_output
            if tool_name == "python_test":
                invocation = service.get_invocation_by_idempotency_key(
                    tool_name, f"agent:{agent_name}", owner_scope, f"f9-audit:{run_id}:{agent_name}:{tool_name}:{index}:invoke"
                )
                if invocation:
                    tester_output = invocation.get("outputs") or {}
                    report["evidence"]["semantic_output"] = tester_output

            service.record_audit(
                "agent_audit",
                "agent_audit.case",
                "agents",
                run_id,
                "success" if report.get("verdict") == "VERIFIED" else "failure",
                {"run_id": run_id, "report": report},
            )
            reports.append(report)

    cleanup = _cleanup_fixture(service, fixture, actor, owner_scope, run_id)
    counts: dict[str, int] = {}
    for report in reports:
        verdict = report.get("verdict", "FAILED")
        counts[verdict] = counts.get(verdict, 0) + 1
    final_ok = (
        len(reports) == 15
        and not missing
        and not unexpected
        and not unavailable_tools
        and {report.get("agent") for report in reports if report.get("agent") in PRODUCTION_AGENT_ORDER}
            == set(PRODUCTION_AGENT_ORDER)
        and counts.get("FAILED", 0) == 0
        and cleanup.get("ok") is True
    )
    result = {
        "run_id": run_id,
        "agent_count": len(PRODUCTION_AGENT_ORDER),
        "summary": counts,
        "cleanup": cleanup,
        "ok": final_ok,
        "reports": reports,
    }
    service.record_audit(
        "agent_audit",
        "agent_audit.completed",
        "agent_audit_runs",
        run_id,
        "success" if final_ok else "failure",
        {"run_id": run_id, "requested_by": actor, "owner_scope": owner_scope, "summary": counts, "cleanup_ok": cleanup.get("ok")},
    )
    return result