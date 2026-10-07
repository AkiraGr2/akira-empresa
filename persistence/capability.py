"""Reglas puras del Capability Engine de AKIRA.

Este modulo no persiste ni ejecuta tools. Define contratos, estados,
transiciones, validacion de evidencia y calculo de estado efectivo.
"""
from __future__ import annotations

import datetime as _dt
import json
from typing import Any, Mapping

CAPABILITY_SCHEMA_VERSION = "capability.v1"
CAPABILITY_VERIFICATION_SCHEMA_VERSION = "capability_verification.v1"

CAPABILITY_IMPLEMENTATION_STATES = (
    "not_implemented",
    "partial",
    "implemented",
    "deprecated",
)
CAPABILITY_VERIFICATION_STATES = (
    "unverified",
    "verified",
    "stale",
    "failed",
)
CAPABILITY_AVAILABILITY_STATES = (
    "available",
    "degraded",
    "blocked",
    "unavailable",
)
CAPABILITY_MATURITY_STATES = (
    "experimental",
    "stable",
)
CAPABILITY_COST_STATES = (
    "free",
    "conditional",
    "paid_required",
    "unknown",
)
CAPABILITY_KINDS = (
    "intrinsic",
    "tool_backed",
    "provider_dependent",
    "composite",
)
CAPABILITY_CATEGORIES = (
    "identity",
    "memory",
    "knowledge",
    "learning",
    "graph",
    "cognitive",
    "tooling",
    "agents",
    "missions",
    "security",
    "storage",
    "multimedia",
    "orchestration",
    "repair",
    "evolution",
    "hive",
    "external",
    "general",
)
CAPABILITY_VERIFICATION_EVENTS = (
    "verification",
    "revalidation",
    "availability_check",
    "invalidation",
)
CAPABILITY_VERIFICATION_RESULTS = (
    "pass",
    "fail",
    "inconclusive",
    "not_run",
)
CAPABILITY_EVIDENCE_TYPES = (
    "selftest",
    "integration_test",
    "e2e_test",
    "runtime_observation",
    "database_observation",
    "tool_invocation",
    "ci",
    "human_validation",
    "external_check",
)
CAPABILITY_FRESHNESS_MODES = (
    "manual",
    "on_change",
    "time_based",
)

MAX_CAPABILITY_NAME = 96
MAX_CAPABILITY_DESCRIPTION = 2000
MAX_CAPABILITY_ITEMS = 30
MAX_DEPENDENCY_ITEMS = 20
MAX_LIMITATION_ITEMS = 20
MAX_JSON_KEYS = 40
MAX_JSON_DEPTH = 5
MAX_JSON_STRING = 2000
MAX_JSON_BYTES = 16000
MAX_EVIDENCE_ITEMS = 20


class CapabilityContractError(ValueError):
    """Contrato de Capability Engine invalido."""


