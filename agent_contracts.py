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
    """Validate the semantic envelope produced by an agent task."""
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

    ok = True
    if agent_name == "researcher":
        result = outputs.get("result")
        if not isinstance(result, dict):
            ok = False
            detail["result"] = "missing"
        elif tool_name == "web_search":
            ok = isinstance(result.get("results"), list) and isinstance(result.get("query"), str)
            detail["result_count"] = int(result.get("result_count") or 0)
            detail["has_reference"] = any(
                isinstance(item, dict) and item.get("reference")
                for item in (result.get("results") or [])
            )
        elif tool_name == "github_repo_read":
            ok = bool(result.get("ok")) and bool(result.get("files") or result.get("root"))
        elif tool_name == "memory_search":
            ok = isinstance(result.get("results"), list)
        return ok, detail

    if agent_name == "memorizer":
        if tool_name == "memory_save":
            ok = outputs.get("stored") is True and bool(outputs.get("id"))
        else:
            ok = isinstance(outputs.get("results"), list) or "found" in outputs
        return ok, detail

    if agent_name == "graph_builder":
        if tool_name in {"graph_create_node", "graph_create_edge"}:
            ok = bool(outputs.get("id"))
        else:
            ok = isinstance(outputs.get("edges"), list)
        return ok, detail

    if agent_name == "learner":
        ok = bool(outputs.get("id"))
        return ok, detail

    if agent_name == "internal":
        if tool_name == "self_model_read":
            model = outputs.get("self_model")
            ok = isinstance(model, dict) and all(
                key in model for key in ("identity", "capabilities", "tools", "models")
            )
        else:
            ok = bool(outputs.get("cycle_id")) and int(outputs.get("events_count") or 0) == 9
        return ok, detail

    if agent_name == "developer":
        proposal = outputs.get("proposal")
        ok = (
            isinstance(proposal, dict)
            and proposal.get("status") == "proposal"
            and proposal.get("write_performed") is False
            and proposal.get("requires_human_approval") is True
        )
        return ok, detail

    if agent_name == "tester":
        tests = outputs.get("tests")
        ok = (
            str(outputs.get("status") or "").lower() in {"passed", "success"}
            and isinstance(tests, list)
        )
        return ok, detail

    if agent_name == "reviewer":
        review = outputs.get("review")
        ok = (
            isinstance(review, dict)
            and str(review.get("verdict") or "").lower() in {"approve", "approved", "request_changes"}
        )
        return ok, detail

    if agent_name == "autonomy_orchestrator":
        autonomy = outputs.get("autonomy")
        ok = (
            isinstance(autonomy, dict)
            and autonomy.get("status") == "awaiting_approval"
            and outputs.get("awaits_human_approval") is True
            and outputs.get("external_write_performed") is False
        )
        return ok, detail

    return False, {"reason": "no_semantic_contract"}
