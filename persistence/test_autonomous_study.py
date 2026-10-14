import unittest

from persistence.autonomous_study import (
    extract_study_topic,
    extract_study_undo_id,
    run_autonomous_study,
    undo_autonomous_study,
)


class _Service:
    def __init__(self):
        self.records = {}
        self.next_id = 0

    def save_learning(self, data, actor, idempotency_key, owner_scope):
        for record in self.records.values():
            if record["idempotency_key"] == idempotency_key:
                return {"record": dict(record), "outcome": "already_synced"}
        self.next_id += 1
        record = dict(data, id=f"learn_{self.next_id}", version=1,
                      owner_scope=owner_scope, idempotency_key=idempotency_key)
        self.records[record["id"]] = record
        return {"record": dict(record), "outcome": "created"}

    def get_learning(self, learning_id, owner_scope=None):
        record = self.records[learning_id]
        if owner_scope and record.get("owner_scope") != owner_scope:
            return None
        return dict(record)

    def update_learning(self, learning_id, changes, expected_version=None,
                        actor=None, owner_scope=None):
        record = self.records[learning_id]
        if expected_version != record["version"]:
            raise RuntimeError("version_conflict")
        record.update(changes)
        record["version"] += 1
        return dict(record)

    def add_learning_evidence(self, learning_id, evidence, expected_version=None,
                              actor=None, owner_scope=None):
        record = self.records[learning_id]
        return self.update_learning(
            learning_id, {"evidence": list(record["evidence"]) + evidence},
            expected_version=expected_version, actor=actor, owner_scope=owner_scope,
        )

    def update_learning_status(self, learning_id, status, expected_version=None,
                               actor=None, owner_scope=None):
        return self.update_learning(
            learning_id, {"status": status}, expected_version=expected_version,
            actor=actor, owner_scope=owner_scope,
        )

    def promote_learning_to_graph(self, learning_id, actor=None, owner_scope=None):
        record = self.records[learning_id]
        return {"promoted": True, "learning": dict(record),
                "memory": {"privacy_level": "PRIVATE"}}

    def cleanup_learning_materialization(self, learning_id, actor=None, owner_scope=None):
        self.cleaned = learning_id
        return {"archived_nodes": 1, "archived_memories": 1, "archived_edges": 1}


class _FailingPromotionService(_Service):
    def promote_learning_to_graph(self, learning_id, actor=None, owner_scope=None):
        raise RuntimeError("promotion_failure")


def _sources():
    return [
        {"title": "Official source A", "reference": "https://developer.mozilla.org/a",
         "snippet": "A sufficiently long factual snippet from a technical source."},
        {"title": "Official source B", "reference": "https://web.dev/b",
         "snippet": "Another sufficiently long factual snippet from an independent source."},
    ]


