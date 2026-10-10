import unittest
from unittest.mock import patch

from github_readonly import (
    GitHubReadUpstreamError,
    GitHubReadValidationError,
    verify_applied_commit_reference,
)
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

    def make_evaluating(self, evolution_id):
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
        return current

    def test_schema_contract_and_statuses(self):
        self.assertEqual(EVOLUTION_STATUSES[0], "detected")
        self.assertEqual(EVOLUTION_STATUSES[-1], "failed")
        self.assertEqual(entity_spec("evolution_records")["table"], "evolution_records")
        record = validate_evolution_record({
            "target_component": "component.test",
            "detected_need": "Necesidad",
            "owner_scope": "scope:A",
        })
        self.assertEqual(record["status"], "detected")

    def test_creation_cannot_skip_detected_state(self):
        with self.assertRaises(ValidationError):
            self.service.create_evolution(
                {
                    "target_component": "component.test",
                    "detected_need": "No debe nacer en applied.",
                    "owner_scope": "scope:A",
                    "status": "applied",
                },
                actor="owner@example.test",
                owner_scope="scope:A",
            )

    def test_public_update_cannot_bypass_lifecycle_or_approval(self):
        rec = self.create()
        evolution_id = rec["record"]["id"]

        with self.assertRaises(ValidationError):
            self.service.update_evolution(
                evolution_id,
                {"status": "researching"},
                expected_version=1,
                actor="owner@example.test",
                owner_scope="scope:A",
            )
        with self.assertRaises(ValidationError):
            self.service.update_evolution(
                evolution_id,
                {"decision": {"status": "approved"}},
                expected_version=1,
                actor="owner@example.test",
                owner_scope="scope:A",
            )

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

        current = self.make_evaluating(evolution_id)

        with self.assertRaises(ValidationError):
            self.service.apply_evolution(
                evolution_id,
                "https://github.com/AkiraGr2/akira-empresa/commit/" + "a" * 40,
                actor="owner@example.test", owner_scope="scope:A",
            )

        approved = self.service.approve_evolution(
            evolution_id, actor="owner@example.test", owner_scope="scope:A"
        )
        self.assertEqual(approved["decision"]["status"], "approved")
        self.assertEqual(approved["decision"]["approved_by"], "owner@example.test")

        commit_sha = "a" * 40
        base_sha = "b" * 40
        reference = f"https://github.com/AkiraGr2/akira-empresa/commit/{commit_sha}"
        with patch("github_readonly._head_commit_sha", return_value=base_sha), patch(
            "github_readonly._get_json",
            side_effect=[
                {"sha": commit_sha},
                {"merge_base_commit": {"sha": commit_sha}},
            ],
        ):
            applied = self.service.apply_evolution(
                evolution_id, reference,
                actor="owner@example.test", owner_scope="scope:A",
            )
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(applied["change_reference"], reference)
        self.assertEqual(
            applied["evaluation"]["change_reference_verification"]["commit_sha"],
            commit_sha,
        )
        self.assertTrue(
            applied["evaluation"]["change_reference_verification"]["applied_to_base"]
        )

        with self.assertRaises(ValidationError):
            self.service.advance_evolution(
                evolution_id, "failed",
                expected_version=applied["version"],
                actor="owner@example.test", owner_scope="scope:A",
            )

    def test_commit_reference_rejects_noncanonical_and_missing_commits(self):
        with patch("github_readonly._get_json") as get_json:
            with self.assertRaises(GitHubReadValidationError):
                verify_applied_commit_reference("github:commit:test")
            get_json.assert_not_called()

        with patch(
            "github_readonly._get_json",
            side_effect=GitHubReadUpstreamError("not_found"),
        ):
            with self.assertRaises(GitHubReadValidationError):
                verify_applied_commit_reference(
                    "https://github.com/AkiraGr2/akira-empresa/commit/" + "a" * 40
                )

    def test_commit_reference_must_be_reachable_from_main(self):
        commit_sha = "a" * 40
        with patch("github_readonly._head_commit_sha", return_value="b" * 40), patch(
            "github_readonly._get_json",
            side_effect=[
                {"sha": commit_sha},
                {"merge_base_commit": {"sha": "c" * 40}},
            ],
        ):
            with self.assertRaises(GitHubReadValidationError):
                verify_applied_commit_reference(
                    f"https://github.com/AkiraGr2/akira-empresa/commit/{commit_sha}"
                )

    def test_advance_cannot_bypass_commit_verification(self):
        rec = self.create()
        evolution_id = rec["record"]["id"]
        current = self.make_evaluating(evolution_id)
        current = self.service.update_evolution(
            evolution_id,
            {"change_reference": "github:commit:test"},
            expected_version=current["version"],
            actor="owner@example.test",
            owner_scope="scope:A",
        )
        approved = self.service.approve_evolution(
            evolution_id, actor="owner@example.test", owner_scope="scope:A"
        )
        with self.assertRaises(ValidationError):
            self.service.advance_evolution(
                evolution_id, "applied",
                expected_version=approved["version"],
                actor="owner@example.test", owner_scope="scope:A",
            )
        current = self.service.get_evolution(evolution_id, owner_scope="scope:A")
        self.assertEqual(current["status"], "evaluating")
        self.assertEqual(current["version"], approved["version"])

    def test_reject_requires_evaluating_state(self):
        rec = self.create()
        with self.assertRaises(ValidationError):
            self.service.reject_evolution(
                rec["record"]["id"], "sin evaluar",
                actor="owner@example.test", owner_scope="scope:A"
            )


if __name__ == "__main__":
    unittest.main()
