"""F14 Controlled Autonomy orchestration.

The default pipeline is autonomous only up to a hard human-approval gate:
observe -> plan -> delegate -> propose -> sandbox -> test -> evaluate ->
awaiting_approval. External mutation occurs only after explicit approval.
"""
from __future__ import annotations

import hashlib
from typing import Any

from github_readonly import inspect_repository
from specialized_agent_tools import (
    SpecializedAgentError,
    propose_code_change,
    review_code_change,
    run_python_tests_in_workspace,
)
from persistence.autonomy import (
    AutonomyContractError,
    AutonomyService,
    validate_proposal,
)
from github_controlled import ControlledGitHubError, branch_head, controlled_apply, sandbox_changes
from persistence.core import ValidationError


class ControlledAutonomyError(RuntimeError):
    """F14 orchestration failure."""


def _autonomy(service, actor: str, owner_scope: str) -> AutonomyService:
    return AutonomyService(service)


def _advance(a: AutonomyService, run_id: str, status: str, actor: str, owner_scope: str, changes=None):
    try:
        return a.advance(run_id, status, actor, owner_scope, changes)
    except Exception as exc:
        raise ControlledAutonomyError(f"transition_failed:{type(exc).__name__}") from exc


def start_controlled_autonomy(service, request: dict[str, Any], actor: str, owner_scope: str) -> dict[str, Any]:
    a = _autonomy(service, actor, owner_scope)
    created = a.create_run(request, actor=actor, owner_scope=owner_scope)
    run = created["record"]
    run_id = run["id"]

    try:
        base_sha = branch_head(run["repository"], run["base_branch"])
        _advance(
            a, run_id, "planning", actor, owner_scope,
            {
                "base_commit_sha": base_sha,
                "plan": {
                    "mode": "controlled_autonomy_v1",
                    "steps": [
                        "observe_repository",
                        "plan_bounded_change",
                        "delegate_developer",
                        "sandbox_exact_patch",
                        "test_in_isolated_workspace",
                        "review_change",
                        "await_human_approval",
                        "create_isolated_branch_and_draft_pr",
                        "verify_external_result",
                        "learn_outcome",
                    ],
                    "safety": {
                        "main_write": False,
                        "merge": False,
                        "force_push": False,
                        "protected_paths_blocked": True,
                        "human_approval_required": True,
                    },
                },
            },
        )

        _advance(a, run_id, "delegating", actor, owner_scope)

        proposal = propose_code_change(
            inspect_repository,
            run["repository"],
            run["paths"],
            run["instruction"],
            run.get("queries") or [],
        )
        proposal = validate_proposal(proposal)
        if proposal.get("requires_human_approval") is not True or proposal.get("write_performed") is not False:
            raise ControlledAutonomyError("proposal_safety_contract_failed")
        _advance(a, run_id, "proposed", actor, owner_scope, {"proposal": proposal})

        sandbox = sandbox_changes(
            run["repository"],
            base_sha,
            proposal["changes"],
        )
        expected_hashes = {item["path"]: item["sha256"] for item in sandbox["files"]}
        _advance(
            a, run_id, "sandboxed", actor, owner_scope,
            {"sandbox": {**sandbox, "expected_hashes": expected_hashes}},
        )

        compile_paths = [item["path"] for item in proposal["changes"] if item["path"].endswith(".py")]
        proposal_tests = [str(x).strip() for x in (proposal.get("tests") or []) if str(x).strip()]
        requested_tests = [str(x).strip() for x in (run.get("requested_tests") or []) if str(x).strip()]
        tests_to_run = requested_tests or proposal_tests or [
            "test_controlled_autonomy_contract",
            "test_route_security_contract",
            "test_authorization_contract",
        ]
        test_result = _run_sandbox_tests_from_existing_archive(
            run["repository"],
            base_sha,
            proposal["changes"],
            tests_to_run,
            compile_paths,
        )
        if test_result.get("status") != "passed":
            raise ControlledAutonomyError("sandbox_tests_failed")
        _advance(a, run_id, "tested", actor, owner_scope, {"tests": test_result})

        review = review_code_change(
            inspect_repository,
            run["repository"],
            [x["path"] for x in proposal["changes"]],
            proposal,
            test_result,
        )
        if review.get("verdict") != "approve":
            raise ControlledAutonomyError("review_not_approved")

        evaluation = {
            "tests_passed": True,
            "review_verdict": review.get("verdict"),
            "review_summary": str(review.get("summary") or "")[:2000],
            "base_sha": base_sha,
            "external_write_allowed": False,
            "requires_human_approval": True,
        }
        _advance(
            a, run_id, "evaluating", actor, owner_scope,
            {"evaluation": evaluation},
        )
        _advance(
            a, run_id, "awaiting_approval", actor, owner_scope,
            {
                "evaluation": evaluation,
                "decision": {
                    "status": "pending",
                    "reason": "human_authorization_required_before_external_write",
                },
            },
        )
    except Exception as exc:
        reason = str(exc)[:1500]
        try:
            a.record_failure(run_id, reason, actor, owner_scope)
        except Exception:
            pass
        failed = a.get_run(run_id, owner_scope=owner_scope)
        if failed is None:
            raise ControlledAutonomyError(reason) from exc
        return failed

    return a.get_run(run_id, owner_scope=owner_scope) or {}


