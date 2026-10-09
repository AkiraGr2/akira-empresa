"""Fail-closed cryptographic primitives for the proposed Hive Sync v1 protocol.

This module does not authorize publication. It does not validate human consent,
collective membership, recipient audience, evidence/provenance completeness, or the
export allow-list; callers must validate those first and pass an already-sanitized
snapshot. A valid signature proves integrity and service-key possession only, not
that the publication was authorized. No private key is generated at import or startup;
production signing is unavailable unless an operator provides a valid Ed25519 PEM key
file and key ID through explicit configuration.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import math
import os
import re
from uuid import UUID
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import rfc8785
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

PROTOCOL_VERSION = "hive-sync/1"
SIGNING_KEY_FILE_ENV = "HIVE_SYNC_SIGNING_KEY_FILE"
SIGNING_KEY_ID_ENV = "HIVE_SYNC_SIGNING_KEY_ID"
SIGNATURE_FIELD = "signature"
SIGNATURE_CONTEXT = b"AKIRA-HIVE-SYNC-V1\n"
MAX_PRIVATE_KEY_FILE_BYTES = 16 * 1024
MAX_CANONICAL_JSON_BYTES = 1024 * 1024
ALLOWED_EVENT_TYPES = frozenset({"KNOWLEDGE_SNAPSHOT", "KNOWLEDGE_REVOCATION"})
ALLOWED_ENVELOPE_FIELDS = frozenset({
    "protocol_version", "event_type", "event_id", "publication_id",
    "collective_id", "sender_owner_ref", "recipient_membership_id",
    "membership_generation", "sender_sequence", "knowledge_lineage_id",
    "revision_id", "parent_revision_ids", "content_hash", "snapshot",
    "privacy_level", "verification_status", "provenance", "evidence",
    "consent_id", "audience_hash", "issued_at", "service_key_id",
    "canonicalization", "revocation_generation", "signature",
})
ALLOWED_SNAPSHOT_FIELDS = frozenset({
    "concept", "content", "domain", "source", "source_id",
    "source_reference", "confidence", "evidence", "tags", "related_nodes",
})
FORBIDDEN_NESTED_SNAPSHOT_KEYS = frozenset({
    "owner_scope", "owner_id", "owner_email", "user_id", "created_by",
    "idempotency_key", "last_verified_at", "verified_by", "access_token",
    "refresh_token", "authorization", "headers", "session", "private_key",
    "api_key", "password", "secret",
})
_KEY_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_SIGNATURE_RE = re.compile(r"^[A-Za-z0-9_-]{86}$")


class HiveSyncCryptoError(RuntimeError):
    """Base error that is safe to translate to a generic operational status."""


class HiveSyncConfigurationError(HiveSyncCryptoError):
    """Signing configuration is absent or invalid; no fallback key is generated."""


class HiveSyncEnvelopeError(HiveSyncCryptoError):
    """Envelope data cannot be canonicalized or violates the minimal contract."""


class HiveSyncSignatureError(HiveSyncCryptoError):
    """An envelope signature is missing, untrusted, malformed, or invalid."""


def _reject_negative_zero(value: Any) -> None:
    """Reject -0.0 before JCS collapses it to the same representation as +0.0."""
    if isinstance(value, float) and value == 0.0 and math.copysign(1.0, value) < 0:
        raise HiveSyncEnvelopeError("negative_zero_not_allowed")
    if isinstance(value, Mapping):
        for nested in value.values():
            _reject_negative_zero(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _reject_negative_zero(nested)


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    """Serialize a JSON object with RFC 8785 JCS and return its UTF-8 bytes."""
    if not isinstance(value, Mapping):
        raise HiveSyncEnvelopeError("canonical_json_requires_object")
    _reject_negative_zero(value)
    try:
        canonical = rfc8785.dumps(dict(value))
    except Exception as exc:
        # Deliberately omit values/details, which may contain private knowledge.
        raise HiveSyncEnvelopeError("payload_not_canonicalizable") from exc
    if not isinstance(canonical, bytes):
        raise HiveSyncEnvelopeError("canonicalizer_returned_non_bytes")
    if len(canonical) > MAX_CANONICAL_JSON_BYTES:
        raise HiveSyncEnvelopeError("canonical_json_payload_too_large")
    return canonical


def snapshot_sha256(snapshot: Mapping[str, Any]) -> str:
    """Return lowercase SHA-256 hex for the canonical exportable snapshot."""
    if not isinstance(snapshot, Mapping):
        raise HiveSyncEnvelopeError("snapshot_requires_object")
    return hashlib.sha256(canonical_json_bytes(snapshot)).hexdigest()


def _reject_sensitive_snapshot_keys(value: Any) -> None:
    """Reject private/runtime metadata keys anywhere inside a snapshot projection."""
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if isinstance(key, str) and key.strip().lower() in FORBIDDEN_NESTED_SNAPSHOT_KEYS:
                raise HiveSyncEnvelopeError("snapshot_contains_forbidden_metadata")
            _reject_sensitive_snapshot_keys(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _reject_sensitive_snapshot_keys(nested)


def _validate_envelope(envelope: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(envelope, Mapping):
        raise HiveSyncEnvelopeError("envelope_requires_object")
    result = dict(envelope)
    if set(result) - ALLOWED_ENVELOPE_FIELDS:
        raise HiveSyncEnvelopeError("envelope_contains_unknown_fields")
    required = (
        "protocol_version",
        "event_type",
        "event_id",
        "collective_id",
        "recipient_membership_id",
        "consent_id",
        "content_hash",
    )
    for field in required:
        value = result.get(field)
        if not isinstance(value, str) or not value.strip():
            raise HiveSyncEnvelopeError("envelope_field_missing_or_invalid:" + field)

    if result["protocol_version"] != PROTOCOL_VERSION:
        raise HiveSyncEnvelopeError("unsupported_protocol_version")
    event_type = result["event_type"]
    if not isinstance(event_type, str) or event_type not in ALLOWED_EVENT_TYPES:
        raise HiveSyncEnvelopeError("unsupported_event_type")
    # The v1 contract defines event_id, collective_id and recipient membership
    # identifiers as canonical lowercase UUIDs, not arbitrary client-supplied names.
    for field in ("event_id", "collective_id", "recipient_membership_id"):
        try:
            normalized = str(UUID(result[field]))
        except (ValueError, TypeError, AttributeError) as exc:
            raise HiveSyncEnvelopeError("envelope_uuid_invalid:" + field) from exc
        if normalized != result[field]:
            raise HiveSyncEnvelopeError("envelope_uuid_not_canonical:" + field)
    content_hash = result["content_hash"]
    if not isinstance(content_hash, str) or not _HASH_RE.fullmatch(content_hash):
        raise HiveSyncEnvelopeError("content_hash_invalid")

    if result["event_type"] == "KNOWLEDGE_SNAPSHOT":
        snapshot = result.get("snapshot")
        if not isinstance(snapshot, Mapping):
            raise HiveSyncEnvelopeError("snapshot_event_requires_snapshot_object")
        if result.get("privacy_level") != "SHAREABLE":
            raise HiveSyncEnvelopeError("snapshot_must_be_shareable")
        if result.get("verification_status") != "verified":
            raise HiveSyncEnvelopeError("snapshot_must_be_verified")
        if set(snapshot) - ALLOWED_SNAPSHOT_FIELDS:
            raise HiveSyncEnvelopeError("snapshot_contains_unknown_fields")
        _reject_sensitive_snapshot_keys(snapshot)
        if "revocation_generation" in result:
            raise HiveSyncEnvelopeError("snapshot_must_not_contain_revocation_generation")
        actual_hash = snapshot_sha256(snapshot)
        if actual_hash != result["content_hash"]:
            raise HiveSyncEnvelopeError("snapshot_hash_mismatch")
    else:
        # A revocation identifies the previously shared hash; it must not
        # become a channel for re-sending any knowledge payload.
        if "snapshot" in result:
            raise HiveSyncEnvelopeError("revocation_must_not_contain_snapshot")
        if any(field in result for field in ("privacy_level", "verification_status", "evidence", "provenance")):
            raise HiveSyncEnvelopeError("revocation_must_not_contain_knowledge_payload")
        generation = result.get("revocation_generation")
        if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
            raise HiveSyncEnvelopeError("revocation_generation_invalid")
    return result


def _signing_bytes(unsigned_envelope: Mapping[str, Any]) -> bytes:
    return SIGNATURE_CONTEXT + canonical_json_bytes(unsigned_envelope)


def _encode_signature(signature: bytes) -> str:
    return base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")


def _decode_signature(value: Any) -> bytes:
    if not isinstance(value, str) or not _SIGNATURE_RE.fullmatch(value):
        raise HiveSyncSignatureError("signature_encoding_invalid")
    try:
        signature = base64.b64decode(
            value + "==",
            altchars=b"-_",
            validate=True,
        )
    except (binascii.Error, ValueError) as exc:
        raise HiveSyncSignatureError("signature_encoding_invalid") from exc
    if len(signature) != 64 or _encode_signature(signature) != value:
        raise HiveSyncSignatureError("signature_encoding_invalid")
    return signature


def sign_envelope(
    envelope: Mapping[str, Any],
    private_key: Ed25519PrivateKey,
    key_id: str,
) -> dict[str, Any]:
    """Return a new signed envelope; input mappings are never mutated."""
    if not isinstance(private_key, Ed25519PrivateKey):
        raise HiveSyncConfigurationError("ed25519_private_key_required")
    if not isinstance(key_id, str) or not _KEY_ID_RE.fullmatch(key_id):
        raise HiveSyncConfigurationError("signing_key_id_invalid")
    if not isinstance(envelope, Mapping):
        raise HiveSyncEnvelopeError("envelope_requires_object")
    if SIGNATURE_FIELD in envelope:
        raise HiveSyncEnvelopeError("unsigned_envelope_must_not_contain_signature")
    if "service_key_id" in envelope and envelope["service_key_id"] != key_id:
        raise HiveSyncEnvelopeError("service_key_id_mismatch")

    unsigned = dict(envelope)
    unsigned["service_key_id"] = key_id
    unsigned = _validate_envelope(unsigned)
    signature = private_key.sign(_signing_bytes(unsigned))
    signed = dict(unsigned)
    signed[SIGNATURE_FIELD] = _encode_signature(signature)
    return signed


def verify_envelope(
    envelope: Mapping[str, Any],
    trusted_public_keys: Mapping[str, Ed25519PublicKey | bytes],
) -> bool:
    """Verify structure, snapshot hash, key ID and Ed25519 signature."""
    if not isinstance(envelope, Mapping):
        raise HiveSyncSignatureError("envelope_requires_object")
    signed = dict(envelope)
    signature_value = signed.pop(SIGNATURE_FIELD, None)
    unsigned = _validate_envelope(signed)
    key_id = unsigned.get("service_key_id")
    if not isinstance(key_id, str) or not _KEY_ID_RE.fullmatch(key_id):
        raise HiveSyncSignatureError("service_key_id_invalid")

    public_key_value = trusted_public_keys.get(key_id)
    if public_key_value is None:
        raise HiveSyncSignatureError("service_key_untrusted")
    if isinstance(public_key_value, bytes):
        try:
            public_key = Ed25519PublicKey.from_public_bytes(public_key_value)
        except (TypeError, ValueError) as exc:
            raise HiveSyncSignatureError("trusted_public_key_invalid") from exc
    elif isinstance(public_key_value, Ed25519PublicKey):
        public_key = public_key_value
    else:
        raise HiveSyncSignatureError("trusted_public_key_invalid")

    signature = _decode_signature(signature_value)
    try:
        public_key.verify(signature, _signing_bytes(unsigned))
    except InvalidSignature as exc:
        raise HiveSyncSignatureError("signature_verification_failed") from exc
    return True


def load_signing_key_from_environment(
    environ: Mapping[str, str] | None = None,
) -> tuple[str, Ed25519PrivateKey]:
    """Load an explicitly configured Ed25519 private key from a PEM file.

    The key material is never returned in an error message and no key is generated
    implicitly. This function is intentionally not called during module import.
    """
    source = os.environ if environ is None else environ
    key_path_value = source.get(SIGNING_KEY_FILE_ENV)
    key_id = source.get(SIGNING_KEY_ID_ENV)

    if not isinstance(key_path_value, str) or not key_path_value.strip():
        raise HiveSyncConfigurationError("signing_key_file_not_configured")
    if not isinstance(key_id, str) or not _KEY_ID_RE.fullmatch(key_id):
        raise HiveSyncConfigurationError("signing_key_id_not_configured")

    try:
        key_path = Path(key_path_value)
        key_bytes = key_path.read_bytes()
    except (OSError, ValueError) as exc:
        raise HiveSyncConfigurationError("signing_key_file_unavailable") from exc

    if not key_bytes or len(key_bytes) > MAX_PRIVATE_KEY_FILE_BYTES:
        raise HiveSyncConfigurationError("signing_key_file_size_invalid")
    try:
        loaded = serialization.load_pem_private_key(key_bytes, password=None)
    except (ValueError, TypeError) as exc:
        raise HiveSyncConfigurationError("signing_key_file_invalid") from exc
    if not isinstance(loaded, Ed25519PrivateKey):
        raise HiveSyncConfigurationError("signing_key_must_be_ed25519")
    return key_id, loaded
