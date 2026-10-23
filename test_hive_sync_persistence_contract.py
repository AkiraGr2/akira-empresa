"""F15 Hive Collective Sync v1: persistence contract tests.

Verifies:
- Migration 055 structural integrity and RLS policy definitions.
- Entity registration in ENTITIES (all 8 tables with valid specs).
- Service methods for collectives, memberships, consents, outbox, inbox, revisions, conflicts, tombstones.
- Idempotency, atomic rollback on failure, and same-owner isolation enforcement.
"""
import copy
import unittest

from persistence.core import (
    ENTITIES,
    ConflictError,
    NotFoundError,
    ValidationError,
    VerificationError,
    entity_spec,
)
from persistence.migrations import MIGRATIONS
from persistence.service import PersistenceService


class TransactionalFakeTx:
    def __init__(self, repo):
        self.repo = repo

    def __enter__(self):
        self.snapshot_tables = copy.deepcopy(self.repo.tables)
        self.snapshot_audit = copy.deepcopy(self.repo.audit)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Transaction rollback: restore state
            self.repo.tables = self.snapshot_tables
            self.repo.audit = self.snapshot_audit
            return False
        return False

    def create(self, entity, record):
        return self.repo._create(entity, record)

    def update(self, entity, record_id, changes, expected_version):
        return self.repo._update(entity, record_id, changes, expected_version)

    def get(self, entity, record_id):
        return self.repo.get(entity, record_id)

    def search(self, entity, filters=None, limit=50, offset=0, order_by="created_at", descending=True):
        return self.repo.search(entity, filters, limit, offset, order_by, descending)

    def append_audit(self, event):
        self.repo.audit.append(dict(event))


class TransactionalFakeRepo:
    def __init__(self):
        self.tables = {
            "hive_collectives": {},
            "hive_collective_memberships": {},
            "hive_share_consents": {},
            "hive_sync_outbox": {},
            "hive_sync_inbox": {},
            "hive_collective_revisions": {},
            "hive_collective_conflicts": {},
            "hive_revocation_tombstones": {},
        }
        self.audit = []

    def transaction(self):
        return TransactionalFakeTx(self)

    def _create(self, entity, record):
        table = self.tables.setdefault(entity, {})
        key = record.get("idempotency_key")
        if key:
            for current in table.values():
                if current.get("idempotency_key") == key:
                    return dict(current), False

        # Specific unique dedup for outbox/inbox: (recipient_membership_id, event_id)
        if entity in ("hive_sync_outbox", "hive_sync_inbox"):
            rec_id = record.get("recipient_membership_id")
            evt_id = record.get("event_id")
            for current in table.values():
                if current.get("recipient_membership_id") == rec_id and current.get("event_id") == evt_id:
                    return dict(current), False

        rec = dict(record)
        rec.setdefault("version", 1)
        table[rec["id"]] = rec
        return dict(rec), True

    def get(self, entity, record_id):
        row = self.tables.get(entity, {}).get(record_id)
        return dict(row) if row else None

    def exists(self, entity, record_id):
        return self.get(entity, record_id) is not None

    def search(self, entity, filters=None, limit=50, offset=0, order_by="created_at", descending=True):
        rows = [dict(v) for v in self.tables.get(entity, {}).values()]
        filters = filters or {}
        for key, value in filters.items():
            if key.endswith("__in"):
                field = key[:-4]
                rows = [r for r in rows if r.get(field) in set(value)]
            else:
                rows = [r for r in rows if r.get(key) == value]
        return rows[offset:offset + limit]

    def count(self, entity, filters=None):
        return len(self.search(entity, filters or {}, limit=10000))

    def _update(self, entity, record_id, changes, expected_version):
        table = self.tables.setdefault(entity, {})
        row = table.get(record_id)
        if row is None:
            raise NotFoundError(record_id)
        if row.get("version") != expected_version:
            raise ConflictError(f"version mismatch: expected {expected_version}, got {row.get('version')}")
        updated = dict(row)
        updated.update(changes)
        updated["version"] = expected_version + 1
        table[record_id] = updated
        return dict(updated)


