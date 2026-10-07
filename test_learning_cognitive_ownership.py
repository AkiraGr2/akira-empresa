import unittest

from persistence.core import entity_spec
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
        row = next(r for r in self.repo.rows.get(entity, []) if r["id"] == record_id)
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
            "learning_events": [
                {"id": "learn_a", "owner_scope": "scope:A", "status": "candidate", "version": 1},
                {"id": "learn_legacy", "owner_scope": "owner", "status": "candidate", "version": 1},
                {"id": "learn_b", "owner_scope": "scope:B", "status": "candidate", "version": 1},
            ],
            "cognitive_cycles": [
                {"id": "cycle_a", "owner_scope": "scope:A", "status": "in_progress", "version": 1},
                {"id": "cycle_b", "owner_scope": "scope:B", "status": "in_progress", "version": 1},
                {"id": "cycle_legacy", "owner_scope": "owner", "status": "completed", "version": 1},
            ],
            "cognitive_events": [
                {"id": "event_a", "cycle_id": "cycle_a", "stage": "observe", "status": "success", "version": 1},
            ]
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


class OwnershipServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = PersistenceService(FakeRepo())

    def test_learning_is_scoped(self):
        self.assertIsNotNone(self.service.get_learning("learn_a", owner_scope="scope:A"))
        self.assertIsNone(self.service.get_learning("learn_a", owner_scope="scope:B"))
        self.assertIsNone(self.service.get_learning("learn_legacy", owner_scope="scope:A"))

    def test_learning_list_is_scoped(self):
        rows = self.service.search_learning(owner_scope="scope:A", limit=50)
        self.assertEqual({r["id"] for r in rows}, {"learn_a"})

    def test_cognitive_idempotency_scopes_are_declared(self):
        self.assertEqual(
            entity_spec("cognitive_cycles")["idempotency_scope"],
            ("owner_scope",),
        )
        self.assertEqual(
            entity_spec("cognitive_events")["idempotency_scope"],
            ("cycle_id",),
        )

    def test_legacy_cognitive_cycle_is_not_visible_to_scoped_owner(self):
        self.assertIsNone(self.service.get_cycle("cycle_legacy", owner_scope="scope:A"))

    def test_cognitive_cycle_listing_is_strictly_scoped(self):
        rows = self.service.list_cycles(owner_scope="scope:A", limit=50)
        self.assertEqual({r["id"] for r in rows}, {"cycle_a"})

    def test_cognitive_cycle_event_lookup_follows_parent_scope(self):
        self.assertEqual(
            self.service.list_cycle_events("cycle_a", owner_scope="scope:A")[0]["id"],
            "event_a",
        )
        self.assertEqual(
            self.service.list_cycle_events("cycle_a", owner_scope="scope:B"),
            [],
        )

    def test_cognitive_cycle_is_scoped_and_events_follow_parent(self):
        self.assertIsNotNone(self.service.get_cycle("cycle_a", owner_scope="scope:A"))
        self.assertIsNone(self.service.get_cycle("cycle_a", owner_scope="scope:B"))

        with self.assertRaises(NotFoundError):
            self.service.record_stage(
                "cycle_a", "observe", data={"x": 1},
                actor="other@example.test", owner_scope="scope:B",
            )

        self.assertIsNone(
            self.service.get_cycle_with_events("cycle_a", owner_scope="scope:B")
        )

    def test_cognitive_cycle_listing_is_scoped(self):
        rows = self.service.list_cycles(owner_scope="scope:A", limit=50)
        self.assertEqual({r["id"] for r in rows}, {"cycle_a"})


    def _seed_cycle(self, owner_scope="scope:A"):
        cycle = self.service.start_cycle(
            "test",
            {"message": "cycle"},
            actor="tester",
            owner_scope=owner_scope,
        )["record"]
        return cycle

    def _record_all_stages(self, cycle_id, owner_scope="scope:A"):
        for stage in (
            "observe", "interpret", "reason", "decide", "act",
            "observe_result", "evaluate", "learn", "update_self_model",
        ):
            self.service.record_stage(
                cycle_id,
                stage,
                data={"stage": stage},
                actor="tester",
                owner_scope=owner_scope,
                idempotency_key=f"{cycle_id}:{stage}:v1",
            )

    def test_cognitive_stage_cannot_skip_a_stage(self):
        cycle = self._seed_cycle()
        with self.assertRaises(Exception):
            self.service.record_stage(
                cycle["id"], "reason", data={"x": 1},
                actor="tester", owner_scope="scope:A",
            )

    def test_cognitive_stage_cannot_repeat_or_regress_without_idempotent_retry(self):
        cycle = self._seed_cycle()
        self.service.record_stage(
            cycle["id"], "observe", data={"x": 1},
            actor="tester", owner_scope="scope:A",
        )
        with self.assertRaises(Exception):
            self.service.record_stage(
                cycle["id"], "observe", data={"x": 2},
                actor="tester", owner_scope="scope:A",
            )
        self.service.record_stage(
            cycle["id"], "interpret", data={"x": 3},
            actor="tester", owner_scope="scope:A",
        )
        with self.assertRaises(Exception):
            self.service.record_stage(
                cycle["id"], "observe", data={"x": 1},
                actor="tester", owner_scope="scope:A",
            )

    def test_cognitive_stage_idempotent_retry_does_not_move_cursor_backward(self):
        cycle = self._seed_cycle()
        first = self.service.record_stage(
            cycle["id"], "observe", data={"x": 1},
            actor="tester", owner_scope="scope:A",
            idempotency_key=f"{cycle['id']}:observe:v1",
        )
        self.service.record_stage(
            cycle["id"], "interpret", data={"x": 2},
            actor="tester", owner_scope="scope:A",
            idempotency_key=f"{cycle['id']}:interpret:v1",
        )
        retry = self.service.record_stage(
            cycle["id"], "observe", data={"x": 1},
            actor="tester", owner_scope="scope:A",
            idempotency_key=f"{cycle['id']}:observe:v1",
        )
        self.assertEqual(retry["event"]["id"], first["event"]["id"])
        self.assertEqual(retry["cycle"]["current_stage"], "interpret")

    def test_completed_cognitive_cycle_requires_all_successful_stages(self):
        cycle = self._seed_cycle()
        self.service.record_stage(
            cycle["id"], "observe", data={"x": 1},
            actor="tester", owner_scope="scope:A",
        )
        with self.assertRaises(Exception):
            self.service.complete_cycle(
                cycle["id"], "completed",
                actor="tester", owner_scope="scope:A",
            )

        cycle2 = self._seed_cycle()
        self._record_all_stages(cycle2["id"])
        completed = self.service.complete_cycle(
            cycle2["id"], "completed",
            actor="tester", owner_scope="scope:A",
        )
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["current_stage"], "update_self_model")

    def test_cleanup_cannot_touch_foreign_learning(self):
        with self.assertRaises(NotFoundError):
            self.service.cleanup_learning_materialization(
                "learn_b", actor="scope:A", owner_scope="scope:A"
            )



if __name__ == "__main__":
    unittest.main()
