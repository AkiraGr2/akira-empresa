"""Regression contract: sensitive AKIRA routes must remain owner-protected.

This static test makes the security architecture fail closed in CI when a future route
is added under a sensitive subsystem without the centralized owner guard.
"""
from pathlib import Path
import re
import unittest

NEXUS = Path(__file__).with_name("nexus.py")
SENSITIVE_PREFIXES = (
    "/api/v8/self",
    "/api/v8/learning",
    "/api/v8/graph",
    "/api/v8/cognitive",
    "/api/v8/missions",
    "/api/v8/agents",
    "/api/v8/tasks",
    "/api/v8/repair",
    "/api/v8/autonomy",
    "/api/v8/memory",
    "/api/memory",
    "/api/brain",
)
ROUTE_RE = re.compile(r'^@(app)\.(get|post|patch|delete|put)\("([^"]+)"')

PUBLIC_ROUTE_KEYS = {
    ("GET", "/api/v8/graph/public-overview"),
}

def route_blocks(text):
    lines = text.splitlines()
    found = []
    starts = [i for i, line in enumerate(lines) if ROUTE_RE.match(line)]
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
        match = ROUTE_RE.match(lines[start])
        found.append({
            "line": start + 1,
            "method": match.group(2).upper(),
            "path": match.group(3),
            "source": "\n".join(lines[start:end]),
        })
    return found

class SensitiveRouteSecurityContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = NEXUS.read_text(encoding="utf-8")
        cls.routes = route_blocks(cls.text)

    def test_sensitive_routes_use_central_owner_guard(self):
        missing = []
        for route in self.routes:
            route_key = (route["method"], route["path"])
            if route_key in PUBLIC_ROUTE_KEYS:
                continue
            if any(route["path"].startswith(prefix) for prefix in SENSITIVE_PREFIXES):
                if "_require_owner(request)" not in route["source"]:
                    missing.append(
                        f'{route["method"]} {route["path"]} (line {route["line"]})'
                    )
        self.assertFalse(
            missing,
            "Sensitive route(s) without centralized owner guard: " + ", ".join(missing),
        )

    def test_repair_routes_are_owner_protected_and_explicit(self):
        expected = {
            ("POST", "/api/v8/repair"),
            ("GET", "/api/v8/repair"),
            ("GET", "/api/v8/repair/{repair_id}"),
            ("POST", "/api/v8/repair/{repair_id}/advance"),
            ("POST", "/api/v8/repair/{repair_id}/sandbox"),
            ("POST", "/api/v8/repair/{repair_id}/test"),
            ("POST", "/api/v8/repair/{repair_id}/evaluate"),
            ("POST", "/api/v8/repair/{repair_id}/approve"),
            ("POST", "/api/v8/repair/{repair_id}/apply"),
            ("POST", "/api/v8/repair/{repair_id}/discard"),
        }
        found = {
            (r["method"], r["path"])
            for r in self.routes
            if r["path"].startswith("/api/v8/repair")
        }
        self.assertEqual(found, expected)
        for route in self.routes:
            if route["path"].startswith("/api/v8/repair"):
                self.assertIn("_require_owner(request)", route["source"])

    def test_controlled_autonomy_routes_are_owner_protected(self):
        expected = {
            ("POST", "/api/v8/autonomy"),
            ("GET", "/api/v8/autonomy"),
            ("GET", "/api/v8/autonomy/{run_id}"),
            ("POST", "/api/v8/autonomy/{run_id}/approve"),
            ("POST", "/api/v8/autonomy/{run_id}/act"),
            ("POST", "/api/v8/autonomy/{run_id}/reject"),
            ("POST", "/api/v8/autonomy/{run_id}/cancel"),
        }
        found = {
            (r["method"], r["path"])
            for r in self.routes
            if r["path"].startswith("/api/v8/autonomy")
        }
        self.assertEqual(found, expected)
        for route in self.routes:
            if route["path"].startswith("/api/v8/autonomy"):
                self.assertIn("_require_owner(request)", route["source"])

    def test_tool_invocation_history_is_owner_protected(self):
        route = next(
            r for r in self.routes
            if (r["method"], r["path"]) == ("GET", "/api/v8/tools/invocations")
        )
        self.assertIn("_require_owner(request)", route["source"])
        self.assertIn('actor=s["email"]', route["source"])

    def test_conversation_routes_preserve_row_ownership_boundary(self):
        expected = {
            ("POST", "/api/v8/conversations"),
            ("GET", "/api/v8/conversations"),
            ("GET", "/api/v8/conversations/{conversation_id}"),
            ("PATCH", "/api/v8/conversations/{conversation_id}"),
            ("DELETE", "/api/v8/conversations/{conversation_id}"),
        }
        routes = {
            (r["method"], r["path"]): r
            for r in self.routes
            if r["path"].startswith("/api/v8/conversations")
        }
        self.assertEqual(set(routes), expected)
        for key, route in routes.items():
            self.assertIn("get_session(request)", route["source"], key)
            self.assertTrue(
                ("created_by" in route["source"] or "owner=" in route["source"] or 'actor=s["email"]' in route["source"]),
            )

    def test_public_graph_route_contains_no_private_query_access(self):
        route = next(
            r for r in self.routes
            if (r["method"], r["path"]) == ("GET", "/api/v8/graph/public-overview")
        )
        for forbidden in ("owner_scope", "privacy_level", "list_graph_nodes", "list_graph_edges"):
            self.assertNotIn(
                forbidden,
                route["source"],
                "Public graph route must not query private graph persistence",
            )

    def test_graph_mutation_routes_propagate_owner_scope(self):
        reinforce = next(
            r for r in self.routes
            if (r["method"], r["path"]) == ("POST", "/api/v8/graph/reinforce")
        )
        cleanup = next(
            r for r in self.routes
            if (r["method"], r["path"]) == ("POST", "/api/v8/graph/cleanup_tests")
        )
        self.assertIn('owner_scope=s["owner_scope"]', reinforce["source"])
        self.assertIn('{"owner_scope": s["owner_scope"]}', cleanup["source"])

    def test_no_sensitive_route_uses_client_identity_as_authority(self):
        forbidden = (
            'payload.get("is_owner"',
            "payload.get('is_owner'",
            'localStorage.getItem("akira_is_owner"',
            "localStorage.getItem('akira_is_owner'",
        )
        for route in self.routes:
            route_key = (route["method"], route["path"])
            if route_key in PUBLIC_ROUTE_KEYS:
                continue
            if any(route["path"].startswith(prefix) for prefix in SENSITIVE_PREFIXES):
                for fragment in forbidden:
                    self.assertNotIn(
                        fragment,
                        route["source"],
                        f"{route['method']} {route['path']} trusts client identity",
                    )

if __name__ == "__main__":
    unittest.main()