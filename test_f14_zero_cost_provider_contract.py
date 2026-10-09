"""F14 no-charge provider-routing contract; tests make no network calls."""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import specialized_agent_tools as specialized


class F14ZeroCostProviderContractTests(unittest.TestCase):
    def test_preflight_blocks_without_explicit_free_plan_confirmation(self):
        with patch.dict(os.environ, {"AKIRA_F14_GROQ_FREE_PLAN_CONFIRMED": "false"}), \
             patch.object(specialized, "_groq_keys", return_value=["test-groq-key"]):
            result = specialized.f14_zero_cost_provider_preflight()
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "groq_free_plan_not_confirmed")

    def test_preflight_requires_groq_key_even_after_confirmation(self):
        with patch.dict(os.environ, {"AKIRA_F14_GROQ_FREE_PLAN_CONFIRMED": "true"}), \
             patch.object(specialized, "_groq_keys", return_value=[]):
            result = specialized.f14_zero_cost_provider_preflight()
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "groq_api_key_missing")

    def test_unconfirmed_scope_stops_before_any_provider_request(self):
        with patch.dict(os.environ, {"AKIRA_F14_GROQ_FREE_PLAN_CONFIRMED": "false"}), \
             patch.object(specialized, "_groq_keys", return_value=["test-groq-key"]), \
             patch.object(specialized, "_gemini_keys") as gemini_keys, \
             patch("requests.post") as post:
            with specialized.f14_zero_cost_autonomy_scope():
                with self.assertRaisesRegex(
                    specialized.SpecializedAgentError,
                    "f14_zero_cost_autonomy_blocked:groq_free_plan_not_confirmed",
                ):
                    specialized._specialist_json_call("synthetic test", max_output_tokens=1)
            post.assert_not_called()
            gemini_keys.assert_not_called()

    def test_confirmed_scope_uses_groq_only_without_gemini_fallback(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [{"message": {"content": '{"status":"proposal"}'}}]
        }
        with patch.dict(os.environ, {"AKIRA_F14_GROQ_FREE_PLAN_CONFIRMED": "true"}), \
             patch.object(specialized, "_groq_keys", return_value=["test-groq-key"]), \
             patch.object(specialized, "_gemini_keys") as gemini_keys, \
             patch("requests.post", return_value=response) as post:
            with specialized.f14_zero_cost_autonomy_scope():
                result = specialized._specialist_json_call("synthetic test", max_output_tokens=1)
        self.assertEqual(result["status"], "proposal")
        self.assertEqual(result["_model"], "openai/gpt-oss-120b")
        post.assert_called_once()
        self.assertEqual(post.call_args.args[0], "https://api.groq.com/openai/v1/chat/completions")
        gemini_keys.assert_not_called()

    def test_scope_resets_after_exit(self):
        self.assertFalse(specialized.f14_zero_cost_autonomy_active())
        with specialized.f14_zero_cost_autonomy_scope():
            self.assertTrue(specialized.f14_zero_cost_autonomy_active())
        self.assertFalse(specialized.f14_zero_cost_autonomy_active())

    def test_autonomy_preflights_before_persisting_run_and_scopes_both_model_calls(self):
        source = Path("autonomy_engine.py").read_text(encoding="utf-8")
        start = source.index("def start_controlled_autonomy(")
        end = source.index("\ndef _run_sandbox_tests_from_existing_archive(", start)
        function = source[start:end]
        self.assertIn("f14_zero_cost_provider_preflight()", function)
        self.assertLess(
            function.index("f14_zero_cost_provider_preflight()"),
            function.index("created = a.create_run"),
        )
        self.assertEqual(function.count("with f14_zero_cost_autonomy_scope():"), 1)

        proposal_start = source.index("def _prepare_controlled_proposal(")
        proposal_end = source.index("\ndef _enforce_f14_production_verification_contract(", proposal_start)
        proposal_helper = source[proposal_start:proposal_end]
        self.assertEqual(
            proposal_helper.count("with f14_zero_cost_autonomy_scope():"),
            1,
        )


if __name__ == "__main__":
    unittest.main()
