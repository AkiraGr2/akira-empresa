import datetime as dt
import unittest

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


class CapabilityEngineContractTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
