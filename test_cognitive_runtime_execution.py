import unittest
from unittest.mock import patch

import nexus


class FakeCognitiveService:
    def __init__(self, fail_self_model=False):
        self.fail_self_model = fail_self_model
        self.events = []
        self.cycle = {
            "id": "cycle_test",
            "current_stage": "observe",
            "status": "in_progress",
            "version": 1,
            "owner_scope": "scope:A",
        }
        self.completed_status = None
        self.self_model = {"current_state": {}, "version": 1}
        self.capability_verifications = []

    def start_cycle(self, trigger, input_data=None, actor="system", owner_scope=None):
        return {"outcome": "created", "record": dict(self.cycle)}

    def record_stage(self, cycle_id, stage, data=None, status="success", error=None,
                     actor="system", idempotency_key=None, owner_scope=None):
        self.events.append({
            "stage": stage,
            "status": status,
            "data": data or {},
            "error": error,
        })
        self.cycle["current_stage"] = stage
        self.cycle["version"] += 1
        return {
            "event": dict(self.events[-1], id="event_"+stage),
            "cycle": dict(self.cycle),
        }

    def save_learning(self, data, actor="system", idempotency_key=None, owner_scope=None):
        return {"outcome": "created", "record": {"id": "learn_test"}}

    def list_capabilities(self, filters=None, limit=100, offset=0):
        if self.with_capability and (filters or {}).get("name") == "cognitive_cycle_persistent":
            return [{
                "id": "cap_cognitive_test",
                "name": "cognitive_cycle_persistent",
                "verification_state": "unverified",
            }]
        return []

    def list_cycle_events(self, cycle_id, limit=100, owner_scope=None):
        return list(self.events)

    def record_capability_verification(self, capability_id, data, actor="system", idempotency_key=None):
        self.capability_verifications.append({
            "capability_id": capability_id,
            "data": data,
            "idempotency_key": idempotency_key,
        })
        return {
            "outcome": "created",
            "record": {"id": "capver_test"},
            "capability": {
                "id": capability_id,
                "verification_state": "verified",
            },
            "effective_state": "verified",
        }


    def get_self_model(self):
        return dict(self.self_model)

    def update_self_model(self, changes, expected_version, actor="system"):
        if self.fail_self_model:
            raise RuntimeError("synthetic self-model failure")
        self.self_model["current_state"] = changes["current_state"]
        self.self_model["version"] = expected_version + 1
        return dict(self.self_model)

    def complete_cycle(self, cycle_id, final_status="completed", actor="system", owner_scope=None):
        self.completed_status = final_status
        self.cycle["status"] = final_status
        return dict(self.cycle)

    def get_cycle(self, cycle_id, owner_scope=None):
        return dict(self.cycle)


class CognitiveExecutorTests(unittest.TestCase):
    def test_executor_persists_all_stages_in_order_and_completes(self):
        service = FakeCognitiveService()

        with patch.object(nexus, "_recall_memories", return_value=[]),              patch.object(nexus, "_run_reason_stage", return_value=("respuesta", "test-model")):
            result = nexus._execute_cognitive_cycle(
                service,
                "test",
                {"message": "hola"},
                actor="tester",
                owner_scope="scope:A",
            )

        self.assertEqual(
            [event["stage"] for event in service.events],
            [
                "observe", "interpret", "reason", "decide", "act",
                "observe_result", "evaluate", "learn", "update_self_model",
            ],
        )
        self.assertTrue(all(event["status"] == "success" for event in service.events))
        self.assertEqual(service.completed_status, "completed")
        self.assertEqual(result["cycle"]["status"], "completed")
        self.assertEqual(len(result["events"]), 9)
        self.assertEqual(result["learning_id"], "learn_test")

    def test_executor_cannot_hide_self_model_failure_as_completed(self):
        service = FakeCognitiveService(fail_self_model=True)

        with patch.object(nexus, "_recall_memories", return_value=[]),              patch.object(nexus, "_run_reason_stage", return_value=("respuesta", "test-model")):
            result = nexus._execute_cognitive_cycle(
                service,
                "test",
                {"message": "hola"},
                actor="tester",
                owner_scope="scope:A",
            )

        self.assertEqual(service.completed_status, "failed")
        self.assertEqual(result["cycle"]["status"], "failed")
        self.assertEqual(result["events"][-1]["stage"], "update_self_model")
        self.assertEqual(result["events"][-1]["status"], "failure")
        self.assertEqual(result["events"][-1]["error"]["type"], "RuntimeError")

    def test_unexpected_executor_failure_recovers_cycle_from_in_progress(self):
        service = FakeCognitiveService()

        with patch.object(nexus, "_recall_memories", return_value=[]), \
             patch.object(nexus, "_run_reason_stage", return_value=("respuesta", "test-model")), \
             patch.object(nexus, "enforce_akira_identity_global", side_effect=RuntimeError("synthetic executor failure")):
            result = nexus._execute_cognitive_cycle(
                service,
                "test",
                {"message": "hola"},
                actor="tester",
                owner_scope="scope:A",
            )

        self.assertEqual(service.completed_status, "failed")
        self.assertEqual(result["cycle"]["status"], "failed")
        self.assertEqual(result["error"]["type"], "RuntimeError")
        self.assertEqual(result["events"][-1]["stage"], "decide")
        self.assertLess(len(result["events"]), 9)


    def test_successful_cycle_records_cognitive_capability_e2e_evidence(self):
        service = FakeCognitiveService(with_capability=True)

        with patch.object(nexus, "_recall_memories", return_value=[]), \
             patch.object(nexus, "_run_reason_stage", return_value=("respuesta", "test-model")):
            result = nexus._execute_cognitive_cycle(
                service,
                "test",
                {"message": "hola"},
                actor="tester",
                owner_scope="scope:A",
            )

        self.assertEqual(service.completed_status, "completed")
        self.assertEqual(len(service.capability_verifications), 1)
        verification = service.capability_verifications[0]["data"]
        self.assertEqual(verification["test_key"], "cognitive_cycle_persistent_e2e")
        self.assertEqual(verification["result"], "pass")
        self.assertEqual(verification["evidence"][0]["type"], "e2e_test")
        self.assertEqual(verification["evidence"][0]["reference"], "cognitive_cycle:cycle_test")
        self.assertEqual(verification["environment"]["events_count"], 9)
        self.assertEqual(result["capability_verification"]["effective_state"], "verified")


if __name__ == "__main__":
    unittest.main()
