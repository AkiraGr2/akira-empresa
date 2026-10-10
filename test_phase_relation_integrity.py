import unittest
from pathlib import Path

from persistence.selftest import run_relation_integrity_test


class FakeRepo:
    def __init__(self):
        self.rows = {
            "cognitive_cycles": {},
            "cognitive_events": {},
            "learning_events": {},
            "knowledge_records": {},
            "graph_nodes": {},
            "graph_edges": {},
        }

    def get(self, entity, record_id):
        row = self.rows.get(entity, {}).get(record_id)
        return dict(row) if row else None

    def search(self, entity, filters=None, limit=50, **_kwargs):
        rows = list(self.rows.get(entity, {}).values())
        for key, value in (filters or {}).items():
            rows = [row for row in rows if row.get(key) == value]
        return [dict(row) for row in rows[:limit]]

    def delete(self, entity, record_id):
        return self.rows.get(entity, {}).pop(record_id, None) is not None


class FakeService:
    def __init__(self, persist_learning_edge=True):
        self.repo = FakeRepo()
        self.persist_learning_edge = persist_learning_edge
        self._next = 0

    def _id(self, prefix):
        self._next += 1
        return f"{prefix}_{self._next}"

    def start_cycle(self, trigger, input_data=None, owner_scope=None, **_kwargs):
        record = {
            "id": self._id("cycle"),
            "trigger": trigger,
            "input": input_data or {},
            "owner_scope": owner_scope,
            "status": "in_progress",
            "version": 1,
        }
        self.repo.rows["cognitive_cycles"][record["id"]] = record
        return {"record": dict(record)}

    def record_stage(self, cycle_id, stage, data=None, owner_scope=None, **_kwargs):
        cycle = self.repo.get("cognitive_cycles", cycle_id)
        if not cycle or cycle["owner_scope"] != owner_scope:
            raise LookupError(cycle_id)
        event = {
            "id": self._id("event"),
            "cycle_id": cycle_id,
            "stage": stage,
            "status": "success",
            "data": data or {},
        }
        self.repo.rows["cognitive_events"][event["id"]] = event
        cycle["current_stage"] = stage
        cycle["version"] += 1
        self.repo.rows["cognitive_cycles"][cycle_id] = cycle
        return {"event": dict(event), "cycle": dict(cycle)}

    def complete_cycle(self, cycle_id, final_status, owner_scope=None, **_kwargs):
        cycle = self.repo.get("cognitive_cycles", cycle_id)
        if not cycle or cycle["owner_scope"] != owner_scope:
            raise LookupError(cycle_id)
        cycle["status"] = final_status
        cycle["version"] += 1
        self.repo.rows["cognitive_cycles"][cycle_id] = cycle
        return dict(cycle)

    def create_node(self, data, **_kwargs):
        node = {**data, "id": self._id("node"), "status": "active", "version": 1}
        self.repo.rows["graph_nodes"][node["id"]] = node
        return {"record": dict(node)}

    def save_learning(self, data, owner_scope=None, **_kwargs):
        learning = {**data, "id": self._id("learn"), "owner_scope": owner_scope}
        self.repo.rows["learning_events"][learning["id"]] = learning
        learning_node = {
            "id": self._id("node"),
            "node_type": "experience",
            "label": f"learning:{learning['id']}",
            "owner_scope": owner_scope,
            "status": "active",
        }
        self.repo.rows["graph_nodes"][learning_node["id"]] = learning_node
        if self.persist_learning_edge:
            edge = {
                "id": self._id("edge"),
                "from_node": learning_node["id"],
                "to_node": data["knowledge_nodes"][0],
                "relation_type": "learned_from",
                "status": "active",
            }
            self.repo.rows["graph_edges"][edge["id"]] = edge
        return {"record": dict(learning)}

    def save_knowledge(self, data, owner_scope=None, **_kwargs):
        knowledge = {**data, "id": self._id("know"), "owner_scope": owner_scope}
        self.repo.rows["knowledge_records"][knowledge["id"]] = knowledge
        return {"record": dict(knowledge)}

    def get_cycle(self, cycle_id, owner_scope=None):
        row = self.repo.get("cognitive_cycles", cycle_id)
        return row if row and row["owner_scope"] == owner_scope else None

    def list_cycle_events(self, cycle_id, owner_scope=None):
        if self.get_cycle(cycle_id, owner_scope) is None:
            return []
        return self.repo.search("cognitive_events", {"cycle_id": cycle_id}, limit=100)

    def get_learning(self, learning_id, owner_scope=None):
        row = self.repo.get("learning_events", learning_id)
        return row if row and row["owner_scope"] == owner_scope else None

    def get_knowledge(self, knowledge_id, owner_scope=None):
        row = self.repo.get("knowledge_records", knowledge_id)
        return row if row and row["owner_scope"] == owner_scope else None

    def search_knowledge(self, filters=None, owner_scope=None, limit=10):
        return self.repo.search(
            "knowledge_records",
            {**(filters or {}), "owner_scope": owner_scope},
            limit=limit,
        )

    def get_node(self, node_id, owner_scope=None):
        row = self.repo.get("graph_nodes", node_id)
        return row if row and row.get("owner_scope") == owner_scope else None


class RelationIntegritySelftestTests(unittest.TestCase):
    def test_startup_selftest_runs_the_relation_integrity_probe(self):
        source = Path("persistence/selftest.py").read_text(encoding="utf-8")

        self.assertIn('"TEST_RELATION_INTEGRITY",', source)
        self.assertIn("lambda: run_relation_integrity_test(service)", source)
        self.assertNotIn('"status": "N/A"', source)

    def test_cross_phase_links_are_verified_and_fixtures_are_cleaned(self):
        service = FakeService()

        result = run_relation_integrity_test(service)

        self.assertEqual(result["status"], "PASS", result["detail"])
        self.assertTrue(all(not rows for rows in service.repo.rows.values()))

    def test_missing_graph_edge_fails_and_still_cleans_fixtures(self):
        service = FakeService(persist_learning_edge=False)

        result = run_relation_integrity_test(service)

        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(all(not rows for rows in service.repo.rows.values()))


if __name__ == "__main__":
    unittest.main()
