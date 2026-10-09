"""F15 Hive sharing E2E contract against a disposable real PostgreSQL database.

Safety: this module refuses non-loopback DATABASE_URL values. CI runs it only against
its disposable pgvector/PostgreSQL service container; production credentials are never used.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch
from urllib.parse import urlparse

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@127.0.0.1:5432/akira_f12_test",
)
if urlparse(DATABASE_URL).hostname not in {"127.0.0.1", "localhost"}:
    raise RuntimeError("F15 PostgreSQL E2E refuses non-local DATABASE_URL; production access is prohibited")

# Test-only signing key. The guard above rejects non-loopback database URLs before imports.
os.environ["AKIRA_SESSION_SECRET"] = "f15-postgres-e2e-test-only-secret-never-use"
import akira_auth  # noqa: E402
import nexus  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from persistence.core import ConflictError, NotFoundError, StorageError, ValidationError
from persistence.capability_catalog import HIVE_KNOWLEDGE_SHARING_CAPABILITY
from persistence.postgres import PostgresRepository, make_pool, migrate
from persistence.service import PersistenceService

class F15HivePostgresE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pool = make_pool(DATABASE_URL)
        cls.pool.open(wait=True, timeout=30)
        migrate(cls.pool)
        cls.repo = PostgresRepository(cls.pool)
        cls.service = PersistenceService(cls.repo)
        # Importing nexus starts the normal persistence bootstrap in a background
        # thread, which may already have seeded this canonical capability. Reuse
        # the persisted row instead of inventing a second idempotency key.
        capability_rows = cls.service.list_capabilities(
            filters={"name": "hive_knowledge_sharing_v1"}, limit=1
        )
        if not capability_rows:
            cls.service.create_capability(
                HIVE_KNOWLEDGE_SHARING_CAPABILITY,
                actor="f15-postgres-ci",
                idempotency_key="bootstrap:capability:hive_knowledge_sharing_v1:v1",
            )
            capability_rows = cls.service.list_capabilities(
                filters={"name": "hive_knowledge_sharing_v1"}, limit=1
            )
        if len(capability_rows) != 1:
            raise AssertionError("F15 Hive capability bootstrap did not persist exactly one canonical row")
        seeded_capability = capability_rows[0]
        for key in ("category", "implementation_state", "verification_state", "availability_state"):
            if seeded_capability.get(key) != HIVE_KNOWLEDGE_SHARING_CAPABILITY.get(key):
                raise AssertionError(
                    f"F15 Hive capability state mismatch for {key}: {seeded_capability.get(key)!r}"
                )

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

    def create_knowledge(self, owner_scope, source_reference, key, concept, privacy_level="PRIVATE"):
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
                "privacy_level": privacy_level,
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

    def test_authenticated_http_routes_enforce_owner_and_hive_transition_contract(self):
        client = TestClient(nexus.app)
        owner_email = "f15-api-owner@example.test"
        non_owner_email = "f15-api-non-owner@example.test"
        owner_token, _expires, token_error = akira_auth.issue_session(
            sub="f15-api-owner-sub",
            email=owner_email,
        )
        self.assertIsNone(token_error)
        self.assertTrue(owner_token)
        headers = {"Authorization": f"Bearer {owner_token}"}

        non_owner_token, _expires, token_error = akira_auth.issue_session(
            sub="f15-api-non-owner-sub",
            email=non_owner_email,
        )
        self.assertIsNone(token_error)
        non_owner_headers = {"Authorization": f"Bearer {non_owner_token}"}

        # Route authentication must be enforced before any data access.
        self.assertEqual(client.get("/api/v8/hive/status").status_code, 401)
        self.assertEqual(client.get("/api/v8/hive/knowledge").status_code, 401)
        self.assertEqual(
            client.post(
                "/api/v8/hive/knowledge/missing/privacy",
                json={"privacy_level": "SHAREABLE", "expected_version": 1, "confirmed": True},
            ).status_code,
            401,
        )

        with patch.object(nexus, "OWNER_EMAILS", [owner_email]), patch(
            "nexus._persistence_service", return_value=self.service
        ):
            self.assertEqual(client.get("/api/v8/hive/status", headers=non_owner_headers).status_code, 403)
            self.assertEqual(client.get("/api/v8/hive/knowledge", headers=non_owner_headers).status_code, 403)

            status = client.get("/api/v8/hive/status", headers=headers)
            self.assertEqual(status.status_code, 200, status.text)
            self.assertEqual(status.json()["contract"], "hive_knowledge_sharing.v1")
            self.assertEqual(status.json()["capability"]["name"], "hive_knowledge_sharing_v1")
            self.assertEqual(status.json()["capability"]["verification_state"], "unverified")
            self.assertFalse(status.json()["cross_owner_propagation"])
            self.assertFalse(status.json()["collective_sync_available"])

            # Runtime capability lookup failures are reported as controlled 503s,
            # not raw unhandled exceptions from the status endpoint.
            with patch.object(self.service, "list_capabilities", side_effect=StorageError("synthetic test storage failure")):
                unavailable = client.get("/api/v8/hive/status", headers=headers)
            self.assertEqual(unavailable.status_code, 503, unavailable.text)
            self.assertEqual(unavailable.json()["reason"], "storage")
            self.assertEqual(unavailable.json()["error_type"], "StorageError")

            record = self.create_knowledge(
                "owner",
                "https://example.test/f15-api-source",
                "f15:api:owner-record",
                "F15 authenticated API fixture",
            )
            verified = self.verify(record, "owner")

            # A sensitive record needs a separately redacted and verified copy.
            sensitive = self.create_knowledge(
                "owner",
                "https://example.test/f15-api-sensitive-source",
                "f15:api:sensitive-record",
                "F15 sensitive API fixture",
                privacy_level="SENSITIVE",
            )
            sensitive_verified = self.verify(sensitive, "owner")
            sensitive_share = client.post(
                f"/api/v8/hive/knowledge/{sensitive_verified['id']}/privacy",
                headers=headers,
                json={
                    "privacy_level": "SHAREABLE",
                    "expected_version": sensitive_verified["version"],
                    "confirmed": True,
                },
            )
            self.assertEqual(sensitive_share.status_code, 400, sensitive_share.text)
            self.assertEqual(sensitive_share.json()["reason"], "sensitive_knowledge_requires_redaction")
            sensitive_after = self.fresh_repo.get("knowledge_records", sensitive_verified["id"])
            self.assertEqual(sensitive_after["privacy_level"], "SENSITIVE")
            self.assertEqual(sensitive_after["version"], sensitive_verified["version"])

            # Missing explicit consent cannot mutate privacy or version.
            no_consent = client.post(
                f"/api/v8/hive/knowledge/{verified['id']}/privacy",
                headers=headers,
                json={"privacy_level": "SHAREABLE", "expected_version": verified["version"], "confirmed": False},
            )
            self.assertEqual(no_consent.status_code, 400, no_consent.text)
            unchanged = self.fresh_repo.get("knowledge_records", verified["id"])
            self.assertEqual(unchanged["privacy_level"], "PRIVATE")
            self.assertEqual(unchanged["version"], verified["version"])

            # Exact, authenticated owner scope is used for the real HTTP transition.
            shared_response = client.post(
                f"/api/v8/hive/knowledge/{verified['id']}/privacy",
                headers=headers,
                json={
                    "privacy_level": "SHAREABLE",
                    "expected_version": verified["version"],
                    "confirmed": True,
                    "owner_scope": "attacker-controlled-scope",
                    "actor": "attacker@example.test",
                },
            )
            self.assertEqual(shared_response.status_code, 200, shared_response.text)
            shared_payload = shared_response.json()
            self.assertTrue(shared_payload["ok"])
            self.assertFalse(shared_payload["propagation_performed"])
            self.assertEqual(shared_payload["knowledge"]["owner_scope"], "owner")
            shared = self.fresh_repo.get("knowledge_records", verified["id"])
            self.assertEqual(shared["privacy_level"], "SHAREABLE")
            self.assertEqual(shared["version"], verified["version"] + 1)

            feed = client.get("/api/v8/hive/knowledge", headers=headers)
            self.assertEqual(feed.status_code, 200, feed.text)
            self.assertEqual([row["id"] for row in feed.json()["knowledge"]], [shared["id"]])

            # A separate verified record under a different scope must never leak to this owner feed.
            foreign = self.create_knowledge(
                "g:foreign-owner",
                "https://example.test/f15-api-foreign-source",
                "f15:api:foreign-record",
                "Foreign F15 fixture",
            )
            foreign_verified = self.verify(foreign, "g:foreign-owner")
            self.transition(foreign_verified, "g:foreign-owner", "SHAREABLE")
            feed_after_foreign = client.get("/api/v8/hive/knowledge", headers=headers)
            self.assertEqual(feed_after_foreign.status_code, 200, feed_after_foreign.text)
            self.assertEqual([row["id"] for row in feed_after_foreign.json()["knowledge"]], [shared["id"]])

            # Any material edit revokes previous sharing consent and verification.
            # Merely marking the edited row verified again must not republish it.
            false_reverify = client.patch(
                f"/api/v8/knowledge/{shared['id']}",
                headers=headers,
                json={
                    "expected_version": shared["version"],
                    "changes": {
                        "content": "Changed without fresh review",
                        "verification_status": "verified",
                    },
                },
            )
            self.assertEqual(false_reverify.status_code, 400, false_reverify.text)
            unchanged_after_false_reverify = self.fresh_repo.get("knowledge_records", shared["id"])
            self.assertEqual(unchanged_after_false_reverify["privacy_level"], "SHAREABLE")
            self.assertEqual(unchanged_after_false_reverify["version"], shared["version"])

            edit_response = client.patch(
                f"/api/v8/knowledge/{shared['id']}",
                headers=headers,
                json={
                    "expected_version": shared["version"],
                    "changes": {"content": "Materially edited after sharing consent."},
                },
            )
            self.assertEqual(edit_response.status_code, 200, edit_response.text)
            edited = edit_response.json()["knowledge"]
            self.assertEqual(edited["privacy_level"], "PRIVATE")
            self.assertEqual(edited["verification_status"], "partially_verified")
            self.assertEqual(edited["version"], shared["version"] + 1)
            self.assertEqual(
                client.get("/api/v8/hive/knowledge", headers=headers).json()["knowledge"],
                [],
            )

            verify_again = client.post(
                f"/api/v8/knowledge/{shared['id']}/verify",
                headers=headers,
                json={
                    "expected_version": edited["version"],
                    "evidence": [{
                        "type": "manual_verification",
                        "title": "Fresh review after content update",
                        "reference": "https://example.test/f15-fresh-after-edit",
                        "note": "Synthetic evidence independently verifies the edited content.",
                    }],
                },
            )
            self.assertEqual(verify_again.status_code, 200, verify_again.text)
            reverified = verify_again.json()["knowledge"]
            self.assertEqual(reverified["verification_status"], "verified")
            self.assertEqual(reverified["privacy_level"], "PRIVATE")
            self.assertEqual(
                client.get("/api/v8/hive/knowledge", headers=headers).json()["knowledge"],
                [],
            )

            # Publication requires a new explicit owner confirmation after re-verification.
            reshare = client.post(
                f"/api/v8/hive/knowledge/{shared['id']}/privacy",
                headers=headers,
                json={
                    "privacy_level": "SHAREABLE",
                    "expected_version": reverified["version"],
                    "confirmed": True,
                },
            )
            self.assertEqual(reshare.status_code, 200, reshare.text)
            shared = reshare.json()["knowledge"]
            self.assertEqual(shared["privacy_level"], "SHAREABLE")
            self.assertEqual(
                [row["id"] for row in client.get("/api/v8/hive/knowledge", headers=headers).json()["knowledge"]],
                [shared["id"]],
            )

            bypass = client.patch(
                f"/api/v8/knowledge/{shared['id']}",
                headers=headers,
                json={
                    "expected_version": shared["version"],
                    "changes": {"privacy_level": "PRIVATE"},
                },
            )
            self.assertEqual(bypass.status_code, 409, bypass.text)
            still_shared = self.fresh_repo.get("knowledge_records", shared["id"])
            self.assertEqual(still_shared["privacy_level"], "SHAREABLE")
            self.assertEqual(still_shared["version"], shared["version"])

            collective = client.post(
                f"/api/v8/hive/knowledge/{shared['id']}/privacy",
                headers=headers,
                json={
                    "privacy_level": "COLLECTIVE",
                    "expected_version": shared["version"],
                    "confirmed": True,
                },
            )
            self.assertEqual(collective.status_code, 409, collective.text)
            after_collective = self.fresh_repo.get("knowledge_records", shared["id"])
            self.assertEqual(after_collective["privacy_level"], "SHAREABLE")
            self.assertEqual(after_collective["version"], shared["version"])

            revoke = client.post(
                f"/api/v8/hive/knowledge/{shared['id']}/privacy",
                headers=headers,
                json={
                    "privacy_level": "PRIVATE",
                    "expected_version": shared["version"],
                    "confirmed": True,
                },
            )
            self.assertEqual(revoke.status_code, 200, revoke.text)
            self.assertEqual(revoke.json()["knowledge"]["privacy_level"], "PRIVATE")
            feed_after_revoke = client.get("/api/v8/hive/knowledge", headers=headers)
            self.assertEqual(feed_after_revoke.status_code, 200, feed_after_revoke.text)
            self.assertEqual(feed_after_revoke.json()["knowledge"], [])

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
        audit_events = [
            event for event in self.fresh_repo.audit_search(
                actor="f15-postgres-ci", action_prefix="hive.knowledge", limit=100
            )
            if event.get("resource_id") == shared_a["id"]
        ]
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
