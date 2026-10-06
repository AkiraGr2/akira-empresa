import unittest

from persistence.service import PersistenceService


class FakeRepo:
    def __init__(self):
        self.data = {
            "self_model": {
                "id": "akira_primary",
                "identity": {"name": "Akira"},
                "version": 1,
            },
            "capabilities": [
                {
                    "id": "cap1",
                    "name": "session_auth",
                    "implementation_state": "implemented",
                    "verification_state": "verified",
                    "availability_state": "available",
                    "maturity": "experimental",
                    "cost_compatibility": "conditional",
                    "last_verified_at": "2026-10-04T00:00:00Z",
                },
            ],
            "agents": [
                {
                    "name": "tester",
                    "role": "tester",
                    "status": "idle",
                    "allowed_tools": ["github_repo_read", "python_test"],
                },
            ],
            "tools": [
                {
                    "name": "github_repo_read",
                    "category": "code",
                    "status": "available",
                    "permissions": ["auth"],
                },
                {
                    "name": "python_test",
                    "category": "code",
                    "status": "available",
                    "permissions": ["owner"],
                },
            ],
        }

    def get(self, entity, key):
        return self.data.get(entity, {}).get(key) if isinstance(self.data.get(entity), dict) else None

    def search(self, entity, filters=None, limit=100, offset=0, order_by="created_at", descending=True):
        rows = self.data.get(entity, [])
        if isinstance(rows, dict):
            rows = list(rows.values())
        return list(rows)[offset:offset + limit]


class SelfKnowledgeSnapshotTests(unittest.TestCase):
    def test_snapshot_uses_authoritative_registries(self):
        service = PersistenceService(FakeRepo())
        snapshot = service.self_knowledge_snapshot(owner_scope=None)

        self.assertEqual(snapshot["source"], "runtime_authoritative_registry")
        self.assertEqual(snapshot["identity_authority"], "identity_root")
        self.assertEqual(snapshot["identity"]["name"], "Akira")
        self.assertEqual(snapshot["capabilities"][0]["name"], "session_auth")
        self.assertEqual(snapshot["agents"][0]["name"], "tester")
        self.assertIn("python_test", snapshot["tools"][1]["name"])
        self.assertEqual(snapshot["limitations"][0].startswith("Los estados de capability"), True)

    def test_cognitive_cycle_owner_scope_regression(self):
        source = open("nexus.py", encoding="utf-8").read()
        start = source.index("def _execute_cognitive_cycle(")
        end = source.index('@app.post("/api/v8/cognitive/cycle")', start)
        cycle = source[start:end]
        self.assertIn("owner_scope=owner_scope", cycle)
        self.assertNotIn('owner_scope=s["owner_scope"]', cycle)

    def test_self_model_rejects_manual_derived_registry_updates(self):
        from persistence.core import ValidationError, validate_self_model
        for field in ("capabilities", "tools"):
            with self.assertRaises(ValidationError):
                validate_self_model({field: []}, partial=True)

    def test_self_model_exposes_live_registry_projection(self):
        service = PersistenceService(FakeRepo())
        model = service.get_self_model()
        self.assertEqual(model["capabilities"][0]["name"], "session_auth")
        self.assertEqual(model["tools"][0]["name"], "github_repo_read")


if __name__ == "__main__":
    unittest.main()
