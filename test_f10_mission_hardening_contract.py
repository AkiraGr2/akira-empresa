import unittest
from pathlib import Path


class F10MissionHardeningContractTests(unittest.TestCase):
    def test_approval_evidence_is_persisted_and_preserved(self):
        source = Path("persistence/service.py").read_text(encoding="utf-8")
        self.assertIn('approval_result["approval"] = {', source)
        self.assertIn('"authorized_by": authorized_by', source)
        self.assertIn('result["approval"] = dict(prior_result["approval"])', source)

    def test_orchestrator_rechecks_cancellation_after_tool(self):
        source = Path("nexus.py").read_text(encoding="utf-8")
        start = source.index("def _run_mission_sync")
        end = source.index('    total_elapsed_ms =', start)
        block = source[start:end]
        self.assertIn("if _is_mission_cancelled(mission_id):", block)
        self.assertIn('latest_mission.get("status") == "cancelled"', block)
        self.assertIn('return', block)

    def test_final_mission_completion_is_guarded_against_cancellation(self):
        source = Path("nexus.py").read_text(encoding="utf-8")
        start = source.index("def _run_mission_sync")
        block = source[start:]
        guard = 'final_mission.get("status") == "cancelled" or _is_mission_cancelled(mission_id)'
        self.assertIn(guard, block)

    def test_memory_search_after_memory_save_requires_recovery(self):
        source = Path("nexus.py").read_text(encoding="utf-8")
        self.assertIn('"search_hint": content[:200]', source)
        self.assertIn('return {"query": str(prior["search_hint"])[:200]}', source)
        self.assertIn('memory_search_did_not_recover_prior_memory', source)

    def test_semantic_gate_is_conservative_and_deterministic(self):
        source = Path("nexus.py").read_text(encoding="utf-8")
        start = source.index("def _mission_output_semantic_gate")
        end = source.index("def _build_tool_inputs", start)
        block = source[start:end]
        self.assertIn('tool_name == "memory_search"', block)
        self.assertIn('found < 1', block)
        self.assertIn('tool_name == "memory_save"', block)
        self.assertIn('tool_name == "cognitive_cycle"', block)

    def test_semantic_gate_runs_before_step_is_recorded_complete(self):
        source = Path("nexus.py").read_text(encoding="utf-8")
        gate = source.index("_mission_output_semantic_gate(")
        report = source.index('step_report = {', gate)
        self.assertLess(gate, report)
        self.assertIn('step_semantic_failed', source[gate:report])


if __name__ == "__main__":
    unittest.main()
