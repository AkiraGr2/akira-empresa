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

    def test_semantic_gate_runs_before_task_and_step_are_recorded_complete(self):
        source = Path("nexus.py").read_text(encoding="utf-8")
        start = source.index("def _run_mission_sync")
        end = source.index('    total_elapsed_ms =', start)
        block = source[start:end]
        gate = block.index("semantic_ok, semantic_reason = _mission_output_semantic_gate(")
        completion = block.index("service.complete_task(", gate)
        step_complete = block.index('mission_id, "step_completed"', gate)
        report = block.index('step_report = {', gate)

        self.assertLess(gate, completion)
        self.assertLess(completion, step_complete)
        self.assertLess(step_complete, report)
        self.assertIn('step_semantic_failed', block[gate:completion])
        self.assertIn('service.fail_task(', block[gate:completion])

    def test_replayed_task_output_is_validated_before_reuse(self):
        source = Path("nexus.py").read_text(encoding="utf-8")
        start = source.index('if create_result.get("outcome") == "already_synced":')
        end = source.index('                task_id = existing_task["id"]', start)
        replay = source[start:end]

        gate = replay.index("_mission_output_semantic_gate(")
        reuse = replay.index("outputs_by_order[order] = replayed_outputs")
        self.assertLess(gate, reuse)
        self.assertIn('"task_replay_semantic_failed"', replay[gate:reuse])
        self.assertIn('task_ids.append(existing_task["id"])', replay[reuse:])


if __name__ == "__main__":
    unittest.main()
