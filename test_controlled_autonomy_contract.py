import hashlib
import specialized_agent_tools
import tempfile
import unittest
from pathlib import Path

from persistence.capability import validate_capability_verification
from persistence.autonomy import (
    AutonomyContractError,
    AutonomyService,
    AUTONOMY_STATUS_TRANSITIONS,
    validate_change,
    validate_path,
    validate_proposal,
    validate_request,
    validate_transition,
)
import github_controlled
from github_controlled import ControlledGitHubError, apply_unified_patch, sandbox_changes
from specialized_agent_tools import run_python_tests_in_workspace, propose_code_change
from autonomy_engine import (
    _canonicalize_proposal_against_base,
    _enforce_f14_production_verification_contract,
    _prepare_controlled_proposal,
    ControlledAutonomyError,
    _build_f14_learning_event,
    _record_controlled_autonomy_verification,
    apply_approved_controlled_autonomy,
    start_controlled_autonomy,
)
from unittest.mock import Mock, patch
from github_readonly import GitHubReadUpstreamError


class FakeTx:
    def __init__(self, repo):
        self.repo = repo
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def create(self, entity, record):
        key = record.get("idempotency_key")
        scope = record.get("owner_scope")
        if key is not None:
            for row in self.repo.rows.get(entity, []):
                if row.get("idempotency_key") == key and row.get("owner_scope") == scope:
                    return dict(row), False
        self.repo.rows.setdefault(entity, []).append(dict(record))
        return dict(record), True
    def update(self, entity, record_id, changes, expected_version=None):
        for row in self.repo.rows.get(entity, []):
            if row.get("id") == record_id:
                if expected_version is not None and row.get("version") != expected_version:
                    raise RuntimeError("version_conflict")
                row.update(dict(changes))
                row["version"] = int(row.get("version", 1)) + 1
                return dict(row)
        raise KeyError(record_id)
    def append_audit(self, payload):
        self.repo.audit.append(dict(payload))


class FakeRepo:
    def __init__(self):
        self.rows = {"autonomy_runs": []}
        self.audit = []
    def get(self, entity, record_id):
        for row in self.rows.get(entity, []):
            if row.get("id") == record_id:
                return dict(row)
        return None
    def search(self, entity, filters=None, limit=50, offset=0, order_by="created_at", descending=True):
        rows = [dict(r) for r in self.rows.get(entity, [])]
        for k, v in (filters or {}).items():
            rows = [r for r in rows if r.get(k) == v]
        return rows[offset:offset + limit]
    def transaction(self):
        return FakeTx(self)


class FakePersistence:
    def __init__(self):
        self.repo = FakeRepo()


