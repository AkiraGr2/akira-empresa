"""Contratos semánticos de los agentes de AKIRA (F9).

Un agente no se considera válido por existir en la tabla. Su contrato combina:
rol + herramientas permitidas + límites + resultado semánticamente verificable.
"""
from __future__ import annotations

from typing import Any

PRODUCTION_AGENT_ORDER = [
    "researcher",
    "memorizer",
    "graph_builder",
    "learner",
    "internal",
    "developer",
    "tester",
    "reviewer",
    "autonomy_orchestrator",
]

AGENT_CONTRACTS: dict[str, dict[str, Any]] = {
    "researcher": {
        "role": "researcher",
        "allowed_tools": ["web_search", "memory_search", "github_repo_read"],
        "forbidden_tools": ["memory_save", "graph_create_node", "graph_create_edge", "learning_save",
                            "developer_propose", "python_test", "code_review", "controlled_autonomy_start"],
    },
    "memorizer": {
        "role": "memorizer",
        "allowed_tools": ["memory_save", "memory_search"],
        "forbidden_tools": ["learning_save", "developer_propose", "python_test",
                            "code_review", "controlled_autonomy_start"],
    },
    "graph_builder": {
        "role": "graph_builder",
        "allowed_tools": ["graph_create_node", "graph_create_edge", "graph_related"],
        "forbidden_tools": ["memory_save", "learning_save", "developer_propose",
                            "python_test", "code_review", "controlled_autonomy_start"],
    },
    "learner": {
        "role": "learner",
        "allowed_tools": ["learning_save", "memory_save"],
        "forbidden_tools": ["developer_propose", "python_test", "code_review", "controlled_autonomy_start"],
    },
    "internal": {
        "role": "internal",
        "allowed_tools": ["self_model_read", "cognitive_cycle"],
        "forbidden_tools": ["developer_propose", "python_test", "code_review", "controlled_autonomy_start"],
    },
    "developer": {
        "role": "developer",
        "allowed_tools": ["github_repo_read", "developer_propose"],
        "forbidden_tools": ["memory_save", "learning_save", "python_test", "code_review",
                            "controlled_autonomy_start"],
    },
    "tester": {
        "role": "tester",
        "allowed_tools": ["github_repo_read", "python_test"],
        "forbidden_tools": ["memory_save", "learning_save", "developer_propose",
                            "code_review", "controlled_autonomy_start"],
    },
    "reviewer": {
        "role": "reviewer",
        "allowed_tools": ["github_repo_read", "python_test", "code_review"],
        "forbidden_tools": ["memory_save", "learning_save", "developer_propose",
                            "controlled_autonomy_start"],
    },
    "autonomy_orchestrator": {
        "role": "autonomy_orchestrator",
        "allowed_tools": ["controlled_autonomy_start"],
        "forbidden_tools": ["developer_propose", "python_test", "code_review",
                            "memory_save", "learning_save"],
    },
}


