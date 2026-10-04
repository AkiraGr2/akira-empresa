import unittest

from persistence.capability import derive_effective_state
from persistence.core import GRAPH_EDGE_SCHEMA_VERSION, GRAPH_NODE_SCHEMA_VERSION
from persistence.service import LEGACY_OWNER_SCOPE, _scope_matches


class GraphPersistentContractTests(unittest.TestCase):
    def test_schema_versions_and_owner_scope_contract(self):
        self.assertEqual(GRAPH_NODE_SCHEMA_VERSION, "graph_node.v1")
        self.assertEqual(GRAPH_EDGE_SCHEMA_VERSION, "graph_edge.v1")
        self.assertTrue(_scope_matches("g:user-A", "g:user-A"))
        self.assertFalse(_scope_matches("g:user-B", "g:user-A"))
        self.assertTrue(_scope_matches(LEGACY_OWNER_SCOPE, "g:user-A"))

    def test_verified_effective_state(self):
        record = {
            "implementation_state": "implemented",
            "verification_state": "verified",
            "availability_state": "available",
            "maturity": "experimental",
            "cost_compatibility": "conditional",
            "verification_spec": {
                "freshness_policy": {
                    "mode": "on_change",
                    "max_age_seconds": None,
                    "invalidate_on": ["build_change"],
                }
            },
        }
        self.assertEqual(derive_effective_state(record), "verified")


if __name__ == "__main__":
    unittest.main()
