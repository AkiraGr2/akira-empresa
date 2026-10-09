"""F7 provider-routing contract; all inference calls are mocked."""
from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

import nexus
import specialized_agent_tools


class F7ZeroCostProviderContractTests(unittest.TestCase):
    def test_cycle_route_fails_closed_before_start_without_free_groq_confirmation(self):
        owner = {"email": "owner@example.test", "owner_scope": "owner"}
        with patch.object(nexus, "_require_owner", return_value=(owner, None)), \
             patch.object(nexus, "_persistence_service", return_value=object()), \
             patch.object(nexus, "f8_audit_provider_preflight", return_value={
                 "ok": False, "provider": "groq", "reason": "groq_free_plan_not_confirmed",
             }), \
             patch.object(nexus, "_execute_cognitive_cycle") as execute:
            response = nexus.v8_cognitive_cycle(
                Mock(),
                {"trigger": "admin_panel", "input": {"message": "synthetic test"}},
            )

        self.assertEqual(response.status_code, 409)
        self.assertIn(b"zero_cost_provider_not_confirmed", response.body)
        self.assertIn(b'"cycle_started":false', response.body)
        execute.assert_not_called()

    def test_cycle_route_scopes_real_execution_to_groq_only_and_resets_scope(self):
        owner = {"email": "owner@example.test", "owner_scope": "owner"}
        observed_scope = []
        payload = {
            "cycle": {"id": "cycle_test_f7", "status": "completed"},
            "events": [],
            "answer": "mocked answer",
            "learning_id": "learn_test_f7",
            "capability_verification": {"effective_state": "verified"},
        }

        def execute(*args, **kwargs):
            observed_scope.append(nexus._F7_ZERO_COST_COGNITIVE_CYCLE.get())
            return payload

        self.assertFalse(nexus._F7_ZERO_COST_COGNITIVE_CYCLE.get())
        with patch.object(nexus, "_require_owner", return_value=(owner, None)), \
             patch.object(nexus, "_persistence_service", return_value=object()), \
             patch.object(nexus, "f8_audit_provider_preflight", return_value={
                 "ok": True, "provider": "groq", "reason": "free_plan_explicitly_confirmed",
             }), \
             patch.object(nexus, "_execute_cognitive_cycle", side_effect=execute):
            result = nexus.v8_cognitive_cycle(
                Mock(),
                {"trigger": "admin_panel", "input": {"message": "synthetic test"}},
            )

        self.assertEqual(observed_scope, [True])
        self.assertFalse(nexus._F7_ZERO_COST_COGNITIVE_CYCLE.get())
        self.assertTrue(result["ok"])
        self.assertEqual(result["cycle_id"], "cycle_test_f7")

    def test_f7_scope_uses_groq_and_never_reads_gemini_keys(self):
        token = nexus._F7_ZERO_COST_COGNITIVE_CYCLE.set(True)
        try:
            with patch.object(nexus, "_format_recall_block", return_value="retrieved memory"), \
                 patch.object(nexus, "get_groq_fallback", return_value="mocked Groq response") as groq, \
                 patch.object(nexus, "_pick_gemini_keys", side_effect=AssertionError("Gemini must not be called")) as gemini:
                answer, model = nexus._run_reason_stage("test message", [])
        finally:
            nexus._F7_ZERO_COST_COGNITIVE_CYCLE.reset(token)

        self.assertEqual(answer, "mocked Groq response")
        self.assertEqual(model, "groq")
        groq.assert_called_once_with("test message", "retrieved memory")
        gemini.assert_not_called()

    def test_f8_tool_audit_scope_also_routes_cognitive_cycle_to_groq(self):
        with specialized_agent_tools.f8_zero_cost_audit_scope(), \
             patch.object(nexus, "_format_recall_block", return_value="retrieved memory"), \
             patch.object(nexus, "get_groq_fallback", return_value="mocked Groq response") as groq, \
             patch.object(nexus, "_pick_gemini_keys", side_effect=AssertionError("Gemini must not be called")) as gemini:
            answer, model = nexus._run_reason_stage("test message", [])

        self.assertEqual(answer, "mocked Groq response")
        self.assertEqual(model, "groq")
        groq.assert_called_once()
        gemini.assert_not_called()


if __name__ == "__main__":
    unittest.main()
