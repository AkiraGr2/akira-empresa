import unittest

from persistence.service import NotFoundError, PersistenceService


class FakeTx:
    def __init__(self, repo):
        self.repo = repo

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def create(self, entity, record):
        self.repo.rows.setdefault(entity, []).append(dict(record))
        return dict(record), True

    def update(self, entity, record_id, changes, expected_version):
        rows = self.repo.rows.get(entity, [])
        row = next(r for r in rows if r["id"] == record_id)
        if row["version"] != expected_version:
            raise RuntimeError("version conflict")
        row.update(changes)
        row["version"] += 1
        return dict(row)

    def append_audit(self, payload):
        return None


class FakeRepo:
    def __init__(self):
        self.rows = {
            "missions": [
                {"id": "m_a", "created_by": "a@example.test", "status": "waiting_approval", "version": 2,
                 "plan": {"steps": []}},
                {"id": "m_b", "created_by": "b@example.test", "status": "running", "version": 3,
                 "plan": {"steps": []}},
            ],
            "agent_tasks": [
                {"id": "t_a", "owner_scope": "scope:A", "agent_name": "researcher",
                 "tool_name": "web_search", "status": "pending", "version": 1, "mission_id": "m_a"},
                {"id": "t_b", "owner_scope": "scope:B", "agent_name": "researcher",
                 "tool_name": "web_search", "status": "pending", "version": 1, "mission_id": "m_b"},
            ],
            "agents": [
                {"id": "agent_r", "name": "researcher", "status": "idle",
                 "allowed_tools": ["web_search"], "version": 1, "tasks_completed": 0,
                 "tasks_failed": 0},
            ],
            "tools": [
                {"id": "tool_w", "name": "web_search", "status": "available"},
            ],
        }

    def get(self, entity, record_id):
        for row in self.rows.get(entity, []):
            if row.get("id") == record_id:
                return dict(row)
        return None

    def search(self, entity, filters=None, limit=50, offset=0, order_by="created_at", descending=True):
        rows = [dict(r) for r in self.rows.get(entity, [])]
        for key, value in (filters or {}).items():
            rows = [r for r in rows if r.get(key) == value]
        return rows[offset:offset + limit]

    def count(self, entity, filters=None):
        return len(self.search(entity, filters, limit=5000))

    def transaction(self):
        return FakeTx(self)


class MissionTaskOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.service = PersistenceService(FakeRepo())

    def test_mission_read_is_owner_scoped(self):
        self.assertIsNotNone(self.service.get_mission("m_a", owner="a@example.test"))
        self.assertIsNone(self.service.get_mission("m_a", owner="b@example.test"))

    def test_mission_status_update_rejects_foreign_owner(self):
        with self.assertRaises(NotFoundError):
            self.service.update_mission_status(
                "m_a", "running", 2, actor="b@example.test", owner="b@example.test"
            )

    def test_mission_plan_update_rejects_foreign_owner(self):
        with self.assertRaises(NotFoundError):
            self.service.update_mission_plan(
                "m_a", {"steps": [{"order": 1}]}, 2,
                actor="b@example.test", owner="b@example.test"
            )

    def test_task_read_and_transition_are_owner_scoped(self):
        self.assertIsNotNone(self.service.get_task("t_a", owner_scope="scope:A"))
        self.assertIsNone(self.service.get_task("t_a", owner_scope="scope:B"))
        with self.assertRaises(NotFoundError):
            self.service.start_task("t_a", actor="b@example.test", owner_scope="scope:B")

    def test_task_creation_requires_owned_mission(self):
        with self.assertRaises(NotFoundError):
            self.service.create_task(
                "researcher", "web_search", mission_id="m_a",
                actor="b@example.test", owner="b@example.test",
                owner_scope="scope:B",
            )

    def test_task_listing_is_owner_scoped(self):
        rows = self.service.list_tasks(owner_scope="scope:A", limit=50)
        self.assertEqual({r["id"] for r in rows}, {"t_a"})


if __name__ == "__main__":
    unittest.main()
