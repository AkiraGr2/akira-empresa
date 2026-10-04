import ast
from pathlib import Path
import unittest


NEXUS = Path("nexus.py")
WORKFLOW = Path(".github/workflows/backend-syntax.yml")


class AuthorizationContractTests(unittest.TestCase):
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

    def test_owner_helper_uses_only_signed_session_identity(self):
        source = self._function_source("_require_owner")
        self.assertIn("s = get_session(request)", source)
        self.assertIn('s.get("is_owner")', source)
        self.assertIn("owner_required", source)
        self.assertNotIn("request.query_params", source)
        self.assertNotIn("request.cookies", source)
        self.assertNotIn("data.get", source)

    def test_persistent_cognitive_routes_are_owner_only(self):
        owner_only = [
            "v8_learning_create",
            "v8_learning_list",
            "v8_learning_experience",
            "v8_learning_teach",
            "v8_learning_get",
            "v8_learning_reuse",
            "v8_graph_node_create",
            "v8_graph_node_get",
            "v8_graph_edge_create",
            "v8_graph_related",
            "v8_graph_overview",
            "v8_cognitive_cycle",
            "v8_cognitive_cycle_get",
            "v8_cognitive_cycles_list",
            "v8_agents_list",
            "v8_agents_get",
            "v8_tasks_list",
            "v8_tasks_get",
            "v8_agents_run_task",
            "v8_create_mission",
            "v8_list_missions",
            "v8_recent_missions",
            "v8_mission_progress",
            "v8_missions_selftest",
            "v8_mission_diagnose",
            "v8_get_mission",
            "v8_approve_mission",
            "v8_reject_mission",
            "v8_execute_mission",
            "v8_cancel_mission",
        ]
        for name in owner_only:
            source = self._function_source(name)
            self.assertIn("_require_owner(request)", source, name)

    def test_existing_owner_sensitive_endpoints_remain_owner_only(self):
        for name in (
            "v8_self_update",
            "v8_learning_absorption_diagnose",
            "v8_learning_evidence_add",
            "v8_learning_investigate",
            "v8_learning_evaluate",
            "v8_learning_status_update",
            "v8_learning_selftest",
            "v8_learning_selftest_result",
            "v8_graph_reinforce",
            "v8_graph_cleanup_tests",
            "v8_memory_semantic_selftest",
            "v8_memory_semantic_reindex",
        ):
            source = self._function_source(name)
            self.assertIn("_require_owner(request)", source, name)

    def test_legacy_self_repair_surfaces_are_owner_only(self):
        for name in ("self_repair_status", "self_repair_propose"):
            source = self._function_source(name)
            self.assertIn("_require_owner(request)", source, name)
    def test_legacy_maintenance_surfaces_are_owner_only(self):
        for name in ("countermeasures", "sync_to_r2"):
            source = self._function_source(name)
            self.assertIn("_require_owner(request)", source, name)
    def test_public_health_surface_does_not_leak_operational_secrets_or_counts(self):
        source = self._function_source("health")
        self.assertIn('"status":"ok"', source)
        self.assertIn('"version":VERSION', source)
        self.assertIn('"build_marker":BACKEND_BUILD_MARKER', source)
        for marker in (
            "github_token",
            "github_repo",
            "gemini_keys_count",
            "groq_keys_count",
            "gemini_keys_failed",
            "countermeasures",
            "membrana",
            '"consciente": True',
        ):
            self.assertNotIn(marker, source, marker)

    def test_brain_count_and_shared_are_owner_only(self):
        for name in ("brain_count", "brain_shared"):
            source = self._function_source(name)
            self.assertIn("request: Request", source, name)
            self.assertIn("_require_owner(request)", source, name)

    def test_me_route_derives_identity_only_from_signed_session(self):
        source = self._function_source("v8_me")
        self.assertIn("s = get_session(request)", source)
        self.assertIn('s["email"]', source)
        self.assertIn('s["is_owner"]', source)
        self.assertIn('s["owner_scope"]', source)
        self.assertIn('s["exp"]', source)
        self.assertNotIn("request.query_params", source)
        self.assertNotIn("request.cookies", source)
        self.assertNotIn("data.get", source)

    def test_auth_status_declares_client_owner_trust_disabled(self):
        source = self._function_source("v8_auth_status")
        self.assertIn('"trust_client_owner": False', source)

    def test_graph_owner_scope_is_server_derived(self):
        source = self._function_source("v8_graph_node_create")
        self.assertIn('data["owner_scope"] = s.get("owner_scope") or "owner"', source)
        self.assertNotIn('data.get("owner_scope")', source)

    def test_sensitive_tool_registry_permissions_are_owner_only(self):
        expected = [
            '"name": "memory_save"',
            '"name": "memory_search"',
            '"name": "graph_create_node"',
            '"name": "graph_create_edge"',
            '"name": "graph_related"',
            '"name": "learning_save"',
            '"name": "self_model_read"',
            '"name": "cognitive_cycle"',
        ]
        for marker in expected:
            start = self.source.index(marker)
            end = self.source.find("\n", start)
            line = self.source[start:end if end >= 0 else len(self.source)]
            self.assertIn('"permissions": ["owner"]', line, marker)

    def test_legacy_image_tool_is_disabled_under_free_only_policy(self):
        source = self._function_source("_invoke_tool")
        self.assertIn('"CapabilityDisabled"', source)
        self.assertNotIn("image.pollinations.ai/prompt/", source)
        marker = '"name": "image_generate"'
        start = self.source.index(marker)
        end = self.source.find("\n", start)
        line = self.source[start:end if end >= 0 else len(self.source)]
        self.assertIn('"status": "disabled"', line)
        self.assertIn('"permissions": ["owner"]', line)

    def test_memory_routes_are_owner_only(self):
        for name in ("memory_ingest", "v8_memory_semantic_reindex", "memory_search"):
            source = self._function_source(name)
            self.assertIn("_require_owner(request)", source, name)

    def test_chat_recall_requires_owner_session(self):
        source = self._function_source("chat")
        self.assertIn('if session and session.get("is_owner")', source)
        self.assertIn("else []", source)

    def test_chat_stream_recall_requires_owner_session(self):
        source = self._function_source("chat_stream")
        self.assertIn('if session and session.get("is_owner")', source)
        self.assertIn("else []", source)

    def test_conversation_context_is_scoped_in_both_chat_paths(self):
        normal = self._function_source("chat")
        streaming = self._function_source("chat_stream")
        self.assertIn("_format_conversation_context, service, conversation_id, msg, session[\"email\"]", normal)
        self.assertIn("_format_conversation_context, service, conversation_id, msg, session[\"email\"]", streaming)

    def test_conversation_add_message_passes_explicit_owner(self):
        normal = self._function_source("chat")
        streaming = self._function_source("chat_stream")
        self.assertIn("owner=session[\"email\"]", normal)
        self.assertIn("owner=session[\"email\"]", streaming)

    def test_memory_save_tool_has_no_undefined_mission_id_dependency(self):
        source = self._function_source("_invoke_tool")
        branch_start = source.index('if tool_name == "memory_save":')
        branch_end = source.index('if tool_name == "memory_search":', branch_start)
        branch = source[branch_start:branch_end]
        self.assertNotIn("mission_id", branch)
        self.assertIn('"source_id": "tool_registry"', branch)


if __name__ == "__main__":
    unittest.main()
