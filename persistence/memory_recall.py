"""Motor de recuperacion hibrida de memorias de AKIRA.

La funcion es deliberadamente independiente de FastAPI y del proveedor de embeddings:
- recibe el extractor de keywords y el generador de embeddings por inyeccion;
- mantiene la rama lexical cuando la semantica no esta disponible;
- aplica owner_scope tanto al acceso lexical como al vectorial;
- conserva la regla de que aprendizaje protegido solo entra si esta verificado/consolidado y promovido.
"""
from __future__ import annotations

import datetime as _dt


PROTECTED_MEMORY_SOURCES = frozenset(
    {"learning_candidate", "learning_engine", "learning_promoted"}
)


def _memory_recency_score(created_at):
    try:
        raw = str(created_at or "").replace("Z", "+00:00")
        dt = _dt.datetime.fromisoformat(raw)
        now = _dt.datetime.now(_dt.timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_dt.timezone.utc)
        age_days = max(
            0.0,
            (now - dt.astimezone(_dt.timezone.utc)).total_seconds() / 86400.0,
        )
        return 1.0 / (1.0 + age_days / 30.0)
    except Exception:
        return 0.0


def recall_memories(
    service,
    msg,
    limit=5,
    include_semantic=True,
    owner_scope=None,
    extract_keywords=None,
    generate_embedding=None,
    embedding_model=None,
):
    """Recupera memorias aplicando ranking hibrido y aislamiento por propietario."""
    if service is None:
        return []
    query = str(msg or "").strip()
    if not query or not callable(extract_keywords):
        return []

    keywords = extract_keywords(query)
    scored = {}

    def accept(memory, semantic_score=0.0):
        if not isinstance(memory, dict):
            return
        memory_id = memory.get("id")
        if not memory_id or memory.get("status") != "active":
            return

        source = memory.get("source")
        if source in PROTECTED_MEMORY_SOURCES:
            learning_id = memory.get("source_id")
            if not learning_id:
                return
            try:
                learning = service.get_learning(
                    learning_id,
                    owner_scope=owner_scope,
                )
            except Exception:
                learning = None
            context = (
                learning.get("learning_context")
                if isinstance(learning, dict)
                and isinstance(learning.get("learning_context"), dict)
                else {}
            )
            if (
                not learning
                or learning.get("status") not in ("verified", "consolidated")
                or not context.get("promoted")
            ):
                return

        content = str(memory.get("content") or "").lower()
        query_low = query.lower()
        exact = 1.0 if query_low and query_low in content else 0.0
        matched = sum(1 for kw in keywords if kw in content)
        keyword_score = (matched / len(keywords)) if keywords else 0.0
        lexical_score = min(1.0, 0.65 * exact + 0.35 * keyword_score)
        confidence = max(
            0.0,
            min(1.0, float(memory.get("confidence") or 0.0)),
        )
        importance = max(
            0.0,
            min(1.0, float(memory.get("importance") or 0.0) / 10.0),
        )
        recency = _memory_recency_score(memory.get("created_at"))
        semantic_score = max(
            0.0,
            min(1.0, float(semantic_score or 0.0)),
        )
        total = (
            0.55 * semantic_score
            + 0.25 * lexical_score
            + 0.10 * confidence
            + 0.05 * importance
            + 0.05 * recency
        )
        previous = scored.get(memory_id)
        if previous is None or total > previous["score"]:
            scored[memory_id] = {"memory": memory, "score": total}

    # La rama lexical permanece operativa aunque el proveedor semantico falle.
    lexical_rows = []
    for kw in keywords:
        try:
            lexical_rows.extend(
                service.search_memory(
                    {"text_contains": kw},
                    limit=max(10, limit * 4),
                    owner_scope=owner_scope,
                )
            )
        except Exception:
            continue
    try:
        lexical_rows.extend(
            service.search_memory(
                {"text_contains": query[:200]},
                limit=max(10, limit * 4),
                owner_scope=owner_scope,
            )
        )
    except Exception:
        pass

    for memory in lexical_rows:
        accept(memory, 0.0)

    # Rama semantica: el almacenamiento y filtrado vectorial se ejecutan en backend.
    if include_semantic and callable(generate_embedding):
        try:
            query_embedding = generate_embedding(query)
        except Exception as exc:
            query_embedding = None
            print(
                f"[semantic-recall] embedding fallo: "
                f"{type(exc).__name__}: {str(exc)[:160]}"
            )
        if query_embedding:
            try:
                semantic_rows = service.search_memory_semantic(
                    query_embedding,
                    embedding_model,
                    limit=max(20, limit * 6),
                    owner_scope=owner_scope,
                )
                for row in semantic_rows:
                    memory = service.get_memory(
                        row.get("memory_id"),
                        owner_scope=owner_scope,
                    )
                    accept(memory, row.get("semantic_score") or 0.0)
            except Exception as exc:
                print(
                    f"[semantic-recall] fallo: "
                    f"{type(exc).__name__}: {str(exc)[:160]}"
                )

    ranked = sorted(
        scored.values(),
        key=lambda x: (
            x["score"],
            x["memory"].get("created_at") or "",
        ),
        reverse=True,
    )
    result = [
        x["memory"]
        for x in ranked[: max(1, min(int(limit), 20))]
    ]

    # Solo contabilizamos reutilizacion de knowledge ya promovido.
    seen_learning = set()
    for memory in result:
        source = memory.get("source")
        learning_id = memory.get("source_id")
        if (
            source in PROTECTED_MEMORY_SOURCES
            and learning_id
            and learning_id not in seen_learning
        ):
            seen_learning.add(learning_id)
            try:
                learning = service.get_learning(
                    learning_id,
                    owner_scope=owner_scope,
                )
                if (
                    learning
                    and learning.get("status") in ("verified", "consolidated")
                ):
                    context = (
                        learning.get("learning_context")
                        if isinstance(learning.get("learning_context"), dict)
                        else {}
                    )
                    if context.get("promoted"):
                        service.record_reuse(
                            learning_id,
                            actor="recall",
                            owner_scope=owner_scope,
                        )
            except Exception:
                pass

    return result
