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

    def test_safe_provider_inventory_counts_configured_keys(self):
        self.assertIn("def provider_key_inventory():", self.source)
        self.assertIn('"gemini": len(get_gemini_keys())', self.source)
        self.assertIn('"groq": len(get_groq_keys())', self.source)
        self.assertIn('"openrouter": len(get_openrouter_keys())', self.source)
        self.assertIn('"mistral": len(get_mistral_keys())', self.source)

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

    def test_fastapi_uses_lifespan_instead_of_deprecated_startup_event(self):
        self.assertIn("from contextlib import asynccontextmanager", self.source)
        self.assertIn("app=FastAPI(title=PUBLIC_IDENTITY, lifespan=_akira_lifespan)", self.source)
        self.assertIn("from identity_root import IDENTITY_ROOT_VERSION, PUBLIC_IDENTITY, get_identity_root", self.source)
        self.assertIn("async def _akira_lifespan(_app):", self.source)
        self.assertNotIn('@app.on_event("startup")', self.source)
        self.assertLess(
            self.source.index("async def _akira_lifespan(_app):"),
            self.source.index("app=FastAPI(title=PUBLIC_IDENTITY, lifespan=_akira_lifespan)"),
        )

    def test_runtime_capability_contract_is_explicit_and_free_only(self):
        self.assertIn('@app.get("/api/v8/runtime/capabilities")', self.source)
        self.assertIn('"free_only_policy": True', self.source)
        self.assertIn('"paid_api_enabled": False', self.source)
        self.assertIn('"status": "experimental"', self.source)
        self.assertIn('"status": "not_implemented"', self.source)


    def test_media_endpoints_require_session_and_have_independent_rate_limit(self):
        for fn in ("extract_file", "generate_image"):
            source = self._function_source(fn)
            self.assertIn("session = get_session(request)", source)
            self.assertIn("auth_required", source)
            self.assertIn("check_media_rate_limit", source)

    def test_image_experimental_path_is_double_opt_in_and_never_exposes_key(self):
        self.assertIn("def get_pollinations_key():", self.source)
        self.assertIn("def experimental_image_enabled():", self.source)
        source = self._function_source("generate_image")
        self.assertIn("if not experimental_image_enabled():", source)
        self.assertIn('"Authorization": f"Bearer {get_pollinations_key()}"', source)
        self.assertNotIn('?key=', source)
        self.assertNotIn("image.pollinations.ai/prompt/", source)

    def test_pdf_validation_checks_signature_and_strict_base64(self):
        source = self._function_source("extract_file")
        self.assertIn("base64.b64decode(b64, validate=True)", source)
        self.assertIn('raw[:5] != b"%PDF-"', source)

    def test_runtime_image_status_reflects_explicit_opt_in(self):
        self.assertIn('"status": "experimental" if experimental_image_enabled() else "disabled"', self.source)
        self.assertIn('"requires_explicit_opt_in": True', self.source)

    def test_owner_identity_cannot_be_spoofed_through_chat_payload(self):
        source = self._function_source("resolve_is_owner")
        self.assertIn('return bool(s and s["is_owner"])', source)
        self.assertNotIn('data.get("is_owner"', source)
        self.assertNotIn("AKIRA_TRUST_CLIENT_OWNER", source)
        self.assertNotIn("trust_client_owner", source)


if __name__ == "__main__":
    unittest.main()