class ControlledAutonomyContractTests(unittest.TestCase):
    def test_request_is_bounded_and_idempotency_is_allowed(self):
        request = validate_request({
            "goal": "Mejorar una funcion.",
            "repository": "AkiraGr2/akira-empresa",
            "base_branch": "main",
            "paths": ["persistence/core.py"],
            "instruction": "Haz un cambio pequeño y verificable.",
            "queries": ["autonomy"],
            "tests": ["test_controlled_autonomy_contract"],
            "idempotency_key": "f14-test-1",
        })
        self.assertEqual(request["base_branch"], "main")
        self.assertEqual(request["paths"], ["persistence/core.py"])

    def test_idempotent_retry_does_not_restart_or_fail_in_progress_run(self):
        service = FakePersistence()
        request = {
            "goal": "Retry an existing bounded F14 run.",
            "repository": "AkiraGr2/akira-empresa",
            "base_branch": "main",
            "paths": ["docs/F14_PRODUCTION_VERIFICATION.md"],
            "instruction": "Create the bounded verification note.",
            "tests": ["test_controlled_autonomy_contract"],
            "idempotency_key": "f14-idempotent-in-progress",
        }
        lifecycle = AutonomyService(service)
        created = lifecycle.create_run(request, actor="owner@example.com", owner_scope="scope:F14")
        run_id = created["record"]["id"]
        lifecycle.advance(run_id, "planning", "owner@example.com", "scope:F14", {"base_commit_sha": "a" * 40})
        lifecycle.advance(run_id, "delegating", "owner@example.com", "scope:F14")
        lifecycle.advance(run_id, "proposed", "owner@example.com", "scope:F14", {
            "proposal": {"status": "proposal", "summary": "test", "changes": [{"path": "docs/F14_PRODUCTION_VERIFICATION.md"}]}
        })
        lifecycle.advance(run_id, "sandboxed", "owner@example.com", "scope:F14", {
            "sandbox": {"expected_hashes": {"docs/F14_PRODUCTION_VERIFICATION.md": "b" * 64}}
        })

        with patch("autonomy_engine.f14_zero_cost_provider_preflight", return_value={"ok": True}), patch("autonomy_engine.branch_head") as branch_head:
            replayed = start_controlled_autonomy(
                service,
                request,
                actor="owner@example.com",
                owner_scope="scope:F14",
            )

        branch_head.assert_not_called()
        self.assertEqual(replayed["id"], run_id)
        self.assertEqual(replayed["status"], "sandboxed")
        self.assertEqual(len(service.repo.rows["autonomy_runs"]), 1)
        self.assertNotEqual(replayed["status"], "failed")

    def test_protected_paths_and_repository_are_rejected(self):
        with self.assertRaises(AutonomyContractError):
            validate_path(".github/workflows/ci.yml")
        with self.assertRaises(AutonomyContractError):
            validate_path(".env")
        with self.assertRaises(AutonomyContractError):
            validate_request({
                "goal": "x", "repository": "evil/repo", "base_branch": "main",
                "paths": ["README.md"], "instruction": "x"
            })

    def test_transition_graph_is_fail_closed(self):
        self.assertIn("planning", AUTONOMY_STATUS_TRANSITIONS["observing"])
        with self.assertRaises(AutonomyContractError):
            validate_transition("observing", "acting")
        with self.assertRaises(AutonomyContractError):
            validate_transition("evaluated", "completed")
        with self.assertRaises(AutonomyContractError):
            validate_transition("completed", "acting")

    def test_f14_reviewer_rejection_persists_diagnostics_and_fails_closed(self):
        service = FakePersistence()
        path = "docs/F14_PRODUCTION_VERIFICATION.md"
        patch_text = "--- /dev/null\n+++ b/docs/F14_PRODUCTION_VERIFICATION.md\n@@ -0,0 +1,3 @@\n+# Production Verification\n+\n+Human approval was required.\n"
        proposal = {
            "status": "proposal",
            "summary": "Create only the bounded verification note.",
            "changes": [{
                "path": path,
                "operation": "create",
                "reason": "production verification evidence",
                "patch": patch_text,
            }],
            "requires_human_approval": True,
            "write_performed": False,
        }
        review = {
            "verdict": "request_changes",
            "summary": "The proposal needs a clearer validation note.",
            "findings": [{
                "severity": "medium",
                "path": path,
                "message": "The note does not identify the runtime build.",
            }],
            "required_tests": ["confirm the runtime identity is recorded"],
            "write_performed": False,
        }
        with __import__("contextlib").ExitStack() as stack:
            stack.enter_context(patch("autonomy_engine.f14_zero_cost_provider_preflight", return_value={"ok": True}))
            stack.enter_context(patch("autonomy_engine.branch_head", return_value="a" * 40))
            stack.enter_context(patch("autonomy_engine.propose_code_change", return_value=proposal))
            stack.enter_context(patch("autonomy_engine.validate_proposal", side_effect=lambda value: value))
            stack.enter_context(patch("autonomy_engine._canonicalize_proposal_against_base", side_effect=lambda p, _repo, _sha: p))
            stack.enter_context(patch("autonomy_engine.sandbox_changes", return_value={"files": [{"path": path, "sha256": "b" * 64}]}))
            stack.enter_context(patch("autonomy_engine._run_sandbox_tests_from_existing_archive", return_value={"status": "passed", "tests": [{"status": "passed"}]}))
            stack.enter_context(patch("autonomy_engine.review_code_change", return_value=review))
            run = start_controlled_autonomy(
                service,
                {
                    "goal": "Check review diagnostics.",
                    "repository": "AkiraGr2/akira-empresa",
                    "base_branch": "main",
                    "paths": [path],
                    "instruction": "Create only the verification note.",
                    "queries": [path],
                    "tests": ["test_controlled_autonomy_contract"],
                    "idempotency_key": "f14-review-rejection-diagnostics",
                },
                actor="owner@example.com",
                owner_scope="scope:A",
            )

        self.assertEqual(run["status"], "failed")
        self.assertEqual(run["failure_reason"], "review_not_approved:request_changes")
        self.assertEqual(run["evaluation"]["review_verdict"], "request_changes")
        self.assertIn("runtime build", run["evaluation"]["review_findings"][0]["message"])
        self.assertEqual(run["evaluation"]["review_required_tests"], ["confirm the runtime identity is recorded"])
        self.assertFalse(run["evaluation"]["review_write_performed"])
        self.assertFalse(run["evaluation"]["external_write_allowed"])

    def test_proposal_requires_real_unified_patch(self):
        with self.assertRaises(AutonomyContractError):
            validate_proposal({
                "status": "proposal",
                "summary": "bad",
                "changes": [{
                    "path": "README.md",
                    "operation": "modify",
                    "reason": "x",
                    "patch": "cambia el texto"
                }]
            })
        with self.assertRaises(AutonomyContractError):
            validate_proposal({
                "status": "proposal",
                "summary": "delete",
                "changes": [{
                    "path": "README.md",
                    "operation": "delete",
                    "reason": "x",
                    "patch": "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-old\n+new\n"
                }]
            })

    def test_proposal_rejects_malformed_hunk_header(self):
        with self.assertRaises(AutonomyContractError):
            validate_proposal({
                "status": "proposal",
                "summary": "bad hunk",
                "changes": [{
                    "path": "README.md",
                    "operation": "modify",
                    "reason": "x",
                    "patch": "--- a/README.md\n+++ b/README.md\n@@\n-old\n+new\n",
                }],
            })

    def test_proposal_accepts_standard_unified_hunk_context(self):
        result = validate_proposal({
            "status": "proposal",
            "summary": "valid context",
            "changes": [{
                "path": "README.md",
                "operation": "modify",
                "reason": "x",
                "patch": "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@ README\n-old\n+new\n",
            }],
        })
        self.assertEqual(result["changes"][0]["path"], "README.md")

    def test_patch_engine_applies_modify_and_create(self):
        source = "uno\ndos\ntres\n"
        patch = (
            "--- a/test.txt\n"
            "+++ b/test.txt\n"
            "@@ -1,3 +1,3 @@\n"
            " uno\n"
            "-dos\n"
            "+DOS\n"
            " tres\n"
        )
        result = apply_unified_patch(source, patch, "test.txt", "modify")
        self.assertEqual(result, "uno\nDOS\ntres\n")

        create_patch = (
            "--- /dev/null\n"
            "+++ b/docs/new.txt\n"
            "@@ -0,0 +1 @@\n"
            "+hola\n"
        )
        self.assertEqual(
            apply_unified_patch("", create_patch, "docs/new.txt", "create"),
            "hola\n",
        )

    def test_patch_context_mismatch_is_rejected(self):
        patch = (
            "--- a/test.txt\n"
            "+++ b/test.txt\n"
            "@@ -1,1 +1,1 @@\n"
            "-incorrecto\n"
            "+correcto\n"
        )
        with self.assertRaises(ControlledGitHubError):
            apply_unified_patch("real\n", patch, "test.txt", "modify")

    def test_persistent_lifecycle_owner_isolated_and_requires_approval(self):
        service = AutonomyService(FakePersistence())
        first = service.create_run({
            "goal": "test", "repository": "AkiraGr2/akira-empresa", "base_branch": "main",
            "paths": ["README.md"], "instruction": "small", "idempotency_key": "same"
        }, actor="owner@example.com", owner_scope="scope:A")
        second = service.create_run({
            "goal": "test", "repository": "AkiraGr2/akira-empresa", "base_branch": "main",
            "paths": ["README.md"], "instruction": "small", "idempotency_key": "same"
        }, actor="owner@example.com", owner_scope="scope:A")
        third = service.create_run({
            "goal": "test", "repository": "AkiraGr2/akira-empresa", "base_branch": "main",
            "paths": ["README.md"], "instruction": "small", "idempotency_key": "same"
        }, actor="other@example.com", owner_scope="scope:B")
        self.assertEqual(first["outcome"], "created")
        self.assertEqual(second["outcome"], "already_synced")
        self.assertEqual(first["record"]["id"], second["record"]["id"])
        self.assertNotEqual(first["record"]["id"], third["record"]["id"])

        run_id = first["record"]["id"]
        self.assertIsNone(service.get_run(run_id, owner_scope="scope:B"))
        service.advance(run_id, "planning", "owner@example.com", "scope:A", {
            "base_commit_sha": "a" * 40,
            "plan": {"steps": ["observe"]},
        })
        current = service.get_run(run_id, owner_scope="scope:A")
        for status in ("delegating", "proposed", "sandboxed", "tested", "evaluating", "awaiting_approval"):
            service.advance(run_id, status, "owner@example.com", "scope:A")
        approved = service.approve(run_id, "owner@example.com", "scope:A")
        self.assertEqual(approved["status"], "acting")
        self.assertEqual(approved["decision"]["approved_by"], "owner@example.com")
        with self.assertRaises(AutonomyContractError):
            service.approve(run_id, "owner@example.com", "scope:A")

    def test_developer_proposal_accepts_absent_create_target(self):
        calls = []

        def inspector(repo, paths=None, max_files=8, queries=None):
            calls.append(list(paths or []))
            if paths:
                raise GitHubReadUpstreamError("not_found")
            return {
                "ok": True,
                "operation": "inspect_repository",
                "repository": repo,
                "branch": "main",
                "head_commit_sha": "a" * 40,
                "root": [{"name": "docs", "path": "docs", "type": "dir", "size_bytes": 0}],
                "files": [],
                "total_bytes": 0,
            }

        with patch("specialized_agent_tools._specialist_json_call", return_value={
            "status": "proposal",
            "summary": "create target",
            "changes": [{
                "path": "docs/new.txt",
                "operation": "create",
                "reason": "test",
                "patch": "--- /dev/null\n+++ b/docs/new.txt\n@@ -0,0 +1 @@\n+hola\n",
            }],
            "tests": [],
            "risks": [],
        }):
            result = propose_code_change(
                inspector,
                "AkiraGr2/akira-empresa",
                ["docs/new.txt"],
                "Crea el archivo solicitado.",
                ["docs/new.txt"],
            )

        self.assertEqual(result["status"], "proposal")
        self.assertEqual(len(calls), 3)
        self.assertIn("docs/new.txt", calls[0])
        self.assertEqual(calls[1], [])
        self.assertEqual(calls[2], ["docs/new.txt"])
    def test_generated_create_content_builds_canonical_patch_without_model_headers(self):
        from specialized_agent_tools import propose_code_change
        from github_controlled import apply_unified_patch

        file_content = "# Production Verification\n\nHuman approval was required."
        def inspector(repo, paths=None, max_files=8, queries=None):
            if paths:
                raise GitHubReadUpstreamError("not_found")
            return {
                "ok": True, "branch": "main", "head_commit_sha": "a" * 40,
                "root": [], "files": [], "total_bytes": 0,
            }

        with patch("specialized_agent_tools._specialist_json_call", return_value={
            "status": "proposal",
            "summary": "create target from explicit content",
            "changes": [{
                "path": "docs/new.txt",
                "operation": "create",
                "reason": "bounded verification note",
                "content": file_content,
            }],
            "tests": [], "risks": [],
        }):
            result = propose_code_change(
                inspector, "AkiraGr2/akira-empresa", ["docs/new.txt"],
                "Crea la nota de verificación.", ["docs/new.txt"],
            )

        change = result["changes"][0]
        self.assertNotIn("content", change)
        self.assertEqual(
            change["patch"],
            "--- /dev/null\n+++ b/docs/new.txt\n@@ -0,0 +1,3 @@\n"
            "+# Production Verification\n+\n+Human approval was required.\n",
        )
        self.assertEqual(
            apply_unified_patch("", change["patch"], "docs/new.txt", "create"),
            file_content + "\n",
        )

    def test_generated_empty_create_patch_fails_with_actionable_reason(self):
        def inspector(repo, paths=None, max_files=8, queries=None):
            if paths:
                raise GitHubReadUpstreamError("not_found")
            return {
                "ok": True, "branch": "main", "head_commit_sha": "a" * 40,
                "root": [], "files": [], "total_bytes": 0,
            }

        with patch("specialized_agent_tools._specialist_json_call", return_value={
            "status": "proposal",
            "summary": "empty create",
            "changes": [{
                "path": "docs/new.txt",
                "operation": "create",
                "reason": "test missing content",
                "patch": "",
            }],
            "tests": [], "risks": [],
        }):
            with self.assertRaisesRegex(
                specialized_agent_tools.SpecializedAgentError,
                "proposal_create_content_missing:docs/new.txt",
            ):
                propose_code_change(
                    inspector, "AkiraGr2/akira-empresa", ["docs/new.txt"],
                    "Crea una nota.", ["docs/new.txt"],
                )

    def test_generated_create_patch_is_canonicalized_before_sandbox(self):
        from specialized_agent_tools import propose_code_change
        from github_controlled import apply_unified_patch

        def inspector(repo, paths=None, max_files=8, queries=None):
            if paths:
                raise GitHubReadUpstreamError("not_found")
            return {
                "ok": True, "branch": "main", "head_commit_sha": "a" * 40,
                "root": [], "files": [], "total_bytes": 0,
            }

        malformed = (
            "--- /dev/null\n"
            "+++ b/docs/new.txt\n"
            "@@\n"
            "+hola\n"
            "+mundo\n"
        )
        with patch("specialized_agent_tools._specialist_json_call", return_value={
            "status": "proposal",
            "summary": "create target",
            "changes": [{
                "path": "docs/new.txt",
                "operation": "create",
                "reason": "test",
                "patch": malformed,
            }],
            "tests": [], "risks": [],
        }):
            result = propose_code_change(
                inspector,
                "AkiraGr2/akira-empresa",
                ["docs/new.txt"],
                "Crea el archivo solicitado.",
                ["docs/new.txt"],
            )

        canonical = result["changes"][0]["patch"]
        self.assertIn("@@ -0,0 +1,2 @@", canonical)
        self.assertEqual(
            apply_unified_patch("", canonical, "docs/new.txt", "create"),
            "hola\nmundo\n",
        )

    def test_generated_modify_structured_edit_materializes_deterministic_patch(self):
        def inspector(repo, paths=None, max_files=8, queries=None):
            return {
                "files": [{
                    "path": "README.md",
                    "status": "ok",
                    "content": "uno\ndos\ntres\n",
                }]
            }

        with patch("specialized_agent_tools._specialist_json_call", return_value={
            "status": "proposal",
            "summary": "structured modify",
            "changes": [{
                "path": "README.md",
                "operation": "modify",
                "reason": "test",
                "edit": {
                    "find": "dos\n",
                    "replace": "DOS\n",
                },
            }],
            "tests": [], "risks": [],
        }):
            result = propose_code_change(
                inspector,
                "AkiraGr2/akira-empresa",
                ["README.md"],
                "Modifica una linea.",
            )

        generated = result["changes"][0]["patch"]
        self.assertEqual(
            apply_unified_patch("uno\ndos\ntres\n", generated, "README.md", "modify"),
            "uno\nDOS\ntres\n",
        )
        self.assertRegex(generated, r"^--- a/README\.md\n\+\+\+ b/README\.md\n@@ ")

    def test_generated_modify_patch_with_malformed_hunk_fails_closed(self):
        def inspector(repo, paths=None, max_files=8, queries=None):
            return {"files": [{"path": "README.md", "status": "ok", "content": "hello\n"}]}
        with patch("specialized_agent_tools._specialist_json_call", return_value={
            "status": "proposal",
            "summary": "modify target",
            "changes": [{
                "path": "README.md",
                "operation": "modify",
                "reason": "test",
                "patch": "--- a/README.md\n+++ b/README.md\n@@\n-hello\n+hola\n",
            }],
            "tests": [], "risks": [],
        }):
            with self.assertRaises(specialized_agent_tools.SpecializedAgentError):
                specialized_agent_tools.propose_code_change(
                    inspector,
                    "AkiraGr2/akira-empresa",
                    ["README.md"],
                    "Modifica el archivo solicitado.",
                )

    def test_autonomy_proposal_is_canonicalized_against_exact_base_source(self):
        source = "import ast\nimport unittest\nfrom pathlib import Path\n"
        stale_patch = (
            "--- a/test_tool_registry_contract.py\n"
            "+++ b/test_tool_registry_contract.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+# contract comment\n"
            " import unittest\n"
            " from pathlib import Path\n"
        )
        proposal = {
            "status": "proposal",
            "summary": "test",
            "changes": [{
                "path": "test_tool_registry_contract.py",
                "operation": "modify",
                "reason": "test",
                "patch": stale_patch,
            }],
            "tests": [],
            "risks": [],
            "requires_human_approval": True,
            "write_performed": False,
        }
        with patch(
            "autonomy_engine.fetch_text_file",
            return_value={"content": source, "sha": "source-sha", "path": "test_tool_registry_contract.py"},
        ):
            canonical = _canonicalize_proposal_against_base(
                proposal,
                "AkiraGr2/akira-empresa",
                "a" * 40,
            )
        generated = canonical["changes"][0]["patch"]
        self.assertNotEqual(generated, stale_patch)
        self.assertIn(
            "# contract comment\nimport unittest",
            apply_unified_patch(source, generated, "test_tool_registry_contract.py", "modify"),
        )

    def test_sandbox_canonicalizes_stale_hunk_before_apply(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = "import unittest\nfrom pathlib import Path\n"
            target = root / "test_tool_registry_contract.py"
            target.write_text(source, encoding="utf-8")
            stale_patch = (
                "--- a/test_tool_registry_contract.py\n"
                "+++ b/test_tool_registry_contract.py\n"
                "@@ -1,3 +1,4 @@\n"
                "+# sandbox contract comment\n"
                " import unittest\n"
                " from pathlib import Path\n"
            )
            with patch.object(
                github_controlled, "_download_archive", return_value="ignored"
            ), patch.object(
                github_controlled, "_safe_extract", return_value=root
            ):
                result = sandbox_changes(
                    "AkiraGr2/akira-empresa",
                    "b" * 40,
                    [{
                        "path": "test_tool_registry_contract.py",
                        "operation": "modify",
                        "reason": "test",
                        "patch": stale_patch,
                    }],
                )
            self.assertEqual(result["base_sha"], "b" * 40)
            self.assertIn(
                "# sandbox contract comment\nimport unittest",
                target.read_text(encoding="utf-8"),
            )

    def test_workspace_testing_uses_non_shell_commands(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "sample.py").write_text(
                "value = 1\n",
                encoding="utf-8",
            )
            result = run_python_tests_in_workspace(
                str(root),
                tests=[],
                compile_paths=["sample.py"],
            )
            self.assertEqual(result["status"], "passed")
            self.assertTrue(result["commands_are_non_shell"])
            self.assertEqual(result["tests"][0]["command"][:3], [
                __import__("sys").executable, "-m", "py_compile"
            ])

    def test_workspace_testing_requires_allowlisted_tests(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(Exception):
                run_python_tests_in_workspace(
                    temp,
                    tests=["test_not_allowlisted"],
                    compile_paths=[],
                )

    def test_runtime_registry_migration_is_deterministic_and_owner_only(self):
        source = Path("persistence/migrations.py").read_text(encoding="utf-8")
        start = source.index('"046_controlled_autonomy_runtime_registry"')
        block = source[start:]
        self.assertIn("controlled_autonomy_start", block)
        self.assertIn("autonomy_orchestrator", block)
        self.assertIn('["owner"]', block)
        self.assertIn("ON CONFLICT (name) DO NOTHING", block)
        self.assertIn("SELECT 1 / CASE", block)
        self.assertIn("status = 'available'", block)
        self.assertNotIn("DO $", block)

    def test_production_f14_verification_persists_capability_evidence(self):
        service = Mock()
        service.list_capabilities.return_value = [{"id": "cap_f14", "name": "controlled_autonomy_v1"}]
        service.record_capability_verification.return_value = {"record": {"id": "capver_f14"}, "effective_state": "verified"}
        run = {"id": "autonomy_test_123", "created_by": "owner@example.com", "repository": "AkiraGr2/akira-empresa",
               "base_branch": "main", "base_commit_sha": "a" * 40,
               "decision": {"approved_by": "owner@example.com", "approved_at": "2026-10-06T17:00:00+00:00"}}
        action = {"branch_name": "akira/autonomy/autonomy_test_123", "pr_url": "https://github.com/AkiraGr2/akira-empresa/pull/999",
                  "pr_draft": True, "merged": False}
        runtime_ref = "sha256:" + "d" * 48
        with patch("autonomy_engine.runtime_build_ref", return_value=runtime_ref):
            result = _record_controlled_autonomy_verification(service, run, action)
        self.assertEqual(result["effective_state"], "verified")
        args, kwargs = service.record_capability_verification.call_args
        self.assertEqual(args[1]["build_ref"], runtime_ref)
        self.assertEqual(args[1]["environment"]["base_commit_sha"], "a" * 40)
        self.assertNotEqual(args[1]["build_ref"], args[1]["environment"]["base_commit_sha"])
        self.assertEqual(kwargs["idempotency_key"], "f14:e2e:autonomy_test_123")
        self.assertEqual(args[0], "cap_f14")
        self.assertEqual(args[1]["test_key"], "controlled_autonomy_v1_e2e")
        self.assertEqual(args[1]["result"], "pass")
        # Validate the real persistence contract, not only a mocked call.
        validated = validate_capability_verification(args[1])
        self.assertEqual(validated["test_key"], "controlled_autonomy_v1_e2e")
        self.assertNotIn("observed_availability_state", args[1])
        self.assertEqual(len(args[1]["evidence"]), 3)
        self.assertEqual(args[1]["evidence"][1]["type"], "human_validation")

    def test_f14_capability_failure_recovery_never_repeats_github_write(self):
        service = FakePersistence()
        lifecycle = AutonomyService(service)
        created = lifecycle.create_run({
            "goal": "Reconcile final F14 capability evidence",
            "repository": "AkiraGr2/akira-empresa",
            "base_branch": "main",
            "paths": ["docs/F14_PRODUCTION_VERIFICATION.md"],
            "instruction": "Create one bounded Markdown file",
        }, actor="owner@example.com", owner_scope="scope:F14")
        run_id = created["record"]["id"]
        base_sha = "a" * 40
        for status in ("planning", "delegating", "proposed", "sandboxed", "tested", "evaluating", "awaiting_approval"):
            changes = {}
            if status == "planning":
                changes["base_commit_sha"] = base_sha
            elif status == "proposed":
                changes["proposal"] = {"status": "proposal", "summary": "test", "changes": [{"path": "docs/F14_PRODUCTION_VERIFICATION.md"}]}
            elif status == "sandboxed":
                changes["sandbox"] = {"expected_hashes": {"docs/F14_PRODUCTION_VERIFICATION.md": "b" * 64}}
            lifecycle.advance(run_id, status, "owner@example.com", "scope:F14", changes)
        lifecycle.approve(run_id, "owner@example.com", "scope:F14")
        action = {
            "repository": "AkiraGr2/akira-empresa",
            "base_branch": "main",
            "base_sha": base_sha,
            "branch_name": "akira/autonomy/" + run_id,
            "branch_head": "c" * 40,
            "pr_number": 126,
            "pr_url": "https://github.com/AkiraGr2/akira-empresa/pull/126",
            "pr_draft": True,
            "pr_state": "open",
            "merged": False,
        }
        lifecycle.advance(run_id, "external_applied", "owner@example.com", "scope:F14", {
            "action": action, "branch_name": action["branch_name"], "base_commit_sha": base_sha,
        })
        external_evidence = {
            "external_action_verified": True,
            "external_verification": {
                "branch_head_matches": True, "draft_pr": True, "merged": False,
                "base_branch": True, "pr_number": 126, "pr_url": action["pr_url"],
            },
        }
        lifecycle.advance(run_id, "evaluated", "owner@example.com", "scope:F14", {"evaluation": external_evidence})
        lifecycle.advance(run_id, "learned", "owner@example.com", "scope:F14", {"learning_reference": "learn_existing"})
        lifecycle.record_failure(run_id, "capability_verification_failed:ValidationError", "owner@example.com", "scope:F14")

        with patch("autonomy_engine.verify_existing_draft_action", return_value=external_evidence["external_verification"]), \
             patch("autonomy_engine._record_controlled_autonomy_verification", return_value={
                 "record": {"id": "capver_recovered"}, "effective_state": "verified",
             }), \
             patch("autonomy_engine.controlled_apply") as external_write:
            completed = apply_approved_controlled_autonomy(
                service, run_id, "owner@example.com", "scope:F14"
            )

        external_write.assert_not_called()
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["action"]["pr_url"], action["pr_url"])
        self.assertEqual(completed["learning_reference"], "learn_existing")
        self.assertEqual(completed["evaluation"]["capability_effective_state"], "verified")
        self.assertFalse(completed["evaluation"]["recovery"]["external_write_repeated"])
        self.assertEqual(completed["evaluation"]["recovery"]["previous_failure_reason"], "capability_verification_failed:ValidationError")

    def test_lifecycle_requires_learning_reference_for_completion(self):
        service = AutonomyService(FakePersistence())
        created = service.create_run({
            "goal": "test", "repository": "AkiraGr2/akira-empresa", "base_branch": "main",
            "paths": ["README.md"], "instruction": "small",
        }, actor="owner@example.com", owner_scope="scope:A")
        run_id = created["record"]["id"]
        service.advance(run_id, "planning", "owner@example.com", "scope:A", {"base_commit_sha": "a" * 40})
        for status in ("delegating", "proposed", "sandboxed", "tested", "evaluating", "awaiting_approval", "acting", "external_applied", "evaluated"):
            service.advance(run_id, status, "owner@example.com", "scope:A")
        with self.assertRaises(AutonomyContractError):
            service.advance(run_id, "completed", "owner@example.com", "scope:A")
        service.advance(run_id, "learned", "owner@example.com", "scope:A", {"learning_reference": "learn_test"})
        self.assertEqual(service.advance(run_id, "completed", "owner@example.com", "scope:A")["status"], "completed")

    def test_f14_learning_payload_matches_persistence_evidence_contract(self):
        from persistence.core import validate_learning_event

        run = {
            "id": "autonomy_test_learning",
            "repository": "AkiraGr2/akira-empresa",
            "base_branch": "main",
        }
        action = {
            "pr_url": "https://github.com/AkiraGr2/akira-empresa/pull/999",
            "branch_name": "akira/autonomy/autonomy_test_learning",
            "pr_draft": True,
            "merged": False,
        }
        payload = _build_f14_learning_event(run, action)
        clean = validate_learning_event(payload)
        self.assertEqual(clean["event"], "autonomy_run:autonomy_test_learning")
        self.assertEqual(clean["evidence"][0]["type"], "tool_invocation")
        self.assertIn("action_hash=", clean["evidence"][0]["note"])
        self.assertNotIn("summary", clean["evidence"][0])
        self.assertNotIn("hash", clean["evidence"][0])

    def test_f14_learning_failure_cannot_complete_run(self):
        service = Mock()
        run = {
            "id": "autonomy_test_learning_failure",
            "goal": "F14 learning failure test",
            "repository": "AkiraGr2/akira-empresa",
            "base_branch": "main",
            "base_commit_sha": "a" * 40,
            "decision": {
                "status": "approved",
                "mode": "human",
                "approved_by": "owner@example.com",
                "approved_at": "2026-10-06T17:00:00+00:00",
            },
            "proposal": {
                "changes": [{
                    "path": "docs/new.txt",
                    "operation": "create",
                    "reason": "test",
                    "patch": "--- /dev/null\n+++ b/docs/new.txt\n@@ -0,0 +1 @@\n+hola\n",
                }]
            },
            "sandbox": {"expected_hashes": {"docs/new.txt": "b" * 64}},
            "evaluation": {"tests_passed": True, "review_verdict": "approve"},
            "status": "acting",
        }
        action = {
            "branch_name": "akira/autonomy/autonomy_test_learning_failure",
            "base_sha": run["base_commit_sha"],
            "branch_head": "c" * 40,
            "pr_url": "https://github.com/AkiraGr2/akira-empresa/pull/999",
            "pr_draft": True,
            "pr_state": "open",
            "pr_number": 999,
            "base_branch": "main",
            "merged": False,
        }
        actor = "owner@example.com"
        owner_scope = "owner:scope"
        fake_autonomy = Mock()
        fake_autonomy.get_run.return_value = run
        statuses = []

        def record_advance(_a, _run_id, status, _actor, _owner_scope, changes=None):
            statuses.append(status)
            return dict(run, status=status, **(changes or {}))

        service.save_learning.side_effect = ValueError("learning_schema_rejected")

        with patch("autonomy_engine._autonomy", return_value=fake_autonomy), \
             patch("autonomy_engine._advance", side_effect=record_advance), \
             patch("autonomy_engine.controlled_apply", return_value=action), \
             patch("autonomy_engine.branch_head", return_value=action["branch_head"]), \
             patch(
                 "autonomy_engine._record_controlled_autonomy_verification",
                 return_value={"record": {"id": "capver_test"}, "effective_state": "verified"},
             ) as record_verification:
            with self.assertRaises(ControlledAutonomyError) as ctx:
                apply_approved_controlled_autonomy(service, run["id"], actor, owner_scope)

        self.assertEqual(str(ctx.exception), "learning_persistence_failed")
        self.assertIn("external_applied", statuses)
        self.assertIn("evaluated", statuses)
        self.assertNotIn("learned", statuses)
        self.assertNotIn("completed", statuses)
        record_verification.assert_not_called()
        fake_autonomy.record_failure.assert_called_once()
        self.assertIn("learning_persistence_failed:", fake_autonomy.record_failure.call_args.args[1])

    def test_f14_stale_capability_verification_fails_closed_after_learning(self):
        service = Mock()
        run = {
            "id": "autonomy_test_stale_verification",
            "goal": "F14 stale verification fail-closed test",
            "created_by": "owner@example.com",
            "repository": "AkiraGr2/akira-empresa",
            "base_branch": "main",
            "base_commit_sha": "a" * 40,
            "decision": {
                "status": "approved",
                "mode": "human",
                "approved_by": "owner@example.com",
                "approved_at": "2026-10-06T17:00:00+00:00",
            },
            "proposal": {
                "summary": "synthetic change",
                "changes": [{
                    "path": "docs/new.txt",
                    "operation": "create",
                    "reason": "test",
                    "patch": "--- /dev/null\n+++ b/docs/new.txt\n@@ -0,0 +1 @@\n+synthetic\n",
                }],
            },
            "sandbox": {"expected_hashes": {"docs/new.txt": "b" * 64}},
            "evaluation": {"tests_passed": True, "review_verdict": "approve"},
            "status": "acting",
        }
        action = {
            "branch_name": "akira/autonomy/autonomy_test_stale_verification",
            "base_sha": run["base_commit_sha"],
            "branch_head": "c" * 40,
            "pr_url": "https://github.com/AkiraGr2/akira-empresa/pull/999",
            "pr_draft": True,
            "pr_state": "open",
            "pr_number": 999,
            "base_branch": "main",
            "merged": False,
        }
        fake_autonomy = Mock()
        fake_autonomy.get_run.return_value = run
        service.save_learning.return_value = {"record": {"id": "learn_test"}}
        statuses = []

        def record_advance(_a, _run_id, status, _actor, _owner_scope, changes=None):
            statuses.append(status)
            return dict(run, status=status, **(changes or {}))

        with patch("autonomy_engine._autonomy", return_value=fake_autonomy), \
             patch("autonomy_engine._advance", side_effect=record_advance), \
             patch("autonomy_engine.controlled_apply", return_value=action), \
             patch("autonomy_engine.branch_head", return_value=action["branch_head"]), \
             patch(
                 "autonomy_engine._record_controlled_autonomy_verification",
                 return_value={"record": {"id": "capver_stale"}, "effective_state": "stale"},
             ) as record_verification:
            with self.assertRaisesRegex(ControlledAutonomyError, "capability_verification_failed"):
                apply_approved_controlled_autonomy(
                    service, run["id"], "owner@example.com", "owner:scope"
                )

        self.assertIn("evaluated", statuses)
        self.assertIn("learned", statuses)
        self.assertNotIn("completed", statuses)
        record_verification.assert_called_once()
        fake_autonomy.record_failure.assert_called_once()

    def test_controlled_gateway_contract_is_branch_only(self):
        source = Path("github_controlled.py").read_text(encoding="utf-8")
        self.assertIn('BRANCH_PREFIX = "akira/autonomy/"', source)
        self.assertIn('if main_head != base_sha.lower():', source)
        self.assertIn('"draft": True', source)
        self.assertNotIn('"/git/refs/heads/main"', source)
        self.assertNotIn('"merge": True', source)
        self.assertIn('if bool(verified.get("merged"))', source)
        self.assertIn('canonical_patch = canonicalize_modify_patch(path, current["content"], change["patch"])', source)
        self.assertIn('apply_unified_patch(current["content"], canonical_patch, path, "modify")', source)

    def test_external_modify_recanonicalizes_patch_after_terminal_newline_is_trimmed(self):
        path = "README.md"
        source = "uno\ndos\ntres\n"
        patch = github_controlled.deterministic_modify_patch(
            path, source, "dos\n", "DOS\n"
        )
        change = validate_change({
            "path": path,
            "operation": "modify",
            "reason": "regression",
            "patch": patch,
        })

        # validate_change currently trims text, removing the patch's final newline.
        self.assertFalse(change["patch"].endswith("\n"))
        with self.assertRaisesRegex(ControlledGitHubError, "patch_context_mismatch"):
            apply_unified_patch(source, change["patch"], path, "modify")

        canonical_patch = github_controlled.canonicalize_modify_patch(
            path, source, change["patch"]
        )
        result = apply_unified_patch(source, canonical_patch, path, "modify")
        self.assertEqual("uno\nDOS\ntres\n", result)



    def test_f14_bounded_proposal_is_materialized_before_model_edit_generation(self):
        request = {
            "goal": "Verificación de producción F14: añadir el documento de evidencia y su prueba de contenido.",
            "repository": "AkiraGr2/akira-empresa",
            "paths": [
                "docs/F14_PRODUCTION_VERIFICATION.md",
                "test_controlled_autonomy_contract.py",
            ],
            "instruction": "bounded F14 instruction",
            "queries": [],
        }
        source = (
            "class ControlledAutonomyContractTests(unittest.TestCase):\n"
            "    pass\n\n\n"
            "if __name__ == \"__main__\":\n"
            "    unittest.main()\n"
        )
        with patch("autonomy_engine.fetch_text_file", return_value={"content": source}), patch(
            "autonomy_engine.propose_code_change",
            side_effect=AssertionError("bounded F14 must not ask the model to invent an edit anchor"),
        ) as model_proposal:
            result = _prepare_controlled_proposal(request, "a" * 40)

        self.assertEqual(
            [item["path"] for item in result["changes"]],
            [
                "docs/F14_PRODUCTION_VERIFICATION.md",
                "test_controlled_autonomy_contract.py",
            ],
        )
        self.assertTrue(result["requires_human_approval"])
        self.assertFalse(result["write_performed"])
        model_proposal.assert_not_called()

    def test_f14_production_verification_contract_materializes_document_and_test(self):
        request = {
            "goal": "Verificación de producción F14: añadir el documento de evidencia y su prueba de contenido.",
            "repository": "AkiraGr2/akira-empresa",
            "paths": [
                "docs/F14_PRODUCTION_VERIFICATION.md",
                "test_controlled_autonomy_contract.py",
            ],
        }
        source = (
            "class ControlledAutonomyContractTests(unittest.TestCase):\n"
            "    pass\n\n\n"
            "if __name__ == \"__main__\":\n"
            "    unittest.main()\n"
        )
        proposal = {
            "status": "proposal",
            "summary": "Model-generated document only",
            "changes": [{
                "path": "docs/F14_PRODUCTION_VERIFICATION.md",
                "operation": "create",
                "reason": "document",
                "patch": (
                    "--- /dev/null\n"
                    "+++ b/docs/F14_PRODUCTION_VERIFICATION.md\n"
                    "@@ -0,0 +1,3 @@\n"
                    "# model title\n"
                    "+\n"
                    "+note\n"
                ),
            }],
            "requires_human_approval": True,
            "write_performed": False,
        }
        with patch(
            "autonomy_engine.fetch_text_file",
            return_value={"content": source},
        ) as fetch_source:
            result = _enforce_f14_production_verification_contract(
                proposal,
                request,
                "a" * 40,
            )

        self.assertEqual(
            [item["path"] for item in result["changes"]],
            [
                "docs/F14_PRODUCTION_VERIFICATION.md",
                "test_controlled_autonomy_contract.py",
            ],
        )
        document_patch = result["changes"][0]["patch"]
        test_patch = result["changes"][1]["patch"]
        self.assertIn("+# Production Verification - F14", document_patch)
        self.assertIn(
            "+Esta ejecución es una verificación de Controlled Autonomy v1 y requirió aprobación humana.",
            document_patch,
        )
        self.assertIn(
            "test_docs_F14_PRODUCTION_VERIFICATION_exists_and_contains_title_and_human_approval_note",
            test_patch,
        )
        self.assertIn("Path(__file__).resolve().parent", test_patch)
        self.assertIn("self.assertTrue(target.is_file())", test_patch)
        self.assertIn('target.read_text(encoding="utf-8")', test_patch)
        self.assertIn("self.assertIn", test_patch)
        self.assertTrue(result["requires_human_approval"])
        self.assertFalse(result["write_performed"])
        fetch_source.assert_called_once_with(
            "AkiraGr2/akira-empresa",
            "test_controlled_autonomy_contract.py",
            "a" * 40,
        )

    def test_f14_production_verification_contract_ignores_other_scopes(self):
        request = {
            "goal": "Improve a different bounded feature",
            "repository": "AkiraGr2/akira-empresa",
            "paths": ["README.md"],
        }
        proposal = {"status": "proposal", "changes": []}
        with patch("autonomy_engine.fetch_text_file") as fetch_source:
            result = _enforce_f14_production_verification_contract(
                proposal,
                request,
                "b" * 40,
            )
        self.assertIs(result, proposal)
        fetch_source.assert_not_called()



    def test_modify_patch_recovers_unique_removed_block_when_context_is_stale(self):
        path = "example.py"
        source = "before\nTARGET\nafter\n"
        patch = (
            "--- a/example.py\n"
            "+++ b/example.py\n"
            "@@ -1,3 +1,3 @@\n"
            " stale context\n"
            "-TARGET\n"
            "+REPLACED\n"
            " stale tail\n"
        )
        canonical = github_controlled.canonicalize_modify_patch(path, source, patch)
        result = apply_unified_patch(source, canonical, path, "modify")
        self.assertEqual("before\nREPLACED\nafter\n", result)

    def test_modify_patch_still_rejects_nonunique_removed_block(self):
        path = "example.py"
        source = "TARGET\nother\nTARGET\n"
        patch = (
            "--- a/example.py\n"
            "+++ b/example.py\n"
            "@@ -1 +1 @@\n"
            "-TARGET\n"
            "+REPLACED\n"
        )
        with self.assertRaisesRegex(ControlledGitHubError, "patch_anchor_not_unique"):
            github_controlled.canonicalize_modify_patch(path, source, patch)



    def test_docs_F14_PRODUCTION_VERIFICATION_exists_and_contains_title_and_human_approval_note(self):
        target = Path(__file__).resolve().parent / "docs" / "F14_PRODUCTION_VERIFICATION.md"
        self.assertTrue(target.is_file())
        content = target.read_text(encoding="utf-8")
        self.assertIn("# Production Verification - F14", content)
        self.assertIn("Esta ejecución es una verificación de Controlled Autonomy v1 y requirió aprobación humana.", content)


if __name__ == "__main__":
    unittest.main()
