"""Autonomous, private study flow for explicit owner study requests.

The flow is intentionally narrow: it researches only an explicit topic request,
keeps unsupported work as a candidate, and promotes only evidence-backed study
notes. It does not grant permission to publish or change code or infrastructure.
"""

from __future__ import annotations

import hashlib
import math
import re
from urllib.parse import urlparse


MIN_SUPPORT_CONFIDENCE = 0.85
MIN_INDEPENDENT_DOMAINS = 2
MAX_STUDY_SOURCES = 8

_STUDY_REQUEST_RE = re.compile(
    r"^\s*(?:akira[\s,;:.-]*)?(?:"
    r"aprende\s+(?:sobre|acerca\s+de)|"
    r"estudia\s+(?:sobre|acerca\s+de)|"
    r"investiga\s+(?:sobre|acerca\s+de)|"
    r"quiero\s+que\s+aprendas\s+(?:sobre|acerca\s+de)"
    r")\s*(.*)$",
    re.IGNORECASE | re.DOTALL,
)
_STUDY_UNDO_RE = re.compile(
    r"^\s*(?:akira[\s,;:.-]*)?(?:olvida|retira|deshaz)\s+(?:el\s+)?(?:aprendizaje|estudio)\s+"
    r"(learn_[A-Za-z0-9_-]{1,120})\s*[.!]?\s*$",
    re.IGNORECASE,
)


def extract_study_topic(message):
    match = _STUDY_REQUEST_RE.match(str(message or ""))
    topic = (match.group(1) or "").strip() if match else ""
    if len(topic) < 3:
        return None, bool(match)
    return topic[:500], True


def extract_study_undo_id(message):
    match = _STUDY_UNDO_RE.match(str(message or ""))
    return match.group(1) if match else None


def _independent_domain(url):
    hostname = (urlparse(url).hostname or "").lower().rstrip(".")
    parts = [part for part in hostname.split(".") if part]
    return ".".join(parts[-2:]) if len(parts) >= 2 else hostname


def _safe_sources(sources):
    evidence = []
    domains = set()
    for source in sources or []:
        if not isinstance(source, dict):
            continue
        reference = str(source.get("reference") or "").strip()
        title = str(source.get("title") or "").strip()
        snippet = str(source.get("snippet") or "").strip()
        try:
            parsed = urlparse(reference)
            domain = _independent_domain(reference)
        except Exception:
            continue
        if (
            parsed.scheme != "https"
            or not domain
            or not title
            or len(snippet) < 40
            or snippet.casefold() == title.casefold()
        ):
            continue
        if domain in domains:
            continue
        domains.add(domain)
        evidence.append({
            "type": "web_search",
            "title": title[:200],
            "reference": reference[:500],
            "note": snippet[:1000],
        })
        if len(evidence) >= MAX_STUDY_SOURCES:
            break
    return evidence


