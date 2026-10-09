import json
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key

from persistence.hive_sync_crypto import (
    HiveSyncConfigurationError,
    HiveSyncEnvelopeError,
    HiveSyncSignatureError,
    SIGNING_KEY_FILE_ENV,
    SIGNING_KEY_ID_ENV,
    canonical_json_bytes,
    load_signing_key_from_environment,
    sign_envelope,
    snapshot_sha256,
    strict_json_object_loads,
    verify_envelope,
)


def make_snapshot():
    return {
        "concept": "test consent",
        "content": "synthetic, non-sensitive knowledge",
        "source_reference": "https://example.invalid/evidence/1",
    }


def make_envelope(snapshot=None):
    snapshot = make_snapshot() if snapshot is None else snapshot
    return {
        "protocol_version": "hive-sync/1",
        "canonicalization": "RFC8785",
        "event_type": "KNOWLEDGE_SNAPSHOT",
        "event_id": "10000000-0000-4000-8000-000000000001",
        "collective_id": "20000000-0000-4000-8000-000000000001",
        "recipient_membership_id": "30000000-0000-4000-8000-000000000001",
        "publication_id": "40000000-0000-4000-8000-000000000001",
        "sender_owner_ref": "owner-ref-test",
        "membership_generation": 1,
        "sender_sequence": 1,
        "knowledge_lineage_id": "lineage-test-01",
        "revision_id": "revision-test-01",
        "parent_revision_ids": [],
        "audience_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "issued_at": "2026-10-09T00:00:00Z",
        "consent_id": "consent-test-03",
        "content_hash": snapshot_sha256(snapshot),
        "snapshot": snapshot,
        "evidence": [{"reference": "https://example.invalid/evidence/1"}],
        "provenance": {"source_reference": "https://example.invalid/evidence/1"},
        "privacy_level": "SHAREABLE",
        "verification_status": "verified",
    }


