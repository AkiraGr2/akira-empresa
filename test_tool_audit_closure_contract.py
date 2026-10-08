"""F8 closure contract regression tests without providers or production writes."""
import unittest

from tool_audit import TOOL_ORDER, _evaluate_audit_closure


def valid_reports():
    rows = [{"tool": name, "verdict": "VERIFIED"} for name in TOOL_ORDER]
    for row in rows:
        if row["tool"] == "image_generate":
            row["verdict"] = "FAIL_CLOSED"
        elif row["tool"] == "cognitive_cycle":
            row["verdict"] = "VERIFIED_VIA_F7"
    return rows


class ToolAuditClosureContractTests(unittest.TestCase):
    def test_exact_sixteen_case_report_can_close(self):
        result = _evaluate_audit_closure(valid_reports(), {"ok": True})
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["actual_verdicts"], {
            "VERIFIED": 14, "FAIL_CLOSED": 1, "VERIFIED_VIA_F7": 1,
        })
        self.assertTrue(all(result["checks"].values()))

    def test_unexpected_verdict_blocks_closure(self):
        rows = valid_reports()
        next(row for row in rows if row["tool"] == "python_test")["verdict"] = "NOT_APPLICABLE"
        result = _evaluate_audit_closure(rows, {"ok": True})
        self.assertFalse(result["ok"], result)
        self.assertFalse(result["checks"]["verdict_distribution_exact"])

    def test_fail_closed_and_inherited_verdicts_must_match_their_tools(self):
        rows = valid_reports()
        next(row for row in rows if row["tool"] == "image_generate")["verdict"] = "VERIFIED"
        next(row for row in rows if row["tool"] == "python_test")["verdict"] = "FAIL_CLOSED"
        result = _evaluate_audit_closure(rows, {"ok": True})
        self.assertFalse(result["ok"], result)
        self.assertFalse(result["checks"]["disabled_image_fails_closed"])

    def test_case_order_and_count_must_be_exact(self):
        rows = valid_reports()
        rows[0], rows[1] = rows[1], rows[0]
        result = _evaluate_audit_closure(rows, {"ok": True})
        self.assertFalse(result["ok"], result)
        self.assertFalse(result["checks"]["tool_order_exact"])
        result = _evaluate_audit_closure(rows[:-1], {"ok": True})
        self.assertFalse(result["ok"], result)
        self.assertFalse(result["checks"]["case_count_exact"])

    def test_cleanup_failure_blocks_closure(self):
        result = _evaluate_audit_closure(valid_reports(), {"ok": False})
        self.assertFalse(result["ok"], result)
        self.assertFalse(result["checks"]["cleanup_confirmed"])


if __name__ == "__main__":
    unittest.main()
