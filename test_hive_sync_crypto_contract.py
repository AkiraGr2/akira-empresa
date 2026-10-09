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
        "event_type": "KNOWLEDGE_SNAPSHOT",
        "event_id": "evt-test-01",
        "collective_id": "collective-test-01",
        "recipient_membership_id": "membership-test-02",
        "consent_id": "consent-test-03",
        "content_hash": snapshot_sha256(snapshot),
        "snapshot": snapshot,
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


class HiveSyncSignatureContractTests(unittest.TestCase):
    def setUp(self):
        self.private_key = Ed25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()
        self.key_id = "test-key-v1"

    def test_sign_and_verify_snapshot_event(self):
        unsigned = make_envelope()
        original = dict(unsigned)
        signed = sign_envelope(unsigned, self.private_key, self.key_id)

        self.assertTrue(verify_envelope(signed, {self.key_id: self.public_key}))
        self.assertEqual(unsigned, original, "signing must not mutate caller data")
        self.assertNotIn("signature", unsigned)
        self.assertEqual(signed["service_key_id"], self.key_id)
        self.assertNotIn("=", signed["signature"], "base64url signature is unpadded")

    def test_raw_public_key_bytes_can_verify(self):
        signed = sign_envelope(make_envelope(), self.private_key, self.key_id)
        raw_public = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.assertTrue(verify_envelope(signed, {self.key_id: raw_public}))

    def test_recipient_tampering_invalidates_signature(self):
        signed = sign_envelope(make_envelope(), self.private_key, self.key_id)
        signed["recipient_membership_id"] = "attacker-membership"
        with self.assertRaises(HiveSyncSignatureError):
            verify_envelope(signed, {self.key_id: self.public_key})

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

        envelope = make_envelope()
        envelope["event_type"] = "EXECUTE_COMMAND"
        with self.assertRaises(HiveSyncEnvelopeError):
            sign_envelope(envelope, self.private_key, self.key_id)

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
            "event_type": "KNOWLEDGE_REVOCATION",
            "event_id": "evt-revoke-01",
            "collective_id": "collective-test-01",
            "recipient_membership_id": "membership-test-02",
            "consent_id": "consent-test-03",
            "content_hash": snapshot_sha256(make_snapshot()),
            "revocation_generation": 2,
        }
        signed = sign_envelope(envelope, self.private_key, self.key_id)
        self.assertTrue(verify_envelope(signed, {self.key_id: self.public_key}))

    def test_revocation_cannot_carry_snapshot_content(self):
        envelope = {
            "protocol_version": "hive-sync/1",
            "event_type": "KNOWLEDGE_REVOCATION",
            "event_id": "evt-revoke-02",
            "collective_id": "collective-test-01",
            "recipient_membership_id": "membership-test-02",
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
