import hashlib
import tempfile
import unittest
from pathlib import Path

from persistence.autonomy import (
    AutonomyContractError,
    AutonomyService,
    AUTONOMY_STATUS_TRANSITIONS,
    validate_path,
    validate_proposal,
    validate_request,
    validate_transition,
)
from github_controlled import ControlledGitHubError, apply_unified_patch
from specialized_agent_tools import run_python_tests_in_workspace


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
            validate_transition("completed", "acting")

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
        with self.assertRaises(AutonomyContractError):
            # approval is only legal in awaiting_approval, and transition itself
            # advances to acting so it cannot be repeated.
            service.approve(run_id, "owner@example.com", "scope:A")
        # The loop reaches awaiting_approval; approval must be possible exactly once.
        approved = service.approve(run_id, "owner@example.com", "scope:A")
        self.assertEqual(approved["status"], "acting")
        self.assertEqual(approved["decision"]["approved_by"], "owner@example.com")
        with self.assertRaises(AutonomyContractError):
            service.approve(run_id, "owner@example.com", "scope:A")

    def test_workspace_testing_uses_non_shell_commands(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "test_sample.py").write_text(
                "import unittest\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n\nif __name__ == '__main__': unittest.main()\n",
                encoding="utf-8",
            )
            result = run_python_tests_in_workspace(
                str(root),
                tests=["test_sample"],
                compile_paths=["test_sample.py"],
            )
            self.assertEqual(result["status"], "passed")
            self.assertTrue(result["commands_are_non_shell"])

    def test_controlled_gateway_contract_is_branch_only(self):
        source = Path("github_controlled.py").read_text(encoding="utf-8")
        self.assertIn('BRANCH_PREFIX = "akira/autonomy/"', source)
        self.assertIn('if main_head != base_sha.lower():', source)
        self.assertIn('"draft": True', source)
        self.assertNotIn('"/git/refs/heads/main"', source)
        self.assertNotIn('"merge": True', source)
        self.assertIn('if bool(verified.get("merged"))', source)


if __name__ == "__main__":
    unittest.main()
