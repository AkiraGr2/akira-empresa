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
    f14_zero_cost_autonomy_scope,
    f14_zero_cost_provider_preflight,
    propose_code_change,
    review_code_change,
    run_python_tests_in_workspace,
)
from persistence.autonomy import (
    AutonomyContractError,
    AutonomyService,
    validate_proposal,
)
from github_controlled import (
    ControlledGitHubError,
    branch_head,
    canonicalize_modify_patch,
    controlled_apply,
    fetch_text_file,
    sandbox_changes,
    verify_existing_draft_action,
)
from persistence.build_identity import runtime_build_ref
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


def _canonicalize_proposal_against_base(
    proposal: dict[str, Any],
    repository: str,
    base_sha: str,
) -> dict[str, Any]:
    """Bind proposal patches to the exact base source before persistence."""
    canonical_changes = []
    for change in proposal.get("changes") or []:
        item = dict(change)
        if item.get("operation") == "modify":
            path = str(item.get("path") or "").strip()
            if not path:
                raise ControlledAutonomyError("proposal_path_required")
            try:
                source_record = fetch_text_file(repository, path, base_sha)
                item["patch"] = canonicalize_modify_patch(
                    path,
                    source_record["content"],
                    item.get("patch"),
                )
            except ControlledGitHubError as exc:
                raise ControlledAutonomyError(
                    f"proposal_base_source_validation_failed:{path}:{str(exc)[:180]}"
                ) from exc
        canonical_changes.append(item)
    return {**proposal, "changes": canonical_changes}


def start_controlled_autonomy(service, request: dict[str, Any], actor: str, owner_scope: str) -> dict[str, Any]:
    provider_gate = f14_zero_cost_provider_preflight()
    if not provider_gate["ok"]:
        raise ControlledAutonomyError(f"f14_zero_cost_provider_blocked:{provider_gate['reason']}")

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

        with f14_zero_cost_autonomy_scope():
            proposal = propose_code_change(
                inspect_repository,
                run["repository"],
                run["paths"],
                run["instruction"],
                run.get("queries") or [],
            )
        proposal = validate_proposal(proposal)
        proposal = _canonicalize_proposal_against_base(
            proposal,
            run["repository"],
            base_sha,
        )
        requested_paths = set(run.get("paths") or [])
        proposed_paths = {item["path"] for item in proposal.get("changes") or []}
        if not proposed_paths.issubset(requested_paths):
            raise ControlledAutonomyError("proposal_path_outside_requested_scope")
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

        with f14_zero_cost_autonomy_scope():
            review = review_code_change(
                inspect_repository,
                run["repository"],
                [x["path"] for x in proposal["changes"]],
                proposal,
                test_result,
            )

        # Preserve bounded reviewer diagnostics before fail-closed rejection so the
        # owner can distinguish an explicit review rejection from a generic HTTP 422.
        raw_findings = review.get("findings") if isinstance(review.get("findings"), list) else []
        review_findings = []
        for finding in raw_findings[:20]:
            if not isinstance(finding, dict):
                continue
            review_findings.append({
                "severity": str(finding.get("severity") or "unknown")[:32],
                "path": str(finding.get("path") or "")[:240],
                "message": str(finding.get("message") or "")[:800],
            })
        raw_required_tests = review.get("required_tests") if isinstance(review.get("required_tests"), list) else []
        review_required_tests = [str(item).strip()[:300] for item in raw_required_tests[:20] if str(item).strip()]
        review_verdict = str(review.get("verdict") or "missing_verdict")[:80]
        evaluation = {
            "tests_passed": True,
            "review_verdict": review_verdict,
            "review_summary": str(review.get("summary") or "")[:2000],
            "review_findings": review_findings,
            "review_required_tests": review_required_tests,
            "review_write_performed": review.get("write_performed") is True,
            "base_sha": base_sha,
            "external_write_allowed": False,
            "requires_human_approval": True,
        }
        _advance(
            a, run_id, "evaluating", actor, owner_scope,
            {"evaluation": evaluation},
        )
        if review_verdict != "approve":
            raise ControlledAutonomyError(f"review_not_approved:{review_verdict}")
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


