"""Regresiones y metacontrato de learning_persistent."""

from pathlib import Path
import ast
import unittest


class LearningPersistentContractTests(unittest.TestCase):
    def test_learning_evaluate_uses_authenticated_owner_scope(self):
        source = Path("nexus.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        fn = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "v8_learning_evaluate"
        )
        bare_owner_scope_loads = [
            node for node in ast.walk(fn)
            if isinstance(node, ast.Name)
            and node.id == "owner_scope"
            and isinstance(node.ctx, ast.Load)
        ]
        self.assertEqual(
            bare_owner_scope_loads,
            [],
            "v8_learning_evaluate must derive owner_scope from the verified session, not a bare variable",
        )
        fn_source = ast.get_source_segment(source, fn) or ""
        self.assertIn(
            'current = service.get_learning(learning_id, owner_scope=s["owner_scope"])',
            fn_source,
        )
        self.assertIn(
            'owner_scope=s["owner_scope"]',
            fn_source,
        )

    def test_runtime_selftest_persists_capability_verification(self):
        source = Path("persistence/selftest.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        fn = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "t_learning_persistent_capability"
        )
        fn_source = ast.get_source_segment(source, fn) or ""
        self.assertIn("record_capability_verification", fn_source)
        self.assertIn('"test_key": "learning_persistent_contract"', fn_source)
        self.assertIn('"result": "pass" if ok else "fail"', fn_source)
        self.assertIn('effective_state") == "verified"', fn_source)

    def test_canonical_capability_metadata(self):
        source = Path("persistence/capability_catalog.py").read_text(encoding="utf-8")
        self.assertIn('"name": "learning_persistent"', source)
        self.assertIn('"category": "learning"', source)
        self.assertIn('"test_key": "learning_persistent_contract"', source)
        self.assertIn("LEARNING_PERSISTENT_CAPABILITY", source)
        self.assertIn(
            "BASE_CAPABILITIES = (SESSION_AUTH_CAPABILITY, PERSISTENT_MEMORY_CAPABILITY, MEMORY_RECALL_CAPABILITY, LEARNING_PERSISTENT_CAPABILITY)",
            source,
        )


if __name__ == "__main__":
    unittest.main()
