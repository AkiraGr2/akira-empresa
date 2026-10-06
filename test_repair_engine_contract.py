import unittest
from unittest.mock import patch

from persistence.repair import REPAIR_STAGES, REPAIR_STAGE_TRANSITIONS
from persistence.service import NotFoundError, PersistenceService, ValidationError


class FakeTx:
    def __init__(self, repo):
        self.repo = repo

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def update(self, entity, record_id, changes, expected_version):
        row = next(r for r in self.repo.rows[entity] if r["id"] == record_id)
        if row["version"] != expected_version:
            raise RuntimeError("version conflict")
        row.update(changes)
        row["version"] += 1
        return dict(row)

    def create(self, entity, record):
        row = dict(record)
        row.setdefault("version", 1)
        self.repo.rows.setdefault(entity, []).append(row)
        return dict(row), True

    def append_audit(self, payload):
        self.repo.audits.append(dict(payload))


class FakeRepo:
    def __init__(self):
        self.audits = []
        self.rows = {
            "self_model": [{
                "id": "akira_primary",
                "schema_version": "self_model.v2",
                "purpose": {},
                "current_state": {},
                "knowledge_state": {},
                "uncertainties": [],
                "errors": [],
                "repairs": [],
                "evolution": [],
                "version": 1,
            }],
            "identity_root": [{
                "id": "identity_root_primary",
                "canonical_name": "Akira",
                "creator": "Jhon Grimm",
                "essence": "Colmena cognitiva personal. Persistente, verificable, honesta sobre sus capacidades.",
                "language": "es-CO",
                "root_schema_version": "identity_root.v1",
                "status": "active",
            }],
            "capabilities": [{
                "id": "cap1",
                "name": "repair_test_dependency",
                "implementation_state": "implemented",
                "verification_state": "verified",
                "availability_state": "available",
                "maturity": "experimental",
                "cost_compatibility": "free",
                "last_verified_at": "2026-10-06T00:00:00+00:00",
            }],
            "tools": [{
                "id": "tool_test",
                "name": "python_test",
                "category": "code",
                "status": "available",
                "permissions": ["owner"],
            }],
            "agents": [{
                "id": "agent_selftest",
                "name": "selftest_agent",
                "role": "generic",
                "description": "Agente de autopruebas.",
                "allowed_tools": ["python_test"],
                "status": "idle",
                "current_task_id": None,
                "current_action": None,
                "tasks_completed": 0,
                "tasks_failed": 0,
                "version": 1,
            }],
            "agent_tasks": [],
            "learning_events": [],
        }

    def get(self, entity, record_id):
        for row in self.rows.get(entity, []):
            if row.get("id") == record_id:
                return dict(row)
        return None

    def search(self, entity, filters=None, limit=100, offset=0, order_by="created_at", descending=True):
        rows = [dict(r) for r in self.rows.get(entity, [])]
        for key, value in (filters or {}).items():
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


class RepairEngineContractTests(unittest.TestCase):
    def setUp(self):
        self.repo = FakeRepo()
        self.service = PersistenceService(self.repo)

    def test_stage_machine_declares_full_controlled_lifecycle(self):
        self.assertEqual(
            REPAIR_STAGES,
            ("detected", "diagnosed", "isolated", "proposed", "sandboxed",
             "tested", "evaluated", "approved", "applied", "discarded", "failed"),
        )
        self.assertEqual(REPAIR_STAGE_TRANSITIONS["detected"], {"diagnosed", "failed", "discarded"})
        self.assertEqual(REPAIR_STAGE_TRANSITIONS["approved"], {"applied", "discarded", "failed"})

    def test_repair_lifecycle_reaches_applied_with_explicit_approval(self):
        repair = self.service.create_repair(
            target="selftest_agent",
            reason="recuperar estado controlado",
            action_type="disable_selftest_agent",
            actor="owner@example.test",
            owner_scope="scope:A",
        )
        self.assertEqual(repair["stage"], "detected")
        repair = self.service.advance_repair(
            repair["id"], "diagnosed", actor="owner@example.test", owner_scope="scope:A"
        )
        repair = self.service.advance_repair(
            repair["id"], "isolated", actor="owner@example.test", owner_scope="scope:A"
        )
        repair = self.service.advance_repair(
            repair["id"], "proposed", actor="owner@example.test", owner_scope="scope:A",
            proposal={"action_type": "disable_selftest_agent"},
        )
        repair = self.service.sandbox_repair(
            repair["id"], actor="owner@example.test", owner_scope="scope:A"
        )
        self.assertEqual(repair["stage"], "sandboxed")

        with patch("specialized_agent_tools.run_python_tests", return_value={"status": "passed", "tests": ["ok"]}):
            repair = self.service.test_repair(
                repair["id"], actor="owner@example.test", owner_scope="scope:A"
            )
        repair = self.service.evaluate_repair(
            repair["id"], actor="owner@example.test", owner_scope="scope:A"
        )
        self.assertEqual(repair["stage"], "evaluated")

        repair = self.service.approve_repair(
            repair["id"], actor="owner@example.test", owner_scope="scope:A"
        )
        self.assertEqual(repair["status"], "approved")

        with patch.object(self.service, "save_learning", return_value={"outcome": "created"}):
            repair = self.service.apply_repair(
                repair["id"], actor="owner@example.test", owner_scope="scope:A"
            )

        self.assertEqual(repair["stage"], "applied")
        self.assertEqual(repair["status"], "completed")
        agent = self.repo.get("agents", "agent_selftest")
        self.assertEqual(agent["status"], "disabled")

    def test_repair_requires_explicit_approval_before_apply(self):
        repair = self.service.create_repair(
            "selftest_agent", "test", "disable_selftest_agent",
            actor="owner@example.test", owner_scope="scope:A",
        )
        with self.assertRaises(ValidationError):
            self.service.apply_repair(
                repair["id"], actor="owner@example.test", owner_scope="scope:A"
            )

    def test_repair_is_strictly_owner_scoped(self):
        repair = self.service.create_repair(
            "selftest_agent", "test", "disable_selftest_agent",
            actor="owner@example.test", owner_scope="scope:A",
        )
        self.assertIsNone(self.service.get_repair(repair["id"], owner_scope="scope:B"))
        with self.assertRaises(NotFoundError):
            self.service.advance_repair(
                repair["id"], "diagnosed", actor="other@example.test", owner_scope="scope:B"
            )

    def test_unsupported_or_invalid_actions_are_rejected(self):
        with self.assertRaises(ValidationError):
            self.service.create_repair(
                "github", "mutation", "write_github",
                actor="owner@example.test", owner_scope="scope:A",
            )

    def test_sandbox_fails_closed_when_precondition_is_absent(self):
        repair = self.service.create_repair(
            "selftest_agent", "missing target", "detach_orphan_selftest_task",
            actor="owner@example.test", owner_scope="scope:A",
        )
        self.service.advance_repair(repair["id"], "diagnosed", actor="owner@example.test", owner_scope="scope:A")
        self.service.advance_repair(repair["id"], "isolated", actor="owner@example.test", owner_scope="scope:A")
        self.service.advance_repair(
            repair["id"], "proposed", actor="owner@example.test",
            owner_scope="scope:A", proposal={"task_id": "missing_task"},
        )
        failed = self.service.sandbox_repair(
            repair["id"], actor="owner@example.test", owner_scope="scope:A"
        )
        self.assertEqual(failed["stage"], "failed")
        self.assertEqual(failed["status"], "failed")


if __name__ == "__main__":
    unittest.main()
