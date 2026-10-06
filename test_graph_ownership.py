import unittest

from persistence.service import NotFoundError, PersistenceService, ValidationError


class FakeTx:
    def __init__(self, repo):
        self.repo = repo

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def create(self, entity, record):
        self.repo.rows.setdefault(entity, []).append(dict(record))
        return dict(record), True

    def update(self, entity, record_id, changes, expected_version):
        rows = self.repo.rows.get(entity, [])
        row = next(r for r in rows if r["id"] == record_id)
        if row["version"] != expected_version:
            raise RuntimeError("version conflict")
        row.update(changes)
        row["version"] += 1
        return dict(row)

    def append_audit(self, payload):
        return None


class FakeRepo:
    def __init__(self):
        self.rows = {
            "graph_nodes": [
                {"id": "core", "label": "Akira", "owner_scope": "system", "status": "active", "version": 1},
                {"id": "a1", "label": "A", "owner_scope": "scope:A", "status": "active", "version": 1},
                {"id": "b1", "label": "B", "owner_scope": "scope:B", "status": "active", "version": 1},
                {"id": "legacy", "label": "Legacy", "owner_scope": "owner", "status": "active", "version": 1},
                {"id": "archived", "label": "Archived", "owner_scope": "scope:A", "status": "archived", "version": 1},
            ],
            "graph_edges": [
                {"id": "e1", "from_node": "a1", "to_node": "core", "status": "active", "version": 1},
                {"id": "e2", "from_node": "b1", "to_node": "core", "status": "active", "version": 1},
            ],
        }

    def get(self, entity, record_id):
        for row in self.rows.get(entity, []):
            if row.get("id") == record_id:
                return dict(row)
        return None

    def search(self, entity, filters=None, limit=50, offset=0, order_by="created_at", descending=True):
        rows = [dict(r) for r in self.rows.get(entity, [])]
        for key, value in (filters or {}).items():
            rows = [r for r in rows if r.get(key) == value]
        return rows[offset:offset + limit]

    def count(self, entity, filters=None):
        return len(self.search(entity, filters, limit=5000))

    def transaction(self):
        return FakeTx(self)


class GraphOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.service = PersistenceService(FakeRepo())

    def test_node_visibility_is_scoped_with_core_exception(self):
        self.assertIsNotNone(self.service.get_node("a1", owner_scope="scope:A"))
        self.assertIsNone(self.service.get_node("b1", owner_scope="scope:A"))
        self.assertIsNotNone(self.service.get_node("core", owner_scope="scope:A"))

    def test_legacy_owner_node_is_not_visible_to_scoped_owner(self):
        self.assertIsNone(self.service.get_node("legacy", owner_scope="scope:A"))

    def test_list_graph_nodes_does_not_leak_legacy_owner_nodes(self):
        ids = {n["id"] for n in self.service.list_graph_nodes(owner_scope="scope:A")}
        self.assertNotIn("legacy", ids)

    def test_edge_visibility_requires_both_endpoints_to_be_accessible(self):
        self.assertIsNotNone(self.service.get_edge("e1", owner_scope="scope:A"))
        self.assertIsNone(self.service.get_edge("e2", owner_scope="scope:A"))

    def test_related_nodes_does_not_cross_owner_boundary(self):
        edges = self.service.related_nodes("core", owner_scope="scope:A", limit=50)
        self.assertEqual([e["id"] for e in edges], ["e1"])

    def test_list_graph_nodes_scopes_and_keeps_core(self):
        ids = {n["id"] for n in self.service.list_graph_nodes(owner_scope="scope:A")}
        self.assertEqual(ids, {"core", "a1"})

    def test_cross_owner_edge_is_rejected(self):
        with self.assertRaises(NotFoundError):
            self.service.create_edge(
                {"from_node": "a1", "to_node": "b1", "relation_type": "related_to"},
                owner_scope="scope:A",
            )

    def test_edge_rejects_archived_endpoint(self):
        with self.assertRaises(ValidationError):
            self.service.create_edge(
                {"from_node": "archived", "to_node": "a1", "relation_type": "related_to"},
                owner_scope="scope:A",
            )

    def test_internal_upsert_refuses_cross_owner_edge(self):
        self.assertIsNone(
            self.service._upsert_edge(
                "a1", "b1", "related_to", owner_scope="scope:A"
            )
        )

    def test_same_owner_edge_remains_allowed(self):
        result = self.service.create_edge(
            {"from_node": "a1", "to_node": "a1", "relation_type": "related_to"},
            owner_scope="scope:A",
        )
        self.assertEqual(result["record"]["from_node"], "a1")


if __name__ == "__main__":
    unittest.main()
