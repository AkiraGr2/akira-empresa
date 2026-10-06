"""F14 Controlled Autonomy v1: persistent contract and safety policy.

This module owns the autonomy state machine and validation only. External
GitHub mutation lives in github_controlled.py and orchestration lives in
autonomy_engine.py.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping


AUTONOMY_SCHEMA_VERSION = "autonomy.v1"

AUTONOMY_STATUSES = (
    "observing",
    "planning",
    "delegating",
    "proposed",
    "sandboxed",
    "tested",
    "evaluating",
    "awaiting_approval",
    "acting",
    "external_applied",
    "evaluated",
    "learned",
    "completed",
    "rejected",
    "failed",
    "cancelled",
)

AUTONOMY_STATUS_TRANSITIONS = {
    "observing": {"planning", "failed", "cancelled"},
    "planning": {"delegating", "failed", "cancelled"},
    "delegating": {"proposed", "failed", "cancelled"},
    "proposed": {"sandboxed", "failed", "cancelled"},
    "sandboxed": {"tested", "failed", "cancelled"},
    "tested": {"evaluating", "failed", "cancelled"},
    "evaluating": {"awaiting_approval", "rejected", "failed", "cancelled"},
    "awaiting_approval": {"acting", "rejected", "cancelled"},
    "acting": {"external_applied", "failed"},
    "external_applied": {"evaluated", "failed"},
    "evaluated": {"learned", "failed"},
    "learned": {"completed", "failed"},
    "completed": set(),
    "rejected": set(),
    "failed": set(),
    "cancelled": set(),
}

AUTONOMY_ALLOWED_REPOSITORIES = {"AkiraGr2/akira-empresa"}
AUTONOMY_BASE_BRANCH = "main"
AUTONOMY_MAX_FILES = 4
AUTONOMY_MAX_GOAL_CHARS = 4000
AUTONOMY_MAX_PATCH_CHARS = 24000
AUTONOMY_MAX_FILE_BYTES = 120_000
AUTONOMY_ID_PREFIX = "autonomy"

_SAFE_PATH_RE = re.compile(r"^[A-Za-z0-9_./-]+$")


class AutonomyContractError(ValueError):
    """Contrato de autonomia invalido."""


def _text(name: str, value: Any, maximum: int, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise AutonomyContractError(f"{name} debe ser texto")
    value = value.strip()
    if not value and not allow_empty:
        raise AutonomyContractError(f"{name} no puede estar vacio")
    if len(value) > maximum:
        raise AutonomyContractError(f"{name} supera {maximum} caracteres")
    return value


def validate_repository(repository: Any) -> str:
    value = _text("repository", repository, 200)
    if value not in AUTONOMY_ALLOWED_REPOSITORIES:
        raise AutonomyContractError("repository_not_allowlisted")
    return value


def validate_base_branch(branch: Any) -> str:
    value = _text("base_branch", branch, 120)
    if value != AUTONOMY_BASE_BRANCH:
        raise AutonomyContractError("base_branch_not_allowed")
    return value


def validate_path(path: Any) -> str:
    value = _text("path", path, 240).strip("/")
    if not value:
        raise AutonomyContractError("path_empty")
    if not _SAFE_PATH_RE.fullmatch(value):
        raise AutonomyContractError("unsafe_path")
    if ".." in value.split("/"):
        raise AutonomyContractError("parent_path_not_allowed")
    if value.startswith(".git/") or value == ".git":
        raise AutonomyContractError("git_directory_not_allowed")
    low = value.lower()
    protected_prefixes = (
        ".github/workflows/",
        ".github/actions/",
    )
    protected_exact = {
        ".env", ".env.local", ".env.production", ".env.development",
        "render.yaml", "render.yml",
        "docker-compose.yml", "docker-compose.yaml",
    }
    if low in protected_exact or any(low.startswith(prefix) for prefix in protected_prefixes):
        raise AutonomyContractError("protected_path")
    if low.endswith((".pem", ".key", ".p12", ".pfx", ".crt")):
        raise AutonomyContractError("credential_like_path")
    return value


def validate_request(data: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(data, Mapping):
        raise AutonomyContractError("request_debe_ser_objeto")
    allowed = {"goal", "repository", "base_branch", "paths", "instruction", "queries", "tests", "idempotency_key"}
    extra = sorted(set(data) - allowed)
    if extra:
        raise AutonomyContractError(f"campos_no_permitidos:{extra}")

    goal = _text("goal", data.get("goal"), AUTONOMY_MAX_GOAL_CHARS)
    repository = validate_repository(data.get("repository", "AkiraGr2/akira-empresa"))
    base_branch = validate_base_branch(data.get("base_branch", "main"))

    raw_paths = data.get("paths") or []
    if not isinstance(raw_paths, list):
        raise AutonomyContractError("paths_debe_ser_lista")
    if not 1 <= len(raw_paths) <= AUTONOMY_MAX_FILES:
        raise AutonomyContractError(f"paths_debe_tener_1_{AUTONOMY_MAX_FILES}_elementos")
    paths = list(dict.fromkeys(validate_path(x) for x in raw_paths))
    if len(paths) > AUTONOMY_MAX_FILES:
        raise AutonomyContractError("too_many_paths")

    instruction = _text("instruction", data.get("instruction", goal), AUTONOMY_MAX_GOAL_CHARS)
    queries = data.get("queries") or []
    if not isinstance(queries, list):
        raise AutonomyContractError("queries_debe_ser_lista")
    queries = [_text("query", q, 120) for q in queries[:12] if str(q or "").strip()]

    tests = data.get("tests") or []
    if not isinstance(tests, list):
        raise AutonomyContractError("tests_debe_ser_lista")
    tests = [_text("test", t, 200) for t in tests[:6] if str(t or "").strip()]

    return {
        "goal": goal,
        "repository": repository,
        "base_branch": base_branch,
        "paths": paths,
        "instruction": instruction,
        "queries": queries,
        "tests": list(dict.fromkeys(tests)),
    }


def validate_change(change: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(change, Mapping):
        raise AutonomyContractError("change_debe_ser_objeto")
    allowed = {"path", "operation", "reason", "patch"}
    extra = sorted(set(change) - allowed)
    if extra:
        raise AutonomyContractError(f"change_campos_no_permitidos:{extra}")
    operation = _text("operation", change.get("operation"), 16)
    if operation not in {"modify", "create"}:
        raise AutonomyContractError("solo_modify_create")
    path = validate_path(change.get("path"))
    patch = _text("patch", change.get("patch"), AUTONOMY_MAX_PATCH_CHARS)
    if "--- " not in patch or "+++ " not in patch or "@@" not in patch:
        raise AutonomyContractError("patch_unified_required")
    reason = _text("reason", change.get("reason", ""), 1000)
    hunk_headers = [line for line in patch.splitlines() if line.startswith("@@")]
    hunk_pattern = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@")
    if not hunk_headers or any(not hunk_pattern.fullmatch(line) for line in hunk_headers):
        raise AutonomyContractError("patch_hunk_header_invalid")
    return {"path": path, "operation": operation, "reason": reason, "patch": patch}


def validate_proposal(proposal: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(proposal, Mapping):
        raise AutonomyContractError("proposal_debe_ser_objeto")
    if proposal.get("status") != "proposal":
        raise AutonomyContractError("proposal_status_invalid")
    changes = proposal.get("changes")
    if not isinstance(changes, list) or not 1 <= len(changes) <= AUTONOMY_MAX_FILES:
        raise AutonomyContractError("proposal_changes_invalid")
    clean = [validate_change(item) for item in changes]
    paths = [x["path"] for x in clean]
    if len(set(paths)) != len(paths):
        raise AutonomyContractError("duplicate_change_path")
    return {
        "status": "proposal",
        "summary": _text("summary", proposal.get("summary", "Controlled autonomy change"), 2000),
        "changes": clean,
        "tests": proposal.get("tests") if isinstance(proposal.get("tests"), list) else [],
        "risks": proposal.get("risks") if isinstance(proposal.get("risks"), list) else [],
        "requires_human_approval": True,
        "write_performed": False,
    }


def new_run_id() -> str:
    return f"{AUTONOMY_ID_PREFIX}_{uuid.uuid4().hex}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_transition(current: str, new: str) -> None:
    if current not in AUTONOMY_STATUS_TRANSITIONS:
        raise AutonomyContractError(f"estado_actual_desconocido:{current}")
    if new not in AUTONOMY_STATUS_TRANSITIONS[current]:
        raise AutonomyContractError(f"transicion_invalida:{current}->{new}")


class AutonomyService:
    """Persistence adapter for the F14 autonomy lifecycle."""

    CONTROL_FIELDS = {
        "status", "decision", "started_at", "completed_at",
        "base_commit_sha", "branch_name", "action", "learning_reference",
    }

    def __init__(self, persistence_service):
        self.service = persistence_service
        self.repo = persistence_service.repo

    def create_run(self, data: Mapping[str, Any], actor: str, owner_scope: str) -> dict:
        payload = validate_request(data)
        owner = _text("owner_scope", owner_scope, 256)
        actor = _text("actor", actor, 256)
        record = {
            "id": new_run_id(),
            "goal": payload["goal"],
            "repository": payload["repository"],
            "base_branch": payload["base_branch"],
            "base_commit_sha": "",
            "branch_name": "",
            "paths": payload["paths"],
            "instruction": payload["instruction"],
            "queries": payload["queries"],
            "requested_tests": payload["tests"],
            "plan": {},
            "proposal": {},
            "sandbox": {},
            "tests": {},
            "evaluation": {},
            "decision": {},
            "action": {},
            "learning_reference": "",
            "failure_reason": "",
            "status": "observing",
            "owner_scope": owner,
            "created_by": actor,
            "schema_version": AUTONOMY_SCHEMA_VERSION,
            "version": 1,
        }
        idem = str(data.get("idempotency_key") or "").strip()
        if idem:
            if len(idem) > 200:
                raise AutonomyContractError("idempotency_key_too_long")
            record["idempotency_key"] = idem
        with self.repo.transaction() as tx:
            stored, created = tx.create("autonomy_runs", record)
            tx.append_audit({
                "actor": actor,
                "action": "autonomy.create" if created else "autonomy.create.already_synced",
                "resource": "autonomy_runs",
                "resource_id": stored["id"],
                "status": "success",
                "detail": {"repository": stored["repository"], "created": bool(created)},
            })
        verified = self.get_run(stored["id"], owner_scope=owner)
        if verified is None:
            raise RuntimeError("autonomy_create_not_confirmed")
        return {"outcome": "created" if created else "already_synced", "record": verified}

    def get_run(self, run_id: str, owner_scope: str | None = None) -> dict | None:
        row = self.repo.get("autonomy_runs", run_id)
        if row is None:
            return None
        if owner_scope is not None and row.get("owner_scope") != owner_scope:
            return None
        return row

    def list_runs(self, owner_scope: str, status: str | None = None, limit: int = 50) -> list[dict]:
        filters = {"owner_scope": _text("owner_scope", owner_scope, 256)}
        if status:
            if status not in AUTONOMY_STATUSES:
                raise AutonomyContractError("status_invalid")
            filters["status"] = status
        return self.repo.search(
            "autonomy_runs", filters,
            limit=max(1, min(int(limit), 100)),
            offset=0,
            order_by="created_at",
            descending=True,
        )

    def _update(self, run_id: str, changes: Mapping[str, Any], actor: str, owner_scope: str) -> dict:
        current = self.get_run(run_id, owner_scope=owner_scope)
        if current is None:
            raise KeyError(run_id)
        clean = dict(changes)
        if set(clean) & self.CONTROL_FIELDS:
            raise AutonomyContractError("control_fields_only_via_lifecycle")
        if "owner_scope" in clean or "id" in clean:
            raise AutonomyContractError("immutable_identity_fields")
        with self.repo.transaction() as tx:
            updated = tx.update("autonomy_runs", run_id, clean, current["version"])
            tx.append_audit({
                "actor": actor, "action": "autonomy.update",
                "resource": "autonomy_runs", "resource_id": run_id, "status": "success",
                "detail": {"fields": sorted(clean), "new_version": updated["version"]},
            })
        verified = self.get_run(run_id, owner_scope=owner_scope)
        if verified is None or verified.get("version") != current["version"] + 1:
            raise RuntimeError("autonomy_update_not_confirmed")
        return verified

    def advance(self, run_id: str, new_status: str, actor: str, owner_scope: str, changes: Mapping[str, Any] | None = None) -> dict:
        current = self.get_run(run_id, owner_scope=owner_scope)
        if current is None:
            raise KeyError(run_id)
        validate_transition(current.get("status"), new_status)
        clean = dict(changes or {})
        clean["status"] = new_status
        if new_status == "learned":
            learning_reference = str(clean.get("learning_reference") or current.get("learning_reference") or "").strip()
            if not learning_reference:
                raise AutonomyContractError("learned_requires_learning_reference")
        if new_status == "completed":
            learning_reference = str(clean.get("learning_reference") or current.get("learning_reference") or "").strip()
            if current.get("status") != "learned":
                raise AutonomyContractError("completed_requires_learned")
            if not learning_reference:
                raise AutonomyContractError("completed_requires_learning_reference")
        if new_status != "observing" and not current.get("started_at"):
            clean["started_at"] = now_iso()
        if new_status in {"completed", "rejected", "failed", "cancelled"}:
            clean["completed_at"] = now_iso()
        if new_status == "awaiting_approval" and not clean.get("decision"):
            clean["decision"] = {}
        with self.repo.transaction() as tx:
            updated = tx.update("autonomy_runs", run_id, clean, current["version"])
            tx.append_audit({
                "actor": actor,
                "action": "autonomy.status",
                "resource": "autonomy_runs",
                "resource_id": run_id,
                "status": "success",
                "detail": {"from": current.get("status"), "to": new_status, "new_version": updated["version"]},
            })
        verified = self.get_run(run_id, owner_scope=owner_scope)
        if verified is None or verified.get("status") != new_status:
            raise RuntimeError("autonomy_transition_not_confirmed")
        return verified

    def approve(self, run_id: str, actor: str, owner_scope: str) -> dict:
        current = self.get_run(run_id, owner_scope=owner_scope)
        if current is None:
            raise KeyError(run_id)
        if current.get("status") != "awaiting_approval":
            raise AutonomyContractError("approval_requires_awaiting_approval")
        decision = {
            "status": "approved",
            "approved_by": _text("approved_by", actor, 256),
            "approved_at": now_iso(),
            "mode": "human",
        }
        with self.repo.transaction() as tx:
            updated = tx.update(
                "autonomy_runs", run_id,
                {"decision": decision, "status": "acting", "started_at": current.get("started_at") or now_iso()},
                current["version"],
            )
            tx.append_audit({
                "actor": actor,
                "action": "autonomy.approval",
                "resource": "autonomy_runs",
                "resource_id": run_id,
                "status": "success",
                "detail": {"approved_by": actor},
            })
        verified = self.get_run(run_id, owner_scope=owner_scope)
        if verified is None or verified.get("status") != "acting":
            raise RuntimeError("autonomy_approval_not_confirmed")
        return verified

    def reject(self, run_id: str, actor: str, owner_scope: str, reason: str = "rejected_by_owner") -> dict:
        current = self.get_run(run_id, owner_scope=owner_scope)
        if current is None:
            raise KeyError(run_id)
        if current.get("status") != "awaiting_approval":
            raise AutonomyContractError("rejection_requires_awaiting_approval")
        decision = {
            "status": "rejected",
            "rejected_by": _text("rejected_by", actor, 256),
            "rejected_at": now_iso(),
            "mode": "human",
            "reason": _text("reason", reason, 1000),
        }
        with self.repo.transaction() as tx:
            updated = tx.update(
                "autonomy_runs", run_id,
                {"decision": decision, "status": "rejected", "completed_at": now_iso()},
                current["version"],
            )
            tx.append_audit({
                "actor": actor,
                "action": "autonomy.rejection",
                "resource": "autonomy_runs",
                "resource_id": run_id,
                "status": "success",
                "detail": {"rejected_by": actor, "reason": decision["reason"]},
            })
        verified = self.get_run(run_id, owner_scope=owner_scope)
        if verified is None or verified.get("status") != "rejected":
            raise RuntimeError("autonomy_rejection_not_confirmed")
        return verified

    def record_failure(self, run_id: str, reason: str, actor: str, owner_scope: str) -> dict:
        current = self.get_run(run_id, owner_scope=owner_scope)
        if current is None:
            raise KeyError(run_id)
        reason = _text("failure_reason", reason, 1500)
        if current.get("status") in {"completed", "rejected", "failed", "cancelled"}:
            return current
        return self.advance(
            run_id, "failed", actor, owner_scope,
            {"failure_reason": reason},
        )

    def cancel(self, run_id: str, actor: str, owner_scope: str, reason: str = "cancelled_by_owner") -> dict:
        current = self.get_run(run_id, owner_scope=owner_scope)
        if current is None:
            raise KeyError(run_id)
        if current.get("status") in {"completed", "rejected", "failed", "cancelled"}:
            return current
        return self.advance(
            run_id, "cancelled", actor, owner_scope,
            {"failure_reason": _text("reason", reason, 1000)},
        )