def _text(name: str, value: Any, maximum: int, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise CapabilityContractError(f"{name} debe ser texto")
    value = value.strip()
    if not allow_empty and not value:
        raise CapabilityContractError(f"{name} no puede estar vacio")
    if len(value) > maximum:
        raise CapabilityContractError(f"{name} supera el maximo de {maximum} caracteres")
    return value


def _choice(name: str, value: Any, choices) -> str:
    value = _text(name, value, 64)
    if value not in choices:
        raise CapabilityContractError(f"{name} invalido: {value!r}")
    return value


def _json_safe(name: str, value: Any, *, max_items: int = MAX_CAPABILITY_ITEMS,
               max_bytes: int = MAX_JSON_BYTES) -> Any:
    def walk(node: Any, depth: int) -> Any:
        if depth > MAX_JSON_DEPTH:
            raise CapabilityContractError(f"{name} supera la profundidad maxima")
        if node is None or isinstance(node, (bool, int)):
            return node
        if isinstance(node, float):
            if not __import__("math").isfinite(node):
                raise CapabilityContractError(f"{name} contiene un numero no finito")
            return node
        if isinstance(node, str):
            if len(node) > MAX_JSON_STRING:
                raise CapabilityContractError(f"{name} contiene texto demasiado largo")
            return node
        if isinstance(node, list):
            if len(node) > max_items:
                raise CapabilityContractError(f"{name} supera {max_items} elementos")
            return [walk(item, depth + 1) for item in node]
        if isinstance(node, Mapping):
            if len(node) > MAX_JSON_KEYS:
                raise CapabilityContractError(f"{name} supera {MAX_JSON_KEYS} claves")
            out = {}
            for key, item in node.items():
                key = _text(f"{name}.key", str(key), 128)
                out[key] = walk(item, depth + 1)
            return out
        raise CapabilityContractError(f"{name} contiene un tipo no permitido")

    cleaned = walk(value, 0)
    try:
        encoded = json.dumps(cleaned, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CapabilityContractError(f"{name} no es JSON valido") from exc
    if len(encoded) > max_bytes:
        raise CapabilityContractError(f"{name} supera {max_bytes} bytes")
    return cleaned


def _evidence(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise CapabilityContractError("evidence debe ser una lista")
    if len(value) > MAX_EVIDENCE_ITEMS:
        raise CapabilityContractError(f"evidence admite maximo {MAX_EVIDENCE_ITEMS} elementos")
    out = []
    allowed = {"type", "title", "reference", "summary", "hash"}
    for item in value:
        if not isinstance(item, Mapping):
            raise CapabilityContractError("cada evidence debe ser un objeto")
        extra = sorted(set(item) - allowed)
        if extra:
            raise CapabilityContractError(f"campos de evidence no permitidos: {extra}")
        etype = _choice("evidence.type", item.get("type", "unknown"), CAPABILITY_EVIDENCE_TYPES)
        title = _text("evidence.title", item.get("title", ""), 200)
        reference = _text("evidence.reference", item.get("reference", ""), 500)
        summary = _text("evidence.summary", item.get("summary", ""), 1500, allow_empty=True)
        digest = _text("evidence.hash", item.get("hash", ""), 128, allow_empty=True)
        out.append({
            "type": etype,
            "title": title,
            "reference": reference,
            "summary": summary,
            "hash": digest,
        })
    return out


def validate_freshness_policy(policy: Any) -> dict:
    if not isinstance(policy, Mapping):
        raise CapabilityContractError("freshness_policy debe ser un objeto")
    allowed = {"mode", "max_age_seconds", "invalidate_on"}
    extra = sorted(set(policy) - allowed)
    if extra:
        raise CapabilityContractError(f"freshness_policy contiene campos no permitidos: {extra}")
    mode = _choice("freshness_policy.mode", policy.get("mode", "on_change"), CAPABILITY_FRESHNESS_MODES)
    max_age = policy.get("max_age_seconds")
    if max_age is not None:
        if isinstance(max_age, bool) or not isinstance(max_age, int) or max_age <= 0:
            raise CapabilityContractError("max_age_seconds debe ser entero > 0 o None")
    if mode == "time_based" and max_age is None:
        raise CapabilityContractError("time_based requiere max_age_seconds")
    if mode != "time_based" and max_age is not None:
        raise CapabilityContractError("max_age_seconds solo aplica a time_based")
    invalidate_on = policy.get("invalidate_on", [])
    if not isinstance(invalidate_on, list) or len(invalidate_on) > 20:
        raise CapabilityContractError("invalidate_on debe ser una lista de maximo 20 elementos")
    invalidate_on = [_text("freshness_policy.invalidate_on", x, 64) for x in invalidate_on]
    return {"mode": mode, "max_age_seconds": max_age, "invalidate_on": invalidate_on}


def validate_verification_spec(spec: Any) -> dict:
    """Valida el contrato mínimo que explica cómo una capability puede demostrarse."""
    if not isinstance(spec, Mapping):
        raise CapabilityContractError("verification_spec debe ser un objeto")
    allowed = {"method", "test_key", "freshness_policy"}
    extra = sorted(set(spec) - allowed)
    if extra:
        raise CapabilityContractError(f"verification_spec contiene campos no permitidos: {extra}")
    method = _text("verification_spec.method", spec.get("method", ""), 96)
    test_key = _text("verification_spec.test_key", spec.get("test_key", ""), 128)
    freshness = spec.get("freshness_policy")
    if freshness is None:
        raise CapabilityContractError("verification_spec.freshness_policy es obligatorio")
    normalized = validate_freshness_policy(freshness)
    return {"method": method, "test_key": test_key, "freshness_policy": normalized}


def capability_state_snapshot(record: Mapping[str, Any]) -> dict:
    return {
        "implementation_state": record.get("implementation_state"),
        "verification_state": record.get("verification_state"),
        "availability_state": record.get("availability_state"),
        "maturity": record.get("maturity"),
        "cost_compatibility": record.get("cost_compatibility"),
    }


def validate_capability_state(state: Mapping[str, Any]) -> dict:
    if not isinstance(state, Mapping):
        raise CapabilityContractError("capability state debe ser un objeto")
    required = (
        "implementation_state",
        "verification_state",
        "availability_state",
        "maturity",
        "cost_compatibility",
    )
    extra = sorted(set(state) - set(required))
    if extra:
        raise CapabilityContractError(f"state contiene campos no permitidos: {extra}")
    normalized = {
        "implementation_state": _choice("implementation_state", state.get("implementation_state"), CAPABILITY_IMPLEMENTATION_STATES),
        "verification_state": _choice("verification_state", state.get("verification_state"), CAPABILITY_VERIFICATION_STATES),
        "availability_state": _choice("availability_state", state.get("availability_state"), CAPABILITY_AVAILABILITY_STATES),
        "maturity": _choice("maturity", state.get("maturity"), CAPABILITY_MATURITY_STATES),
        "cost_compatibility": _choice("cost_compatibility", state.get("cost_compatibility"), CAPABILITY_COST_STATES),
    }
    if normalized["implementation_state"] == "not_implemented":
        if normalized["verification_state"] == "verified":
            raise CapabilityContractError("not_implemented no puede estar verified")
        if normalized["availability_state"] == "available":
            raise CapabilityContractError("not_implemented no puede estar available")
    if normalized["maturity"] == "stable" and normalized["implementation_state"] == "not_implemented":
        raise CapabilityContractError("not_implemented no puede ser stable")
    return normalized


def validate_capability(data: Mapping[str, Any], partial: bool = False) -> dict:
    if not isinstance(data, Mapping):
        raise CapabilityContractError("capability debe ser un objeto")
    allowed = {
        "name", "description", "category", "kind",
        "implementation_state", "verification_state", "availability_state",
        "maturity", "cost_compatibility",
        "dependencies", "limitations", "verification_spec", "provenance",
    }
    extra = sorted(set(data) - allowed)
    if extra:
        raise CapabilityContractError(f"campos no permitidos: {extra}")
    if not partial:
        for req in ("name", "description"):
            if req not in data:
                raise CapabilityContractError(f"falta el campo obligatorio {req}")
    if partial and not data:
        raise CapabilityContractError("no hay cambios")

    out = {}
    if "name" in data:
        name = _text("name", data["name"], MAX_CAPABILITY_NAME)
        if not all(c.isalnum() or c in "_-" for c in name):
            raise CapabilityContractError("name solo admite letras, numeros, guion y guion bajo")
        out["name"] = name
    if "description" in data:
        out["description"] = _text("description", data["description"], MAX_CAPABILITY_DESCRIPTION)
    if "category" in data or not partial:
        out["category"] = _choice("category", data.get("category", "general"), CAPABILITY_CATEGORIES)
    if "kind" in data or not partial:
        out["kind"] = _choice("kind", data.get("kind", "composite"), CAPABILITY_KINDS)
    if "implementation_state" in data or not partial:
        out["implementation_state"] = _choice(
            "implementation_state", data.get("implementation_state", "not_implemented"),
            CAPABILITY_IMPLEMENTATION_STATES,
        )
    if "verification_state" in data or not partial:
        out["verification_state"] = _choice(
            "verification_state", data.get("verification_state", "unverified"),
            CAPABILITY_VERIFICATION_STATES,
        )
    if "availability_state" in data or not partial:
        out["availability_state"] = _choice(
            "availability_state", data.get("availability_state", "unavailable"),
            CAPABILITY_AVAILABILITY_STATES,
        )
    if "maturity" in data or not partial:
        out["maturity"] = _choice("maturity", data.get("maturity", "experimental"), CAPABILITY_MATURITY_STATES)
    if "cost_compatibility" in data or not partial:
        out["cost_compatibility"] = _choice(
            "cost_compatibility", data.get("cost_compatibility", "unknown"),
            CAPABILITY_COST_STATES,
        )
    if "dependencies" in data or not partial:
        out["dependencies"] = _json_safe(
            "dependencies", data.get("dependencies", []), max_items=MAX_DEPENDENCY_ITEMS
        )
        if not isinstance(out["dependencies"], list):
            raise CapabilityContractError("dependencies debe ser una lista")
    if "limitations" in data or not partial:
        out["limitations"] = _json_safe(
            "limitations", data.get("limitations", []), max_items=MAX_LIMITATION_ITEMS
        )
        if not isinstance(out["limitations"], list):
            raise CapabilityContractError("limitations debe ser una lista")
    if "verification_spec" in data or not partial:
        out["verification_spec"] = _json_safe(
            "verification_spec", data.get("verification_spec", {
                "method": "selftest",
                "test_key": "not_defined",
                "freshness_policy": {"mode": "on_change", "max_age_seconds": None, "invalidate_on": []},
            })
        )
        if not isinstance(out["verification_spec"], Mapping):
            raise CapabilityContractError("verification_spec debe ser un objeto")
        out["verification_spec"] = validate_verification_spec(out["verification_spec"])
    if "provenance" in data or not partial:
        out["provenance"] = _json_safe(
            "provenance", data.get("provenance", {"source": "system", "created_by": "system"})
        )
        if not isinstance(out["provenance"], Mapping):
            raise CapabilityContractError("provenance debe ser un objeto")
    state = {
        "implementation_state": out.get("implementation_state", data.get("implementation_state")),
        "verification_state": out.get("verification_state", data.get("verification_state")),
        "availability_state": out.get("availability_state", data.get("availability_state")),
        "maturity": out.get("maturity", data.get("maturity")),
        "cost_compatibility": out.get("cost_compatibility", data.get("cost_compatibility")),
    }
    if all(value is not None for value in state.values()):
        validate_capability_state(state)
    return out


def validate_capability_verification(data: Mapping[str, Any], partial: bool = False) -> dict:
    if partial:
        raise CapabilityContractError("capability_verifications es append-only")
    if not isinstance(data, Mapping):
        raise CapabilityContractError("verification debe ser un objeto")
    allowed = {
        "event_type", "test_key", "test_version", "result", "evidence",
        "environment", "dependency_snapshot", "runtime_version", "build_ref",
        "actor", "executor", "evaluator", "started_at", "finished_at",
        "error", "observed_availability_state",
    }
    extra = sorted(set(data) - allowed)
    if extra:
        raise CapabilityContractError(f"verification contiene campos no permitidos: {extra}")
    event_type = _choice("event_type", data.get("event_type", "verification"), CAPABILITY_VERIFICATION_EVENTS)
    test_key = _text("test_key", data.get("test_key", ""), 128)
    test_version = _text("test_version", data.get("test_version", "v1"), 64)
    result = _choice("result", data.get("result", "not_run"), CAPABILITY_VERIFICATION_RESULTS)
    evidence = _evidence(data.get("evidence", []))
    if result in ("pass", "fail") and not evidence:
        raise CapabilityContractError("pass/fail requiere evidencia")
    environment = _json_safe("environment", data.get("environment", {}), max_items=20)
    dependency_snapshot = _json_safe(
        "dependency_snapshot", data.get("dependency_snapshot", []), max_items=30
    )
    runtime_version = _text("runtime_version", data.get("runtime_version", "unknown"), 96)
    build_ref = _text("build_ref", data.get("build_ref", "unknown"), 160)
    actor = _text("actor", data.get("actor", "system"), 200)
    executor = _text("executor", data.get("executor", "system"), 200)
    evaluator = _text("evaluator", data.get("evaluator", "system"), 200)
    now_iso = _dt.datetime.now(_dt.timezone.utc).isoformat()
    started_at = _text("started_at", data.get("started_at", now_iso), 80)
    finished_at = _text("finished_at", data.get("finished_at", now_iso), 80)
    started_dt = _parse_iso(started_at)
    finished_dt = _parse_iso(finished_at)
    if started_dt is None or finished_dt is None:
        raise CapabilityContractError("started_at y finished_at deben ser timestamps ISO validos")
    if finished_dt < started_dt:
        raise CapabilityContractError("finished_at no puede ser anterior a started_at")
    error = data.get("error")
    if error is not None:
        error = _json_safe("error", error, max_items=20)
        if not isinstance(error, Mapping):
            raise CapabilityContractError("error debe ser un objeto")
    observed = data.get("observed_availability_state")
    if observed is not None:
        observed = _choice(
            "observed_availability_state", observed, CAPABILITY_AVAILABILITY_STATES
        )
    return {
        "event_type": event_type,
        "test_key": test_key,
        "test_version": test_version,
        "result": result,
        "evidence": evidence,
        "environment": environment,
        "dependency_snapshot": dependency_snapshot,
        "runtime_version": runtime_version,
        "build_ref": build_ref,
        "actor": actor,
        "executor": executor,
        "evaluator": evaluator,
        "started_at": started_at,
        "finished_at": finished_at,
        "error": error,
        "observed_availability_state": observed,
    }


def validate_verification_result_for_event(event_type: str, result: str, evidence: list) -> None:
    event_type = _choice("event_type", event_type, CAPABILITY_VERIFICATION_EVENTS)
    result = _choice("result", result, CAPABILITY_VERIFICATION_RESULTS)
    if event_type == "availability_check" and result == "pass" and not evidence:
        raise CapabilityContractError("availability_check pass requiere evidencia")
    if event_type == "invalidation" and result not in ("fail", "inconclusive"):
        raise CapabilityContractError("invalidation requiere fail o inconclusive")



_STATE_TRANSITIONS = {
    "implementation_state": {
        "not_implemented": {"partial", "implemented"},
        "partial": {"implemented", "deprecated"},
        "implemented": {"partial", "deprecated"},
        "deprecated": {"partial", "implemented"},
    },
    "verification_state": {
        "unverified": {"verified", "failed"},
        "verified": {"stale", "failed"},
        "stale": {"verified", "failed"},
        "failed": {"verified", "stale"},
    },
    "availability_state": {
        "available": {"degraded", "blocked", "unavailable"},
        "degraded": {"available", "blocked", "unavailable"},
        "blocked": {"available", "degraded", "unavailable"},
        "unavailable": {"available", "degraded", "blocked"},
    },
    "maturity": {
        "experimental": {"stable"},
        "stable": {"experimental"},
    },
    "cost_compatibility": {
        "free": {"conditional", "paid_required", "unknown"},
        "conditional": {"free", "paid_required", "unknown"},
        "paid_required": {"free", "conditional", "unknown"},
        "unknown": {"free", "conditional", "paid_required"},
    },
}


def validate_capability_transition(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict:
    before_state = validate_capability_state(before)
    after_state = validate_capability_state(after)
    for field, allowed in _STATE_TRANSITIONS.items():
        previous = before_state[field]
        current = after_state[field]
        if previous == current:
            continue
        if current not in allowed.get(previous, set()):
            raise CapabilityContractError(
                f"transicion no permitida en {field}: {previous} -> {current}"
            )
    return after_state


def _parse_iso(value: Any):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def effective_verification_state(record: Mapping[str, Any], now=None) -> str:
    state = validate_capability_state(capability_state_snapshot(record))
    if state["verification_state"] != "verified":
        return state["verification_state"]
    spec = record.get("verification_spec")
    if not isinstance(spec, Mapping):
        return state["verification_state"]
    policy = spec.get("freshness_policy")
    if not isinstance(policy, Mapping):
        return state["verification_state"]
    try:
        policy = validate_freshness_policy(policy)
    except CapabilityContractError:
        return "stale"
    if policy["mode"] != "time_based":
        return state["verification_state"]
    max_age = policy["max_age_seconds"]
    verified_at = _parse_iso(record.get("last_verified_at"))
    if max_age is None or verified_at is None:
        return "stale"
    current = now or _dt.datetime.now(_dt.timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=_dt.timezone.utc)
    return "stale" if (current - verified_at).total_seconds() > max_age else "verified"


def apply_verification_result(current: Mapping[str, Any], event: Mapping[str, Any]) -> dict:
    before = validate_capability_state(capability_state_snapshot(current))
    event_type = _choice("event_type", event.get("event_type"), CAPABILITY_VERIFICATION_EVENTS)
    result = _choice("result", event.get("result"), CAPABILITY_VERIFICATION_RESULTS)
    evidence = event.get("evidence") or []
    validate_verification_result_for_event(event_type, result, evidence)

    after = dict(before)
    if event_type in ("verification", "revalidation"):
        if result == "pass":
            after["verification_state"] = "verified"
        elif result == "fail":
            after["verification_state"] = "failed"
        elif result == "inconclusive" and before["verification_state"] == "verified":
            after["verification_state"] = "stale"
    elif event_type == "invalidation":
        if before["verification_state"] != "unverified":
            after["verification_state"] = "stale"
        else:
            raise CapabilityContractError("una capability unverified no puede invalidarse como stale")
    elif event_type == "availability_check":
        observed = event.get("observed_availability_state")
        if observed is None:
            raise CapabilityContractError("availability_check requiere observed_availability_state")
        after["availability_state"] = _choice(
            "observed_availability_state", observed, CAPABILITY_AVAILABILITY_STATES
        )

    validate_capability_state(after)
    validate_capability_transition(before, after)
    return after


def derive_effective_state(record: Mapping[str, Any]) -> str:
    state = validate_capability_state(capability_state_snapshot(record))
    impl = state["implementation_state"]
    verification = effective_verification_state(record)
    availability = state["availability_state"]

    if impl == "deprecated":
        return "deprecated"
    if impl == "not_implemented":
        return "not_implemented"
    if verification == "failed":
        return "failed"
    if verification == "stale":
        return "stale"
    if impl == "partial":
        if verification == "verified" and availability == "available":
            return "partial_verified"
        return "partial"
    if verification == "verified":
        if availability == "available":
            return "verified"
        if availability == "degraded":
            return "verified_degraded"
        return "verified_unavailable"
    if availability == "available":
        return "implemented_unverified_available"
    if availability == "degraded":
        return "implemented_unverified_degraded"
    if availability == "blocked":
        return "blocked"
    return "unavailable"
