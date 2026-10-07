"""Auditoría E2E individual de las herramientas de AKIRA (F8).

El auditor prueba una herramienta por vez usando el mismo dispatcher del runtime,
registra evidencia en tool_invocations/audit_log y limpia fixtures de escritura.
No sustituye la evidencia de F7: cognitive_cycle se certifica mediante la evidencia
E2E ya cerrada de F7 y se evita crear otro ciclo durante esta auditoría.
"""
from __future__ import annotations

import base64
import hashlib
import json
import time
import uuid
from typing import Any, Callable

from persistence.autonomy import AutonomyService
from persistence.core import ValidationError, validate_tool_inputs

TOOL_ORDER = [
    "web_search",
    "github_repo_read",
    "memory_save",
    "memory_search",
    "graph_create_node",
    "graph_create_edge",
    "graph_related",
    "learning_save",
    "self_model_read",
    "extract_pdf",
    "image_generate",
    "cognitive_cycle",
    "developer_propose",
    "python_test",
    "code_review",
    "controlled_autonomy_start",
]

READ_ONLY_TOOLS = {
    "web_search",
    "github_repo_read",
    "memory_search",
    "graph_related",
    "self_model_read",
    "python_test",
    "developer_propose",
    "code_review",
    "controlled_autonomy_start",
    "extract_pdf",
}

WRITE_TOOLS = {
    "memory_save",
    "graph_create_node",
    "graph_create_edge",
    "learning_save",
}

MAX_RESULTS_TO_AUDIT = 5


def _digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


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
    if expected in {"any", "object"}:
        return True
    return True


def _schema_ok(outputs: Any, schema: Any) -> tuple[bool, list[str]]:
    if not isinstance(schema, dict):
        return False, ["outputs_schema_not_object"]
    if not isinstance(outputs, dict):
        return False, ["outputs_not_object"]
    failures: list[str] = []
    for key, expected in schema.items():
        if key not in outputs:
            failures.append(f"missing_output:{key}")
            continue
        if not _matches_type(outputs[key], expected):
            failures.append(f"wrong_type:{key}:expected={expected}")
    return not failures, failures


def _build_minimal_pdf_b64() -> str:
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        4: b"<< /Length 46 >>\nstream\nBT /F1 12 Tf 20 100 Td (AKIRA F8 TOOL AUDIT) Tj ET\nendstream",
        5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    data = b"%PDF-1.4\n"
    offsets = {0: 0}
    for index in range(1, 6):
        offsets[index] = len(data)
        data += f"{index} 0 obj\n".encode("ascii") + objects[index] + b"\nendobj\n"
    xref_pos = len(data)
    data += b"xref\n0 6\n0000000000 65535 f \n"
    for index in range(1, 6):
        data += f"{offsets[index]:010d} 00000 n \n".encode("ascii")
    data += (
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n"
        + str(xref_pos).encode("ascii")
        + b"\n%%EOF\n"
    )
    return base64.b64encode(data).decode("ascii")


