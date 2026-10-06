import datetime as dt
from pathlib import Path
import unittest

from persistence.service import PersistenceService, ConflictError

from persistence.capability import (
    CapabilityContractError,
    apply_verification_result,
    derive_effective_state,
    effective_verification_state,
    validate_capability,
    validate_capability_state,
    validate_capability_transition,
)


def state(
    implementation_state="implemented",
    verification_state="unverified",
    availability_state="available",
    maturity="experimental",
    cost_compatibility="unknown",
):
    return {
        "implementation_state": implementation_state,
        "verification_state": verification_state,
        "availability_state": availability_state,
        "maturity": maturity,
        "cost_compatibility": cost_compatibility,
    }




class _CapabilityTx:
    def __init__(self, repo):
        self.repo = repo

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def create(self, entity, record):
        self.repo.rows.setdefault(entity, []).append(dict(record))
        return dict(record), True

    def append_audit(self, payload):
        return None


class _CapabilityRepo:
    def __init__(self):
        self.rows = {"capabilities": []}

    def search(self, entity, filters=None, limit=50, offset=0, order_by="created_at", descending=True):
        rows = [dict(row) for row in self.rows.get(entity, [])]
        for key, value in (filters or {}).items():
            rows = [row for row in rows if row.get(key) == value]
        return rows[offset:offset + limit]

    def transaction(self):
        return _CapabilityTx(self)

    def get(self, entity, record_id):
        for row in self.rows.get(entity, []):
            if row.get("id") == record_id:
                return dict(row)
        return None

    def append_audit(self, payload):
        return None