class AutonomousStudyTests(unittest.TestCase):
    def test_explicit_study_phrases_extract_the_requested_topic(self):
        self.assertEqual(
            extract_study_topic("Akira, aprende sobre desarrollo web a nivel senior"),
            ("desarrollo web a nivel senior", True),
        )
        self.assertEqual(
            extract_study_topic("quiero que aprendas sobre Python avanzado"),
            ("Python avanzado", True),
        )
        self.assertEqual(extract_study_topic("¿Qué sabes de Python?"), (None, False))

    def test_undo_phrase_requires_a_learning_id(self):
        self.assertEqual(
            extract_study_undo_id("Akira, olvida el aprendizaje learn_123"),
            "learn_123",
        )
        self.assertIsNone(extract_study_undo_id("olvida todo lo que sabes"))

    def test_supported_study_is_private_and_promoted_without_owner_approval(self):
        service = _Service()
        result = run_autonomous_study(
            service, "desarrollo web", "owner@example.com", "owner-1",
            lambda _topic, max_results: _sources(),
            lambda _topic, evidence: {
                "verdict": "supported", "confidence": 0.91,
                "summary": "Resumen útil respaldado por las fuentes [0] [1].",
                "supporting_evidence": [0, 1], "contradicting_evidence": [],
                "gaps": [], "evaluated_by": "test",
            },
        )

        record = result["learning"]
        self.assertTrue(result["promoted"])
        self.assertEqual(record["status"], "consolidated")
        self.assertEqual(record["lesson"], "Resumen útil respaldado por las fuentes [0] [1].")
        self.assertEqual(record["learning_context"]["privacy_level"], "PRIVATE")
        self.assertEqual(len(record["evidence"]), 2)

    def test_weak_evidence_stays_candidate_and_is_not_promoted(self):
        service = _Service()
        result = run_autonomous_study(
            service, "programación", "owner@example.com", "owner-1",
            lambda _topic, max_results: _sources(),
            lambda _topic, evidence: {
                "verdict": "mixed", "confidence": 0.99,
                "summary": "Fuentes contradictorias.",
                "supporting_evidence": [0], "contradicting_evidence": [1],
                "gaps": [],
            },
        )

        self.assertFalse(result["promoted"])
        self.assertEqual(result["learning"]["status"], "candidate")
        self.assertEqual(result["learning"]["learning_context"]["study_state"], "needs_review")

    def test_summary_without_source_citations_stays_candidate(self):
        service = _Service()
        result = run_autonomous_study(
            service, "programación", "owner@example.com", "owner-1",
            lambda _topic, max_results: _sources(),
            lambda _topic, _evidence: {
                "verdict": "supported", "confidence": 0.99,
                "summary": "Resumen sin referencias.",
                "supporting_evidence": [0, 1],
            },
        )
        self.assertFalse(result["promoted"])
        self.assertEqual(result["learning"]["status"], "candidate")

    def test_one_independent_source_is_not_enough(self):
        service = _Service()
        result = run_autonomous_study(
            service, "programación", "owner@example.com", "owner-1",
            lambda _topic, max_results: [
                _sources()[0],
                {**_sources()[0], "reference": "https://sub.developer.mozilla.org/another"},
            ],
            lambda *_args: self.fail("evaluation must not run without independent sources"),
        )

        self.assertEqual(result["reason"], "insufficient_independent_sources")
        self.assertEqual(result["learning"]["status"], "candidate")

    def test_missing_owner_scope_is_rejected_before_persistence(self):
        with self.assertRaisesRegex(ValueError, "owner_scope_required"):
            run_autonomous_study(
                _Service(), "programación", "owner@example.com", "",
                lambda *_args: [], lambda *_args: {},
            )

    def test_undo_withdraws_materialized_study_from_active_recall(self):
        service = _Service()
        learned = run_autonomous_study(
            service, "desarrollo web", "owner@example.com", "owner-1",
            lambda _topic, max_results: _sources(),
            lambda _topic, _evidence: {
                "verdict": "supported", "confidence": 0.91,
                "summary": "Lección con evidencia [0] [1].",
                "supporting_evidence": [0, 1],
            },
        )
        result = undo_autonomous_study(
            service, learned["learning"]["id"], "owner@example.com", "owner-1"
        )
        self.assertEqual(result["learning"]["status"], "obsolete")
        self.assertEqual(result["learning"]["learning_context"]["study_state"], "withdrawn")
        self.assertEqual(result["archived"]["archived_memories"], 1)
        self.assertEqual(service.cleaned, learned["learning"]["id"])

    def test_undo_refuses_non_study_learning(self):
        service = _Service()
        created = service.save_learning({
            "source": "user_teaching", "event": "other", "lesson": "Otro aprendizaje",
            "learning_context": {}, "status": "candidate", "evidence": [],
        }, actor="owner", idempotency_key="other", owner_scope="owner-1")
        with self.assertRaisesRegex(ValueError, "not_autonomous_study"):
            undo_autonomous_study(
                service, created["record"]["id"], "owner", "owner-1"
            )

    def test_failed_promotion_withdraws_learning_instead_of_recalling_partial_state(self):
        service = _FailingPromotionService()
        result = run_autonomous_study(
            service, "desarrollo web", "owner@example.com", "owner-1",
            lambda _topic, max_results: _sources(),
            lambda _topic, _evidence: {
                "verdict": "supported", "confidence": 0.91,
                "summary": "Lección con evidencia [0] [1].",
                "supporting_evidence": [0, 1],
            },
        )
        self.assertFalse(result["promoted"])
        self.assertEqual(result["learning"]["status"], "obsolete")
        self.assertEqual(
            result["learning"]["learning_context"]["study_state"],
            "promotion_failed_withdrawn",
        )
        self.assertEqual(service.cleaned, result["learning"]["id"])


if __name__ == "__main__":
    unittest.main()
