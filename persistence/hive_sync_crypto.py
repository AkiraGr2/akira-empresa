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
from datetime import datetime
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
CANONICALIZATION_VERSION = "RFC8785"
SIGNING_KEY_FILE_ENV = "HIVE_SYNC_SIGNING_KEY_FILE"
SIGNING_KEY_ID_ENV = "HIVE_SYNC_SIGNING_KEY_ID"
SIGNATURE_FIELD = "signature"
SIGNATURE_CONTEXT = b"AKIRA-HIVE-SYNC-V1\n"
MAX_PRIVATE_KEY_FILE_BYTES = 16 * 1024
MAX_CANONICAL_JSON_BYTES = 1024 * 1024
MAX_JSON_NESTING_DEPTH = 64
MAX_JSON_NODE_COUNT = 100_000
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
    # Omit internal identifiers (source_id, related_nodes) by default; callers
    # must transform approved provenance into an explicit safe reference first.
    "concept", "content", "domain", "source", "source_reference",
    "confidence", "evidence", "tags",
})
FORBIDDEN_NESTED_SNAPSHOT_KEYS = frozenset({
    "owner_scope", "owner_id", "owner_email", "user_id", "created_by",
    "idempotency_key", "last_verified_at", "verified_by", "access_token",
    "refresh_token", "authorization", "headers", "session", "private_key",
    "api_key", "password", "secret",
})
_KEY_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_UTC_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")
_SIGNATURE_RE = re.compile(r"^[A-Za-z0-9_-]{86}$")


class HiveSyncCryptoError(RuntimeError):
    """Base error that is safe to translate to a generic operational status."""


class HiveSyncConfigurationError(HiveSyncCryptoError):
    """Signing configuration is absent or invalid; no fallback key is generated."""


class HiveSyncEnvelopeError(HiveSyncCryptoError):
    """Envelope data cannot be canonicalized or violates the minimal contract."""


class HiveSyncSignatureError(HiveSyncCryptoError):
    """An envelope signature is missing, untrusted, malformed, or invalid."""


def _utf8_size(value: str) -> int:
    """Return strict UTF-8 size, translating invalid surrogate input to a safe error."""
    try:
        return len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise HiveSyncEnvelopeError("canonical_json_string_not_valid_unicode") from exc


def _preflight_json_value(value: Any) -> None:
    """Bound and validate a JSON-like tree before recursive checks or serialization.

    This avoids spending unbounded memory on oversized payloads and prevents deeply
    nested caller data from escaping as RecursionError before the canonicalizer runs.
    """
    stack = [(value, 0)]
    node_count = 0
    estimated_bytes = 0
    while stack:
        current, depth = stack.pop()
        node_count += 1
        if node_count > MAX_JSON_NODE_COUNT:
            raise HiveSyncEnvelopeError("canonical_json_node_limit_exceeded")
        if depth > MAX_JSON_NESTING_DEPTH:
            raise HiveSyncEnvelopeError("canonical_json_nesting_too_deep")

        if isinstance(current, Mapping):
            estimated_bytes += 2
            for key, nested in current.items():
                if not isinstance(key, str):
                    raise HiveSyncEnvelopeError("canonical_json_object_key_not_string")
                if len(key) > MAX_CANONICAL_JSON_BYTES:
                    raise HiveSyncEnvelopeError("canonical_json_payload_too_large")
                estimated_bytes += _utf8_size(key) + 3
                stack.append((nested, depth + 1))
        elif isinstance(current, (list, tuple)):
            estimated_bytes += 2
            for nested in current:
                stack.append((nested, depth + 1))
        elif isinstance(current, str):
            if len(current) > MAX_CANONICAL_JSON_BYTES:
                raise HiveSyncEnvelopeError("canonical_json_payload_too_large")
            estimated_bytes += _utf8_size(current) + 2
        elif current is None or isinstance(current, bool):
            estimated_bytes += 5
        elif isinstance(current, int):
            estimated_bytes += min(current.bit_length() // 3 + 3, MAX_CANONICAL_JSON_BYTES + 1)
        elif isinstance(current, float):
            estimated_bytes += 32
        else:
            raise HiveSyncEnvelopeError("canonical_json_value_type_unsupported")

        if estimated_bytes > MAX_CANONICAL_JSON_BYTES:
            raise HiveSyncEnvelopeError("canonical_json_payload_too_large")


def _reject_negative_zero(value: Any) -> None:
    """Reject -0.0 before JCS collapses it to the same representation as +0.0."""
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, float) and current == 0.0 and math.copysign(1.0, current) < 0:
            raise HiveSyncEnvelopeError("negative_zero_not_allowed")
        if isinstance(current, Mapping):
            stack.extend(current.values())
        elif isinstance(current, (list, tuple)):
            stack.extend(current)


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    """Serialize a JSON object with RFC 8785 JCS and return its UTF-8 bytes."""
    if not isinstance(value, Mapping):
        raise HiveSyncEnvelopeError("canonical_json_requires_object")
    _preflight_json_value(value)
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
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, Mapping):
            for key, nested in current.items():
                if isinstance(key, str) and key.strip().lower() in FORBIDDEN_NESTED_SNAPSHOT_KEYS:
                    raise HiveSyncEnvelopeError("snapshot_contains_forbidden_metadata")
                stack.append(nested)
        elif isinstance(current, (list, tuple)):
            stack.extend(current)


