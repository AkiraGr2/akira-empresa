import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, 'akira-empresa')
sys.modules['fastapi'] = MagicMock()
sys.modules['fastapi.responses'] = MagicMock()

from nexus import (
    _audit_code_syntax,
    _synthesize_autonomous_learning_plan,
    _validate_mission_plan,
    _build_tool_inputs,
    _mission_output_semantic_gate,
    _invoke_tool,
)


class LearningContractTests(unittest.TestCase):
    def test_audit_code_syntax_python_valid(self):
        code = "class AkiraAgent:\n    def execute(self):\n        return 100"
        res = _audit_code_syntax(code, "python")
        self.assertTrue(res["ok"])
        self.assertTrue(res["valid"])
        self.assertIn("AkiraAgent", res["ast_summary"]["classes"])
        self.assertIn("execute", res["ast_summary"]["functions"])
        self.assertEqual(len(res["syntax_errors"]), 0)

    def test_audit_code_syntax_python_invalid(self):
        code = "def broken(:\n    pass"
        res = _audit_code_syntax(code, "python")
        self.assertTrue(res["ok"])
        self.assertFalse(res["valid"])
        self.assertGreaterEqual(len(res["syntax_errors"]), 1)
        self.assertIn("line", res["syntax_errors"][0])

    def test_audit_code_syntax_json_valid_and_invalid(self):
        valid_res = _audit_code_syntax('{"akira": true, "version": 8}', "json")
        self.assertTrue(valid_res["ok"])
        self.assertTrue(valid_res["valid"])

        invalid_res = _audit_code_syntax('{"akira": true, invalid}', "json")
        self.assertTrue(invalid_res["ok"])
        self.assertFalse(invalid_res["valid"])
        self.assertGreaterEqual(len(invalid_res["syntax_errors"]), 1)

    def test_synthesize_autonomous_learning_plan_for_code_syntax(self):
        objective = "aprender sobre programación y sintaxis de código"
        plan = _synthesize_autonomous_learning_plan(objective, None)
        self.assertIsNotNone(plan)
        self.assertIn("steps", plan)
        steps = plan["steps"]
        self.assertEqual(len(steps), 5)
        # Step 1: web_search
        self.assertEqual(steps[0]["tool"], "web_search")
        self.assertEqual(steps[0]["agent"], "researcher")
        # Step 2: code_syntax_audit
        self.assertEqual(steps[1]["tool"], "code_syntax_audit")
        self.assertEqual(steps[1]["agent"], "developer")
        self.assertEqual(steps[1]["receives_from"], 1)
        # Step 3: learning_save
        self.assertEqual(steps[2]["tool"], "learning_save")
        self.assertEqual(steps[2]["agent"], "learner")
        self.assertEqual(steps[2]["receives_from"], 2)
        # Step 4: graph_create_node
        self.assertEqual(steps[3]["tool"], "graph_create_node")
        self.assertEqual(steps[3]["agent"], "graph_builder")
        self.assertEqual(steps[3]["receives_from"], 3)
        # Step 5: memory_save
        self.assertEqual(steps[4]["tool"], "memory_save")
        self.assertEqual(steps[4]["agent"], "memorizer")
        self.assertEqual(steps[4]["receives_from"], 4)

    def test_build_tool_inputs_web_fetch_and_code_audit(self):
        step_fetch = {"task": "Revisar https://python.org para aprender sintaxis"}
        inp_fetch = _build_tool_inputs("web_fetch", step_fetch, {}, "m1")
        self.assertEqual(inp_fetch["url"], "https://python.org")

        step_audit = {"task": "def test(): return True", "language": "python"}
        inp_audit = _build_tool_inputs("code_syntax_audit", step_audit, {}, "m1")
        self.assertEqual(inp_audit["code"], "def test(): return True")
        self.assertEqual(inp_audit["language"], "python")

    def test_semantic_gate_web_fetch_and_code_audit(self):
        ok, reason = _mission_output_semantic_gate("web_fetch", {}, {"ok": True, "result": {}}, {})
        self.assertTrue(ok)
        ok_fail, reason_fail = _mission_output_semantic_gate("web_fetch", {}, {"ok": False}, {})
        self.assertFalse(ok_fail)

        ok_code, reason_code = _mission_output_semantic_gate("code_syntax_audit", {}, {"ok": True, "valid": True}, {})
        self.assertTrue(ok_code)
        ok_code_fail, reason_code_fail = _mission_output_semantic_gate("code_syntax_audit", {}, {"ok": False}, {})
        self.assertFalse(ok_code_fail)

    @patch("web_engine.fetch_url")
    def test_invoke_tool_web_fetch(self, mock_fetch):
        mock_fetch.return_value = {"ok": True, "title": "Test Title", "content": "Sample content"}
        mock_service = MagicMock()
        mock_service.get_tool_by_name.return_value = {
            "name": "web_fetch",
            "status": "available",
            "permissions": ["auth"],
            "inputs_schema": {"url": "str", "max_chars": "int"}
        }
        res, err = _invoke_tool(mock_service, "web_fetch", {"url": "https://example.com", "max_chars": 1000}, "test_actor")
        self.assertIsNone(err)
        self.assertTrue(res["ok"])
        self.assertEqual(res["result"]["title"], "Test Title")


if __name__ == "__main__":
    unittest.main()