def _run_sandbox_tests_from_existing_archive(
    repository: str,
    base_sha: str,
    changes: list[dict[str, Any]],
    tests: list[str],
    compile_paths: list[str],
) -> dict[str, Any]:
    # Reuses the same archive/patch validator but needs the workspace alive for test execution.
    # This is implemented inline to keep the archive ephemeral and never persist executable files.
    from github_controlled import _download_archive, _safe_extract, apply_unified_patch
    from pathlib import Path
    import tempfile

    with tempfile.TemporaryDirectory(prefix="akira-f14-test-") as temp:
        target = Path(temp)
        archive = _download_archive(repository, base_sha, target)
        root = _safe_extract(archive, target)
        for raw in changes:
            change = raw
            path = change["path"]
            file_path = root / path
            if change["operation"] == "modify":
                if not file_path.is_file():
                    raise ControlledAutonomyError(f"missing_sandbox_file:{path}")
                source = file_path.read_text(encoding="utf-8")
            else:
                source = ""
                if file_path.exists():
                    raise ControlledAutonomyError(f"create_target_exists:{path}")
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(
                apply_unified_patch(source, change["patch"], path, change["operation"]),
                encoding="utf-8",
            )
        return run_python_tests_in_workspace(
            str(root),
            tests=tests,
            compile_paths=compile_paths,
        )


def approve_and_apply_controlled_autonomy(
    service,
    run_id: str,
    actor: str,
    owner_scope: str,
) -> dict[str, Any]:
    a = _autonomy(service, actor, owner_scope)
    run = a.get_run(run_id, owner_scope=owner_scope)
    if run is None:
        raise ControlledAutonomyError("autonomy_run_not_found")
    if run.get("status") != "awaiting_approval":
        raise ControlledAutonomyError("autonomy_run_not_awaiting_approval")
    if not isinstance(run.get("proposal"), dict) or not run["proposal"].get("changes"):
        raise ControlledAutonomyError("proposal_missing")
    approval = a.approve(run_id, actor, owner_scope)
    proposal = run["proposal"]
    sandbox = run.get("sandbox") if isinstance(run.get("sandbox"), dict) else {}
    expected_hashes = sandbox.get("expected_hashes") if isinstance(sandbox.get("expected_hashes"), dict) else {}
    if not expected_hashes:
        raise ControlledAutonomyError("sandbox_hash_evidence_missing")

    try:
        action = controlled_apply(
            repository=run["repository"],
            base_sha=run["base_commit_sha"],
            run_id=run_id,
            changes=proposal["changes"],
            title=f"Akira F14: {proposal.get('summary') or run['goal']}",
            body=(
                "Controlled Autonomy v1\n\n"
                f"Run: {run_id}\n"
                f"Base SHA: {run['base_commit_sha']}\n"
                "Safety: branch-only, serial content writes, Draft PR, no merge.\n"
                f"Approved by: {approval['decision']['approved_by']}\n"
            ),
            expected_hashes=expected_hashes,
        )
    except Exception as exc:
        try:
            a.record_failure(run_id, str(exc)[:1500], actor, owner_scope)
        except Exception:
            pass
        raise ControlledAutonomyError(str(exc)[:1500]) from exc

    _advance(
        a, run_id, "external_applied", actor, owner_scope,
        {
            "action": action,
            "branch_name": action["branch_name"],
            "base_commit_sha": action["base_sha"],
        },
    )

    current_head = branch_head(run["repository"], action["branch_name"])
    verified = {
        "branch_head_matches": current_head == action["branch_head"],
        "draft_pr": action.get("pr_draft") is True,
        "merged": action.get("merged") is False,
        "base_branch": action.get("base_branch") == "main",
        "pr_number": action.get("pr_number"),
        "pr_url": action.get("pr_url"),
    }
    if not all(verified.values()):
        a.record_failure(run_id, "external_verification_failed", actor, owner_scope)
        raise ControlledAutonomyError("external_verification_failed")

    evaluation = dict(run.get("evaluation") or {})
    evaluation.update({
        "external_action_verified": True,
        "external_verification": verified,
        "verified_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    })
    _advance(a, run_id, "evaluated", actor, owner_scope, {"evaluation": evaluation})

    learning_reference = ""
    try:
        lesson = (
            f"F14 controlled autonomy: proposal tested and externally applied as Draft PR "
            f"{action['pr_url']} without writing main or merging."
        )
        learning = service.save_learning(
            {
                "source": "controlled_autonomy_v1",
                "event": f"autonomy_run:{run_id}",
                "lesson": lesson,
                "knowledge_nodes": [],
                "relationships": [],
                "confidence": 1.0,
                "outcome": "success",
                "status": "candidate",
                "evidence": [{
                    "type": "tool_invocation",
                    "title": "Controlled GitHub action",
                    "reference": action["pr_url"],
                    "summary": "Draft PR created from approved F14 run.",
                    "hash": hashlib.sha256(str(action).encode("utf-8")).hexdigest()[:32],
                }],
            },
            actor=actor,
            owner_scope=owner_scope,
            idempotency_key=f"f14:learning:{run_id}",
        )
        learning_reference = learning["record"]["id"]
        _advance(
            a, run_id, "learned", actor, owner_scope,
            {"learning_reference": learning_reference},
        )
    except Exception:
        # Learning is post-action enrichment; it must never falsely turn a verified
        # external action into a failed action.
        pass

    final = _advance(
        a, run_id, "completed", actor, owner_scope,
        {"evaluation": evaluation},
    )
    return final


