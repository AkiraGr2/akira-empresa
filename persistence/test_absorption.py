import unittest

from persistence.absorption import (
    AbsorptionContractError,
    validate_absorption_decision,
)


def valid_payload(**overrides):
    payload = {
        "decision": "CANDIDATE",
        "knowledge_kind": "semantic",
        "value": "Akira debe conservar una regla reutilizable.",
        "reason": "La información puede ser útil más adelante.",
        "confidence": 0.8,
        "novelty": 0.7,
        "reusability": 0.9,
        "evidence": [],
        "source": "chat",
        "source_id": "test-1",
        "safe_for_recall": False,
    }
    payload.update(overrides)
    return payload


class AbsorptionContractTests(unittest.TestCase):
    def test_valid_decision_normalizes_safe_for_recall(self):
        result = validate_absorption_decision(valid_payload())
        self.assertEqual(result["decision"], "CANDIDATE")
        self.assertFalse(result["safe_for_recall"])

    def test_rejects_unknown_fields(self):
        with self.assertRaises(AbsorptionContractError):
            validate_absorption_decision(valid_payload(extra="no"))

    def test_rejects_direct_recall(self):
        with self.assertRaises(AbsorptionContractError):
            validate_absorption_decision(valid_payload(safe_for_recall=True))

    def test_allows_empty_value_on_ignore(self):
        result = validate_absorption_decision(
            valid_payload(decision="IGNORE", knowledge_kind="unknown", value="")
        )
        self.assertEqual(result["decision"], "IGNORE")
        self.assertEqual(result["value"], "")

    def test_rejects_ignore_with_evidence(self):
        with self.assertRaises(AbsorptionContractError):
            validate_absorption_decision(
                valid_payload(
                    decision="IGNORE",
                    evidence=[{
                        "type": "test",
                        "title": "synthetic",
                        "reference": "selftest://absorption",
                        "note": "",
                    }],
                )
            )

    def test_rejects_out_of_range_scores(self):
        with self.assertRaises(AbsorptionContractError):
            validate_absorption_decision(valid_payload(confidence=1.1))

    def test_rejects_bad_evidence_shape(self):
        with self.assertRaises(AbsorptionContractError):
            validate_absorption_decision(valid_payload(evidence=[{"title": "missing reference"}]))


if __name__ == "__main__":
    unittest.main()