def validate_agent_definition(agent: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate a persisted production-agent definition against its contract."""
    if not isinstance(agent, dict):
        return False, ["agent_not_object"]
    name = str(agent.get("name") or "").strip()
    contract = AGENT_CONTRACTS.get(name)
    if contract is None:
        return False, [f"unknown_production_agent:{name}"]
    failures: list[str] = []
    if agent.get("role") != contract["role"]:
        failures.append(f"wrong_role:{agent.get('role')}!= {contract['role']}")
    if list(agent.get("allowed_tools") or []) != list(contract["allowed_tools"]):
        failures.append("allowed_tools_mismatch")
    if agent.get("status") == "disabled":
        failures.append("production_agent_disabled")
    if not str(agent.get("description") or "").strip():
        failures.append("description_missing")
    return not failures, failures


def validate_agent_result(
    agent_name: str,
    tool_name: str,
    outputs: Any,
    error: Any = None,
) -> tuple[bool, dict[str, Any]]:
    """Validate the semantic envelope produced by an agent task.

    Shared capabilities have one shared semantic shape regardless of which
    production agent is exercising them. Agent-specific tools add stricter
    semantic requirements below.
    """
    detail: dict[str, Any] = {}
    contract = AGENT_CONTRACTS.get(agent_name)
    if contract is None:
        return False, {"reason": "unknown_agent"}
    if tool_name not in contract["allowed_tools"]:
        return False, {"reason": "tool_not_allowed_by_contract"}
    if error is not None:
        return False, {"reason": "tool_error", "error": error}
    if not isinstance(outputs, dict):
        return False, {"reason": "outputs_not_object"}

    if tool_name == "github_repo_read":
        result = outputs.get("result")
        ok = (
            isinstance(result, dict)
            and result.get("ok") is True
            and bool(result.get("files") or result.get("root"))
            and isinstance(result.get("head_commit_sha"), str)
            and len(result.get("head_commit_sha") or "") == 40
        )
        detail["head_commit_sha_present"] = bool(
            isinstance(result, dict) and result.get("head_commit_sha")
        )
        return ok, detail

    if tool_name == "memory_search":
        ok = isinstance(outputs.get("results"), list) and isinstance(outputs.get("found"), int)
        detail["result_count"] = len(outputs.get("results") or [])
        detail["found"] = outputs.get("found")
        return ok, detail

    if tool_name == "memory_save":
        ok = outputs.get("stored") is True and bool(outputs.get("id"))
        detail["stored"] = outputs.get("stored")
        detail["semantic_indexed"] = outputs.get("semantic_indexed")
        return ok, detail

    if tool_name in {"graph_create_node", "graph_create_edge"}:
        ok = bool(outputs.get("id"))
        return ok, detail

    if tool_name == "graph_related":
        ok = isinstance(outputs.get("edges"), list) and isinstance(outputs.get("count"), int)
        return ok, detail

    if tool_name == "learning_save":
        ok = bool(outputs.get("id")) and str(outputs.get("outcome") or "") in {"created", "existing"}
        return ok, detail

    if tool_name == "python_test":
        tests = outputs.get("tests")
        ok = (
            str(outputs.get("status") or "").lower() in {"passed", "success"}
            and isinstance(tests, list)
        )
        detail["test_count"] = len(tests) if isinstance(tests, list) else 0
        return ok, detail

    if tool_name == "web_search":
        result = outputs.get("result")
        if not isinstance(result, dict):
            return False, {"reason": "result_missing"}
        references = result.get("results") or []
        ok = (
            isinstance(references, list)
            and isinstance(result.get("query"), str)
            and int(result.get("result_count") or 0) > 0
            and int(result.get("result_count") or 0) == len(references)
            and all(
                isinstance(item, dict)
                and isinstance(item.get("reference"), str)
                and item.get("reference").startswith(("http://", "https://"))
                for item in references
            )
        )
        detail["result_count"] = int(result.get("result_count") or 0)
        detail["has_reference"] = all(
            isinstance(item, dict)
            and isinstance(item.get("reference"), str)
            and item.get("reference").startswith(("http://", "https://"))
            for item in references
        )
        return ok, detail

    if tool_name == "self_model_read":
        model = outputs.get("self_model")
        ok = isinstance(model, dict) and all(
            key in model for key in ("identity", "capabilities", "tools", "models")
        )
        return ok, detail

    if tool_name == "cognitive_cycle":
        ok = (
            bool(outputs.get("cycle_id"))
            and int(outputs.get("events_count") or 0) == 9
            and not outputs.get("error")
        )
        detail["events_count"] = int(outputs.get("events_count") or 0)
        detail["learning_id_present"] = bool(outputs.get("learning_id"))
        return ok, detail

    if tool_name == "developer_propose":
        proposal = outputs.get("proposal")
        ok = (
            isinstance(proposal, dict)
            and proposal.get("status") == "proposal"
            and proposal.get("write_performed") is False
            and proposal.get("requires_human_approval") is True
        )
        detail["change_count"] = len(proposal.get("changes") or []) if isinstance(proposal, dict) else 0
        return ok, detail

    if tool_name == "code_review":
        review = outputs.get("review")
        ok = (
            isinstance(review, dict)
            and str(review.get("verdict") or "").lower() in {
                "approve", "approved", "request_changes"
            }
        )
        return ok, detail

    if tool_name == "controlled_autonomy_start":
        autonomy = outputs.get("autonomy")
        if not isinstance(autonomy, dict):
            return False, {"reason": "autonomy_missing"}
        awaits_approval = outputs.get("awaits_human_approval") is True
        external_write = outputs.get("external_write_performed") is True
        status = str(autonomy.get("status") or "")
        if (
            status == "awaiting_approval"
            and awaits_approval
            and not external_write
        ):
            detail["autonomy_id"] = autonomy.get("id")
            detail["verification_mode"] = "awaiting_human_approval"
            return True, detail

        safe_fail_closed_reasons = {
            "proposal_path_outside_requested_scope",
            "proposal_safety_contract_failed",
            "protected_path",
            "credential_like_path",
            "sandbox_tests_failed",
            "review_not_approved",
            "proposal_base_source_validation_failed",
        }
        reason = str(autonomy.get("failure_reason") or "")
        if (
            status == "failed"
            and reason in safe_fail_closed_reasons
            and not awaits_approval
            and not external_write
        ):
            detail["autonomy_id"] = autonomy.get("id")
            detail["verification_mode"] = "fail_closed"
            detail["failure_reason"] = reason
            return True, detail

        return False, {
            "reason": "autonomy_safety_contract_failed",
            "status": status,
            "failure_reason": reason,
            "awaits_human_approval": awaits_approval,
            "external_write_performed": external_write,
        }

    return False, {"reason": "no_semantic_contract"}

