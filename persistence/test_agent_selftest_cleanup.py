"""Tests for scoped agent-task fixture cleanup in the production selftest."""
import unittest
from contextlib import contextmanager

from persistence.selftest import cleanup_agent_test_tasks


class FakeTaskRepository:
    def __init__(self, tasks, refuse_delete=None):
        self.tasks = dict(tasks)
        self.refuse_delete = refuse_delete
        self.audit = []

    @contextmanager
    def transaction(self):
        yield self

    def delete(self, entity, record_id):
        if entity != "agent_tasks" or record_id == self.refuse_delete:
            return False
        return self.tasks.pop(record_id, None) is not None

    def get(self, entity, record_id):
        if entity != "agent_tasks":
            return None
        return self.tasks.get(record_id)

    def append_audit(self, event):
        self.audit.append(event)


class FakeTaskService:
    def __init__(self, repo):
        self.repo = repo

    def get_task(self, task_id):
        return self.repo.get("agent_tasks", task_id)


class AgentSelftestCleanupTests(unittest.TestCase):
    def test_cleanup_deletes_only_current_run_fixtures_and_confirms_them(self):
        repo = FakeTaskRepository({
            "task_current": {"id": "task_current"},
            "task_historical": {"id": "task_historical"},
        })
        service = FakeTaskService(repo)

        result = cleanup_agent_test_tasks(service, ["task_current", "task_current"])

        self.assertTrue(result["ok"])
        self.assertEqual(result["attempted"], 1)
        self.assertEqual(result["deleted"], 1)
        self.assertEqual(repo.tasks, {"task_historical": {"id": "task_historical"}})
        self.assertEqual(repo.audit[0]["action"], "agent_task.fixture.delete")
        self.assertEqual(repo.audit[0]["status"], "success")
        self.assertTrue(repo.audit[0]["detail"]["absence_confirmed"])

    def test_cleanup_failure_is_visible_and_keeps_the_row(self):
        repo = FakeTaskRepository(
            {"task_current": {"id": "task_current"}},
            refuse_delete="task_current",
        )
        service = FakeTaskService(repo)

        result = cleanup_agent_test_tasks(service, ["task_current"])

        self.assertFalse(result["ok"])
        self.assertEqual(result["failures"][0]["reason"], "task_still_exists")
        self.assertIn("task_current", repo.tasks)
        self.assertEqual(repo.audit[0]["status"], "failure")
        self.assertFalse(repo.audit[0]["detail"]["absence_confirmed"])


if __name__ == "__main__":
    unittest.main()