def run_autonomous_study(
    service,
    topic,
    actor,
    owner_scope,
    search_sources,
    evaluate,
    *,
    min_confidence=MIN_SUPPORT_CONFIDENCE,
):
    """Research a requested topic and promote it only after independent support.

    `search_sources` and `evaluate` are injected so the state machine can be
    tested without network, model, or database access.
    """
    topic = str(topic or "").strip()[:500]
    if not topic:
        raise ValueError("study_topic_required")
    if not owner_scope or not str(owner_scope).strip():
        raise ValueError("owner_scope_required")

    topic_key = hashlib.sha256(
        (str(owner_scope).strip() + "\0" + topic.casefold()).encode("utf-8")
    ).hexdigest()[:32]
    learning_payload = {
        "source": "autonomous_study",
        "event": "explicit_owner_study_request",
        "lesson": f"Tema solicitado para estudio: {topic}",
        "knowledge_nodes": [],
        "relationships": [],
        "confidence": 0.0,
        "outcome": "unknown",
        "status": "candidate",
        "evidence": [],
        "learning_context": {
            "mode": "autonomous_study",
            "study_topic": topic,
            "study_state": "researching",
            "privacy_level": "PRIVATE",
            "memory_type": "semantic",
            "importance": 7,
            "tags": ["autonomous-study", "private"],
        },
    }
    base_idempotency_key = "autonomous_study_" + topic_key
    idempotency_key = base_idempotency_key
    # Keep retries idempotent while allowing a withdrawn/failed study to be
    # researched again. Each terminal record deterministically names the next
    # generation, so concurrent retries converge on the same candidate.
    for _ in range(100):
        created = service.save_learning(
            learning_payload, actor=actor, idempotency_key=idempotency_key,
            owner_scope=owner_scope,
        )
        record = created.get("record") or {}
        if not record.get("id"):
            raise RuntimeError("study_candidate_not_persisted")
        status = record.get("status") or "candidate"
        if created.get("outcome") != "already_synced" or status not in {"obsolete", "discarded"}:
            break
        idempotency_key = base_idempotency_key + "_retry_" + str(record["id"])
    else:
        raise RuntimeError("study_retry_limit_exceeded")
    learning_id = record.get("id")
    if created.get("outcome") == "already_synced" and record.get("status") == "consolidated":
        return {"learning": record, "reused": True, "promoted": True}

    sources = search_sources(topic, max_results=MAX_STUDY_SOURCES)
    evidence = _safe_sources(sources)
    if evidence:
        record = service.add_learning_evidence(
            learning_id, evidence, expected_version=record.get("version"),
            actor=actor, owner_scope=owner_scope,
        )
    domains = {_independent_domain(item["reference"]) for item in evidence}
    if len(domains) < MIN_INDEPENDENT_DOMAINS:
        context = dict(record.get("learning_context") or {})
        context.update({"study_state": "needs_more_sources", "source_count": len(evidence)})
        record = service.update_learning(
            learning_id, {"learning_context": context},
            expected_version=record.get("version"), actor=actor, owner_scope=owner_scope,
        )
        return {"learning": record, "reused": False, "promoted": False,
                "reason": "insufficient_independent_sources"}

    result = evaluate(topic, evidence)
    if not isinstance(result, dict):
        raise ValueError("study_evaluation_invalid")
    try:
        confidence = float(result.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    if not math.isfinite(confidence):
        confidence = 0.0
    verdict = str(result.get("verdict") or "insufficient").strip().lower()
    summary = str(result.get("summary") or "").strip()[:4000]
    valid_indexes = [
        index for index in (result.get("supporting_evidence") or [])
        if isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(evidence)
    ]
    supported_domains = {_independent_domain(evidence[index]["reference"]) for index in valid_indexes}
    citations_complete = bool(valid_indexes) and all(
        re.search(r"\[\s*" + str(index) + r"\s*\]", summary)
        for index in valid_indexes
    )
    supported = (
        verdict == "supported"
        and confidence >= float(min_confidence)
        and len(supported_domains) >= MIN_INDEPENDENT_DOMAINS
        and citations_complete
        and bool(summary)
    )
    analysis = {
        "verdict": verdict if verdict in {"supported", "mixed", "contradicted", "insufficient"} else "insufficient",
        "confidence": max(0.0, min(1.0, confidence)),
        "summary": summary,
        "supporting_evidence": valid_indexes,
        "contradicting_evidence": [
            index for index in (result.get("contradicting_evidence") or [])
            if isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(evidence)
        ],
        "gaps": [str(item)[:500] for item in (result.get("gaps") or [])[:20]],
        "evaluated_by": str(result.get("evaluated_by") or "autonomous_evaluator")[:128],
    }
    context = dict(record.get("learning_context") or {})
    context.update({
        "study_state": "ready_to_consolidate" if supported else "needs_review",
        "source_count": len(evidence),
        "independent_supporting_domains": len(supported_domains),
    })
    changes = {"verification_analysis": analysis, "learning_context": context}
    if supported:
        changes.update({"lesson": summary, "confidence": confidence})
    record = service.update_learning(
        learning_id, changes, expected_version=record.get("version"),
        actor=actor, owner_scope=owner_scope,
    )
    if not supported:
        return {"learning": record, "reused": False, "promoted": False,
                "reason": "evidence_not_strong_enough"}

    record = service.update_learning_status(
        learning_id, "verified", expected_version=record.get("version"),
        actor=actor, owner_scope=owner_scope,
    )
    record = service.update_learning_status(
        learning_id, "consolidated", expected_version=record.get("version"),
        actor=actor, owner_scope=owner_scope,
    )
    try:
        promoted = service.promote_learning_to_graph(
            learning_id, actor=actor, owner_scope=owner_scope,
        )
    except Exception:
        latest = service.get_learning(learning_id, owner_scope=owner_scope)
        if latest and latest.get("status") == "consolidated":
            latest = service.update_learning_status(
                learning_id, "obsolete", expected_version=latest.get("version"),
                actor=actor, owner_scope=owner_scope,
            )
        service.cleanup_learning_materialization(
            learning_id, actor=actor, owner_scope=owner_scope,
        )
        if latest:
            failed_context = dict(latest.get("learning_context") or {})
            failed_context["study_state"] = "promotion_failed_withdrawn"
            latest = service.update_learning(
                learning_id, {"learning_context": failed_context},
                expected_version=latest.get("version"), actor=actor,
                owner_scope=owner_scope,
            )
        return {"learning": latest or record, "reused": False, "promoted": False,
                "reason": "promotion_failed_withdrawn"}
    if not promoted.get("promoted"):
        context = dict(record.get("learning_context") or {})
        context["study_state"] = "consolidated_promotion_pending"
        record = service.update_learning(
            learning_id, {"learning_context": context},
            expected_version=record.get("version"), actor=actor, owner_scope=owner_scope,
        )
        return {"learning": record, "reused": False, "promoted": False,
                "reason": promoted.get("reason") or "promotion_pending"}
    return {"learning": promoted.get("learning") or record,
            "memory": promoted.get("memory"), "reused": False,
            "promoted": True, "reason": "evidence_supported"}


def undo_autonomous_study(service, learning_id, actor, owner_scope):
    """Withdraw a study result from active recall without deleting its audit trail."""
    if not owner_scope or not str(owner_scope).strip():
        raise ValueError("owner_scope_required")
    record = service.get_learning(learning_id, owner_scope=owner_scope)
    if record is None:
        raise ValueError("learning_not_found")
    context = record.get("learning_context")
    context = context if isinstance(context, dict) else {}
    if record.get("source") != "autonomous_study" or context.get("mode") != "autonomous_study":
        raise ValueError("not_autonomous_study")

    status = record.get("status") or "candidate"
    status_target = {"candidate": "discarded", "verified": "obsolete",
                     "consolidated": "obsolete"}.get(status)
    if status_target:
        record = service.update_learning_status(
            learning_id, status_target, expected_version=record.get("version"),
            actor=actor, owner_scope=owner_scope,
        )
    elif status not in {"obsolete", "discarded"}:
        raise ValueError("learning_status_not_reversible")

    current_context = dict(record.get("learning_context") or {})
    if current_context.get("study_state") != "withdrawn":
        current_context["study_state"] = "withdrawn"
        record = service.update_learning(
            learning_id, {"learning_context": current_context},
            expected_version=record.get("version"), actor=actor, owner_scope=owner_scope,
        )
    cleanup = service.cleanup_learning_materialization(
        learning_id, actor=actor, owner_scope=owner_scope,
    )
    return {"learning": record, "archived": cleanup}