class CapabilityEngineContractTests(unittest.TestCase):
    def test_runtime_selftest_guard_receives_local_context(self):
        source = Path("persistence/selftest.py").read_text(encoding="utf-8")
        self.assertIn("def _guard(name, fn, service, created_ids):", source)
        self.assertIn("results.append(_guard(name, fn, service, created_ids))", source)

    def test_valid_capability_and_effective_state(self):
        record = validate_capability({
            "name": "ci_capability_contract",
            "description": "Contrato determinista del Capability Engine.",
            "category": "general",
            "kind": "composite",
            **state(),
            "dependencies": [],
            "limitations": [],
            "verification_spec": {
                "method": "selftest",
                "test_key": "ci_capability_contract",
                "freshness_policy": {
                    "mode": "on_change",
                    "max_age_seconds": None,
                    "invalidate_on": ["build_change"],
                },
            },
            "provenance": {"source": "ci", "created_by": "ci"},
        })
        self.assertEqual(record["verification_state"], "unverified")
        self.assertEqual(derive_effective_state(record), "implemented_unverified_available")

    def test_impossible_state_is_rejected(self):
        with self.assertRaises(CapabilityContractError):
            validate_capability_state(state(
                implementation_state="not_implemented",
                verification_state="verified",
                availability_state="available",
            ))

    def test_illegal_transition_is_rejected(self):
        with self.assertRaises(CapabilityContractError):
            validate_capability_transition(
                state(verification_state="unverified"),
                state(verification_state="stale"),
            )

    def test_valid_verification_transition_is_accepted(self):
        result = validate_capability_transition(
            state(verification_state="unverified"),
            state(verification_state="verified"),
        )
        self.assertEqual(result["verification_state"], "verified")

    def test_pass_verification_marks_capability_verified(self):
        current = {
            **state(),
            "verification_spec": {
                "freshness_policy": {
                    "mode": "on_change",
                    "max_age_seconds": None,
                    "invalidate_on": [],
                }
            },
        }
        event = {
            "event_type": "verification",
            "result": "pass",
            "evidence": [{
                "type": "ci",
                "title": "Capability contract",
                "reference": "ci:capability",
                "summary": "Contrato aprobado por CI.",
                "hash": "",
            }],
        }
        after = apply_verification_result(current, event)
        self.assertEqual(after["verification_state"], "verified")

    def test_invalidation_turns_verified_into_stale(self):
        current = {
            **state(verification_state="verified"),
            "verification_spec": {
                "freshness_policy": {
                    "mode": "on_change",
                    "max_age_seconds": None,
                    "invalidate_on": [],
                }
            },
        }
        event = {
            "event_type": "invalidation",
            "result": "fail",
            "evidence": [{
                "type": "ci",
                "title": "Invalidation",
                "reference": "ci:invalidation",
                "summary": "Cambio de dependencia.",
                "hash": "",
            }],
        }
        after = apply_verification_result(current, event)
        self.assertEqual(after["verification_state"], "stale")

    def test_time_based_freshness_expires_verified_state(self):
        verified_at = "2026-10-04T12:00:00+00:00"
        record = {
            **state(verification_state="verified"),
            "last_verified_at": verified_at,
            "verification_spec": {
                "freshness_policy": {
                    "mode": "time_based",
                    "max_age_seconds": 3600,
                    "invalidate_on": ["time"],
                }
            },
        }
        fresh_now = dt.datetime(2026, 10, 4, 12, 30, tzinfo=dt.timezone.utc)
        stale_now = dt.datetime(2026, 10, 4, 14, 1, tzinfo=dt.timezone.utc)
        self.assertEqual(effective_verification_state(record, now=fresh_now), "verified")
        self.assertEqual(effective_verification_state(record, now=stale_now), "stale")

    def test_partial_verified_effective_state_requires_available(self):
        record = {
            **state(
                implementation_state="partial",
                verification_state="verified",
                availability_state="available",
            ),
            "verification_spec": {
                "freshness_policy": {
                    "mode": "on_change",
                    "max_age_seconds": None,
                    "invalidate_on": [],
                }
            },
        }
        self.assertEqual(derive_effective_state(record), "partial_verified")


    def test_capability_registry_bootstrap_is_idempotent_by_name_and_key(self):
        service = PersistenceService(_CapabilityRepo())
        payload = {
            "name": "bootstrap_capability",
            "description": "Capability de prueba para bootstrap.",
            "category": "general",
            "kind": "intrinsic",
            "implementation_state": "implemented",
            "verification_state": "unverified",
            "availability_state": "available",
            "maturity": "experimental",
            "cost_compatibility": "unknown",
            "dependencies": [],
            "limitations": [],
            "verification_spec": {
                "method": "selftest",
                "test_key": "bootstrap_capability_contract",
                "freshness_policy": {
                    "mode": "on_change",
                    "max_age_seconds": None,
                    "invalidate_on": ["build_change"],
                },
            },
            "provenance": {"source": "ci", "created_by": "ci"},
        }
        first = service.create_capability(
            payload,
            actor="ci",
            idempotency_key="bootstrap:capability:bootstrap_capability:v1",
        )
        second = service.create_capability(
            payload,
            actor="ci",
            idempotency_key="bootstrap:capability:bootstrap_capability:v1",
        )
        self.assertEqual(first["outcome"], "created")
        self.assertEqual(second["outcome"], "already_synced")
        self.assertEqual(first["record"]["id"], second["record"]["id"])

    def test_capability_registry_rejects_conflicting_reuse_of_name(self):
        service = PersistenceService(_CapabilityRepo())
        payload = {
            "name": "conflicting_capability",
            "description": "Definicion A.",
            "category": "general",
            "kind": "intrinsic",
            "implementation_state": "implemented",
            "verification_state": "unverified",
            "availability_state": "available",
            "maturity": "experimental",
            "cost_compatibility": "unknown",
            "dependencies": [],
            "limitations": [],
            "verification_spec": {
                "method": "selftest",
                "test_key": "conflicting_capability_contract",
                "freshness_policy": {
                    "mode": "on_change",
                    "max_age_seconds": None,
                    "invalidate_on": [],
                },
            },
            "provenance": {"source": "ci", "created_by": "ci"},
        }
        service.create_capability(
            payload,
            actor="ci",
            idempotency_key="bootstrap:conflicting_capability:v1",
        )
        changed = dict(payload)
        changed["description"] = "Definicion B."
        with self.assertRaises(ConflictError):
            service.create_capability(
                changed,
                actor="ci",
                idempotency_key="bootstrap:conflicting_capability:v2",
            )


if __name__ == "__main__":
    unittest.main()
