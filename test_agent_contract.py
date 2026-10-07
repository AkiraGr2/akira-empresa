import unittest
from unittest.mock import patch

from agent_contracts import AGENT_CONTRACTS, PRODUCTION_AGENT_ORDER, validate_agent_definition, validate_agent_result
from nexus import _AGENT_SEED, _invoke_registered_tool
from persistence.core import validate_agent


class AgentContractTests(unittest.TestCase):
    def test_all_production_agent_seeds_match_contracts(self):
        seeded = {item["name"]: item for item in _AGENT_SEED}
        self.assertEqual(set(PRODUCTION_AGENT_ORDER), set(seeded))
        for name in PRODUCTION_AGENT_ORDER:
            ok, failures = validate_agent_definition({**seeded[name], "status": "idle"})
            self.assertTrue(ok, f"{name}: {failures}")
            self.assertEqual(seeded[name]["allowed_tools"], AGENT_CONTRACTS[name]["allowed_tools"])

    def test_autonomy_orchestrator_role_is_valid(self):
        record = validate_agent({
            "name": "autonomy_orchestrator",
            "role": "autonomy_orchestrator",
            "description": "Orquestador controlado.",
            "allowed_tools": ["controlled_autonomy_start"],
        })
        self.assertEqual(record["role"], "autonomy_orchestrator")

    def test_researcher_web_search_requires_real_references(self):
        ok, _ = validate_agent_result(
            "researcher",
            "web_search",
            {
                "result": {
                    "query": "FastAPI",
                    "result_count": 0,
                    "results": [],
                }
            },
        )
        self.assertFalse(ok)

        ok, _ = validate_agent_result(
            "researcher",
            "web_search",
            {
                "result": {
                    "query": "FastAPI",
                    "result_count": 1,
                    "results": [{"reference": "https://fastapi.tiangolo.com/", "title": "FastAPI"}],
                }
            },
        )
        self.assertTrue(ok)

    def test_researcher_web_search_rejects_incoherent_result_count(self):
        ok, _ = validate_agent_result(
            "researcher",
            "web_search",
            {
                "result": {
                    "query": "FastAPI",
                    "result_count": 2,
                    "results": [{"reference": "https://fastapi.tiangolo.com/", "title": "FastAPI"}],
                }
            },
        )
        self.assertFalse(ok)

    def test_shared_capabilities_are_verified_for_every_allowed_agent(self):
        github_output = {
            "result": {
                "ok": True,
                "files": [{"path": "test_agent_contract.py"}],
                "root": [],
                "head_commit_sha": "a" * 40,
            }
        }
        for agent_name in ("researcher", "developer", "tester", "reviewer"):
            self.assertTrue(
                validate_agent_result(agent_name, "github_repo_read", github_output)[0],
                agent_name,
            )

        python_output = {"status": "passed", "tests": [{"name": "example", "status": "passed"}]}
        for agent_name in ("tester", "reviewer"):
            self.assertTrue(
                validate_agent_result(agent_name, "python_test", python_output)[0],
                agent_name,
            )

        memory_output = {"results": [{"id": "mem_1", "content": "audit"}], "found": 1}
        for agent_name in ("researcher", "memorizer"):
            self.assertTrue(
                validate_agent_result(agent_name, "memory_search", memory_output)[0],
                agent_name,
            )

    def test_autonomy_fail_closed_is_a_verified_safety_outcome(self):
        ok, detail = validate_agent_result(
            "autonomy_orchestrator",
            "controlled_autonomy_start",
            {
                "autonomy": {
                    "status": "failed",
                    "failure_reason": "proposal_path_outside_requested_scope",
                    "id": "autonomy_test",
                },
                "awaits_human_approval": False,
                "external_write_performed": False,
            },
        )
        self.assertTrue(ok)
        self.assertEqual(detail["verification_mode"], "fail_closed")

    def test_semantic_contract_rejects_apparent_success(self):
        ok, _ = validate_agent_result(
            "developer",
            "developer_propose",
            {
                "proposal": {
                    "status": "proposal",
                    "write_performed": True,
                    "requires_human_approval": True,
                }
            },
        )
        self.assertFalse(ok)

        ok, _ = validate_agent_result(
            "autonomy_orchestrator",
            "controlled_autonomy_start",
            {
                "autonomy": {"status": "awaiting_approval"},
                "awaits_human_approval": True,
                "external_write_performed": True,
            },
        )
        self.assertFalse(ok)

    def test_registered_tool_fails_closed_when_invocation_persistence_fails(self):
        service = type("Service", (), {})()
        service.get_tool_by_name = lambda name: {
            "name": "self_model_read",
            "status": "available",
            "permissions": ["owner"],
            "inputs_schema": {},
            "outputs_schema": {"self_model": "dict"},
        }
        service.get_invocation_by_idempotency_key = lambda *args: None

        def fail_persist(*args, **kwargs):
            raise RuntimeError("database unavailable")

        service.log_invocation = fail_persist

        with patch("nexus._invoke_tool", return_value=({"self_model": {}}, None)):
            result = _invoke_registered_tool(
                service,
                "self_model_read",
                {},
                actor="agent:internal",
                owner_scope="scope:test",
                idempotency_key="f9-persist-failure",
            )

        self.assertFalse(result["ok"])
        self.assertFalse(result["persisted"])
        self.assertEqual(result["error"]["type"], "RuntimeError")
        self.assertEqual(result["error"]["message"], "tool invocation persistence failed")


class AgentContractExecutionEnvelopeTests(unittest.TestCase):
    def test_internal_self_model_envelope_is_semantically_checked(self):
        ok, _ = validate_agent_result(
            "internal",
            "self_model_read",
            {"self_model": {"identity": {}, "capabilities": [], "tools": [], "models": {}}},
        )
        self.assertTrue(ok)

    def test_tester_failed_result_is_not_verified(self):
        ok, _ = validate_agent_result(
            "tester",
            "python_test",
            {"status": "failed", "tests": []},
        )
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()