import ast
import unittest
from pathlib import Path
from unittest.mock import patch

import specialized_agent_tools

ROOT = Path(__file__).resolve().parent


class SpecializedAgentsContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT / "nexus.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        cls.tool_seed = next(
            ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "_TOOL_SEED" for t in node.targets)
        )
        cls.agent_seed = next(
            ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "_AGENT_SEED" for t in node.targets)
        )

    def test_specialized_tools_are_owner_only_and_available(self):
        tools = {item["name"]: item for item in self.tool_seed}
        expected = {"developer_propose", "python_test", "code_review"}
        self.assertTrue(expected.issubset(tools))
        for name in expected:
            self.assertEqual(tools[name]["permissions"], ["owner"])
            self.assertEqual(tools[name].get("status", "available"), "available")

    def test_specialized_agents_have_narrow_tool_contracts(self):
        agents = {item["name"]: item for item in self.agent_seed}
        self.assertEqual(agents["developer"]["allowed_tools"], ["github_repo_read", "developer_propose"])
        self.assertEqual(agents["tester"]["allowed_tools"], ["github_repo_read", "python_test"])
        self.assertEqual(agents["reviewer"]["allowed_tools"], ["github_repo_read", "python_test", "code_review"])

    def test_specialized_tools_never_offer_direct_github_write(self):
        source = (ROOT / "specialized_agent_tools.py").read_text(encoding="utf-8")
        self.assertNotIn("git push", source.lower())
        self.assertNotIn("subprocess.Popen", source)
        self.assertNotIn("os.system", source)
        self.assertNotIn("shell=True", source)
        self.assertIn('"write_performed"] = False', source)
        self.assertIn('"requires_human_approval"] = True', source)

    def test_tester_rejects_unsafe_test_module(self):
        with self.assertRaises(specialized_agent_tools.SpecializedAgentError):
            specialized_agent_tools.run_python_tests(tests=["../evil"])

    def test_tester_requires_explicit_targets(self):
        with self.assertRaises(specialized_agent_tools.SpecializedAgentError):
            specialized_agent_tools.run_python_tests()

    def test_developer_proposal_is_explicitly_non_mutating(self):
        fake_inspection = {"files": [{"path": "README.md", "status": "ok", "content": "hello"}]}
        fake_result = {
            "status": "proposal",
            "summary": "safe proposal",
            "changes": [],
            "tests": [],
            "risks": [],
        }
        with patch.object(specialized_agent_tools, "_specialist_json_call", return_value=fake_result):
            result = specialized_agent_tools.propose_code_change(
                lambda *a, **k: fake_inspection,
                "AkiraGr2/akira-empresa",
                ["README.md"],
                "small documentation change",
            )
        self.assertFalse(result["write_performed"])
        self.assertTrue(result["requires_human_approval"])

    def test_reviewer_produces_non_mutating_review(self):
        fake_inspection = {"files": [{"path": "README.md", "status": "ok", "content": "hello"}]}
        fake_result = {
            "verdict": "approve",
            "summary": "safe",
            "findings": [],
            "required_tests": [],
        }
        with patch.object(specialized_agent_tools, "_specialist_json_call", return_value=fake_result):
            result = specialized_agent_tools.review_code_change(
                lambda *a, **k: fake_inspection,
                "AkiraGr2/akira-empresa",
                ["README.md"],
                {"status": "proposal", "changes": []},
                {"status": "passed"},
            )
        self.assertEqual(result["verdict"], "approve")
        self.assertFalse(result["write_performed"])

    def test_tester_executes_compile_without_shell(self):
        result = specialized_agent_tools.run_python_tests(
            compile_paths=["test_specialized_agents_contract.py"]
        )
        self.assertTrue(result["commands_are_non_shell"])
        self.assertEqual(result["status"], "passed")


if __name__ == "__main__":
    unittest.main()
