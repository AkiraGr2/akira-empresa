"""F15 Hive sharing contract: explicit owner-scoped publication, no propagation."""
import unittest

from persistence.core import ConflictError, NotFoundError, ValidationError
from persistence.service import PersistenceService
from test_knowledge_persistent_contract import FakeRepo


class HiveKnowledgeSharingContractTests(unittest.TestCase):
    def setUp(self):
        self.repo = FakeRepo()
        self.service = PersistenceService(self.repo)

    def create_knowledge(self, owner_scope="scope:A", source_reference="test://f15-source", privacy_level="PRIVATE"):
        payload = {
            "concept": "F15 share gate",
            "content": "Solo el propietario puede autorizar este conocimiento para compartirlo.",
            "domain": "f15-security",
            "source": "manual_review",
            "source_reference": source_reference,
            "confidence": 0.9,
            "tags": ["f15", "hive"],
            "related_nodes": [],
            "privacy_level": privacy_level,
        }
        return self.service.save_knowledge(
            payload, actor="owner@example.test", owner_scope=owner_scope
        )["record"]

    def verify_knowledge(self, owner_scope="scope:A", source_reference="test://f15-source", privacy_level="PRIVATE"):
        record = self.create_knowledge(owner_scope, source_reference, privacy_level=privacy_level)
        return self.service.verify_knowledge(
            record["id"],
            [{
                "type": "manual_verification",
                "title": "F15 contract evidence",
                "reference": "test://f15-evidence",
                "note": "Reviewed by the test fixture; synthetic test evidence only.",
            }],
            actor="owner@example.test",
            expected_version=record["version"],
            owner_scope=owner_scope,
        )

    def share(self, record, owner_scope="scope:A", expected_version=None, confirmed=True):
        return self.service.transition_knowledge_privacy(
            record["id"],
            target_privacy_level="SHAREABLE",
            expected_version=record["version"] if expected_version is None else expected_version,
            confirmed=confirmed,
            actor="owner@example.test",
            owner_scope=owner_scope,
        )

    def test_share_requires_explicit_confirmation(self):
        verified = self.verify_knowledge()
        with self.assertRaisesRegex(ValidationError, "explicit_share_confirmation_required"):
            self.share(verified, confirmed=False)
        stored = self.repo.get("knowledge_records", verified["id"])
        self.assertEqual(stored["privacy_level"], "PRIVATE")
        self.assertEqual(stored["version"], verified["version"])

    def test_sensitive_knowledge_requires_redaction_before_sharing(self):
        sensitive = self.verify_knowledge(privacy_level="SENSITIVE")
        with self.assertRaisesRegex(ValidationError, "sensitive_knowledge_requires_redaction"):
            self.share(sensitive)
        stored = self.repo.get("knowledge_records", sensitive["id"])
        self.assertEqual(stored["privacy_level"], "SENSITIVE")
        self.assertEqual(stored["version"], sensitive["version"])

    def test_share_requires_verified_knowledge_and_provenance(self):
        unverified = self.create_knowledge()
        with self.assertRaisesRegex(ValidationError, "verified_knowledge_required_for_share"):
            self.share(unverified)

        without_reference = self.verify_knowledge(source_reference=None)
        with self.assertRaisesRegex(ValidationError, "share_provenance_required"):
            self.share(without_reference)
        stored = self.repo.get("knowledge_records", without_reference["id"])
        self.assertEqual(stored["privacy_level"], "PRIVATE")

    def test_share_is_versioned_audited_and_never_claims_propagation(self):
        verified = self.verify_knowledge()
        shared = self.share(verified)
        self.assertEqual(shared["privacy_level"], "SHAREABLE")
        self.assertEqual(shared["version"], verified["version"] + 1)

        events = [e for e in self.repo.audit if e.get("resource_id") == verified["id"]]
        event = next(e for e in events if e.get("action") == "hive.knowledge.share")
        self.assertEqual(event["status"], "success")
        self.assertEqual(event["detail"]["owner_scope"], "scope:A")
        self.assertEqual(event["detail"]["previous_version"], verified["version"])
        self.assertEqual(event["detail"]["new_version"], shared["version"])
        self.assertIs(event["detail"]["explicit_confirmation"], True)
        self.assertIs(event["detail"]["propagation_performed"], False)

    def test_export_view_is_exact_owner_scoped_and_excludes_private_or_unverified(self):
        owner_shared = self.share(self.verify_knowledge(owner_scope="scope:A"), owner_scope="scope:A")
        self.share(self.verify_knowledge(owner_scope="scope:B"), owner_scope="scope:B")
        self.verify_knowledge(owner_scope="scope:A")  # verified but still PRIVATE
        self.create_knowledge(owner_scope="scope:A")  # unverified and PRIVATE

        rows = self.service.list_hive_knowledge(owner_scope="scope:A")
        self.assertEqual([r["id"] for r in rows], [owner_shared["id"]])
        self.assertTrue(all(r["owner_scope"] == "scope:A" for r in rows))
        self.assertTrue(all(r["privacy_level"] == "SHAREABLE" for r in rows))
        self.assertTrue(all(r["verification_status"] == "verified" for r in rows))

    def test_legacy_owner_scope_is_not_an_authorization_to_share(self):
        legacy = self.verify_knowledge(owner_scope="owner")
        with self.assertRaises(NotFoundError):
            self.share(legacy, owner_scope="scope:A")
        stored = self.repo.get("knowledge_records", legacy["id"])
        self.assertEqual(stored["privacy_level"], "PRIVATE")

    def test_cross_owner_read_and_write_fail_closed(self):
        record = self.verify_knowledge(owner_scope="scope:A")
        with self.assertRaises(NotFoundError):
            self.share(record, owner_scope="scope:B")
        self.assertEqual(
            self.service.list_hive_knowledge(owner_scope="scope:B"),
            [],
        )

    def test_collective_promotion_fails_closed_without_mutation(self):
        record = self.create_knowledge()
        with self.assertRaisesRegex(ValidationError, "collective_sync_not_configured"):
            self.service.transition_knowledge_privacy(
                record["id"],
                target_privacy_level="COLLECTIVE",
                expected_version=record["version"],
                confirmed=True,
                actor="owner@example.test",
                owner_scope="scope:A",
            )
        stored = self.repo.get("knowledge_records", record["id"])
        self.assertEqual(stored["privacy_level"], "PRIVATE")
        self.assertEqual(stored["version"], record["version"])

    def test_stale_version_rejected_and_share_can_be_revoked(self):
        verified = self.verify_knowledge()
        with self.assertRaises(ConflictError):
            self.share(verified, expected_version=verified["version"] - 1)
        shared = self.share(verified)
        revoked = self.service.transition_knowledge_privacy(
            shared["id"],
            target_privacy_level="PRIVATE",
            expected_version=shared["version"],
            confirmed=True,
            actor="owner@example.test",
            owner_scope="scope:A",
        )
        self.assertEqual(revoked["privacy_level"], "PRIVATE")
        self.assertEqual(revoked["version"], shared["version"] + 1)
        self.assertEqual(self.service.list_hive_knowledge(owner_scope="scope:A"), [])
        events = [e for e in self.repo.audit if e.get("resource_id") == shared["id"]]
        self.assertTrue(any(e.get("action") == "hive.knowledge.revoke" for e in events))

    def test_editing_shared_knowledge_revokes_consent_until_explicit_reshare(self):
        verified = self.verify_knowledge()
        shared = self.share(verified)

        with self.assertRaisesRegex(
            ValidationError, "knowledge factual change requires reverification separately"
        ):
            self.service.update_knowledge(
                shared["id"],
                {"content": "Changed content", "verification_status": "verified"},
                expected_version=shared["version"],
                actor="owner@example.test",
                owner_scope="scope:A",
            )
        unchanged = self.repo.get("knowledge_records", shared["id"])
        self.assertEqual(unchanged["privacy_level"], "SHAREABLE")
        self.assertEqual(unchanged["version"], shared["version"])

        edited = self.service.update_knowledge(
            shared["id"],
            {"content": "Materially changed after prior sharing consent."},
            expected_version=shared["version"],
            actor="owner@example.test",
            owner_scope="scope:A",
        )
        self.assertEqual(edited["privacy_level"], "PRIVATE")
        self.assertEqual(edited["verification_status"], "partially_verified")
        self.assertEqual(edited["version"], shared["version"] + 1)
        self.assertEqual(self.service.list_hive_knowledge(owner_scope="scope:A"), [])

        reverified = self.service.verify_knowledge(
            edited["id"],
            [{
                "type": "manual_verification",
                "title": "Fresh evidence after edit",
                "reference": "test://f15-fresh-after-edit",
                "note": "This verifies the edited content independently.",
            }],
            actor="owner@example.test",
            expected_version=edited["version"],
            owner_scope="scope:A",
        )
        self.assertEqual(reverified["verification_status"], "verified")
        self.assertEqual(reverified["privacy_level"], "PRIVATE")
        self.assertEqual(self.service.list_hive_knowledge(owner_scope="scope:A"), [])

        reshared = self.share(reverified)
        self.assertEqual(reshared["privacy_level"], "SHAREABLE")
        self.assertEqual(self.service.list_hive_knowledge(owner_scope="scope:A")[0]["id"], reshared["id"])

    def test_generic_knowledge_update_cannot_bypass_the_hive_gate(self):
        record = self.create_knowledge()
        with self.assertRaisesRegex(ValidationError, "explicit_hive_privacy_transition_required"):
            self.service.update_knowledge(
                record["id"],
                {"privacy_level": "SHAREABLE"},
                expected_version=record["version"],
                actor="owner@example.test",
                owner_scope="scope:A",
            )
        stored = self.repo.get("knowledge_records", record["id"])
        self.assertEqual(stored["privacy_level"], "PRIVATE")
        self.assertEqual(stored["version"], record["version"])


if __name__ == "__main__":
    unittest.main()
