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


if __name__ == "__main__":
    unittest.main()
