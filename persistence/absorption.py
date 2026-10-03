"""Contrato y validación del motor de absorción autónoma de Akira.

Este módulo define SOLO el contrato de decisión. No persiste memoria,
no crea nodos y no decide por sí mismo qué debe aprender Akira.
La integración con chat y el Learning Engine se hará en fases posteriores.

Regla fundamental:
    conversación != memoria

Una decisión distinta de CANDIDATE/UPDATE/REINFORCE/CONFLICT no debe
materializar conocimiento por este contrato.
"""

from __future__ import annotations

from typing import Any, Mapping


ABSORPTION_DECISIONS = (
    "IGNORE",
    "CANDIDATE",
    "REINFORCE",
    "UPDATE",
    "CONFLICT",
)

ABSORPTION_KINDS = (
    "semantic",
    "procedural",
    "user_context",
    "preference",
    "experience",
    "unknown",
)

# Decisiones que pueden justificar una futura entrada al Learning Engine.
# La materialización real NO ocurre aquí.
ABSORPTION_LEARNING_DECISIONS = frozenset(
    {"CANDIDATE", "REINFORCE", "UPDATE", "CONFLICT"}
)

MAX_REASON_LENGTH = 1000
MAX_VALUE_LENGTH = 5000
MAX_EVIDENCE_ITEMS = 20


class AbsorptionContractError(ValueError):
    """Payload de decisión autónoma inválido."""


def validate_absorption_target(target_learning_id: str, allowed_target_ids) -> str:
    """Valida que el objetivo provenga de la lista explícitamente presentada al decisor."""
    target = _text("target_learning_id", target_learning_id, 256)
    allowed = {
        str(value).strip()
        for value in (allowed_target_ids or [])
        if str(value).strip()
    }
    if target not in allowed:
        raise AbsorptionContractError(
            "target_learning_id no pertenece a los objetivos elegibles presentados por el servidor"
        )
    return target


def _text(name: str, value: Any, maximum: int, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise AbsorptionContractError(f"{name} debe ser texto")
    value = value.strip()
    if not allow_empty and not value:
        raise AbsorptionContractError(f"{name} no puede estar vacío")
    if len(value) > maximum:
        raise AbsorptionContractError(f"{name} supera el máximo de {maximum} caracteres")
    return value


def _confidence(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AbsorptionContractError("confidence debe ser numérico")
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise AbsorptionContractError("confidence debe estar entre 0 y 1")
    return value


def _score(name: str, value: Any) -> float:
    return _confidence(value)


def _evidence(value: Any) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise AbsorptionContractError("evidence debe ser una lista")
    if len(value) > MAX_EVIDENCE_ITEMS:
        raise AbsorptionContractError(
            f"evidence admite máximo {MAX_EVIDENCE_ITEMS} elementos"
        )

    out: list[dict[str, str]] = []
    allowed = {"type", "title", "reference", "note"}
    for item in value:
        if not isinstance(item, Mapping):
            raise AbsorptionContractError("cada evidence debe ser un objeto")
        extra = sorted(set(item) - allowed)
        if extra:
            raise AbsorptionContractError(
                f"campos de evidence no permitidos: {extra}"
            )
        title = _text("evidence.title", item.get("title", ""), 200)
        reference = _text("evidence.reference", item.get("reference", ""), 500)
        out.append(
            {
                "type": _text(
                    "evidence.type", item.get("type", "unknown"), 32
                ),
                "title": title,
                "reference": reference,
                "note": _text(
                    "evidence.note", item.get("note", ""), 1000, allow_empty=True
                ),
            }
        )
    return out


def validate_absorption_decision(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Valida el contrato que producirá el decisor autónomo.

    Importante: esta función es deliberadamente pura. No escribe memoria,
    no crea candidatos y no modifica el grafo.
    """
    if not isinstance(payload, Mapping):
        raise AbsorptionContractError("la decisión debe ser un objeto")

    allowed = {
        "decision",
        "knowledge_kind",
        "value",
        "reason",
        "confidence",
        "novelty",
        "reusability",
        "evidence",
        "source",
        "source_id",
        "target_learning_id",
        "safe_for_recall",
    }
    extra = sorted(set(payload) - allowed)
    if extra:
        raise AbsorptionContractError(f"campos no permitidos: {extra}")

    decision = _text("decision", payload.get("decision"), 32)
    if decision not in ABSORPTION_DECISIONS:
        raise AbsorptionContractError(
            f"decision inválida: {decision!r}"
        )

    kind = _text("knowledge_kind", payload.get("knowledge_kind", "unknown"), 32)
    if kind not in ABSORPTION_KINDS:
        raise AbsorptionContractError(
            f"knowledge_kind inválido: {kind!r}"
        )

    value = _text(
        "value",
        payload.get("value", ""),
        MAX_VALUE_LENGTH,
        allow_empty=(decision == "IGNORE"),
    )
    reason = _text("reason", payload.get("reason", ""), MAX_REASON_LENGTH)
    confidence = _confidence(payload.get("confidence", 0.0))
    novelty = _score("novelty", payload.get("novelty", 0.0))
    reusability = _score("reusability", payload.get("reusability", 0.0))
    source = _text("source", payload.get("source", "chat"), 64)
    source_id = _text(
        "source_id", payload.get("source_id", ""), 256, allow_empty=True
    )
    target_learning_id = _text(
        "target_learning_id",
        payload.get("target_learning_id", ""),
        256,
        allow_empty=True,
    )
    if decision in ("REINFORCE", "UPDATE", "CONFLICT") and not target_learning_id:
        raise AbsorptionContractError(
            f"{decision} requiere target_learning_id"
        )
    if decision in ("IGNORE", "CANDIDATE") and target_learning_id:
        raise AbsorptionContractError(
            f"{decision} no debe declarar target_learning_id"
        )
    evidence = _evidence(payload.get("evidence", []))

    safe_for_recall = payload.get("safe_for_recall", False)
    if not isinstance(safe_for_recall, bool):
        raise AbsorptionContractError("safe_for_recall debe ser booleano")

    # Regla dura: el decisor nunca puede saltarse el estado de verificación.
    # Aunque un modelo entregue true, la decisión autónoma inicial no puede
    # marcar una entrada como directamente recuperable.
    if safe_for_recall:
        raise AbsorptionContractError(
            "safe_for_recall debe ser false durante la decisión de absorción"
        )

    # IGNORE no puede transportar conocimiento que luego se materialice.
    if decision == "IGNORE" and evidence:
        raise AbsorptionContractError(
            "IGNORE no debe transportar evidencia de materialización"
        )

    return {
        "decision": decision,
        "knowledge_kind": kind,
        "value": value,
        "reason": reason,
        "confidence": confidence,
        "novelty": novelty,
        "reusability": reusability,
        "evidence": evidence,
        "source": source,
        "source_id": source_id,
        "target_learning_id": target_learning_id,
        "safe_for_recall": False,
    }
