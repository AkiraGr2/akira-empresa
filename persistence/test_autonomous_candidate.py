import asyncio
import unittest

import nexus


class FakeService:
    def __init__(self):
        self.calls = []

    def save_learning(self, data, actor, idempotency_key):
        self.calls.append(
            {
                "data": dict(data),
                "actor": actor,
                "idempotency_key": idempotency_key,
            }
        )
        return {
            "outcome": "created",
            "record": {"id": "learn_auto_test", **data},
        }


class AutonomousCandidateTests(unittest.IsolatedAsyncioTestCase):
    async def test_candidate_persists_candidate_only(self):
        previous_mode = nexus.ABSORPTION_MODE
        previous_decider = nexus._decide_absorption
        try:
            nexus.ABSORPTION_MODE = "candidate"
            nexus._decide_absorption = lambda *args, **kwargs: {
                "decision": "CANDIDATE",
                "knowledge_kind": "procedural",
                "value": "Regla autonoma de prueba.",
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
            service = FakeService()
            result = await nexus._run_absorption_candidate(
                "mensaje autonomo suficientemente largo para prueba",
                service,
                "owner@test",
                conversation_id="conv_test",
            )
            self.assertEqual(len(service.calls), 1)
            self.assertTrue(result["materialized_candidate"])
            payload = service.calls[0]["data"]
            self.assertEqual(payload["status"], "candidate")
            self.assertEqual(payload["source"], "autonomous_absorption")
            self.assertEqual(payload["evidence"], [])
            self.assertEqual(payload["knowledge_nodes"], [])
            self.assertEqual(payload["relationships"], [])
            self.assertEqual(payload["outcome"], "unknown")
        finally:
            nexus.ABSORPTION_MODE = previous_mode
            nexus._decide_absorption = previous_decider

    async def test_non_candidate_never_persists(self):
        previous_mode = nexus.ABSORPTION_MODE
        previous_decider = nexus._decide_absorption
        try:
            nexus.ABSORPTION_MODE = "candidate"
            for decision_name in ("IGNORE", "REINFORCE", "UPDATE", "CONFLICT"):
                nexus._decide_absorption = lambda *args, d=decision_name, **kwargs: {
                    "decision": d,
                    "knowledge_kind": "procedural",
                    "value": "valor",
                    "reason": "test",
                    "confidence": 0.9,
                    "novelty": 0.8,
                    "reusability": 0.8,
                    "evidence": [],
                    "source": "chat",
                    "source_id": "chat:" + d,
                    "target_learning_id": "learn_target" if d in ("REINFORCE", "UPDATE", "CONFLICT") else "",
                    "safe_for_recall": False,
                }
                service = FakeService()
                result = await nexus._run_absorption_candidate(
                    "mensaje autonomo suficientemente largo para prueba",
                    service,
                    "owner@test",
                )
                self.assertEqual(service.calls, [])
                self.assertEqual(result["decision"], decision_name)
        finally:
            nexus.ABSORPTION_MODE = previous_mode
            nexus._decide_absorption = previous_decider


if __name__ == "__main__":
    unittest.main()
