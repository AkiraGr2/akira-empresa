"""Free, isolated F12 API + PostgreSQL integration test.

Safety: refuses any DATABASE_URL that is not loopback. GitHub Actions supplies a
throwaway pgvector/PostgreSQL service container; production credentials are never used.
"""
from __future__ import annotations

import os
import unittest
from urllib.parse import urlparse
from unittest.mock import patch

# This key is test-only and must never be configured in a deployed environment.
os.environ["AKIRA_SESSION_SECRET"] = "f12-e2e-test-only-secret-never-use-in-production-2026"
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@127.0.0.1:5432/akira_f12_test",
)
if urlparse(DATABASE_URL).hostname not in {"127.0.0.1", "localhost"}:
    raise RuntimeError("F12 E2E tests refuse non-local DATABASE_URL; production access is prohibited")
os.environ["DATABASE_URL"] = DATABASE_URL

import akira_auth  # noqa: E402
import nexus  # noqa: E402
import specialized_agent_tools  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from persistence.postgres import PostgresRepository, make_pool, migrate  # noqa: E402
from persistence.selftest import run_relation_integrity_test  # noqa: E402
from persistence.service import PersistenceService  # noqa: E402


class F12RepairPostgresApiE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pool = make_pool(DATABASE_URL)
        cls.pool.open(wait=True, timeout=30)
        migrate(cls.pool)
        cls.repo = PostgresRepository(cls.pool)
        cls.service = PersistenceService(cls.repo)

        # Seed only disposable fixture data in this empty CI database.
        cls.self_model = cls.service.get_self_model()
        tool = cls.service.register_tool(
            {
                "name": "python_test",
                "description": "Synthetic tool used only by F12 CI fixture",
                "category": "code",
                "permissions": ["owner"],
                "inputs_schema": {"tests": "list"},
                "outputs_schema": {"status": "str"},
                "limits_json": {"max_tests": 6},
                "risks": [],
                "status": "available",
            },
            actor="f12-ci-setup",
            idempotency_key="f12-ci-python-test-tool",
        )
        cls.tool_id = tool["record"]["id"]
        agent = cls.service.register_agent(
            {
                "name": "selftest_agent",
                "role": "generic",
                "description": "Synthetic self-test agent; safe to mutate only in this CI database",
                "allowed_tools": ["python_test"],
                "status": "idle",
                "current_task_id": None,
                "current_action": None,
                "tasks_completed": 0,
                "tasks_failed": 0,
            },
            actor="f12-ci-setup",
            idempotency_key="f12-ci-selftest-agent",
        )
        cls.agent_id = agent["record"]["id"]
        cls.repair_id = None

        # A second independently opened pool proves postconditions and audit data
        # are persisted and readable beyond the request/service instance.
        cls.fresh_pool = make_pool(DATABASE_URL)
        cls.fresh_pool.open(wait=True, timeout=30)
        cls.fresh_repo = PostgresRepository(cls.fresh_pool)
        cls.fresh_service = PersistenceService(cls.fresh_repo)

    @classmethod
    def tearDownClass(cls):
        # Remove the synthetic fixture, leaving only audit evidence in the
        # temporary database. The entire database container is destroyed by CI.
        try:
            if getattr(cls, "repair_id", None):
                current = cls.service.get_self_model()
                repairs = [
                    r for r in (current.get("repairs") or [])
                    if r.get("id") != cls.repair_id
                ]
                if repairs != (current.get("repairs") or []):
                    cls.service.update_self_model(
                        {"repairs": repairs},
                        current["version"],
                        actor="f12-ci-cleanup",
                    )
            if getattr(cls, "agent_id", None):
                cls.repo.delete("agents", cls.agent_id)
            if getattr(cls, "tool_id", None):
                cls.repo.delete("tools", cls.tool_id)
            if getattr(cls, "self_model", None):
                cls.repo.delete("self_model", cls.self_model["id"])
        finally:
            for name in ("fresh_pool", "pool"):
                pool = getattr(cls, name, None)
                if pool is not None:
                    pool.close()

    def test_complete_authenticated_repair_cycle_persists_and_reads_back(self):
        client = TestClient(nexus.app)
        owner_email = "ci-owner@example.test"
        token, _expires, reason = akira_auth.issue_session(
            sub="f12-postgres-e2e-synthetic-owner",
            email=owner_email,
        )
        self.assertIsNone(reason)
        self.assertTrue(token)
        headers = {"Authorization": f"Bearer {token}"}

        # The actual HTTP API must reject unauthenticated access first.
        unauthenticated = client.get("/api/v8/repair")
        self.assertEqual(unauthenticated.status_code, 401)

        with patch.object(nexus, "OWNER_EMAILS", [owner_email]), patch(
            "nexus._persistence_service", return_value=self.service
        ):
            created = client.post(
                "/api/v8/repair",
                headers=headers,
                json={
                    "target": "selftest_agent",
                    "reason": "F12 disposable PostgreSQL end-to-end fixture",
                    "action_type": "disable_selftest_agent",
                    # These client-controlled identity fields must be ignored.
                    "owner_scope": "attacker-scope",
                    "actor": "attacker@example.test",
                },
            )
            self.assertEqual(created.status_code, 200, created.text)
            self.assertTrue(created.json().get("ok"))
            repair = created.json()["repair"]
            self.__class__.repair_id = repair["id"]
            self.assertEqual(repair["owner_scope"], "owner")
            self.assertEqual(repair["stage"], "detected")

            for stage in ("diagnosed", "isolated", "proposed"):
                payload = {"stage": stage}
                if stage == "proposed":
                    payload["proposal"] = {"action_type": "disable_selftest_agent"}
                response = client.post(
                    f"/api/v8/repair/{repair['id']}/advance",
                    headers=headers,
                    json=payload,
                )
                self.assertEqual(response.status_code, 200, response.text)
                self.assertTrue(response.json().get("ok"), response.text)

            sandboxed = client.post(
                f"/api/v8/repair/{repair['id']}/sandbox",
                headers=headers,
            )
            self.assertEqual(sandboxed.status_code, 200, sandboxed.text)
            self.assertEqual(sandboxed.json()["repair"]["stage"], "sandboxed")

            # Run the allowlisted contract tests for real in a child process.
            tested = client.post(
                f"/api/v8/repair/{repair['id']}/test",
                headers=headers,
            )
            self.assertEqual(tested.status_code, 200, tested.text)
            self.assertEqual(tested.json()["repair"]["stage"], "tested")
            self.assertEqual(tested.json()["repair"]["tests"]["status"], "passed")

            evaluated = client.post(
                f"/api/v8/repair/{repair['id']}/evaluate",
                headers=headers,
            )
            self.assertEqual(evaluated.status_code, 200, evaluated.text)
            self.assertEqual(evaluated.json()["repair"]["stage"], "evaluated")
            self.assertFalse(evaluated.json()["repair"]["evaluation"]["code_mutation_allowed"])

            approved = client.post(
                f"/api/v8/repair/{repair['id']}/approve",
                headers=headers,
            )
            self.assertEqual(approved.status_code, 200, approved.text)
            self.assertEqual(approved.json()["repair"]["stage"], "approved")
            self.assertEqual(approved.json()["repair"]["status"], "approved")

            with patch.object(
                self.service, "save_learning", return_value={"outcome": "created"}
            ) as save_learning:
                applied = client.post(
                    f"/api/v8/repair/{repair['id']}/apply",
                    headers=headers,
                )
                save_learning.assert_called_once()
            self.assertEqual(applied.status_code, 200, applied.text)
            result = applied.json()["repair"]
            self.assertEqual(result["stage"], "applied")
            self.assertEqual(result["status"], "completed")
            self.assertIn("postcondition_verified", result["result"])
            self.assertIn("apply_postcondition_verified", result["evidence"])

        # Independently re-read from a separate pool/connection, not the object
        # that handled the API requests.
        persisted = self.fresh_service.get_repair(
            self.__class__.repair_id,
            owner_scope="owner",
        )
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted["stage"], "applied")
        self.assertEqual(persisted["status"], "completed")
        self.assertIn("postcondition_verified", persisted["result"])

        agent = self.fresh_service.get_agent_by_name("selftest_agent")
        self.assertIsNotNone(agent)
        self.assertEqual(agent["status"], "disabled")

        repair_events = self.fresh_repo.audit_search(action_prefix="repair.", limit=100)
        apply_event = next(
            (
                e for e in repair_events
                if e["action"] == "repair.apply"
                and (e.get("detail") or {}).get("repair_id") == self.__class__.repair_id
            ),
            None,
        )
        postcondition_event = next(
            (
                e for e in repair_events
                if e["action"] == "repair.apply.postcondition"
                and e.get("resource_id") == self.__class__.repair_id
            ),
            None,
        )
        self.assertIsNotNone(apply_event, "repair.apply audit event was not persisted")
        self.assertIsNotNone(postcondition_event, "repair.apply.postcondition audit event was not persisted")
        self.assertEqual(postcondition_event["status"], "success")
        self.assertTrue(postcondition_event["detail"]["postcondition_verified"])
        self.assertEqual(apply_event["actor"], owner_email)

        client.close()
        print(
            "F12_POSTGRES_E2E_PASS "
            f"repair_id={self.__class__.repair_id} "
            "auth=verified lifecycle=applied fresh_readback=verified "
            "audit=verified synthetic_fixture=cleanup_on_teardown"
        )

    def test_cross_phase_relation_integrity_against_postgres(self):
        result = run_relation_integrity_test(self.service)

        self.assertEqual(result["status"], "PASS", result["detail"])
        self.assertIn("'cleanup': True", result["detail"])
        print(
            "F12_RELATION_INTEGRITY_POSTGRES_PASS "
            "cycle=learning=knowledge=graph verified synthetic_fixture=cleanup"
        )


if __name__ == "__main__":
    unittest.main()
