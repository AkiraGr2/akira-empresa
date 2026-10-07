import unittest
from pathlib import Path

from persistence.core import ValidationError, validate_tool_inputs


class ToolRegistryContractTests(unittest.TestCase):
    def test_registered_inputs_are_schema_validated_before_dispatch(self):
        tool = {
            "name": "example",
            "inputs_schema": {
                "query": "str",
                "limit": "int",
                "flags": "list",
            },
        }
        self.assertEqual(
            validate_tool_inputs(tool, {"query": "hola", "limit": 2, "flags": []}),
            {"query": "hola", "limit": 2, "flags": []},
        )
        with self.assertRaises(ValidationError):
            validate_tool_inputs(tool, {"query": "hola", "unknown": "x"})
        with self.assertRaises(ValidationError):
            validate_tool_inputs(tool, {"query": 42})

    def test_tool_invocation_storage_is_owner_scoped(self):
        core = Path("persistence/core.py").read_text(encoding="utf-8")
        self.assertIn('"owner_scope"', core)
        self.assertIn('"idempotency_scope": ("owner_scope", "tool_name")', core)

        migrations = Path("persistence/migrations.py").read_text(encoding="utf-8")
        self.assertIn('"054_tool_invocation_owner_scope_and_idempotency"', migrations)
        self.assertIn(
            "ON public.tool_invocations (owner_scope, tool_name, idempotency_key)",
            migrations,
        )

    def test_service_exposes_replay_lookup_for_idempotent_invocations(self):
        source = Path("persistence/service.py").read_text(encoding="utf-8")
        self.assertIn("def get_invocation_by_idempotency_key", source)
        self.assertIn('"owner_scope": scope', source)
        self.assertIn('"idempotency_key": key', source)

    def test_generic_tool_route_replays_existing_idempotency_key(self):
        source = Path("nexus.py").read_text(encoding="utf-8")
        self.assertIn("get_invocation_by_idempotency_key", source)
        self.assertIn('"replayed": True', source)
        self.assertIn('idempotency_key = payload.get("idempotency_key")', source)

    def test_generic_tool_route_imports_runtime_validation_contract(self):
        source = Path("nexus.py").read_text(encoding="utf-8")
        self.assertIn("from persistence.core import PersistenceError, ValidationError, validate_tool_inputs", source)

    def test_generic_tool_route_passes_schema_validated_inputs_to_executor(self):
        source = Path("nexus.py").read_text(encoding="utf-8")
        self.assertIn("validate_tool_inputs(tool, inputs)", source)
        self.assertIn('owner_scope=s.get("owner_scope") if s.get("is_owner") else None', source)
        self.assertIn("owner_scope=owner_scope", source)

    def test_lifespan_waits_for_persistence_before_tool_seed(self):
        source = Path("nexus.py").read_text(encoding="utf-8")
        wait_pos = source.index("for attempt in range(15):")
        seed_pos = source.index("_seed_tools_and_agents()", wait_pos)
        ready_pos = source.index("if _persistence_service() is not None:", wait_pos)
        self.assertLess(wait_pos, ready_pos)
        self.assertLess(ready_pos, seed_pos)

    def test_web_search_registry_schema_matches_structured_runtime_output(self):
        source = Path("nexus.py").read_text(encoding="utf-8")
        self.assertIn('"name": "web_search"', source)
        self.assertIn('"outputs_schema": {"result": "dict"}', source)

    def test_web_search_returns_structured_results_not_fake_fallback(self):
        source = Path("nexus.py").read_text(encoding="utf-8")
        self.assertIn('def search_web(q, max_results=3):', source)
        self.assertIn('"result_count": len(results)', source)
        self.assertIn('"results": results', source)
        self.assertNotIn('or "Busqueda"', source)

    def test_every_registered_tool_has_a_runtime_dispatch_branch(self):
        source = Path("nexus.py").read_text(encoding="utf-8")
        expected = {
            "web_search", "github_repo_read",
            "memory_save", "memory_search",
            "graph_create_node", "graph_create_edge", "graph_related",
            "learning_save", "self_model_read", "extract_pdf",
            "image_generate", "cognitive_cycle",
            "developer_propose", "python_test", "code_review",
            "controlled_autonomy_start",
        }
        for tool_name in expected:
            self.assertRegex(
                source,
                rf'if tool_name == ["\\\']{tool_name}["\\\']',
                msg=f"faltante branch de dispatcher: {tool_name}",
            )

    def test_individual_tool_auditor_covers_exact_registry_set(self):
        audit = Path("tool_audit.py").read_text(encoding="utf-8")
        expected = {
            "web_search", "github_repo_read",
            "memory_save", "memory_search",
            "graph_create_node", "graph_create_edge", "graph_related",
            "learning_save", "self_model_read", "extract_pdf",
            "image_generate", "cognitive_cycle",
            "developer_propose", "python_test", "code_review",
            "controlled_autonomy_start",
        }
        import ast
        tree = ast.parse(audit)
        value = None
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "TOOL_ORDER":
                        value = [elt.value for elt in node.value.elts]
        self.assertEqual(set(value or []), expected)
        self.assertEqual(len(value or []), 16)

    def test_individual_tool_auditor_is_persistent_and_uses_runtime_dispatcher(self):
        source = Path("nexus.py").read_text(encoding="utf-8")
        audit = Path("tool_audit.py").read_text(encoding="utf-8")
        self.assertIn("from tool_audit import TOOL_ORDER, run_tool_audit", source)
        self.assertIn('def _invoke_registered_tool(', source)
        self.assertIn('run_tool_audit(', source)
        self.assertIn('service.record_audit(', audit)
        self.assertIn('service.get_invocation_by_idempotency_key(', audit)
        self.assertIn('AutonomyService(service)', audit)
        self.assertIn('F7 E2E verification; no duplicate cognitive cycle', audit)

    def test_canonical_tool_registry_capability_exists(self):
        from persistence.capability_catalog import BASE_CAPABILITIES
        matches = [c for c in BASE_CAPABILITIES if c.get("name") == "tool_registry"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["category"], "tooling")
        self.assertEqual(matches[0]["verification_spec"]["test_key"], "tool_registry_contract")

    def test_selftest_verifies_the_canonical_tool_registry_capability(self):
        source = Path("persistence/selftest.py").read_text(encoding="utf-8")
        self.assertIn('name = "TEST_TOOL_REGISTRY_CONTRACT"', source)
        self.assertIn('name": "tool_registry"', source)
        self.assertIn('test_key": "tool_registry_contract"', source)
        self.assertIn("service.record_capability_verification(", source)



if __name__ == "__main__":
    unittest.main()
