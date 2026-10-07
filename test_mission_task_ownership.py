import unittest
from pathlib import Path

from persistence.core import entity_spec
from persistence.service import NotFoundError, PersistenceService, ValidationError


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
        self.search_calls = []
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
                {"id": "agent_b", "name": "busy_agent", "status": "busy",
                 "allowed_tools": ["web_search"], "version": 1, "tasks_completed": 0,
                 "tasks_failed": 0},
            ],
            "tools": [
                {"id": "tool_w", "name": "web_search", "status": "available", "permissions": ["auth"]},
                {"id": "tool_disabled", "name": "disabled_tool", "status": "disabled", "permissions": ["auth"]},
                {"id": "tool_bad", "name": "bad_tool", "status": "available", "permissions": []},
            ],
        }

    def get(self, entity, record_id):
        for row in self.rows.get(entity, []):
            if row.get("id") == record_id:
                return dict(row)
        return None

    def search(self, entity, filters=None, limit=50, offset=0, order_by="created_at", descending=True):
        filters = dict(filters or {})
        self.search_calls.append((entity, dict(filters)))
        rows = [dict(r) for r in self.rows.get(entity, [])]
        for key, value in filters.items():
            if key.endswith("__in"):
                field = key[:-4]
                rows = [r for r in rows if r.get(field) in value]
            else:
                rows = [r for r in rows if r.get(key) == value]
        return rows[offset:offset + limit]

    def count(self, entity, filters=None):
        return len(self.search(entity, filters, limit=5000))

    def transaction(self):
        return FakeTx(self)


class MissionTaskOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.service = PersistenceService(FakeRepo())

    def test_mission_idempotency_scope_is_owner(self):
        self.assertEqual(
            entity_spec("missions")["idempotency_scope"],
            ("created_by",),
        )

    def test_mission_approval_persists_authorized_by(self):
        source = Path("persistence/service.py").read_text(encoding="utf-8")
        self.assertIn('changes["authorized_by"] = owner or actor', source)

    def test_mission_cancel_route_uses_cascade_service(self):
        source = Path("nexus.py").read_text(encoding="utf-8")
        start = source.index('@app.post("/api/v8/missions/{mission_id}/cancel")')
        end = source.index("\n# ============================================================", start)
        block = source[start:end]
        self.assertIn("service.cancel_mission(", block)
        self.assertNotIn('service.update_mission_status(mission_id, "paused"', block)
        self.assertNotIn('service.update_mission_status(mission_id, "cancelled"', block)

    def test_orphan_mission_cleanup_is_boot_only(self):
        source = Path("nexus.py").read_text(encoding="utf-8")
        first_mission_route = source.index('@app.post("/api/v8/missions")')
        boot_block = source[:first_mission_route]
        self.assertIn("if service is not None:", boot_block)
        self.assertIn("_cleanup_orphan_missions(service)", boot_block)

        selftest_start = source.index("def v8_missions_selftest")
        selftest_end = source.index('@app.get("/api/v8/missions/{mission_id}/diagnose")')
        selftest_block = source[selftest_start:selftest_end]
        self.assertIn('_selftest_missions_run(owner=s["email"], owner_scope=s["owner_scope"])', selftest_block)
        self.assertNotIn("_cleanup_orphan_missions(", selftest_block)

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

    def test_get_task_fallback_is_query_scoped(self):
        repo = FakeRepo()
        original_get = repo.get

        def get_without_task_reads(entity, record_id):
            if entity == "agent_tasks":
                return None
            return original_get(entity, record_id)

        repo.get = get_without_task_reads
        service = PersistenceService(repo)

        self.assertIsNotNone(service.get_task("t_a", owner_scope="scope:A"))
        self.assertIsNone(service.get_task("t_a", owner_scope="scope:B"))

        task_queries = [filters for entity, filters in repo.search_calls if entity == "agent_tasks"]
        self.assertIn(
            {"id": "t_a", "owner_scope": "scope:A"},
            task_queries,
        )
        self.assertIn(
            {"id": "t_a", "owner_scope": "scope:B"},
            task_queries,
        )

    def test_create_task_verification_readback_is_scoped(self):
        repo = FakeRepo()
        service = PersistenceService(repo)

        result = service.create_task(
            "researcher",
            "web_search",
            inputs={"query": "test"},
            actor="scope:A",
            owner_scope="scope:A",
        )

        self.assertTrue(result["record"]["id"].startswith("task_"))
        task_queries = [filters for entity, filters in repo.search_calls if entity == "agent_tasks"]
        self.assertIn(
            {
                "id": result["record"]["id"],
                "owner_scope": "scope:A",
            },
            task_queries,
        )

    def test_task_creation_requires_owned_mission(self):
        with self.assertRaises(NotFoundError):
            self.service.create_task(
                "researcher", "web_search", mission_id="m_a",
                actor="b@example.test", owner="b@example.test",
                owner_scope="scope:B",
            )

    def test_legacy_task_is_not_visible_to_scoped_owner(self):
        self.service.repo.rows["agent_tasks"].append(
            {"id": "t_legacy", "owner_scope": "owner", "agent_name": "researcher",
             "tool_name": "web_search", "status": "completed", "version": 1, "mission_id": None}
        )
        self.assertIsNone(self.service.get_task("t_legacy", owner_scope="scope:A"))

    def test_task_idempotency_scope_is_owner(self):
        self.assertEqual(
            entity_spec("agent_tasks")["idempotency_scope"],
            ("owner_scope",),
        )

    def test_task_creation_rejects_unavailable_tool(self):
        self.service.repo.rows["agents"][0]["allowed_tools"] = ["disabled_tool"]
        with self.assertRaises(ValidationError):
            self.service.create_task(
                "researcher", "disabled_tool",
                actor="scope:A", owner_scope="scope:A",
            )

    def test_task_creation_rejects_invalid_tool_permissions(self):
        self.service.repo.rows["agents"][0]["allowed_tools"] = ["bad_tool"]
        with self.assertRaises(ValidationError):
            self.service.create_task(
                "researcher", "bad_tool",
                actor="scope:A", owner_scope="scope:A",
            )

    def test_start_task_rejects_busy_agent(self):
        self.service.repo.rows["agent_tasks"].append(
            {"id": "t_busy", "owner_scope": "scope:A", "agent_name": "busy_agent",
             "tool_name": "web_search", "status": "pending", "version": 1, "mission_id": None}
        )
        with self.assertRaises(ValidationError):
            self.service.start_task("t_busy", actor="scope:A", owner_scope="scope:A")

    def test_registered_agent_allowed_tools_must_be_available_and_valid(self):
        with self.assertRaises(ValidationError):
            self.service.register_agent(
                {"name": "invalid_agent", "role": "generic", "description": "test",
                 "allowed_tools": ["disabled_tool"]},
                actor="selftest",
            )
        with self.assertRaises(ValidationError):
            self.service.register_agent(
                {"name": "bad_perm_agent", "role": "generic", "description": "test",
                 "allowed_tools": ["bad_tool"]},
                actor="selftest",
            )

    def test_cancel_mission_cascades_nonterminal_tasks_without_counting_failures(self):
        for agent in self.service.repo.rows["agents"]:
            if agent["id"] == "agent_r":
                agent["status"] = "busy"
                agent["current_task_id"] = "t_b"
                agent["current_action"] = "web_search"
                agent["version"] = 2

        result = self.service.cancel_mission(
            "m_b",
            reason="cancelacion solicitada por propietario",
            actor="b@example.test",
            owner="b@example.test",
        )
        self.assertEqual(result["status"], "cancelled")

        task = self.service.get_task("t_b", owner_scope="scope:B")
        self.assertIsNotNone(task)
        self.assertEqual(task["status"], "cancelled")
        self.assertEqual(
            task["outputs"]["cancel_reason"],
            "cancelacion solicitada por propietario",
        )

        agent = self.service.repo.get("agents", "agent_r")
        self.assertEqual(agent["status"], "idle")
        self.assertIsNone(agent["current_task_id"])
        self.assertEqual(agent["tasks_failed"], 0)

    def test_cancel_mission_leaves_completed_tasks_untouched(self):
        self.service.repo.rows["agent_tasks"].append(
            {"id": "t_completed", "owner_scope": "scope:B", "agent_name": "researcher",
             "tool_name": "web_search", "status": "completed", "version": 1,
             "mission_id": "m_b", "outputs": {}, "completed_at": "2026-10-06T00:00:00Z"}
        )
        self.service.cancel_mission(
            "m_b",
            reason="ya no se necesita",
            actor="b@example.test",
            owner="b@example.test",
        )
        task = self.service.get_task("t_completed", owner_scope="scope:B")
        self.assertEqual(task["status"], "completed")

    def test_legacy_cancelled_mission_reconciliation_migration_is_scoped(self):
        source = Path("persistence/migrations.py").read_text(encoding="utf-8")
        start = source.index('"044_reconcile_legacy_cancelled_mission_tasks"')
        block = source[start:]
        self.assertIn("m.status = 'cancelled'", block)
        self.assertIn("t.status IN ('pending','running')", block)
        self.assertIn("'mission.task.legacy_reconcile'", block)
        self.assertIn("status = 'cancelled'", block)


    def test_legacy_cancelled_mission_reconciliation_preserves_outputs(self):
        source = Path("persistence/migrations.py").read_text(encoding="utf-8")
        start = source.index('"044_reconcile_legacy_cancelled_mission_tasks"')
        block = source[start:]
        self.assertIn("outputs = COALESCE(t.outputs, '{}'::jsonb) || jsonb_build_object", block)
        self.assertIn("'legacy_cancelled_mission_reconciliation'", block)
        self.assertIn("completed_at = COALESCE(t.completed_at, now())", block)

    def test_task_listing_is_owner_scoped(self):
        rows = self.service.list_tasks(owner_scope="scope:A", limit=50)
        self.assertEqual({r["id"] for r in rows}, {"t_a"})


if __name__ == "__main__":
    unittest.main()
