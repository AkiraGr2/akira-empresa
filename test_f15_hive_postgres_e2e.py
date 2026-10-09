"""F15 Hive sharing E2E contract against a disposable real PostgreSQL database.

Safety: this module refuses non-loopback DATABASE_URL values. CI runs it only against
its disposable pgvector/PostgreSQL service container; production credentials are never used.
"""
from __future__ import annotations

import os
import unittest
from urllib.parse import urlparse

from persistence.core import ConflictError, NotFoundError, ValidationError
from persistence.postgres import PostgresRepository, make_pool, migrate
from persistence.service import PersistenceService

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@127.0.0.1:5432/akira_f12_test",
)
if urlparse(DATABASE_URL).hostname not in {"127.0.0.1", "localhost"}:
    raise RuntimeError("F15 PostgreSQL E2E refuses non-local DATABASE_URL; production access is prohibited")


class F15HivePostgresE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pool = make_pool(DATABASE_URL)
        cls.pool.open(wait=True, timeout=30)
        migrate(cls.pool)
        cls.repo = PostgresRepository(cls.pool)
        cls.service = PersistenceService(cls.repo)

        cls.fresh_pool = make_pool(DATABASE_URL)
        cls.fresh_pool.open(wait=True, timeout=30)
        cls.fresh_repo = PostgresRepository(cls.fresh_pool)
        cls.fresh_service = PersistenceService(cls.fresh_repo)
        cls.created_ids = []

    @classmethod
    def tearDownClass(cls):
        # The CI database is disposable. Delete only fixture Knowledge rows created
        # by this test; retain audit rows until the whole CI container is destroyed.
        try:
            for record_id in reversed(getattr(cls, "created_ids", [])):
                cls.repo.delete("knowledge_records", record_id)
        finally:
            for name in ("fresh_pool", "pool"):
                pool = getattr(cls, name, None)
                if pool is not None:
                    pool.close()

    def create_knowledge(self, owner_scope, source_reference, key, concept):
        record = self.service.save_knowledge(
            {
                "concept": concept,
                "content": "Disposable F15 fixture; not production information.",
                "domain": "f15-hive-postgres-test",
                "source": "f15_postgres_e2e",
                "source_reference": source_reference,
                "confidence": 0.95,
                "tags": ["f15", "hive", "postgres-e2e"],
                "related_nodes": [],
                "privacy_level": "PRIVATE",
            },
            actor="f15-postgres-ci",
            owner_scope=owner_scope,
            idempotency_key=key,
        )["record"]
        self.__class__.created_ids.append(record["id"])
        return record

    def verify(self, record, owner_scope):
        return self.service.verify_knowledge(
            record["id"],
            [{
                "type": "manual_verification",
                "title": "Disposable F15 E2E evidence",
                "reference": "https://example.test/f15-e2e-evidence",
                "note": "Synthetic verification evidence used only inside disposable CI PostgreSQL.",
            }],
            actor="f15-postgres-ci",
            expected_version=record["version"],
            owner_scope=owner_scope,
        )

    def transition(self, record, owner_scope, privacy_level, version=None, confirmed=True):
        return self.service.transition_knowledge_privacy(
            record["id"],
            target_privacy_level=privacy_level,
            expected_version=record["version"] if version is None else version,
            confirmed=confirmed,
            actor="f15-postgres-ci",
            owner_scope=owner_scope,
        )

    def test_share_gate_persists_exact_scope_version_audit_and_revocation(self):
        owner_a = "f15-postgres-owner-A"
        owner_b = "f15-postgres-owner-B"

        private_a = self.create_knowledge(owner_a, "https://example.test/source-a", "f15:a:source", "Shareable A")
        verified_a = self.verify(private_a, owner_a)
        private_unverified = self.create_knowledge(owner_a, "https://example.test/source-unverified", "f15:a:unverified", "Unverified A")
        private_no_provenance = self.create_knowledge(owner_a, None, "f15:a:no-provenance", "No provenance A")
        verified_no_provenance = self.verify(private_no_provenance, owner_a)

        private_b = self.create_knowledge(owner_b, "https://example.test/source-b", "f15:b:source", "Shareable B")
        verified_b = self.verify(private_b, owner_b)

        # Fail closed on absent consent; no version or privacy mutation.
        with self.assertRaisesRegex(ValidationError, "explicit_share_confirmation_required"):
            self.transition(verified_a, owner_a, "SHAREABLE", confirmed=False)
        after_no_consent = self.fresh_repo.get("knowledge_records", verified_a["id"])
        self.assertEqual(after_no_consent["privacy_level"], "PRIVATE")
        self.assertEqual(after_no_consent["version"], verified_a["version"])

        with self.assertRaisesRegex(ValidationError, "verified_knowledge_required_for_share"):
            self.transition(private_unverified, owner_a, "SHAREABLE")
        with self.assertRaisesRegex(ValidationError, "share_provenance_required"):
            self.transition(verified_no_provenance, owner_a, "SHAREABLE")

        # A stale version cannot overwrite the persisted row.
        with self.assertRaises(ConflictError):
            self.transition(verified_a, owner_a, "SHAREABLE", version=verified_a["version"] - 1)

        shared_a = self.transition(verified_a, owner_a, "SHAREABLE")
        shared_b = self.transition(verified_b, owner_b, "SHAREABLE")
        self.assertEqual(shared_a["privacy_level"], "SHAREABLE")
        self.assertEqual(shared_a["version"], verified_a["version"] + 1)
        self.assertIs(shared_a.get("updated_at") is not None, True)

        # Collective promotion is not implemented and must not mutate persisted data.
        with self.assertRaisesRegex(ValidationError, "collective_sync_not_configured"):
            self.transition(shared_a, owner_a, "COLLECTIVE")
        after_collective = self.fresh_repo.get("knowledge_records", shared_a["id"])
        self.assertEqual(after_collective["privacy_level"], "SHAREABLE")
        self.assertEqual(after_collective["version"], shared_a["version"])

        with self.assertRaises(NotFoundError):
            self.transition(shared_a, owner_b, "PRIVATE")

        owner_a_feed = self.fresh_service.list_hive_knowledge(owner_scope=owner_a)
        owner_b_feed = self.fresh_service.list_hive_knowledge(owner_scope=owner_b)
        self.assertEqual([r["id"] for r in owner_a_feed], [shared_a["id"]])
        self.assertEqual([r["id"] for r in owner_b_feed], [shared_b["id"]])
        self.assertTrue(all(r["owner_scope"] == owner_a for r in owner_a_feed))

        # The generic update path cannot bypass the explicit Hive privacy gate.
        with self.assertRaisesRegex(ValidationError, "explicit_hive_privacy_transition_required"):
            self.service.update_knowledge(
                shared_a["id"],
                {"privacy_level": "PRIVATE"},
                expected_version=shared_a["version"],
                actor="f15-postgres-ci",
                owner_scope=owner_a,
            )

        revoked_a = self.service.transition_knowledge_privacy(
            shared_a["id"],
            target_privacy_level="PRIVATE",
            expected_version=shared_a["version"],
            confirmed=True,
            actor="f15-postgres-ci",
            owner_scope=owner_a,
        )
        self.assertEqual(revoked_a["privacy_level"], "PRIVATE")
        self.assertEqual(revoked_a["version"], shared_a["version"] + 1)
        self.assertEqual(self.fresh_service.list_hive_knowledge(owner_scope=owner_a), [])

        # Inspect database audit evidence through an independently opened connection.
        audit_events = self.fresh_repo.search(
            "audit_log", {"resource_id": shared_a["id"]}, limit=100,
            order_by="created_at", descending=False,
        )
        actions = [event.get("action") for event in audit_events]
        self.assertIn("hive.knowledge.share", actions)
        self.assertIn("hive.knowledge.revoke", actions)
        share_event = next(event for event in audit_events if event.get("action") == "hive.knowledge.share")
        detail = share_event.get("detail") or {}
        self.assertEqual(detail.get("owner_scope"), owner_a)
        self.assertEqual(detail.get("contract"), "hive_knowledge_sharing.v1")
        self.assertIs(detail.get("explicit_confirmation"), True)
        self.assertIs(detail.get("propagation_performed"), False)

        # A legacy scope alias must not grant access from a different owner scope.
        legacy = self.create_knowledge("owner", "https://example.test/legacy", "f15:legacy:owner", "Legacy owner row")
        verified_legacy = self.verify(legacy, "owner")
        with self.assertRaises(NotFoundError):
            self.transition(verified_legacy, owner_a, "SHAREABLE")
        legacy_after = self.fresh_repo.get("knowledge_records", legacy["id"])
        self.assertEqual(legacy_after["privacy_level"], "PRIVATE")


if __name__ == "__main__":
    unittest.main()