def _expected_inputs(tool_name: str, repo_name: str, fixture_tag: str) -> dict[str, Any]:
    if tool_name == "web_search":
        return {"query": "documentación oficial de FastAPI"}
    if tool_name == "github_repo_read":
        return {
            "repo": repo_name,
            "path": "",
            "paths": ["test_tool_registry_contract.py"],
            "queries": ["test_every_registered_tool_has_a_runtime_dispatch_branch"],
            "max_files": 2,
        }
    if tool_name == "memory_save":
        return {
            "content": f"AKIRA F8 TOOL AUDIT {fixture_tag}",
            "memory_type": "system",
        }
    if tool_name == "memory_search":
        return {"query": f"AKIRA F8 TOOL AUDIT {fixture_tag}"}
    if tool_name == "graph_create_node":
        return {"node_type": "error", "label": f"AKIRA F8 TOOL AUDIT {fixture_tag}"}
    if tool_name == "graph_create_edge":
        return {"from_node": "", "to_node": "", "relation_type": "related_to"}
    if tool_name == "graph_related":
        return {"node_id": ""}
    if tool_name == "learning_save":
        return {
            "event": f"f8_tool_audit_{fixture_tag}",
            "lesson": f"Auditoría E2E controlada de F8: {fixture_tag}",
            "source": "tool_audit",
        }
    if tool_name == "self_model_read":
        return {}
    if tool_name == "extract_pdf":
        return {
            "filename": "akira_f8_tool_audit.pdf",
            "content_base64": _build_minimal_pdf_b64(),
        }
    if tool_name == "image_generate":
        return {"prompt": "AKIRA F8 TOOL AUDIT"}
    if tool_name == "cognitive_cycle":
        return {"message": "AKIRA F8 TOOL AUDIT"}  # not executed
    if tool_name == "developer_propose":
        return {
            "repo": repo_name,
            "paths": ["test_tool_registry_contract.py"],
            "queries": ["test_every_registered_tool_has_a_runtime_dispatch_branch"],
            "instruction": "Revisa este archivo y propone como máximo una mejora de prueba, sin escribir ni aplicar cambios.",
        }
    if tool_name == "python_test":
        return {
            "tests": [
                "ToolRegistryContractTests.test_registered_inputs_are_schema_validated_before_dispatch",
            ],
            "compile_paths": [],
        }
    if tool_name == "code_review":
        return {
            "repo": repo_name,
            "paths": ["test_tool_registry_contract.py"],
            "proposal": {
                "summary": "F8 audit synthetic proposal",
                "changes": [],
                "tests": ["ToolRegistryContractTests.test_registered_inputs_are_schema_validated_before_dispatch"],
                "requires_human_approval": True,
                "write_performed": False,
            },
            "test_results": {"status": "passed", "source": "f8_tool_audit"},
        }
    if tool_name == "controlled_autonomy_start":
        return {
            "goal": "Auditoría F8 segura y sin escritura externa",
            "repository": repo_name,
            "base_branch": "main",
            "paths": ["test_tool_registry_contract.py"],
            "instruction": "No escribir ni aplicar cambios. Preparar y probar una propuesta de mejora de pruebas, requiriendo aprobación humana.",
            "queries": ["test_every_registered_tool_has_a_runtime_dispatch_branch"],
            "tests": [
                "ToolRegistryContractTests.test_registered_inputs_are_schema_validated_before_dispatch",
            ],
            "idempotency_key": "",
        }
    return {}


def _audit_negative_input(tool: dict[str, Any]) -> tuple[bool, str]:
    invalid = {"__akira_f8_invalid__": True}
    try:
        validate_tool_inputs(tool, invalid)
    except ValidationError as exc:
        return True, type(exc).__name__
    except Exception as exc:
        return False, f"unexpected:{type(exc).__name__}"
    return False, "validator_accepted_unknown_input"


def _record_case(service, actor: str, run_id: str, tool_name: str, report: dict[str, Any]) -> None:
    service.record_audit(
        "tool_audit",
        "tool_audit.case",
        "tools",
        tool_name,
        "success" if report.get("verdict") in {"VERIFIED", "FAIL_CLOSED", "VERIFIED_VIA_F7"} else "failure",
        {
            "run_id": run_id,
            "requested_by": actor,
            "report": report,
        },
    )


