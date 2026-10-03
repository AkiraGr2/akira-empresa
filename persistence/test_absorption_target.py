import unittest

from persistence.absorption import (
    AbsorptionContractError,
    validate_absorption_decision,
    validate_absorption_target,
)


def _base(decision, **extra):
    payload = {
        "decision": decision,
        "knowledge_kind": "semantic",
        "value": "valor de prueba suficientemente estable",
        "reason": "caso de prueba",
        "confidence": 0.9,
        "novelty": 0.5,
        "reusability": 0.8,
        "evidence": [],
        "source": "chat",
        "source_id": "chat:test",
        "safe_for_recall": False,
    }
    payload.update(extra)
    return payload


class AbsorptionTargetIdentityTests(unittest.TestCase):
    def test_update_requires_target_learning_id(self):
        with self.assertRaises(AbsorptionContractError):
            validate_absorption_decision(_base("UPDATE"))

    def test_reinforce_requires_target_learning_id(self):
        with self.assertRaises(AbsorptionContractError):
            validate_absorption_decision(_base("REINFORCE"))

    def test_conflict_requires_target_learning_id(self):
        with self.assertRaises(AbsorptionContractError):
            validate_absorption_decision(_base("CONFLICT"))

    def test_update_accepts_explicit_target(self):
        result = validate_absorption_decision(
            _base("UPDATE", target_learning_id="learn_123")
        )
        self.assertEqual(result["target_learning_id"], "learn_123")

    def test_candidate_rejects_target(self):
        with self.assertRaises(AbsorptionContractError):
            validate_absorption_decision(
                _base("CANDIDATE", target_learning_id="learn_123")
            )

    def test_ignore_rejects_target(self):
        with self.assertRaises(AbsorptionContractError):
            validate_absorption_decision(
                _base("IGNORE", value="", target_learning_id="learn_123")
            )
    def test_target_must_be_presented_by_server(self):
        with self.assertRaises(AbsorptionContractError):
            validate_absorption_target("learn_123", ["learn_999"])

    def test_target_allowlist_accepts_presented_id(self):
        self.assertEqual(
            validate_absorption_target("learn_123", ["learn_123", "learn_999"]),
            "learn_123",
        )



if __name__ == "__main__":
    unittest.main()
