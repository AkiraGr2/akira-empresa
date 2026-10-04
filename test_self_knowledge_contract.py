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


if __name__ == "__main__":
    unittest.main()