class HiveSyncCanonicalizationContractTests(unittest.TestCase):
    def test_jcs_is_stable_and_sorts_object_keys(self):
        value = {"z": 1, "a": "á", "n": [True, None]}
        self.assertEqual(
            canonical_json_bytes(value),
            b'{"a":"\xc3\xa1","n":[true,null],"z":1}',
        )

    def test_rfc8785_number_serialization_vector(self):
        # RFC 8785 §3.2.2 example: canonicalize binary64 values, not input spelling.
        value = {"numbers": [333333333.33333329, 1e30, 4.50, 2e-3, 1e-27]}
        self.assertEqual(
            canonical_json_bytes(value),
            b'{"numbers":[333333333.3333333,1e+30,4.5,0.002,1e-27]}',
        )

    def test_rfc8785_utf16_property_sorting_vector(self):
        # RFC 8785 §3.2.3 property-order example, including non-ASCII keys.
        value = {
            "\u20ac": "Euro Sign",
            "\r": "Carriage Return",
            "\ufb33": "Hebrew Letter Dalet With Dagesh",
            "1": "One",
            "\U0001f600": "Emoji: Grinning Face",
            "\u0080": "Control",
            "\u00f6": "Latin Small Letter O With Diaeresis",
        }
        expected = (
            '{"\\r":"Carriage Return","1":"One","\u0080":"Control",'
            '"\u00f6":"Latin Small Letter O With Diaeresis","€":"Euro Sign",'
            '"😀":"Emoji: Grinning Face","דּ":"Hebrew Letter Dalet With Dagesh"}'
        )
        self.assertEqual(canonical_json_bytes(value).decode("utf-8"), expected)

    def test_negative_zero_is_rejected_before_signing(self):
        with self.assertRaises(HiveSyncEnvelopeError):
            canonical_json_bytes({"nested": [0, {"negative": -0.0}]})

    def test_snapshot_hash_is_sha256_of_jcs_bytes(self):
        snapshot = make_snapshot()
        import hashlib

        self.assertEqual(
            snapshot_sha256(snapshot),
            hashlib.sha256(canonical_json_bytes(snapshot)).hexdigest(),
        )

    def test_non_object_snapshot_is_rejected(self):
        with self.assertRaises(HiveSyncEnvelopeError):
            snapshot_sha256(["not", "an", "object"])

    def test_noncanonicalizable_values_fail_closed(self):
        with self.assertRaises(HiveSyncEnvelopeError):
            canonical_json_bytes({1: "non-string JSON key"})
        with self.assertRaises(HiveSyncEnvelopeError):
            canonical_json_bytes({"number": float("nan")})

    def test_canonical_payload_size_is_bounded(self):
        with self.assertRaises(HiveSyncEnvelopeError):
            canonical_json_bytes({"blob": "x" * (1024 * 1024)})

    def test_extreme_nesting_is_rejected_before_recursive_processing(self):
        value = "leaf"
        for _ in range(100):
            value = [value]
        with self.assertRaises(HiveSyncEnvelopeError):
            canonical_json_bytes({"nested": value})

    def test_excessive_node_count_is_rejected(self):
        with self.assertRaises(HiveSyncEnvelopeError):
            canonical_json_bytes({"items": [None] * 100_001})

    def test_node_limit_stops_before_exhausting_large_container(self):
        class GuardedList(list):
            def __iter__(self):
                for index, item in enumerate(super().__iter__()):
                    if index >= 100_000:
                        raise AssertionError("preflight eagerly consumed too many siblings")
                    yield item

        # A bounded traversal rejects this before iterating the entire container.
        with self.assertRaises(HiveSyncEnvelopeError):
            canonical_json_bytes({"items": GuardedList([None] * 200_000)})

    def test_cyclic_python_object_graph_is_rejected(self):
        cyclic = []
        cyclic.append(cyclic)
        with self.assertRaises(HiveSyncEnvelopeError):
            canonical_json_bytes({"cycle": cyclic})

    def test_repeated_but_acyclic_subobject_is_allowed(self):
        shared = {"safe": "value"}
        self.assertEqual(
            canonical_json_bytes({"first": shared, "second": shared}),
            b'{"first":{"safe":"value"},"second":{"safe":"value"}}',
        )

    def test_invalid_unicode_is_rejected_with_contract_error(self):
        with self.assertRaises(HiveSyncEnvelopeError):
            canonical_json_bytes({"invalid": chr(0xD800)})

    def test_unsupported_python_objects_are_rejected_before_serialization(self):
        with self.assertRaises(HiveSyncEnvelopeError):
            canonical_json_bytes({"unexpected": object()})

    def test_strict_json_parser_rejects_duplicate_keys(self):
        for raw in (
            '{"event_type":"KNOWLEDGE_SNAPSHOT","event_type":"KNOWLEDGE_REVOCATION"}',
            '{"nested":{"role":"owner","role":"attacker"}}',
            '{"event_type":"KNOWLEDGE_SNAPSHOT","\\u0065vent_type":"KNOWLEDGE_REVOCATION"}',
        ):
            with self.subTest(raw=raw):
                with self.assertRaises(HiveSyncEnvelopeError):
                    strict_json_object_loads(raw)

    def test_strict_json_parser_rejects_all_negative_zero_spellings(self):
        for raw in ('{"value":-0}', '{"value":-0.0}', '{"value":-0e0}', '{"value":-0.000E+4}'):
            with self.subTest(raw=raw):
                with self.assertRaises(HiveSyncEnvelopeError):
                    strict_json_object_loads(raw)

    def test_strict_json_parser_rejects_nonfinite_and_invalid_json(self):
        for raw in ('{"value":NaN}', '{"value":Infinity}', '{"value":-Infinity}', '{"value":1e400}', '{"broken":'):
            with self.subTest(raw=raw):
                with self.assertRaises(HiveSyncEnvelopeError):
                    strict_json_object_loads(raw)
        with self.assertRaises(HiveSyncEnvelopeError):
            strict_json_object_loads(b'{"value":"\xff"}')

    def test_strict_json_parser_requires_object_root(self):
        for raw in ('[]', 'null', '"scalar"'):
            with self.subTest(raw=raw):
                with self.assertRaises(HiveSyncEnvelopeError):
                    strict_json_object_loads(raw)


