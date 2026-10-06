import unittest

from persistence.service import PersistenceService


class FakeRepo:
    def __init__(self):
        self.data = {
            "self_model": {
                "id": "akira_primary",
                "identity": {"name": "Akira"},
                "purpose": {},
                "models": [],
                "current_state": {},
                "knowledge_state": {},
                "uncertainties": [],
                "errors": [],
                "repairs": [],
                "evolution": [],
                "version": 1,
            },
            "capabilities": [
                {
                    "id": "cap1",
                    "name": "session_auth",
                    "implementation_state": "implemented",
                    "verification_state": "verified",
                    "availability_state": "available",
                    "maturity": "experimental",
                    "cost_compatibility": "conditional",
                    "last_verified_at": "2026-10-04T00:00:00Z",
                },
            ],
            "agents": [
                {
                    "name": "tester",
                    "role": "tester",
                    "status": "idle",
                    "allowed_tools": ["github_repo_read", "python_test"],
                },
            ],
            "tools": [
                {
                    "name": "github_repo_read",
                    "category": "code",
                    "status": "available",
                    "permissions": ["auth"],
                },
                {
                    "name": "python_test",
                    "category": "code",
                    "status": "available",
                    "permissions": ["owner"],
                },
            ],
        }

    def get(self, entity, key):
        rows = self.data.get(entity, {})
        if entity == "self_model" and isinstance(rows, dict) and rows.get("id") == key:
            return rows
        return rows.get(key) if isinstance(rows, dict) else None

    def search(self, entity, filters=None, limit=100, offset=0, order_by="created_at", descending=True):
        rows = self.data.get(entity, [])
        if isinstance(rows, dict):
            rows = list(rows.values())
        return list(rows)[offset:offset + limit]


