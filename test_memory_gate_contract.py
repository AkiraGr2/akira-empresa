import unittest

from nexus import _memory_gate_decide


class _BrokenSearchService:
    def search_memory(self, *args, **kwargs):
        raise RuntimeError("storage unavailable")


class MemoryGateFailClosedTests(unittest.TestCase):
    def test_duplicate_check_failure_does_not_allow_save(self):
        result = _memory_gate_decide(
            _BrokenSearchService(),
            "esta es una memoria suficientemente larga para la prueba",
            "semantic",
            5,
            ["gate-test"],
            "owner@example.test",
            "g:user-A",
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["decision"], "reject")
        self.assertEqual(result["reason"], "duplicate_check_unavailable")


if __name__ == "__main__":
    unittest.main()
