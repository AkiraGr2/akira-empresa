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

    def test_generic_tool_route_passes_schema_validated_inputs_to_executor(self):
        source = Path("nexus.py").read_text(encoding="utf-8")
        self.assertIn("validate_tool_inputs(tool, inputs)", source)
        self.assertIn('owner_scope=s["owner_scope"] if s.get("is_owner") else None', source)

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
