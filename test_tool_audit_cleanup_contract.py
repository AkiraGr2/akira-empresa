"""Regression coverage for F8 tool-audit fixture cleanup.

Tests only synthetic in-memory records; no provider calls or production database writes.
"""
from __future__ import annotations

import copy
import unittest

from tool_audit import _cleanup_fixture


class FakeRepository:
    def __init__(self, nodes, edges, learning_events, memories, fail_deletes=None):
        self.tables = {
            "graph_nodes": {row["id"]: copy.deepcopy(row) for row in nodes},
            "graph_edges": {row["id"]: copy.deepcopy(row) for row in edges},
            "learning_events": {row["id"]: copy.deepcopy(row) for row in learning_events},
            "memories": {row["id"]: copy.deepcopy(row) for row in memories},
        }
        self.fail_deletes = set(fail_deletes or ())

    def search(self, entity, filters=None, limit=100, order_by=None, descending=False):
        filters = filters or {}
        rows = [
            copy.deepcopy(row)
            for row in self.tables[entity].values()
            if all(row.get(key) == value for key, value in filters.items())
        ]
        if order_by:
            rows.sort(key=lambda row: row.get(order_by) or "", reverse=descending)
        return rows[:limit]

    def get(self, entity, record_id):
        row = self.tables[entity].get(record_id)
        return copy.deepcopy(row) if row is not None else None

    def delete(self, entity, record_id):
        if (entity, record_id) in self.fail_deletes:
            return False
        if entity == "graph_nodes":
            linked = any(
                edge.get("from_node") == record_id or edge.get("to_node") == record_id
                for edge in self.tables["graph_edges"].values()
            )
            if linked:
                raise RuntimeError("fixture node still has graph edges")
        return self.tables[entity].pop(record_id, None) is not None


class FakeService:
    def __init__(self, repo):
        self.repo = repo
        self.audit_events = []

    def record_audit(self, actor, action, resource, resource_id=None, status="success", detail=None):
        self.audit_events.append({
            "actor": actor,
            "action": action,
            "resource": resource,
            "resource_id": resource_id,
            "status": status,
            "detail": copy.deepcopy(detail or {}),
        })


def make_service(fail_deletes=None):
    nodes = [
        {"id": "node_f8_a", "label": "AKIRA F8 TOOL AUDIT test-run", "created_at": "2026-10-08T00:00:00Z"},
        {"id": "node_f8_b", "label": "AKIRA F8 TOOL AUDIT B test-run", "created_at": "2026-10-08T00:00:01Z"},
        {"id": "node_core", "label": "Akira", "created_at": "2026-01-01T00:00:00Z"},
        {"id": "node_unrelated", "label": "Unrelated user content", "created_at": "2026-01-02T00:00:00Z"},
    ]
    edges = [
        {"id": "edge_f8_fixture", "from_node": "node_f8_a", "to_node": "node_f8_b", "created_at": "2026-10-08T00:00:02Z"},
        {"id": "edge_f8_outgoing", "from_node": "node_f8_a", "to_node": "node_core", "created_at": "2026-10-08T00:00:03Z"},
        {"id": "edge_f8_incoming", "from_node": "node_core", "to_node": "node_f8_b", "created_at": "2026-10-08T00:00:04Z"},
        {"id": "edge_unrelated", "from_node": "node_core", "to_node": "node_unrelated", "created_at": "2026-01-03T00:00:00Z"},
    ]
    learning_events = [{"id": "learn_f8_fixture", "event": "f8_tool_audit_test-run"}]
    memories = [{"id": "mem_f8_fixture", "content": "AKIRA F8 TOOL AUDIT test-run"}]
    repo = FakeRepository(nodes, edges, learning_events, memories, fail_deletes=fail_deletes)
    return FakeService(repo)


FIXTURE = {
    "graph_node_a_id": "node_f8_a",
    "graph_node_b_id": "node_f8_b",
    "graph_edge_id": "edge_f8_fixture",
    "learning_id": "learn_f8_fixture",
    "memory_id": "mem_f8_fixture",
}


class ToolAuditCleanupContractTests(unittest.TestCase):
    def test_cleanup_removes_incoming_and_outgoing_fixture_edges_before_nodes(self):
        service = make_service()

        cleanup = _cleanup_fixture(
            service,
            copy.deepcopy(FIXTURE),
            actor="f8-test-owner",
            owner_scope="owner",
            audit_tag="f8-cleanup-regression",
        )

        self.assertTrue(cleanup["ok"], cleanup)
        for entity, record_id in (
            ("graph_nodes", "node_f8_a"),
            ("graph_nodes", "node_f8_b"),
            ("graph_edges", "edge_f8_fixture"),
            ("graph_edges", "edge_f8_outgoing"),
            ("graph_edges", "edge_f8_incoming"),
            ("learning_events", "learn_f8_fixture"),
            ("memories", "mem_f8_fixture"),
        ):
            self.assertIsNone(service.repo.get(entity, record_id), f"{entity}/{record_id} leaked")

        # Cleanup must not delete the core node or unrelated graph data.
        self.assertIsNotNone(service.repo.get("graph_nodes", "node_core"))
        self.assertIsNotNone(service.repo.get("graph_nodes", "node_unrelated"))
        self.assertIsNotNone(service.repo.get("graph_edges", "edge_unrelated"))
        self.assertTrue(all(
            action.get("confirmed_absent", True)
            for action in cleanup["actions"]
        ))
        self.assertEqual(service.audit_events[-1]["action"], "tool_audit.cleanup")
        self.assertEqual(service.audit_events[-1]["status"], "success")
        self.assertTrue(service.audit_events[-1]["detail"]["cleanup"]["ok"])

    def test_cleanup_fails_closed_when_a_fixture_edge_cannot_be_deleted(self):
        service = make_service(fail_deletes={("graph_edges", "edge_f8_incoming")})

        cleanup = _cleanup_fixture(
            service,
            copy.deepcopy(FIXTURE),
            actor="f8-test-owner",
            owner_scope="owner",
            audit_tag="f8-cleanup-fail-closed",
        )

        self.assertFalse(cleanup["ok"], cleanup)
        self.assertIsNotNone(service.repo.get("graph_edges", "edge_f8_incoming"))
        self.assertEqual(service.audit_events[-1]["action"], "tool_audit.cleanup")
        self.assertEqual(service.audit_events[-1]["status"], "failure")
        self.assertFalse(service.audit_events[-1]["detail"]["cleanup"]["ok"])


if __name__ == "__main__":
    unittest.main()
