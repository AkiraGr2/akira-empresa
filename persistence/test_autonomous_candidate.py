import unittest

from persistence.absorption import (
    AbsorptionContractError,
    build_autonomous_candidate,
)


def _decision(**overrides):
    value = {
        "decision": "CANDIDATE",
        "knowledge_kind": "procedural",
        "value": "Regla autonoma de prueba suficientemente durable.",
        "reason": "util para el proyecto",
        "confidence": 0.9,
        "novelty": 0.8,
        "reusability": 0.9,
        "evidence": [],
        "source": "chat",
        "source_id": "chat:test-source-1",
        "target_learning_id": "",
        "safe_for_recall": False,
    }
    value.update(overrides)
    return value


class AutonomousCandidateTests(unittest.TestCase):
    def test_builds_candidate_only(self):
        result = build_autonomous_candidate(
            _decision(),
            conversation_id="conv_test",
        )
        payload = result["learning"]
        self.assertEqual(payload["status"], "candidate")
        self.assertEqual(payload["source"], "autonomous_absorption")
        self.assertEqual(payload["evidence"], [])
        self.assertEqual(payload["knowledge_nodes"], [])
        self.assertEqual(payload["relationships"], [])
        self.assertEqual(payload["outcome"], "unknown")
        self.assertEqual(payload["learning_context"]["conversation_id"], "conv_test")
        self.assertTrue(result["idempotency_key"].startswith("absorption_candidate_"))

    def test_non_candidate_rejected(self):
        for decision in ("IGNORE", "REINFORCE", "UPDATE", "CONFLICT"):
            with self.assertRaises(AbsorptionContractError):
                build_autonomous_candidate(
                    _decision(
                        decision=decision,
                        value="" if decision == "IGNORE" else "valor",
                        target_learning_id=(
                            "learn_target"
                            if decision in ("REINFORCE", "UPDATE", "CONFLICT")
                            else ""
                        ),
                    )
                )

    def test_same_source_id_reuses_idempotency_key(self):
        first = build_autonomous_candidate(_decision(source_id="chat:stable"))
        second = build_autonomous_candidate(_decision(source_id="chat:stable"))
        self.assertEqual(first["idempotency_key"], second["idempotency_key"])

    def test_different_source_id_gets_different_idempotency_key(self):
        first = build_autonomous_candidate(_decision(source_id="chat:a"))
        second = build_autonomous_candidate(_decision(source_id="chat:b"))
        self.assertNotEqual(first["idempotency_key"], second["idempotency_key"])


if __name__ == "__main__":
    unittest.main()