def _cleanup_fixture(service, fixture: dict[str, Any], actor: str, owner_scope: str, audit_tag: str) -> dict[str, Any]:
    cleanup = {"ok": True, "actions": []}

    for entity, record_id in (
        ("graph_edges", fixture.get("graph_edge_id")),
        ("graph_nodes", fixture.get("graph_node_b_id")),
        ("graph_nodes", fixture.get("graph_node_a_id")),
        ("learning_events", fixture.get("learning_id")),
        ("memories", fixture.get("memory_id")),
    ):
        if not record_id:
            continue
        try:
            deleted = service.repo.delete(entity, record_id)
            still = service.repo.get(entity, record_id)
            step_ok = bool(deleted) and still is None
            cleanup["actions"].append({
                "entity": entity,
                "id": record_id,
                "deleted": bool(deleted),
                "confirmed_absent": still is None,
            })
            if not step_ok:
                cleanup["ok"] = False
        except Exception as exc:
            cleanup["ok"] = False
            cleanup["actions"].append({
                "entity": entity,
                "id": record_id,
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
                    reason="f8_tool_audit_cleanup",
                )
            cleanup["actions"].append({
                "entity": "autonomy_runs",
                "id": autonomy_id,
                "status_after": (run or {}).get("status"),
            })
            if run and run.get("status") not in {"cancelled", "failed", "rejected", "completed"}:
                cleanup["ok"] = False
        except Exception as exc:
            cleanup["ok"] = False
            cleanup["actions"].append({
                "entity": "autonomy_runs",
                "id": autonomy_id,
                "error_type": type(exc).__name__,
            })

    service.record_audit(
        "tool_audit",
        "tool_audit.cleanup",
        "tools",
        audit_tag,
        "success" if cleanup["ok"] else "failure",
        {
            "run_id": audit_tag,
            "requested_by": actor,
            "cleanup": cleanup,
        },
    )
    return cleanup


def _run_one(
    service,
    invoke: Callable[..., tuple[dict[str, Any] | None, dict[str, Any] | None]],
    actor: str,
    owner_scope: str,
    run_id: str,
    tool_name: str,
    repo_name: str,
    fixture: dict[str, Any],
    dependency_outputs: dict[str, Any],
) -> dict[str, Any]:
    started = time.time()
    tool = service.get_tool_by_name(tool_name)
    report: dict[str, Any] = {
        "tool": tool_name,
        "verdict": "FAILED",
        "checks": {},
        "evidence": {},
    }
    if tool is None:
        report["checks"]["registered"] = False
        report["error"] = "tool_not_registered"
        return report

    report["checks"]["registered"] = True
    report["checks"]["status_available"] = tool.get("status") == "available"

    negative_ok, negative_detail = _audit_negative_input(tool)
    report["checks"]["input_rejection"] = negative_ok
    report["evidence"]["invalid_input"] = negative_detail

    if tool.get("status") != "available":
        if tool_name == "image_generate" and tool.get("status") == "disabled":
            report["verdict"] = "FAIL_CLOSED"
            report["checks"]["disabled_as_intended"] = True
            report["checks"]["no_execution_allowed"] = True
        else:
            report["error"] = f"tool_status_{tool.get('status')}"
        report["elapsed_ms"] = int((time.time() - started) * 1000)
        return report

    if tool_name == "cognitive_cycle":
        cap = service.list_capabilities(filters={"name": "cognitive_cycle_persistent"}, limit=1)
        verified = bool(cap and cap[0].get("verification_state") == "verified")
        report["verdict"] = "VERIFIED_VIA_F7" if verified else "FAILED"
        report["checks"]["inherited_f7_e2e"] = verified
        report["evidence"]["basis"] = "F7 E2E verification; no duplicate cognitive cycle executed by F8 audit"
        report["elapsed_ms"] = int((time.time() - started) * 1000)
        return report

    inputs = _expected_inputs(tool_name, repo_name, run_id)
    if tool_name == "memory_search":
        memory_id = fixture.get("memory_id")
        if not memory_id:
            report["verdict"] = "INCONCLUSIVE"
            report["error"] = "memory_fixture_missing"
            return report
    if tool_name == "graph_create_edge":
        inputs["from_node"] = fixture.get("graph_node_a_id") or ""
        inputs["to_node"] = fixture.get("graph_node_b_id") or ""
    if tool_name == "graph_related":
        inputs["node_id"] = fixture.get("graph_node_a_id") or ""

    idem = f"f8-audit:{run_id}:{tool_name}"
    outputs, error = invoke(
        service,
        tool_name,
        inputs,
        actor,
        owner_scope,
        idempotency_key=idem,
    )
    report["checks"]["execution"] = error is None
    report["evidence"]["invocation_idempotency_key"] = idem
    report["evidence"]["execution_error"] = error

    invocation = service.get_invocation_by_idempotency_key(
        tool_name,
        actor,
        owner_scope,
        idem,
    )
    report["checks"]["invocation_persisted"] = invocation is not None
    report["checks"]["owner_scope"] = bool(
        invocation and invocation.get("owner_scope") == owner_scope
    )

    if error is not None:
        report["verdict"] = "FAILED"
        report["elapsed_ms"] = int((time.time() - started) * 1000)
        return report

    outputs = outputs or {}
    schema_ok, schema_failures = _schema_ok(outputs, tool.get("outputs_schema") or {})
    report["checks"]["output_schema"] = schema_ok
    report["evidence"]["output_schema_failures"] = schema_failures
    report["evidence"]["output_keys"] = sorted(outputs.keys())
    report["evidence"]["output_digest"] = _digest(outputs)

    semantic_ok = True
    semantic_detail: dict[str, Any] = {}

    if tool_name == "web_search":
        result = outputs.get("result") if isinstance(outputs.get("result"), dict) else {}
        count = int(result.get("result_count") or 0)
        semantic_ok = count > 0 and bool(result.get("query"))
        semantic_detail = {
            "result_count": count,
            "query": result.get("query"),
            "has_reference": bool(
                result.get("results")
                and isinstance(result["results"], list)
                and any(item.get("reference") for item in result["results"] if isinstance(item, dict))
            ),
        }
        semantic_ok = semantic_ok and semantic_detail["has_reference"]
    elif tool_name == "github_repo_read":
        result = outputs.get("result") if isinstance(outputs.get("result"), dict) else {}
        semantic_ok = bool(result.get("ok")) and (
            bool(result.get("files")) or bool(result.get("root"))
        )
        semantic_detail = {"files": len(result.get("files") or []), "root_entries": len(result.get("root") or [])}
    elif tool_name == "memory_save":
        semantic_ok = bool(outputs.get("stored")) and bool(outputs.get("id"))
        fixture["memory_id"] = outputs.get("id")
    elif tool_name == "memory_search":
        semantic_ok = int(outputs.get("found") or 0) >= 1
    elif tool_name == "graph_create_node":
        semantic_ok = bool(outputs.get("id"))
        if not fixture.get("graph_node_a_id"):
            fixture["graph_node_a_id"] = outputs.get("id")
        else:
            fixture["graph_node_b_id"] = outputs.get("id")
    elif tool_name == "graph_create_edge":
        semantic_ok = bool(outputs.get("id"))
        fixture["graph_edge_id"] = outputs.get("id")
    elif tool_name == "graph_related":
        semantic_ok = isinstance(outputs.get("edges"), list) and int(outputs.get("count") or 0) >= 1
    elif tool_name == "learning_save":
        semantic_ok = bool(outputs.get("id"))
        fixture["learning_id"] = outputs.get("id")
    elif tool_name == "self_model_read":
        semantic_ok = isinstance(outputs.get("self_model"), dict)
    elif tool_name == "extract_pdf":
        semantic_ok = "AKIRA F8 TOOL AUDIT" in str(outputs.get("text") or "")
    elif tool_name == "developer_propose":
        proposal = outputs.get("proposal") if isinstance(outputs.get("proposal"), dict) else {}
        semantic_ok = proposal.get("write_performed") is False and proposal.get("requires_human_approval") is True
        dependency_outputs["developer_propose"] = proposal
    elif tool_name == "python_test":
        semantic_ok = str(outputs.get("status") or "").lower() in {"passed", "success"}
        dependency_outputs["python_test"] = outputs
    elif tool_name == "code_review":
        review = outputs.get("review") if isinstance(outputs.get("review"), dict) else {}
        semantic_ok = str(review.get("verdict") or "").lower() in {"approve", "approved"}
    elif tool_name == "controlled_autonomy_start":
        semantic_ok = (
            outputs.get("awaits_human_approval") is True
            and outputs.get("external_write_performed") is False
        )
        run = outputs.get("autonomy") if isinstance(outputs.get("autonomy"), dict) else {}
        fixture["autonomy_run_id"] = run.get("id")
        semantic_detail = {
            "status": run.get("status"),
            "awaits_human_approval": outputs.get("awaits_human_approval"),
            "external_write_performed": outputs.get("external_write_performed"),
        }

    report["checks"]["semantic_result"] = semantic_ok
    report["evidence"]["semantic"] = semantic_detail

    # Probar replay sin ejecutar por segunda vez.
    replay = service.get_invocation_by_idempotency_key(tool_name, actor, owner_scope, idem)
    report["checks"]["idempotency_key_registered"] = replay is not None

    report["verdict"] = (
        "VERIFIED"
        if all(report["checks"].values())
        else "FAILED"
    )
    report["elapsed_ms"] = int((time.time() - started) * 1000)
    return report


def run_tool_audit(
    service,
    invoke: Callable[..., tuple[dict[str, Any] | None, dict[str, Any] | None]],
    actor: str,
    owner_scope: str,
    run_id: str,
    repo_name: str = "AkiraGr2/akira-empresa",
) -> dict[str, Any]:
    """Execute the full individual-tool audit and return a JSON-safe report."""
    fixture: dict[str, Any] = {}
    dependencies: dict[str, Any] = {}
    reports: list[dict[str, Any]] = []

    for tool_name in TOOL_ORDER:
        try:
            report = _run_one(
                service,
                invoke,
                actor,
                owner_scope,
                run_id,
                tool_name,
                repo_name,
                fixture,
                dependencies,
            )
        except Exception as exc:
            report = {
                "tool": tool_name,
                "verdict": "FAILED",
                "checks": {},
                "evidence": {},
                "error": {"type": type(exc).__name__, "message": str(exc)[:300]},
            }
        _record_case(service, actor, run_id, tool_name, report)
        reports.append(report)

    cleanup = _cleanup_fixture(service, fixture, actor, owner_scope, run_id)
    counts: dict[str, int] = {}
    for report in reports:
        verdict = report.get("verdict", "FAILED")
        counts[verdict] = counts.get(verdict, 0) + 1

    final_ok = (
        counts.get("FAILED", 0) == 0
        and counts.get("INCONCLUSIVE", 0) == 0
        and cleanup.get("ok") is True
        and len(reports) == len(TOOL_ORDER)
    )

    return {
        "run_id": run_id,
        "tool_count": len(reports),
        "summary": counts,
        "cleanup": cleanup,
        "ok": final_ok,
        "reports": reports,
    }