class SelfKnowledgeSnapshotTests(unittest.TestCase):
    def test_snapshot_uses_authoritative_registries(self):
        service = PersistenceService(FakeRepo())
        snapshot = service.self_knowledge_snapshot(owner_scope=None)

        self.assertEqual(snapshot["source"], "runtime_authoritative_registry")
        self.assertEqual(snapshot["identity_authority"], "identity_root")
        self.assertEqual(snapshot["identity"]["name"], "Akira")
        self.assertEqual(snapshot["capabilities"][0]["name"], "session_auth")
        self.assertEqual(snapshot["agents"][0]["name"], "tester")
        self.assertIn("python_test", snapshot["tools"][1]["name"])
        self.assertEqual(snapshot["limitations"][0].startswith("Los estados de capability"), True)

    def test_cognitive_cycle_owner_scope_regression(self):
        with open("nexus.py", encoding="utf-8") as handle:
            source = handle.read()
        start = source.index("def _execute_cognitive_cycle(")
        end = source.index('@app.post("/api/v8/cognitive/cycle")', start)
        cycle = source[start:end]
        self.assertIn("owner_scope=owner_scope", cycle)
        self.assertNotIn('owner_scope=s["owner_scope"]', cycle)

    def test_self_model_semantic_contract_rejects_unstructured_state(self):
        from persistence.core import ValidationError, validate_self_model
        with self.assertRaises(ValidationError):
            validate_self_model({"current_state": {"cycles_completed": -1}}, partial=True)
        with self.assertRaises(ValidationError):
            validate_self_model({"uncertainties": ["legacy string"]}, partial=True)
        with self.assertRaises(ValidationError):
            validate_self_model({
                "errors": [{
                    "id": "e1",
                    "type": "runtime",
                    "message": "x",
                    "status": "unknown",
                    "first_seen_at": "2026-10-06T00:00:00+00:00",
                    "last_seen_at": "2026-10-06T00:00:00+00:00",
                }]
            }, partial=True)

    def test_self_model_semantic_contract_accepts_observed_state_and_records(self):
        from persistence.core import validate_self_model
        result = validate_self_model({
            "current_state": {
                "cycles_completed": 4,
                "last_cycle_id": "cycle_1",
                "last_cycle_at": "2026-10-06T01:00:00+00:00",
                "last_observed_at": "2026-10-06T01:00:01+00:00",
                "last_cycle_trigger": "manual",
                "last_cycle_model": "gemini-3.8-flash",
            },
            "knowledge_state": {
                "last_observed_at": "2026-10-06T01:00:00+00:00",
                "sources": [{
                    "id": "CapabilityEngine",
                    "kind": "registry",
                    "observed_at": "2026-10-06T01:00:00+00:00",
                }],
            },
            "uncertainties": [{
                "id": "u1",
                "statement": "Hay una dependencia externa.",
                "kind": "capability",
                "status": "open",
                "evidence": [],
                "created_at": "2026-10-06T01:00:00+00:00",
            }],
            "errors": [{
                "id": "e1",
                "type": "runtime",
                "message": "Ejemplo",
                "status": "open",
                "occurrences": 1,
                "first_seen_at": "2026-10-06T01:00:00+00:00",
                "last_seen_at": "2026-10-06T01:00:00+00:00",
                "evidence": [],
            }],
            "repairs": [{
                "id": "r1",
                "target": "chat",
                "reason": "corregir regresion",
                "status": "completed",
                "proposed_at": "2026-10-06T01:00:00+00:00",
                "started_at": "2026-10-06T01:02:00+00:00",
                "completed_at": "2026-10-06T01:05:00+00:00",
                "evidence": [],
                "result": "corregido y verificado",
            }],
            "evolution": [{
                "id": "ev1",
                "proposal": "mejorar contrato",
                "rationale": "evitar ambiguedad",
                "status": "proposed",
                "proposed_at": "2026-10-06T01:00:00+00:00",
                "evidence": [],
            }],
        }, partial=True)
        self.assertEqual(result["current_state"]["cycles_completed"], 4)
        self.assertEqual(result["uncertainties"][0]["status"], "open")
        self.assertEqual(result["errors"][0]["occurrences"], 1)
        self.assertEqual(result["repairs"][0]["status"], "completed")
        self.assertEqual(result["evolution"][0]["status"], "proposed")
        from persistence.core import ValidationError, validate_self_model
        with self.assertRaises(ValidationError):
            validate_self_model({
                "uncertainties": [{
                    "id": "u2",
                    "statement": "Debe resolverse",
                    "kind": "evidence",
                    "status": "resolved",
                    "evidence": [],
                    "created_at": "2026-10-06T01:00:00+00:00",
                }]
            }, partial=True)
        with self.assertRaises(ValidationError):
            validate_self_model({
                "repairs": [{
                    "id": "r2",
                    "target": "chat",
                    "reason": "test",
                    "status": "completed",
                    "proposed_at": "2026-10-06T01:00:00+00:00",
                    "evidence": [],
                    "result": "ok",
                }]
            }, partial=True)
        with self.assertRaises(ValidationError):
            validate_self_model({
                "evolution": [{
                    "id": "ev2",
                    "proposal": "test",
                    "rationale": "test",
                    "status": "implemented",
                    "proposed_at": "2026-10-06T01:00:00+00:00",
                    "evidence": [],
                }]
            }, partial=True)


    def test_self_model_models_follow_authoritative_registry(self):
        from persistence.model_registry import model_registry_snapshot
        service = PersistenceService(FakeRepo())
        model = service.get_self_model()
        self.assertEqual(model["models"], model_registry_snapshot()["routes"])
    def test_self_model_rejects_manual_derived_registry_updates(self):
        from persistence.core import ValidationError, validate_self_model
        for field in ("capabilities", "tools"):
            with self.assertRaises(ValidationError):
                validate_self_model({field: []}, partial=True)

    def test_self_model_read_rejects_invalid_persisted_semantics(self):
        from persistence.core import ValidationError
        service = PersistenceService(FakeRepo())
        service.repo.data["self_model"]["current_state"] = {"cycles_completed": -1}
        with self.assertRaises(ValidationError):
            service.get_self_model()

    def test_self_model_exposes_live_registry_projection(self):
        service = PersistenceService(FakeRepo())
        model = service.get_self_model()
        self.assertEqual(model["capabilities"][0]["name"], "session_auth")
        self.assertEqual(model["tools"][0]["name"], "github_repo_read")


if __name__ == "__main__":
    unittest.main()
