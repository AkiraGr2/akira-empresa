import ast
from pathlib import Path
import unittest


NEXUS = Path("nexus.py")
WORKFLOW = Path(".github/workflows/backend-syntax.yml")


class ProviderFailoverRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = NEXUS.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def _function_source(self, name):
        node = next(
            n for n in self.tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name
        )
        return ast.get_source_segment(self.source, node)

    def test_gemini_429_does_not_abort_remaining_keys(self):
        source = self._function_source("_chat_try_gemini")
        self.assertIn("code = _log_gemini_error", source)
        self.assertNotIn('if code == 429:\n                    return None', source)
        self.assertIn("continue", source)

    def test_stream_gemini_429_does_not_raise_immediately(self):
        source = self._function_source("_stream_call_gemini")
        self.assertNotIn('raise RuntimeError("Gemini quota agotada; fallback inmediato")', source)
        self.assertIn("# Un 429 no debe cortar la lista de credenciales Gemini.", source)
        self.assertIn("continue", source)

    def test_openrouter_supports_multiple_keys(self):
        self.assertIn("def get_openrouter_keys():", self.source)
        self.assertIn("def _pick_openrouter_keys():", self.source)
        self.assertIn('os.getenv(f"OPENROUTER_API_KEY_{i}"', self.source)


    def test_mistral_is_optional_fourth_provider(self):
        self.assertIn("def get_mistral_keys():", self.source)
        self.assertIn("def _pick_mistral_keys():", self.source)
        self.assertIn("def get_mistral_fallback(", self.source)
        self.assertIn('"https://api.mistral.ai/v1/chat/completions"', self.source)
        self.assertIn('"mistral-small-latest"', self.source)
        self.assertGreaterEqual(self.source.count("get_mistral_fallback"), 3)

    def test_gemini_429_uses_short_cooldown(self):
        self.assertIn(
            '_mark_key_failed(key, seconds=(120 if code == 429 else 3600))',
            self.source,
        )

    def test_user_does_not_receive_false_generic_key_exhaustion_message(self):
        stream = self._function_source("chat_stream")
        self.assertNotIn("Keys agotadas. {str(ge)[:120]}", stream)
        self.assertIn("No fue posible obtener respuesta de ningún proveedor configurado.", stream)

    def test_backend_workflow_runs_this_regression_suite(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("python -m unittest test_provider_failover -v", workflow)


if __name__ == "__main__":
    unittest.main()