def _record_controlled_autonomy_verification(service, run, action):
    """Persist formal F14 capability evidence after a successful production action."""
    rows = service.list_capabilities({"name": "controlled_autonomy_v1"}, limit=5)
    capability = rows[0] if rows else None
    if capability is None:
        raise ControlledAutonomyError("f14_capability_not_registered")
    decision = run.get("decision") if isinstance(run.get("decision"), dict) else {}
    run_id = str(run.get("id") or "").strip()
    pr_url = str(action.get("pr_url") or "").strip()
    evidence = [
        {"type": "e2e_test", "title": "Controlled Autonomy v1 production run", "reference": run_id,
         "summary": "Ejecución real de F14 completó propuesta, sandbox, pruebas y revisión.",
         "hash": hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:32]},
        {"type": "human_validation", "title": "Aprobación explícita del propietario",
         "reference": str(decision.get("approved_by") or run.get("created_by") or "owner"),
         "summary": "La compuerta humana fue aprobada antes de la acción externa.",
         "hash": hashlib.sha256(f"{decision.get('approved_by','')}:{decision.get('approved_at','')}".encode("utf-8")).hexdigest()[:32]},
        {"type": "external_check", "title": "Draft PR y rama aislada verificados", "reference": pr_url or run_id,
         "summary": "La rama de autonomía coincide con la acción y el Draft PR permanece sin merge.",
         "hash": hashlib.sha256(str(action).encode("utf-8")).hexdigest()[:32]},
    ]
    return service.record_capability_verification(
        capability["id"],
        {
            "event_type": "verification",
            "test_key": "controlled_autonomy_v1_e2e",
            "test_version": "v1",
            "result": "pass",
            "evidence": evidence,
            "environment": {
                "repository": run.get("repository"), "base_branch": run.get("base_branch"),
                "base_commit_sha": run.get("base_commit_sha"), "branch_name": action.get("branch_name"),
                "draft_pr": action.get("pr_draft") is True, "merged": action.get("merged"),
            },
            "dependency_snapshot": ["AutonomyService", "github_controlled", "isolated_workspace_tests", "owner_scope", "human_approval"],
            "runtime_version": "controlled_autonomy_v1",
            "build_ref": runtime_build_ref(),
            "actor": str(run.get("created_by") or "owner"), "executor": "controlled_autonomy", "evaluator": "system",
            "observed_availability_state": "available",
        },
        actor=str(run.get("created_by") or "owner"),
        idempotency_key=f"f14:e2e:{run_id}",
    )

def _build_f14_learning_event(run: dict[str, Any], action: dict[str, Any]) -> dict[str, Any]:
    """Build a learning event that exactly matches the persistence evidence contract."""
    run_id = str(run.get("id") or "").strip()
    pr_url = str(action.get("pr_url") or "").strip()
    action_hash = hashlib.sha256(str(action).encode("utf-8")).hexdigest()[:32]
    return {
        "source": "controlled_autonomy_v1",
        "event": f"autonomy_run:{run_id}",
        "lesson": (
            f"F14 controlled autonomy: proposal tested and externally applied as Draft PR "
            f"{pr_url} without writing main or merging."
        ),
        "knowledge_nodes": [],
        "relationships": [],
        "confidence": 1.0,
        "outcome": "success",
        "status": "candidate",
        "evidence": [{
            "type": "tool_invocation",
            "title": "Controlled GitHub action",
            "reference": pr_url or run_id,
            "note": (
                "Draft PR created from approved F14 run; "
                f"action_hash={action_hash}"
            ),
        }],
    }


