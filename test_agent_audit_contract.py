import unittest

from agent_audit import _audit_task


class FakeService:
    def __init__(self, agent_status="idle"):
        self.agent_status = agent_status
        self.task = {"id": "task_test", "status": "running", "version": 1}
        self.completed = False

    def get_agent_by_name(self, name):
        return {
            "name": "internal",
            "role": "internal",
            "description": "Introspección y ciclos cognitivos.",
            "allowed_tools": ["self_model_read", "cognitive_cycle"],
            "status": self.agent_status,
            "current_task_id": None if self.completed else "task_test",
        }

    def get_tool_by_name(self, name):
        return {
            "name": "self_model_read",
            "status": "available",
            "permissions": ["owner"],
            "inputs_schema": {},
            "outputs_schema": {"self_model": "dict"},
        }

    def create_task(self, *args, **kwargs):
        return {"outcome": "created", "record": dict(self.task)}

    def start_task(self, task_id, actor=None, owner_scope=None):
        self.task["status"] = "running"

    def complete_task(self, task_id, outputs=None, duration_ms=0, actor=None, owner_scope=None):
        self.completed = True
        self.task = {**self.task, "status": "completed", "outputs": outputs or {}}
        return dict(self.task)

    def fail_task(self, *args, **kwargs):
        self.task["status"] = "failed"

    def get_task(self, task_id, owner_scope=None):
        return dict(self.task)

    def get_learning(self, *args, **kwargs):
        return None

    def get_memory(self, *args, **kwargs):
        return None


class AgentAuditLifecycleTests(unittest.TestCase):
    def test_completed_agent_must_return_to_idle(self):
        service = FakeService("idle")

        def invoke(*args, **kwargs):
            return {
                "ok": True,
                "outputs": {
                    "self_model": {
                        "identity": {},
                        "capabilities": [],
                        "tools": [],
                        "models": {},
                    }
                },
                "persisted": True,
                "invocation_id": "inv_test",
                "error": None,
                "duration_ms": 1,
            }

        report = _audit_task(
            service, invoke, "owner@example.test", "scope:test",
            "agent_audit_test", "internal", "self_model_read", {},
            {}, 1,
        )
        self.assertTrue(report["checks"]["task_completed_and_persisted"])
        self.assertTrue(report["checks"]["agent_returned_idle"])
        self.assertEqual(report["verdict"], "VERIFIED")

    def test_busy_agent_after_completion_is_not_verified(self):
        service = FakeService("busy")

        def invoke(*args, **kwargs):
            return {
                "ok": True,
                "outputs": {
                    "self_model": {
                        "identity": {},
                        "capabilities": [],
                        "tools": [],
                        "models": {},
                    }
                },
                "persisted": True,
                "invocation_id": "inv_test",
                "error": None,
                "duration_ms": 1,
            }

        report = _audit_task(
            service, invoke, "owner@example.test", "scope:test",
            "agent_audit_test", "internal", "self_model_read", {},
            {}, 1,
        )
        self.assertFalse(report["checks"]["agent_returned_idle"])
        self.assertEqual(report["verdict"], "FAILED")


if __name__ == "__main__":
    unittest.main()
