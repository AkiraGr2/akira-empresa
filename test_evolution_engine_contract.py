import unittest

from persistence.core import (
    EVOLUTION_STATUSES,
    ValidationError,
    entity_spec,
    validate_evolution_record,
)
from persistence.service import PersistenceService


class FakeTx:
    def __init__(self, repo):
        self.repo = repo

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def create(self, entity, record):
        return self.repo._create(entity, record)

    def update(self, entity, record_id, changes, expected_version):
        return self.repo._update(entity, record_id, changes, expected_version)

    def append_audit(self, event):
        self.repo.audit.append(dict(event))


class FakeRepo:
    def __init__(self):
        self.tables = {"evolution_records": {}}
        self.audit = []

    def transaction(self):
        return FakeTx(self)

    def _create(self, entity, record):
        table = self.tables.setdefault(entity, {})
        key = record.get("idempotency_key")
        if key:
            for current in table.values():
                if (
                    current.get("idempotency_key") == key
                    and current.get("owner_scope") == record.get("owner_scope")
                ):
                    return dict(current), False
        table[record["id"]] = dict(record, version=1)
        return dict(table[record["id"]]), True

    def get(self, entity, record_id):
        row = self.tables.get(entity, {}).get(record_id)
        return dict(row) if row else None

    def search(self, entity, filters=None, limit=50, offset=0, order_by="created_at", descending=True):
        rows = [dict(v) for v in self.tables.get(entity, {}).values()]
        filters = filters or {}
        for key, value in filters.items():
            rows = [r for r in rows if r.get(key) == value]
        return rows[offset:offset + limit]

    def _update(self, entity, record_id, changes, expected_version):
        row = self.tables.get(entity, {}).get(record_id)
        if row is None:
            raise KeyError(record_id)
        if row["version"] != expected_version:
            from persistence.core import ConflictError
            raise ConflictError("version conflict")
        row = dict(row)
        row.update(changes)
        row["version"] += 1
        self.tables[entity][record_id] = row
        return dict(row)


class EvolutionEngineContractTests(unittest.TestCase):
    def setUp(self):
        self.service = PersistenceService(FakeRepo())

    def create(self, scope="scope:A", key=None):
        return self.service.create_evolution(
            {
                "target_component": "component.test",
                "detected_need": "Necesidad de prueba controlada.",
                "owner_scope": scope,
            },
            actor="owner@example.test",
            idempotency_key=key,
            owner_scope=scope,
        )

    def test_schema_contract_and_statuses(self):
        self.assertEqual(EVOLUTION_STATUSES[0], "detected")
        self.assertEqual(EVOLUTION_STATUSES[-1], "failed")
        self.assertIn("evolution_records", entity_spec("evolution_records"))
        record = validate_evolution_record({
            "target_component": "component.test",
            "detected_need": "Necesidad",
            "owner_scope": "scope:A",
        })
        self.assertEqual(record["status"], "detected")

    def test_idempotency_is_owner_scoped(self):
        first = self.create(scope="scope:A", key="evolution:idem:v1")
        second = self.create(scope="scope:A", key="evolution:idem:v1")
        third = self.create(scope="scope:B", key="evolution:idem:v1")
        self.assertEqual(first["outcome"], "created")
        self.assertEqual(second["outcome"], "already_synced")
        self.assertEqual(third["outcome"], "created")
        self.assertNotEqual(first["record"]["id"], third["record"]["id"])

    def test_owner_isolation_and_ordered_progression(self):
        rec = self.create(scope="scope:A")
        evolution_id = rec["record"]["id"]
        self.assertIsNone(self.service.get_evolution(evolution_id, owner_scope="scope:B"))

        with self.assertRaises(ValidationError):
            self.service.advance_evolution(
                evolution_id, "designing",
                expected_version=1,
                actor="owner@example.test",
                owner_scope="scope:A",
            )

        current = self.service.get_evolution(evolution_id, owner_scope="scope:A")
        for status, fields in (
            ("researching", {"research_reference": "research://test"}),
            ("designing", {"design": "Diseño mínimo"}),
            ("prototyping", {"prototype_reference": "prototype://test"}),
            ("testing", {"tests": [{"name": "contract", "status": "passed"}]}),
            ("evaluating", {"evaluation": {"verdict": "supported", "confidence": 0.95}}),
        ):
            current = self.service.update_evolution(
                evolution_id, fields, expected_version=current["version"],
                actor="owner@example.test", owner_scope="scope:A",
            )
            current = self.service.advance_evolution(
                evolution_id, status, expected_version=current["version"],
                actor="owner@example.test", owner_scope="scope:A",
            )

        self.assertEqual(current["status"], "evaluating")

    def test_apply_requires_human_approval_and_change_reference(self):
        rec = self.create()
        evolution_id = rec["record"]["id"]

        for status, fields in (
            ("researching", {"research_reference": "research://test"}),
            ("designing", {"design": "Diseño mínimo"}),
            ("prototyping", {"prototype_reference": "prototype://test"}),
            ("testing", {"tests": [{"name": "contract", "status": "passed"}]}),
            ("evaluating", {"evaluation": {"verdict": "supported", "confidence": 0.95}}),
        ):
            current = self.service.get_evolution(evolution_id, owner_scope="scope:A")
            current = self.service.update_evolution(
                evolution_id, fields, expected_version=current["version"],
                actor="owner@example.test", owner_scope="scope:A",
            )
            self.service.advance_evolution(
                evolution_id, status, expected_version=current["version"],
                actor="owner@example.test", owner_scope="scope:A",
            )

        with self.assertRaises(ValidationError):
            self.service.apply_evolution(
                evolution_id, "github:commit:test",
                actor="owner@example.test", owner_scope="scope:A",
            )

        approved = self.service.approve_evolution(
            evolution_id, actor="owner@example.test", owner_scope="scope:A"
        )
        self.assertEqual(approved["decision"]["status"], "approved")
        self.assertEqual(approved["decision"]["approved_by"], "owner@example.test")

        applied = self.service.apply_evolution(
            evolution_id, "github:commit:test",
            actor="owner@example.test", owner_scope="scope:A",
        )
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(applied["change_reference"], "github:commit:test")

        with self.assertRaises(ValidationError):
            self.service.advance_evolution(
                evolution_id, "failed",
                expected_version=applied["version"],
                actor="owner@example.test", owner_scope="scope:A",
            )

    def test_reject_requires_evaluating_state(self):
        rec = self.create()
        with self.assertRaises(ValidationError):
            self.service.reject_evolution(
                rec["record"]["id"], "sin evaluar",
                actor="owner@example.test", owner_scope="scope:A"
            )


if __name__ == "__main__":
    unittest.main()
