import unittest
from proactive_engine import (
    evaluate_proactive_cycle,
    execute_proactive_action,
    get_day_period,
    LEVEL_COGNITIVE_DESCRIPTOR,
)

class TestProactiveEngineContract(unittest.TestCase):
    def test_level_cognitive_descriptor(self):
        self.assertEqual(LEVEL_COGNITIVE_DESCRIPTOR["level"], 4)
        self.assertEqual(LEVEL_COGNITIVE_DESCRIPTOR["code"], "LEVEL_4_PURE_PROACTIVITY")
        self.assertIn("J.A.R.V.I.S.", LEVEL_COGNITIVE_DESCRIPTOR["directive"])

    def test_day_period(self):
        period = get_day_period()
        self.assertIn(period, ("mañana", "tarde", "noche"))

    def test_evaluate_proactive_cycle(self):
        mock_sweep = lambda **kwargs: {
            "status": "success",
            "new_items_count": 2,
            "new_items": [{"title": "Python 3.13", "link": "https://python.org"}]
        }
        res = evaluate_proactive_cycle(send_telegram=False, sentinel_sweep_fn=mock_sweep)
        self.assertTrue(res["ok"])
        self.assertEqual(res["level_descriptor"]["level"], 4)
        self.assertIn("suggested_action", res)
        self.assertIn("NIVEL 4: PROACTIVIDAD PURA", res["proactive_message"])

    def test_execute_proactive_action(self):
        res1 = execute_proactive_action("security_audit")
        self.assertTrue(res1["ok"])
        self.assertEqual(res1["action"], "security_audit")

        res2 = execute_proactive_action("generic_action")
        self.assertTrue(res2["ok"])
        self.assertIn("completada", res2["result"])

if __name__ == "__main__":
    unittest.main()