def _validate_issued_at(value: str) -> None:
    """Require the canonical v1 UTC timestamp form and a real calendar date."""
    if not _UTC_TIMESTAMP_RE.fullmatch(value):
        raise HiveSyncEnvelopeError("issued_at_invalid")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise HiveSyncEnvelopeError("issued_at_invalid") from exc


def _validate_envelope(envelope: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(envelope, Mapping):
        raise HiveSyncEnvelopeError("envelope_requires_object")
    result = dict(envelope)
    if set(result) - ALLOWED_ENVELOPE_FIELDS:
        raise HiveSyncEnvelopeError("envelope_contains_unknown_fields")
    required_string_fields = (
        "protocol_version",
        "canonicalization",
        "event_type",
        "event_id",
        "publication_id",
        "collective_id",
        "sender_owner_ref",
        "recipient_membership_id",
        "knowledge_lineage_id",
        "revision_id",
        "consent_id",
        "audience_hash",
        "issued_at",
        "content_hash",
    )
    for field in required_string_fields:
        value = result.get(field)
        if not isinstance(value, str) or not value.strip():
            raise HiveSyncEnvelopeError("envelope_field_missing_or_invalid:" + field)

    for field in ("membership_generation", "sender_sequence"):
        value = result.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise HiveSyncEnvelopeError("envelope_positive_integer_required:" + field)

    parent_revision_ids = result.get("parent_revision_ids")
    if not isinstance(parent_revision_ids, list) or any(
        not isinstance(parent_id, str) or not parent_id.strip()
        for parent_id in parent_revision_ids
    ):
        raise HiveSyncEnvelopeError("parent_revision_ids_invalid")
    if len(set(parent_revision_ids)) != len(parent_revision_ids):
        raise HiveSyncEnvelopeError("parent_revision_ids_duplicate")

    _validate_issued_at(result["issued_at"])
    if result["protocol_version"] != PROTOCOL_VERSION:
        raise HiveSyncEnvelopeError("unsupported_protocol_version")
    if result["canonicalization"] != CANONICALIZATION_VERSION:
        raise HiveSyncEnvelopeError("unsupported_canonicalization")
    if not _HASH_RE.fullmatch(result["audience_hash"]):
        raise HiveSyncEnvelopeError("audience_hash_invalid")
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
        for field in ("evidence", "provenance"):
            if field not in result or result[field] is None:
                raise HiveSyncEnvelopeError("envelope_field_missing_or_invalid:" + field)
        snapshot = result.get("snapshot")
        if not isinstance(snapshot, Mapping):
            raise HiveSyncEnvelopeError("snapshot_event_requires_snapshot_object")
        for field in ("concept", "content"):
            value = snapshot.get(field)
            if not isinstance(value, str) or not value.strip():
                raise HiveSyncEnvelopeError("snapshot_concept_content_required")
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