class HiveSyncPersistenceContractTests(unittest.TestCase):
    def setUp(self):
        self.repo = TransactionalFakeRepo()
        self.service = PersistenceService(self.repo)
        self.owner = "identity:owner_primary"

    # --- 1. Schema & Migration 055 Verification ---

    def test_migration_055_exists_and_contains_all_eight_tables(self):
        mig_055 = next((m for m in MIGRATIONS if m[0] == "055_hive_collective_sync_v1"), None)
        self.assertIsNotNone(mig_055, "Migración 055_hive_collective_sync_v1 debe existir")
        sql = mig_055[1]
        expected_tables = (
            "hive_collectives",
            "hive_collective_memberships",
            "hive_share_consents",
            "hive_sync_outbox",
            "hive_sync_inbox",
            "hive_collective_revisions",
            "hive_collective_conflicts",
            "hive_revocation_tombstones",
        )
        for table in expected_tables:
            self.assertIn(f"CREATE TABLE {table}", sql, f"Tabla {table} debe crearse en la migración")
            self.assertIn(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY", sql)
            self.assertIn(f'CREATE POLICY "akira_deny_anon_authenticated_select" ON {table}', sql)

    def test_entities_registration_for_hive_sync_tables(self):
        expected_tables = (
            "hive_collectives",
            "hive_collective_memberships",
            "hive_share_consents",
            "hive_sync_outbox",
            "hive_sync_inbox",
            "hive_collective_revisions",
            "hive_collective_conflicts",
            "hive_revocation_tombstones",
        )
        for table in expected_tables:
            self.assertIn(table, ENTITIES, f"{table} debe estar registrada en ENTITIES")
            spec = entity_spec(table)
            self.assertEqual(spec["table"], table)
            self.assertTrue(len(spec["columns"]) > 0)
            self.assertIn("id", spec["columns"])
            self.assertIn("schema_version", spec["columns"])
            self.assertTrue(spec["idempotent"])

    # --- 2. Collective Lifecycle ---

    def test_create_collective_success_and_scoping(self):
        res = self.service.create_collective(self.owner, "Colmena Principal", "Colectiva de prueba")
        self.assertEqual(res["outcome"], "created")
        coll = res["record"]
        self.assertEqual(coll["owner_identity_ref"], self.owner)
        self.assertEqual(coll["name"], "Colmena Principal")
        self.assertEqual(coll["status"], "active")

        # Get collective with correct owner
        found = self.service.get_collective(coll["id"], owner_identity_ref=self.owner)
        self.assertIsNotNone(found)
        self.assertEqual(found["id"], coll["id"])

        # Opacity / security: get collective with different owner returns None
        denied = self.service.get_collective(coll["id"], owner_identity_ref="identity:foreign_user")
        self.assertIsNone(denied)

    def test_create_collective_idempotency(self):
        key = "idemp:coll:create:1"
        res1 = self.service.create_collective(self.owner, "Colmena Uno", idempotency_key=key)
        self.assertEqual(res1["outcome"], "created")
        res2 = self.service.create_collective(self.owner, "Colmena Uno", idempotency_key=key)
        self.assertEqual(res2["outcome"], "already_synced")
        self.assertEqual(res1["record"]["id"], res2["record"]["id"])

    # --- 3. Membership & Cross-Owner Isolation ---

    def test_invite_and_accept_membership_same_owner(self):
        coll = self.service.create_collective(self.owner, "Colmena Test")["record"]
        res = self.service.invite_instance(coll["id"], "inst_laptop_01", self.owner, instance_label="Laptop")
        self.assertEqual(res["outcome"], "created")
        mem = res["record"]
        self.assertEqual(mem["status"], "invited")
        self.assertEqual(mem["instance_id"], "inst_laptop_01")

        # Accept invitation
        accepted = self.service.accept_invitation(mem["id"], self.owner)
        self.assertEqual(accepted["status"], "active")
        self.assertIsNotNone(accepted.get("accepted_at"))

    def test_cannot_invite_to_foreign_owner_collective(self):
        coll = self.service.create_collective(self.owner, "Colmena Propietaria")["record"]
        # Foreign owner cannot add an instance to this collective
        with self.assertRaises(ValidationError):
            self.service.invite_instance(coll["id"], "inst_rogue_01", "identity:attacker")

    def test_cannot_accept_invitation_with_foreign_owner(self):
        coll = self.service.create_collective(self.owner, "Colmena Propietaria")["record"]
        mem = self.service.invite_instance(coll["id"], "inst_phone_01", self.owner)["record"]
        with self.assertRaises(NotFoundError):
            self.service.accept_invitation(mem["id"], "identity:foreign_owner")

    def test_cannot_accept_already_accepted_or_revoked_invitation(self):
        coll = self.service.create_collective(self.owner, "Colmena Test")["record"]
        mem = self.service.invite_instance(coll["id"], "inst_pc_01", self.owner)["record"]
        self.service.accept_invitation(mem["id"], self.owner)

        # Trying to accept again must fail validation
        with self.assertRaises(ValidationError):
            self.service.accept_invitation(mem["id"], self.owner)

    # --- 4. Outbox Staging & Idempotency ---

    def test_stage_sync_outbox_atomicity_and_deduplication(self):
        coll = self.service.create_collective(self.owner, "Colmena Sync")["record"]
        sender_mem = self.service.invite_instance(coll["id"], "inst_desktop", self.owner)["record"]
        self.service.accept_invitation(sender_mem["id"], self.owner)

        rec1 = self.service.invite_instance(coll["id"], "inst_laptop", self.owner)["record"]
        self.service.accept_invitation(rec1["id"], self.owner)
        rec2 = self.service.invite_instance(coll["id"], "inst_phone", self.owner)["record"]
        self.service.accept_invitation(rec2["id"], self.owner)

        # Create active consent record
        consent_id = "cons_test_01"
        self.repo.tables["hive_share_consents"][consent_id] = {
            "id": consent_id,
            "collective_id": coll["id"],
            "owner_identity_ref": self.owner,
            "sender_instance_id": "inst_desktop",
            "sender_membership_id": sender_mem["id"],
            "knowledge_id": "know_123",
            "knowledge_version": 1,
            "content_hash": "a" * 64,
            "audience_hash": "b" * 64,
            "status": "active",
            "version": 1,
        }

        envelope_data = {
            "event_id": "evt_test_01",
            "publication_id": "pub_test_01",
            "collective_id": coll["id"],
            "sender_instance_id": "inst_desktop",
            "sender_membership_id": sender_mem["id"],
            "event_type": "KNOWLEDGE_SNAPSHOT",
            "envelope_hash": "c" * 64,
            "content_hash": "a" * 64,
            "knowledge_lineage_id": "lin_test_01",
            "revision_id": "rev_test_01",
            "sender_sequence": 1,
            "envelope": {"test": "data"},
        }
        recipients = [
            {"recipient_instance_id": "inst_laptop", "recipient_membership_id": rec1["id"], "membership_generation": 1},
            {"recipient_instance_id": "inst_phone", "recipient_membership_id": rec2["id"], "membership_generation": 1},
        ]

        outbox_entries = self.service.stage_sync_outbox(consent_id, envelope_data, recipients)
        self.assertEqual(len(outbox_entries), 2)
        for entry in outbox_entries:
            self.assertEqual(entry["outcome"], "created")
            self.assertEqual(entry["record"]["status"], "pending")

        # Staging same event to same recipients must be idempotent (already_synced)
        second_run = self.service.stage_sync_outbox(consent_id, envelope_data, recipients)
        self.assertEqual(len(second_run), 2)
        for entry in second_run:
            self.assertEqual(entry["outcome"], "already_synced")

    # --- 5. Inbox Reception & Acknowledgement ---

    def test_receive_envelope_and_acknowledge_lifecycle(self):
        coll = self.service.create_collective(self.owner, "Colmena Inbox")["record"]
        rec_mem = self.service.invite_instance(coll["id"], "inst_target", self.owner)["record"]
        self.service.accept_invitation(rec_mem["id"], self.owner)

        envelope_data = {
            "event_id": "evt_inbox_01",
            "publication_id": "pub_inbox_01",
            "collective_id": coll["id"],
            "sender_instance_id": "inst_source",
            "sender_membership_id": "mem_source",
            "recipient_instance_id": "inst_target",
            "recipient_membership_id": rec_mem["id"],
            "membership_generation": 1,
            "sender_sequence": 1,
            "event_type": "KNOWLEDGE_SNAPSHOT",
            "envelope_hash": "e" * 64,
            "content_hash": "d" * 64,
            "knowledge_lineage_id": "lin_01",
            "revision_id": "rev_01",
            "envelope": {"concept": "F15 Hive Sync"},
        }

        # 1. Receive
        recv_res = self.service.receive_sync_envelope(envelope_data)
        self.assertEqual(recv_res["outcome"], "created")
        inbox = recv_res["record"]
        self.assertEqual(inbox["status"], "received")

        # 2. Duplicate receive is idempotent
        recv_dup = self.service.receive_sync_envelope(envelope_data)
        self.assertEqual(recv_dup["outcome"], "already_synced")

        # 3. Acknowledge -> validated
        val = self.service.acknowledge_inbox(inbox["id"], "validated", self.owner, validation_result={"valid": True})
        self.assertEqual(val["status"], "validated")
        self.assertTrue(val["validation_result"]["valid"])

        # 4. Acknowledge -> accepted with hash and receipt
        acc = self.service.acknowledge_inbox(
            inbox["id"], "accepted", self.owner,
            accepted_hash="d" * 64, accepted_version=1
        )
        self.assertEqual(acc["status"], "accepted")
        self.assertIsNotNone(acc.get("receipt"))
        self.assertEqual(acc.get("accepted_hash"), "d" * 64)

    def test_receive_fails_if_recipient_membership_is_inactive(self):
        coll = self.service.create_collective(self.owner, "Colmena Test")["record"]
        invited_mem = self.service.invite_instance(coll["id"], "inst_unaccepted", self.owner)["record"]

        envelope_data = {
            "event_id": "evt_inactive_01",
            "recipient_membership_id": invited_mem["id"],
        }
        with self.assertRaises(ValidationError):
            self.service.receive_sync_envelope(envelope_data)

    # --- 6. Revision Immutability & Conflict Recording ---

    def test_record_revision_and_conflict(self):
        coll = self.service.create_collective(self.owner, "Colmena Revisions")["record"]

        rev1 = self.service.record_revision(
            coll["id"], "lineage:alpha", "rev:1", "f" * 64,
            snapshot={"concept": "Alpha", "content": "Version 1"},
            origin="received", actor="owner@test"
        )["record"]
        self.assertEqual(rev1["revision_id"], "rev:1")
        self.assertEqual(rev1["origin"], "received")

        # Conflicting revision competing for same lineage
        conflict = self.service.record_conflict(
            coll["id"], "lineage:alpha", ["rev:1", "rev:2_competing"], base_revision_id="rev:base"
        )["record"]
        self.assertEqual(conflict["status"], "pending")
        self.assertEqual(len(conflict["competing_revision_ids"]), 2)

    # --- 7. Revocation Tombstone & Outbox Cancellation ---

    def test_record_revocation_creates_tombstone_and_cancels_pending_outbox(self):
        coll = self.service.create_collective(self.owner, "Colmena Revoc")["record"]
        sender_mem = self.service.invite_instance(coll["id"], "inst_src", self.owner)["record"]
        self.service.accept_invitation(sender_mem["id"], self.owner)
        rec_mem = self.service.invite_instance(coll["id"], "inst_dst", self.owner)["record"]
        self.service.accept_invitation(rec_mem["id"], self.owner)

        consent_id = "cons_to_revoke"
        self.repo.tables["hive_share_consents"][consent_id] = {
            "id": consent_id,
            "collective_id": coll["id"],
            "owner_identity_ref": self.owner,
            "status": "active",
            "version": 1,
        }

        # Stage pending outbox entry
        outbox_id = "out_pending_01"
        self.repo.tables["hive_sync_outbox"][outbox_id] = {
            "id": outbox_id,
            "consent_id": consent_id,
            "collective_id": coll["id"],
            "status": "pending",
            "version": 1,
            "created_at": "2026-10-23T00:00:00Z",
        }

        tombstone_res = self.service.record_revocation(
            coll["id"], consent_id, "lineage:test",
            content_hash="1" * 64, revocation_generation=1,
            actor="owner@test"
        )
        self.assertEqual(tombstone_res["outcome"], "created")
        tombstone = tombstone_res["record"]
        self.assertEqual(tombstone["revocation_generation"], 1)

        # Verify consent is marked revoked
        revoked_consent = self.repo.get("hive_share_consents", consent_id)
        self.assertEqual(revoked_consent["status"], "revoked")
        self.assertEqual(revoked_consent["revocation_generation"], 1)

        # Verify pending outbox entry was cancelled
        cancelled_outbox = self.repo.get("hive_sync_outbox", outbox_id)
        self.assertEqual(cancelled_outbox["status"], "cancelled")

    # --- 8. Transactional Atomicity (Rollback on Failure) ---

    def test_transactional_rollback_preserves_state(self):
        coll = self.service.create_collective(self.owner, "Colmena Rollback")["record"]
        initial_memberships = len(self.repo.tables["hive_collective_memberships"])

        # Attempt to invite an instance with invalid collective_id inside service call
        with self.assertRaises(NotFoundError):
            self.service.invite_instance("col_non_existent", "inst_ghost", self.owner)

        # Verify no partial rows written
        self.assertEqual(len(self.repo.tables["hive_collective_memberships"]), initial_memberships)


if __name__ == "__main__":
    unittest.main()