def apply_approved_controlled_autonomy(
    service,
    run_id: str,
    actor: str,
    owner_scope: str,
) -> dict[str, Any]:
    a = _autonomy(service, actor, owner_scope)
    run = a.get_run(run_id, owner_scope=owner_scope)
    if run is None:
        raise ControlledAutonomyError("autonomy_run_not_found")

    failure_reason = str(run.get("failure_reason") or "")
    stored_evaluation = dict(run.get("evaluation") or {})
    is_recovery = (
        run.get("status") == "failed"
        and failure_reason.startswith("capability_verification_failed:")
        and isinstance(run.get("action"), dict)
        and bool(run["action"].get("pr_url"))
        and bool(str(run.get("learning_reference") or "").strip())
        and stored_evaluation.get("external_action_verified") is True
    )
    if run.get("status") != "acting" and not is_recovery:
        raise ControlledAutonomyError("autonomy_run_requires_explicit_approval")
    decision = run.get("decision") if isinstance(run.get("decision"), dict) else {}
    if decision.get("status") != "approved" or decision.get("mode") != "human":
        raise ControlledAutonomyError("human_approval_evidence_missing")
    if not isinstance(run.get("proposal"), dict) or not run["proposal"].get("changes"):
        raise ControlledAutonomyError("proposal_missing")
    sandbox = run.get("sandbox") if isinstance(run.get("sandbox"), dict) else {}
    expected_hashes = sandbox.get("expected_hashes") if isinstance(sandbox.get("expected_hashes"), dict) else {}
    if not expected_hashes:
        raise ControlledAutonomyError("sandbox_hash_evidence_missing")

    if is_recovery:
        # The approved external write already happened. Verify it again, but never create
        # another branch/commit/PR while reconciling only the final capability evidence.
        action = run["action"]
        try:
            verified = verify_existing_draft_action(run["repository"], action)
        except Exception as exc:
            raise ControlledAutonomyError(
                f"f14_recovery_external_verification_failed:{type(exc).__name__}"
            ) from exc
        evaluation = dict(run.get("evaluation") or {})
        evaluation.update({
            "external_action_verified": True,
            "external_verification": verified,
            "recovery_verified_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        })
    else:
        approval = run
        try:
            action = controlled_apply(
                repository=run["repository"],
                base_sha=run["base_commit_sha"],
                run_id=run_id,
                changes=run["proposal"]["changes"],
                title=f"Akira F14: {run['proposal'].get('summary') or run['goal']}",
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

        try:
            learning = service.save_learning(
                _build_f14_learning_event(run, action),
                actor=actor,
                owner_scope=owner_scope,
                idempotency_key=f"f14:learning:{run_id}",
            )
            learning_reference = str(learning["record"]["id"]).strip()
            if not learning_reference:
                raise ControlledAutonomyError("learning_reference_missing")
            _advance(
                a, run_id, "learned", actor, owner_scope,
                {"learning_reference": learning_reference},
            )
        except Exception as exc:
            try:
                a.record_failure(
                    run_id,
                    f"learning_persistence_failed:{type(exc).__name__}",
                    actor,
                    owner_scope,
                )
            except Exception:
                pass
            raise ControlledAutonomyError("learning_persistence_failed") from exc

    try:
        capability_verification = _record_controlled_autonomy_verification(service, run, action)
        effective_state = capability_verification.get("effective_state")
        if effective_state != "verified":
            raise ControlledAutonomyError("f14_capability_verification_not_current")
        evaluation["capability_verification_id"] = capability_verification["record"]["id"]
        evaluation["capability_effective_state"] = effective_state
    except Exception as exc:
        if not is_recovery:
            try:
                a.record_failure(
                    run_id,
                    f"capability_verification_failed:{type(exc).__name__}",
                    actor,
                    owner_scope,
                )
            except Exception:
                pass
        raise ControlledAutonomyError("capability_verification_failed") from exc

    if is_recovery:
        try:
            return a.recover_capability_verification_failure(
                run_id, actor, owner_scope, evaluation
            )
        except Exception as exc:
            raise ControlledAutonomyError(
                f"capability_verification_recovery_failed:{type(exc).__name__}"
            ) from exc

    final = _advance(
        a, run_id, "completed", actor, owner_scope,
        {"evaluation": evaluation},
    )
    return final

