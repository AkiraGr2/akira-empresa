import unittest
import ast
import re
from pathlib import Path

class TestNexusSuiteContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nexus_source = Path("nexus.py").read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.nexus_source)

    def test_new_tools_defined_in_tool_seed(self):
        expected_tools = [
            "deep_research",
            "fact_triangulate",
            "web_structured_extract",
            "dependency_vulnerability_audit",
            "executive_dossier_generate",
            "sentinel_sweep",
        ]
        for tool in expected_tools:
            self.assertIn(f'"name": "{tool}"', self.nexus_source, f"Tool '{tool}' no encontrada en _TOOL_SEED de nexus.py")

    def test_agent_seed_wiring(self):
        self.assertIn('"deep_research"', self.nexus_source)
        self.assertIn('"fact_triangulate"', self.nexus_source)
        self.assertIn('"web_structured_extract"', self.nexus_source)
        self.assertIn('"dependency_vulnerability_audit"', self.nexus_source)
        self.assertIn('"sentinel_sweep"', self.nexus_source)

    def test_build_tool_inputs_has_new_tool_handlers(self):
        self.assertIn('if tool_name == "deep_research":', self.nexus_source)
        self.assertIn('if tool_name == "fact_triangulate":', self.nexus_source)
        self.assertIn('if tool_name == "web_structured_extract":', self.nexus_source)
        self.assertIn('if tool_name == "dependency_vulnerability_audit":', self.nexus_source)
        self.assertIn('if tool_name == "executive_dossier_generate":', self.nexus_source)
        self.assertIn('if tool_name == "sentinel_sweep":', self.nexus_source)

    def test_invoke_tool_has_dispatch_handlers(self):
        self.assertIn('from deep_research import deep_research_topic', self.nexus_source)
        self.assertIn('from fact_checker import triangulate_claim', self.nexus_source)
        self.assertIn('from web_extractor import extract_structured_web', self.nexus_source)
        self.assertIn('from code_vulnerability_auditor import audit_dependencies', self.nexus_source)
        self.assertIn('from executive_dossier import generate_and_dispatch_dossier', self.nexus_source)
        self.assertIn('from sentinel_cron import run_sentinel_sweep', self.nexus_source)

    def test_new_rest_endpoints_declared(self):
        expected_endpoints = [
            '/api/v8/research/deep',
            '/api/v8/facts/triangulate',
            '/api/v8/web/structured-extract',
            '/api/v8/code/audit-dependencies',
            '/api/v8/dossiers/generate',
            '/api/v8/sentinel/sweep',
            '/api/v8/proactive/status',
            '/api/v8/proactive/evaluate',
            '/api/v8/proactive/execute-action',
        ]
        for ep in expected_endpoints:
            self.assertTrue(
                f'@app.post("{ep}")' in self.nexus_source or f'@app.get("{ep}")' in self.nexus_source,
                f"Endpoint {ep} no registrado en nexus.py"
            )

if __name__ == "__main__":
    unittest.main()
