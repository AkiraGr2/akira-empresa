import unittest

from persistence.core import ValidationError
from persistence.service import PersistenceService


class _Tx:
    def __init__(self, repo):
        self.repo = repo

    def update(self, entity, record_id, changes, expected_version):
        record = self.repo.data[entity][record_id]
        if record.get("version") != expected_version:
            raise RuntimeError("version_conflict")
        record.update(changes)
        record["version"] = expected_version + 1
        return dict(record)

    def append_audit(self, payload):
        self.repo.audit.append(dict(payload))


class _Repo:
    def __init__(self, learning):
        self.data = {"learning_events": {learning["id"]: dict(learning)}}
        self.audit = []

    def get(self, entity, record_id):
        record = self.data.get(entity, {}).get(record_id)
        return dict(record) if record is not None else None

    def update(self, entity, record_id, changes, expected_version):
        return _Tx(self).update(entity, record_id, changes, expected_version)

    def append_audit(self, payload):
        self.audit.append(dict(payload))

    def transaction(self):
        class _Ctx:
            def __enter__(_self):
                return _Tx(self)

            def __exit__(_self, exc_type, exc, tb):
                return False
        return _Ctx()


def _learning(status="verified", analysis=None):
    return {
        "id": "learn_test_gate",
        "status": status,
        "version": 1,
        "evidence": [{"type": "manual_verification", "title": "test", "reference": "test"}],
        "verification_analysis": analysis or {},
        "lesson": "Una leccion de prueba.",
        "source": "test",
        "event": "test",
        "knowledge_nodes": [],
        "relationships": [],
        "confidence": 0.8,
        "outcome": "unknown",
        "learning_context": {},
    }


class ConsolidationGateTests(unittest.TestCase):
    def test_verified_without_evaluation_cannot_consolidate(self):
        service = PersistenceService(_Repo(_learning()))
        with self.assertRaises(ValidationError):
            service.update_learning_status("learn_test_gate", "consolidated", expected_version=1)
        self.assertEqual(service.get_learning("learn_test_gate")["status"], "verified")

    def test_supported_below_threshold_cannot_consolidate(self):
        service = PersistenceService(_Repo(_learning(
            analysis={"verdict": "supported", "confidence": 0.69}
        )))
        with self.assertRaises(ValidationError):
            service.update_learning_status("learn_test_gate", "consolidated", expected_version=1)

    def test_supported_at_threshold_can_consolidate(self):
        service = PersistenceService(_Repo(_learning(
            analysis={"verdict": "supported", "confidence": 0.70}
        )))
        result = service.update_learning_status(
            "learn_test_gate", "consolidated", expected_version=1
        )
        self.assertEqual(result["status"], "consolidated")
        self.assertEqual(result["version"], 2)

    def test_contradicted_cannot_consolidate(self):
        service = PersistenceService(_Repo(_learning(
            analysis={"verdict": "contradicted", "confidence": 0.99}
        )))
        with self.assertRaises(ValidationError):
            service.update_learning_status("learn_test_gate", "consolidated", expected_version=1)


if __name__ == "__main__":
    unittest.main()