class HiveSyncSignatureContractTests(unittest.TestCase):
    def setUp(self):
        self.private_key = Ed25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()
        self.key_id = "test-key-v1"

    def test_unknown_envelope_fields_are_rejected(self):
        for field in ("owner_scope", "authorization", "debug_secret"):
            with self.subTest(field=field):
                envelope = make_envelope()
                envelope[field] = "must-not-leak"
                with self.assertRaises(HiveSyncEnvelopeError):
                    sign_envelope(envelope, self.private_key, self.key_id)

    def test_snapshot_projection_rejects_unallowlisted_fields(self):
        for field in ("owner_scope", "id", "status", "created_at", "verified_by", "source_id", "related_nodes"):
            with self.subTest(field=field):
                snapshot = make_snapshot()
                snapshot[field] = "must-not-leak"
                with self.assertRaises(HiveSyncEnvelopeError):
                    sign_envelope(make_envelope(snapshot), self.private_key, self.key_id)

    def test_nested_snapshot_rejects_private_runtime_metadata(self):
        snapshot = make_snapshot()
        snapshot["evidence"] = [{"metadata": {"access_token": "synthetic-secret"}}]
        with self.assertRaises(HiveSyncEnvelopeError):
            sign_envelope(make_envelope(snapshot), self.private_key, self.key_id)

    def test_signed_evidence_and_provenance_reject_sensitive_keys(self):
        cases = (
            ("evidence", [{"metadata": {"apiKey": "synthetic-secret"}}]),
            ("provenance", {"context": {"ownerId": "synthetic-owner"}}),
            ("evidence", [{"credentials": {"user": "synthetic-user"}}]),
            ("evidence", [{"headers": {"clientSecret": "synthetic-secret"}}]),
            ("provenance", {"transport": {"bearer-token": "synthetic-token"}}]),
            ("evidence", [{"session": {"serviceRoleKey": "synthetic-key"}}]),
            ("provenance", {"config": {"connection_string": "synthetic-dsn"}}]),
        )
        for field, value in cases:
            with self.subTest(field=field, value=value):
                envelope = make_envelope()
                envelope[field] = value
                with self.assertRaises(HiveSyncEnvelopeError):
                    sign_envelope(envelope, self.private_key, self.key_id)

    def test_cyclic_snapshot_is_rejected_before_sensitive_metadata_scan(self):
        envelope = make_envelope()
        cyclic = []
        cyclic.append(cyclic)
        envelope["snapshot"]["evidence"] = cyclic
        with self.assertRaises(HiveSyncEnvelopeError):
            sign_envelope(envelope, self.private_key, self.key_id)

    def test_revocation_rejects_knowledge_payload_metadata(self):
        envelope = {
            "protocol_version": "hive-sync/1",
        "canonicalization": "RFC8785",
            "event_type": "KNOWLEDGE_REVOCATION",
            "event_id": "10000000-0000-4000-8000-000000000005",
            "collective_id": "20000000-0000-4000-8000-000000000001",
            "recipient_membership_id": "30000000-0000-4000-8000-000000000001",
            "publication_id": "40000000-0000-4000-8000-000000000001",
            "sender_owner_ref": "owner-ref-test",
            "membership_generation": 1,
            "sender_sequence": 1,
            "knowledge_lineage_id": "lineage-test-01",
            "revision_id": "revision-test-01",
            "parent_revision_ids": [],
            "audience_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "issued_at": "2026-10-09T00:00:00Z",
            "consent_id": "consent-test-03",
            "content_hash": snapshot_sha256(make_snapshot()),
            "revocation_generation": 3,
            "privacy_level": "SHAREABLE",
        }
        with self.assertRaises(HiveSyncEnvelopeError):
            sign_envelope(envelope, self.private_key, self.key_id)

    def test_canonicalization_marker_is_required_and_fixed(self):
        envelope = make_envelope()
        del envelope["canonicalization"]
        with self.assertRaises(HiveSyncEnvelopeError):
            sign_envelope(envelope, self.private_key, self.key_id)

        for bad_value in ("JCS", "RFC8785-JCS", None, 1):
            with self.subTest(canonicalization=bad_value):
                envelope = make_envelope()
                envelope["canonicalization"] = bad_value
                with self.assertRaises(HiveSyncEnvelopeError):
                    sign_envelope(envelope, self.private_key, self.key_id)

    def test_minimum_v1_envelope_fields_are_required(self):
        required = (
            "publication_id",
            "sender_owner_ref",
            "membership_generation",
            "sender_sequence",
            "knowledge_lineage_id",
            "revision_id",
            "parent_revision_ids",
            "audience_hash",
            "issued_at",
            "evidence",
            "provenance",
        )
        for field in required:
            with self.subTest(field=field):
                envelope = make_envelope()
                envelope.pop(field)
                with self.assertRaises(HiveSyncEnvelopeError):
                    sign_envelope(envelope, self.private_key, self.key_id)

    def test_generation_sequence_audience_hash_and_parents_are_validated(self):
        for field in ("membership_generation", "sender_sequence"):
            for value in (0, -1, True, "1", None):
                with self.subTest(field=field, value=value):
                    envelope = make_envelope()
                    envelope[field] = value
                    with self.assertRaises(HiveSyncEnvelopeError):
                        sign_envelope(envelope, self.private_key, self.key_id)

        for value in ("short", "g" * 64, None):
            with self.subTest(audience_hash=value):
                envelope = make_envelope()
                envelope["audience_hash"] = value
                with self.assertRaises(HiveSyncEnvelopeError):
                    sign_envelope(envelope, self.private_key, self.key_id)

        for value in ("not-an-array", [1], ["revision", ""], ["revision", "revision"]):
            with self.subTest(parent_revision_ids=value):
                envelope = make_envelope()
                envelope["parent_revision_ids"] = value
                with self.assertRaises(HiveSyncEnvelopeError):
                    sign_envelope(envelope, self.private_key, self.key_id)

    def test_issued_at_must_be_canonical_utc_timestamp(self):
        invalid_values = (
            "",
            "now",
            "2026-10-09T00:00:00+00:00",
            "2026-10-09T01:00:00+01:00",
            "2026-02-30T00:00:00Z",
            "2026-10-09 00:00:00Z",
            "2026-10-09T00:00:00.1234567Z",
        )
        for value in invalid_values:
            with self.subTest(issued_at=value):
                envelope = make_envelope()
                envelope["issued_at"] = value
                with self.assertRaises(HiveSyncEnvelopeError):
                    sign_envelope(envelope, self.private_key, self.key_id)

        envelope = make_envelope()
        envelope["issued_at"] = "2026-10-09T00:00:00.123456Z"
        signed = sign_envelope(envelope, self.private_key, self.key_id)
        self.assertTrue(verify_envelope(signed, {self.key_id: self.public_key}))

    def test_snapshot_requires_nonempty_string_concept_and_content(self):
        for field in ("concept", "content"):
            with self.subTest(field=field, kind="missing"):
                snapshot = make_snapshot()
                snapshot.pop(field)
                with self.assertRaises(HiveSyncEnvelopeError):
                    sign_envelope(make_envelope(snapshot), self.private_key, self.key_id)
            for bad_value in ("", "  ", None, 1, []):
                with self.subTest(field=field, bad_value=bad_value):
                    snapshot = make_snapshot()
                    snapshot[field] = bad_value
                    with self.assertRaises(HiveSyncEnvelopeError):
                        sign_envelope(make_envelope(snapshot), self.private_key, self.key_id)

    def test_sign_and_verify_snapshot_event(self):
        unsigned = make_envelope()
        original = dict(unsigned)
        signed = sign_envelope(unsigned, self.private_key, self.key_id)

        self.assertTrue(verify_envelope(signed, {self.key_id: self.public_key}))
        self.assertEqual(unsigned, original, "signing must not mutate caller data")
        self.assertNotIn("signature", unsigned)
        self.assertEqual(signed["service_key_id"], self.key_id)
        self.assertNotIn("=", signed["signature"], "base64url signature is unpadded")

    def test_raw_json_envelope_is_parsed_strictly_before_verification(self):
        signed = sign_envelope(make_envelope(), self.private_key, self.key_id)
        raw = json.dumps(signed, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.assertTrue(verify_envelope(raw, {self.key_id: self.public_key}))

        decoded = raw.decode("utf-8")
        marker = '"event_type":"KNOWLEDGE_SNAPSHOT"'
        self.assertIn(marker, decoded)
        ambiguous = decoded.replace(
            marker,
            marker + ',"event_type":"KNOWLEDGE_REVOCATION"',
            1,
        )
        with self.assertRaises(HiveSyncEnvelopeError):
            verify_envelope(ambiguous, {self.key_id: self.public_key})

    def test_raw_public_key_bytes_can_verify(self):
        signed = sign_envelope(make_envelope(), self.private_key, self.key_id)
        raw_public = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.assertTrue(verify_envelope(signed, {self.key_id: raw_public}))

    def test_recipient_tampering_invalidates_signature(self):
        signed = sign_envelope(make_envelope(), self.private_key, self.key_id)
        signed["recipient_membership_id"] = "30000000-0000-4000-8000-000000000009"
        with self.assertRaises(HiveSyncSignatureError):
            verify_envelope(signed, {self.key_id: self.public_key})

    def test_malformed_content_hash_type_fails_closed(self):
        for bad_hash in (None, 123, [], {"hash": "abc"}):
            with self.subTest(content_hash=bad_hash):
                envelope = make_envelope()
                envelope["content_hash"] = bad_hash
                with self.assertRaises(HiveSyncEnvelopeError):
                    sign_envelope(envelope, self.private_key, self.key_id)

    def test_snapshot_content_hash_mismatch_is_rejected(self):
        signed = sign_envelope(make_envelope(), self.private_key, self.key_id)
        signed["snapshot"]["content"] = "tampered"
        with self.assertRaises(HiveSyncEnvelopeError):
            verify_envelope(signed, {self.key_id: self.public_key})

    def test_private_or_sensitive_snapshot_cannot_be_signed(self):
        for level in ("PRIVATE", "SENSITIVE", "COLLECTIVE"):
            with self.subTest(level=level):
                envelope = make_envelope()
                envelope["privacy_level"] = level
                with self.assertRaises(HiveSyncEnvelopeError):
                    sign_envelope(envelope, self.private_key, self.key_id)

    def test_unverified_snapshot_cannot_be_signed(self):
        envelope = make_envelope()
        envelope["verification_status"] = "partially_verified"
        with self.assertRaises(HiveSyncEnvelopeError):
            sign_envelope(envelope, self.private_key, self.key_id)

    def test_unknown_protocol_and_event_type_fail_closed(self):
        envelope = make_envelope()
        envelope["protocol_version"] = "hive-sync/999"
        with self.assertRaises(HiveSyncEnvelopeError):
            sign_envelope(envelope, self.private_key, self.key_id)

        for bad_event_type in ("EXECUTE_COMMAND", [], {"type": "KNOWLEDGE_SNAPSHOT"}, None):
            with self.subTest(event_type=bad_event_type):
                envelope = make_envelope()
                envelope["event_type"] = bad_event_type
                with self.assertRaises(HiveSyncEnvelopeError):
                    sign_envelope(envelope, self.private_key, self.key_id)

    def test_v1_identifiers_must_be_canonical_uuids(self):
        for field, bad_value in (
            ("event_id", "evt-not-a-uuid"),
            ("collective_id", "a0000000-0000-4000-8000-000000000001".upper()),
            ("recipient_membership_id", "not-a-membership-uuid"),
        ):
            with self.subTest(field=field, bad_value=bad_value):
                envelope = make_envelope()
                envelope[field] = bad_value
                with self.assertRaises(HiveSyncEnvelopeError):
                    sign_envelope(envelope, self.private_key, self.key_id)

    def test_revocation_generation_must_be_positive_integer(self):
        base = {
            "protocol_version": "hive-sync/1",
        "canonicalization": "RFC8785",
            "event_type": "KNOWLEDGE_REVOCATION",
            "event_id": "10000000-0000-4000-8000-000000000004",
            "collective_id": "20000000-0000-4000-8000-000000000001",
            "recipient_membership_id": "30000000-0000-4000-8000-000000000001",
            "publication_id": "40000000-0000-4000-8000-000000000001",
            "sender_owner_ref": "owner-ref-test",
            "membership_generation": 1,
            "sender_sequence": 1,
            "knowledge_lineage_id": "lineage-test-01",
            "revision_id": "revision-test-01",
            "parent_revision_ids": [],
            "audience_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "issued_at": "2026-10-09T00:00:00Z",
            "consent_id": "consent-test-03",
            "content_hash": snapshot_sha256(make_snapshot()),
        }
        for value in (0, -1, True, "2", None):
            with self.subTest(value=value):
                envelope = dict(base, revocation_generation=value)
                with self.assertRaises(HiveSyncEnvelopeError):
                    sign_envelope(envelope, self.private_key, self.key_id)
        with self.assertRaises(HiveSyncEnvelopeError):
            sign_envelope(base, self.private_key, self.key_id)

    def test_missing_signature_is_rejected(self):
        with self.assertRaises(HiveSyncSignatureError):
            verify_envelope(make_envelope(), {self.key_id: self.public_key})

    def test_unknown_key_id_is_rejected(self):
        signed = sign_envelope(make_envelope(), self.private_key, self.key_id)
        with self.assertRaises(HiveSyncSignatureError):
            verify_envelope(signed, {"other-key": self.public_key})

    def test_wrong_public_key_is_rejected(self):
        signed = sign_envelope(make_envelope(), self.private_key, self.key_id)
        wrong_public = Ed25519PrivateKey.generate().public_key()
        with self.assertRaises(HiveSyncSignatureError):
            verify_envelope(signed, {self.key_id: wrong_public})

    def test_signature_with_invalid_encoding_is_rejected(self):
        signed = sign_envelope(make_envelope(), self.private_key, self.key_id)
        signed["signature"] = "not a base64url signature"
        with self.assertRaises(HiveSyncSignatureError):
            verify_envelope(signed, {self.key_id: self.public_key})

    def test_signer_rejects_existing_signature_and_wrong_key_id(self):
        envelope = make_envelope()
        envelope["signature"] = "already-signed"
        with self.assertRaises(HiveSyncEnvelopeError):
            sign_envelope(envelope, self.private_key, self.key_id)

        envelope = make_envelope()
        envelope["service_key_id"] = "different-key"
        with self.assertRaises(HiveSyncEnvelopeError):
            sign_envelope(envelope, self.private_key, self.key_id)

    def test_revocation_envelope_can_reference_hash_without_snapshot(self):
        envelope = {
            "protocol_version": "hive-sync/1",
        "canonicalization": "RFC8785",
            "event_type": "KNOWLEDGE_REVOCATION",
            "event_id": "10000000-0000-4000-8000-000000000002",
            "collective_id": "20000000-0000-4000-8000-000000000001",
            "recipient_membership_id": "30000000-0000-4000-8000-000000000001",
            "publication_id": "40000000-0000-4000-8000-000000000001",
            "sender_owner_ref": "owner-ref-test",
            "membership_generation": 1,
            "sender_sequence": 1,
            "knowledge_lineage_id": "lineage-test-01",
            "revision_id": "revision-test-01",
            "parent_revision_ids": [],
            "audience_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "issued_at": "2026-10-09T00:00:00Z",
            "consent_id": "consent-test-03",
            "content_hash": snapshot_sha256(make_snapshot()),
            "revocation_generation": 2,
        }
        signed = sign_envelope(envelope, self.private_key, self.key_id)
        self.assertTrue(verify_envelope(signed, {self.key_id: self.public_key}))

    def test_revocation_cannot_carry_snapshot_content(self):
        envelope = {
            "protocol_version": "hive-sync/1",
        "canonicalization": "RFC8785",
            "event_type": "KNOWLEDGE_REVOCATION",
            "event_id": "10000000-0000-4000-8000-000000000003",
            "collective_id": "20000000-0000-4000-8000-000000000001",
            "recipient_membership_id": "30000000-0000-4000-8000-000000000001",
            "publication_id": "40000000-0000-4000-8000-000000000001",
            "sender_owner_ref": "owner-ref-test",
            "membership_generation": 1,
            "sender_sequence": 1,
            "knowledge_lineage_id": "lineage-test-01",
            "revision_id": "revision-test-01",
            "parent_revision_ids": [],
            "audience_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "issued_at": "2026-10-09T00:00:00Z",
            "consent_id": "consent-test-03",
            "content_hash": snapshot_sha256(make_snapshot()),
            "snapshot": make_snapshot(),
        }
        with self.assertRaises(HiveSyncEnvelopeError):
            sign_envelope(envelope, self.private_key, self.key_id)

    def test_loaded_key_file_signs_and_verifies(self):
        key_bytes = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "hive-sync-test-key.pem"
            path.write_bytes(key_bytes)
            key_id, loaded_key = load_signing_key_from_environment({
                SIGNING_KEY_FILE_ENV: str(path),
                SIGNING_KEY_ID_ENV: self.key_id,
            })
        signed = sign_envelope(make_envelope(), loaded_key, key_id)
        self.assertTrue(verify_envelope(signed, {key_id: loaded_key.public_key()}))

    def test_missing_key_configuration_does_not_generate_key(self):
        with self.assertRaises(HiveSyncConfigurationError):
            load_signing_key_from_environment({})
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(HiveSyncConfigurationError):
                load_signing_key_from_environment({
                    SIGNING_KEY_FILE_ENV: str(Path(temporary) / "missing.pem"),
                    SIGNING_KEY_ID_ENV: self.key_id,
                })

    def test_invalid_key_file_is_rejected_without_exposing_contents(self):
        secret_marker = "DO_NOT_LEAK_THIS_PRIVATE_KEY"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.pem"
            path.write_text(secret_marker, encoding="utf-8")
            with self.assertRaises(HiveSyncConfigurationError) as raised:
                load_signing_key_from_environment({
                    SIGNING_KEY_FILE_ENV: str(path),
                    SIGNING_KEY_ID_ENV: self.key_id,
                })
        self.assertNotIn(secret_marker, str(raised.exception))

    def test_non_ed25519_private_key_is_rejected(self):
        rsa_key = generate_private_key(public_exponent=65537, key_size=2048)
        pem = rsa_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "rsa-key.pem"
            path.write_bytes(pem)
            with self.assertRaises(HiveSyncConfigurationError):
                load_signing_key_from_environment({
                    SIGNING_KEY_FILE_ENV: str(path),
                    SIGNING_KEY_ID_ENV: self.key_id,
                })

    def test_invalid_key_id_is_rejected(self):
        with self.assertRaises(HiveSyncConfigurationError):
            sign_envelope(make_envelope(), self.private_key, "../bad-key-id")


if __name__ == "__main__":
    unittest.main()
