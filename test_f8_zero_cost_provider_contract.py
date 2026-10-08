"""No-charge guard for F8 audit provider routing; tests make no network calls."""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import specialized_agent_tools as specialized


class F8ZeroCostProviderContractTests(unittest.TestCase):
    def test_preflight_blocks_without_explicit_free_plan_confirmation(self):
        with patch.dict(os.environ, {"AKIRA_F8_GROQ_FREE_PLAN_CONFIRMED": "false"}), \
             patch.object(specialized, "_groq_keys", return_value=["test-groq-key"]):
            result = specialized.f8_audit_provider_preflight()
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "groq_free_plan_not_confirmed")

    def test_preflight_requires_groq_key_even_after_confirmation(self):
        with patch.dict(os.environ, {"AKIRA_F8_GROQ_FREE_PLAN_CONFIRMED": "true"}), \
             patch.object(specialized, "_groq_keys", return_value=[]):
            result = specialized.f8_audit_provider_preflight()
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "groq_api_key_missing")

    def test_unconfirmed_audit_scope_fails_before_any_provider_request(self):
        with patch.dict(os.environ, {"AKIRA_F8_GROQ_FREE_PLAN_CONFIRMED": "false"}), \
             patch.object(specialized, "_groq_keys", return_value=["test-groq-key"]), \
             patch.object(specialized, "_gemini_keys", return_value=["test-gemini-key"]), \
             patch("requests.post") as post:
            with specialized.f8_zero_cost_audit_scope():
                with self.assertRaisesRegex(
                    specialized.SpecializedAgentError,
                    "groq_free_plan_not_confirmed",
                ):
                    specialized._specialist_json_call("synthetic test", max_output_tokens=1)
            post.assert_not_called()

    def test_confirmed_audit_scope_calls_groq_only_and_never_falls_back_to_gemini(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [{"message": {"content": '{"status":"proposal"}'}}]
        }
        with patch.dict(os.environ, {"AKIRA_F8_GROQ_FREE_PLAN_CONFIRMED": "true"}), \
             patch.object(specialized, "_groq_keys", return_value=["test-groq-key"]), \
             patch.object(specialized, "_gemini_keys", side_effect=AssertionError("Gemini fallback must not run")), \
             patch("requests.post", return_value=response) as post:
            with specialized.f8_zero_cost_audit_scope():
                result = specialized._specialist_json_call("synthetic test", max_output_tokens=1)
        self.assertEqual(result["status"], "proposal")
        self.assertEqual(result["_model"], "openai/gpt-oss-120b")
        post.assert_called_once()
        self.assertEqual(post.call_args.args[0], "https://api.groq.com/openai/v1/chat/completions")

    def test_audit_scope_resets_after_exit(self):
        self.assertFalse(specialized.f8_zero_cost_audit_active())
        with specialized.f8_zero_cost_audit_scope():
            self.assertTrue(specialized.f8_zero_cost_audit_active())
        self.assertFalse(specialized.f8_zero_cost_audit_active())

    def test_runtime_blocks_audit_before_start_and_skips_embedding_side_effect(self):
        source = Path("nexus.py").read_text(encoding="utf-8")
        route_start = source.index('@app.post("/api/v8/tools/audit")')
        route_end = source.index('@app.get("/api/v8/tools/audit/{run_id}")', route_start)
        route = source[route_start:route_end]
        self.assertIn("f8_audit_provider_preflight()", route)
        self.assertLess(route.index("f8_audit_provider_preflight()"), route.index('run_id = "tool_audit_"'))
        self.assertIn('"audit_started": False', route)
        self.assertIn("with f8_zero_cost_audit_scope():", source)
        embedding_start = source.index("def _index_memory_embedding(")
        embedding_end = source.index("\ndef ", embedding_start + 5)
        embedding_function = source[embedding_start:embedding_end]
        self.assertIn("if f8_zero_cost_audit_active():", embedding_function)
        self.assertIn("return False", embedding_function)


if __name__ == "__main__":
    unittest.main()
