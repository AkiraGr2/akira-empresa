"""PersistenceService: unica puerta de entrada para guardar y recuperar estado de AKIRA (Fase 4).

Secuencia de toda escritura importante: VALIDATE -> WRITE -> COMMIT -> VERIFY -> RETURN SUCCESS.
Si algo falla se lanza una excepcion: nunca se devuelve exito ("guardado") sobre una escritura no confirmada.

V8-Fase5: self-model persistente (singleton con id="akira_primary").
V8-Fase6: learning_events, graph_nodes, graph_edges.
V8-Fase7: cognitive_cycles y cognitive_events (append-only).
V8-Fase8: tools y tool_invocations (log append-only).
"""
from __future__ import annotations

import datetime as _dt

from .core import (COGNITIVE_CYCLE_SCHEMA_VERSION, COGNITIVE_EVENT_SCHEMA_VERSION,
                   COGNITIVE_STAGES, GRAPH_EDGE_SCHEMA_VERSION, GRAPH_NODE_SCHEMA_VERSION,
                   HIVE_VISIBLE, LEARNING_SCHEMA_VERSION, MEMORY_SCHEMA_VERSION,
                   SELF_MODEL_PRIMARY_ID, SELF_MODEL_SCHEMA_VERSION, TOOL_INVOCATION_SCHEMA_VERSION,
                   TOOL_SCHEMA_VERSION, ConflictError, NotFoundError, PersistenceError,
                   StorageError, ValidationError, VerificationError, new_id,
                   validate_cognitive_cycle, validate_cognitive_event, validate_graph_edge,
                   validate_graph_node, validate_learning_event, validate_memory,
                   validate_self_model, validate_tool, validate_tool_invocation)

_COMPARE_FIELDS = ("content", "memory_type", "importance", "confidence", "tags", "privacy_level",
                   "source", "owner_scope")

_SELF_MODEL_DEFAULTS = {
    "identity": {
        "name": "Akira",
        "version": "V7.3",
        "creator": "Jhon Grimm",
        "language": "es-CO",
        "essence": "Colmena cognitiva personal. Persistente, verificable, honesta sobre sus capacidades.",
    },
    "purpose": {
        "primary": "Asistir a Jhon Grimm como colmena cognitiva persistente.",
        "derived": [
            "recordar de verdad",
            "recuperar sin inventar",
            "aprender de la experiencia",
            "no aparentar mas capacidad de la real",
        ],
    },
    "capabilities": [
        {"name": "chat", "status": "verified"},
        {"name": "streaming", "status": "verified"},
        {"name": "persistent_memory", "status": "verified"},
        {"name": "memory_recall", "status": "verified"},
        {"name": "session_auth", "status": "verified"},
        {"name": "identity_filter", "status": "verified"},
        {"name": "pdf_extraction", "status": "verified"},
        {"name": "voice_dictation", "status": "verified"},
        {"name": "image_generation", "status": "verified"},
        {"name": "file_creation", "status": "verified"},
        {"name": "multi_key_pool", "status": "verified"},
        {"name": "non_blocking_chat", "status": "verified"},
        {"name": "self_model_persistent", "status": "verified"},
        {"name": "learning_persistent", "status": "verified"},
        {"name": "graph_persistent", "status": "verified"},
        {"name": "cognitive_cycle_persistent", "status": "verified"},
        {"name": "tool_registry", "status": "verified"},
        {"name": "agents", "status": "not_implemented"},
        {"name": "missions", "status": "not_implemented"},
        {"name": "self_repair_full", "status": "not_implemented"},
        {"name": "evolution_engine", "status": "not_implemented"},
        {"name": "hive", "status": "not_implemented"},
        {"name": "knowledge_graph_full", "status": "not_implemented"},
    ],
    "tools": [
        {"name": "postgres", "role": "persistencia", "status": "verified"},
        {"name": "gemini", "role": "inferencia_primaria", "status": "verified"},
        {"name": "groq", "role": "inferencia_fallback", "status": "verified"},
        {"name": "google_auth", "role": "identidad", "status": "verified"},
        {"name": "pymupdf", "role": "pdf", "status": "verified"},
        {"name": "pollinations", "role": "imagen", "status": "verified"},
        {"name": "tool_registry", "role": "herramientas", "status": "verified"},
        {"name": "r2", "role": "almacenamiento", "status": "partial"},
    ],
    "models": [
        {"provider": "gemini", "model": "gemini-3.8-flash", "role": "primario"},
        {"provider": "groq", "model": "openai/gpt-oss-120b", "role": "fallback"},
    ],
    "current_state": {},
    "knowledge_state": {},
    "uncertainties": [
        "No hay pruebas de conciencia subjetiva.",
        "La calidad de las respuestas depende del proveedor externo.",
        "El grafo neuronal completo todavia no existe.",
        "Los agentes y misiones todavia no existen.",
        "R2 tiene arquitectura preparada pero sin escritura real verificada.",
    ],
    "errors": [],
    "repairs": [],
    "evolution": [],
}


def _now_iso():
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


class PersistenceService:
    def __init__(self, repo):
        self.repo = repo

    # ------------------------------------------------------------ auditoria
    def record_audit(self, actor, action, resource, resource_id=None, status="success", detail=None):
        self.repo.append_audit({"actor": actor, "action": action, "resource": resource,
                                "resource_id": resource_id, "status": status, "detail": detail or {}})

    def _audit_failure_generic(self, actor, action, resource, resource_id, error):
        try:
            self.record_audit(actor, action, resource, resource_id, "failure",
                              {"error_type": type(error).__name__})
        except Exception:
            pass

    def recent_audit(self, actor=None, action_prefix=None, limit=20):
        return self.repo.audit_search(actor=actor, action_prefix=action_prefix, limit=limit)

    # ------------------------------------------------------------ memoria
    def save_memory(self, data, actor="system", idempotency_key=None):
        fields = validate_memory(data)
        if "created_by" not in fields:
            fields["created_by"] = actor
        record = dict(fields, id=new_id("mem"), status="active", schema_version=MEMORY_SCHEMA_VERSION)
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str) or not 0 < len(idempotency_key.strip()) <= 200:
                raise ValidationError("idempotency_key debe ser texto de 1 a 200 caracteres")
            record["idempotency_key"] = idempotency_key.strip()

        try:
            with self.repo.transaction() as tx:
                stored, created = tx.create("memories", record)
                tx.append_audit({
                    "actor": actor,
                    "action": "memory.create" if created else "memory.create.already_synced",
                    "resource": "memories", "resource_id": stored["id"], "status": "success",
                    "detail": {"privacy_level": stored["privacy_level"], "memory_type": stored["memory_type"]},
                })
        except PersistenceError as e:
            self._audit_failure_generic(actor, "memory.create", "memories", None, e)
            raise
        except Exception as e:
            self._audit_failure_generic(actor, "memory.create", "memories", None, e)
            raise StorageError(type(e).__name__) from e

        verified = self.repo.get("memories", stored["id"])
        if verified is None:
            raise VerificationError("escritura no confirmada: el registro no se puede releer")
        expected = stored if not created else fields
        for f in _COMPARE_FIELDS:
            if verified.get(f) != expected.get(f, verified.get(f)):
                raise VerificationError(f"escritura no confirmada: el campo {f} no coincide al releer")
        result = {"outcome": "created" if created else "already_synced", "record": verified}
        if not created:
            result["matches_request"] = all(verified.get(f) == fields.get(f) for f in fields if f in verified)
        return result

    def get_memory(self, memory_id):
        return self.repo.get("memories", memory_id)

    def exists_memory(self, memory_id):
        return self.repo.exists("memories", memory_id)

    def update_memory(self, memory_id, changes, expected_version, actor="system"):
        clean = validate_memory(changes, partial=True)
        return self._update(memory_id, clean, expected_version, actor, "memory.update")

    def archive_memory(self, memory_id, expected_version=None, actor="system"):
        if expected_version is None:
            current = self.repo.get("memories", memory_id)
            if current is None:
                raise NotFoundError(memory_id)
            expected_version = current["version"]
        return self._update(memory_id, {"status": "archived"}, expected_version, actor, "memory.archive")

    def _update(self, memory_id, changes, expected_version, actor, action):
        if isinstance(expected_version, bool) or not isinstance(expected_version, int) or expected_version < 1:
            raise ValidationError("expected_version debe ser un entero >= 1")
        try:
            with self.repo.transaction() as tx:
                updated = tx.update("memories", memory_id, changes, expected_version)
                tx.append_audit({"actor": actor, "action": action, "resource": "memories",
                                 "resource_id": memory_id, "status": "success",
                                 "detail": {"fields": sorted(changes), "new_version": updated["version"]}})
        except PersistenceError as e:
            self._audit_failure_generic(actor, action, "memories", memory_id, e)
            raise
        except Exception as e:
            self._audit_failure_generic(actor, action, "memories", memory_id, e)
            raise StorageError(type(e).__name__) from e
        verified = self.repo.get("memories", memory_id)
        if (verified is None or verified["version"] != expected_version + 1
                or any(verified.get(k) != v for k, v in changes.items())):
            raise VerificationError("actualizacion no confirmada al releer")
        return verified

    def _memory_filters(self, filters, hive):
        f = dict(filters or {})
        if "status" not in f and "status__in" not in f:
            f["status"] = "active"
        if hive:
            f.pop("privacy_level", None)
            f["privacy_level__in"] = list(HIVE_VISIBLE)
        return f

    def search_memory(self, filters=None, hive=False, limit=50, offset=0, order_by="created_at", descending=True):
        limit = max(1, min(int(limit), 200))
        return self.repo.search("memories", self._memory_filters(filters, hive), limit=limit,
                                offset=max(0, int(offset)), order_by=order_by, descending=descending)

    def count_memory(self, filters=None, hive=False):
        return self.repo.count("memories", self._memory_filters(filters, hive))

    def health(self):
        return self.repo.ping()

    # ------------------------------------------------------------ self-model
    def get_self_model(self):
        current = self.repo.get("self_model", SELF_MODEL_PRIMARY_ID)
        if current is not None:
            return current
        record = {
            "id": SELF_MODEL_PRIMARY_ID,
            "schema_version": SELF_MODEL_SCHEMA_VERSION,
            "idempotency_key": f"{SELF_MODEL_PRIMARY_ID}_v1",
        }
        for field, value in _SELF_MODEL_DEFAULTS.items():
            record[field] = value
        try:
            with self.repo.transaction() as tx:
                stored, created = tx.create("self_model", record)
                tx.append_audit({
                    "actor": "system", "action": "self_model.create" if created else "self_model.create.already_exists",
                    "resource": "self_model", "resource_id": stored["id"], "status": "success",
                    "detail": {"created": created, "schema_version": SELF_MODEL_SCHEMA_VERSION},
                })
        except PersistenceError:
            raise
        except Exception as e:
            raise StorageError(type(e).__name__) from e
        verified = self.repo.get("self_model", SELF_MODEL_PRIMARY_ID)
        if verified is None:
            raise VerificationError("self-model no confirmado: no se puede releer tras crearlo")
        return verified

    def update_self_model(self, changes, expected_version, actor="system"):
        clean = validate_self_model(changes, partial=True)
        if isinstance(expected_version, bool) or not isinstance(expected_version, int) or expected_version < 1:
            raise ValidationError("expected_version debe ser un entero >= 1")
        try:
            with self.repo.transaction() as tx:
                updated = tx.update("self_model", SELF_MODEL_PRIMARY_ID, clean, expected_version)
                tx.append_audit({
                    "actor": actor, "action": "self_model.update", "resource": "self_model",
                    "resource_id": SELF_MODEL_PRIMARY_ID, "status": "success",
                    "detail": {"fields": sorted(clean), "new_version": updated["version"]},
                })
        except PersistenceError:
            raise
        except Exception as e:
            raise StorageError(type(e).__name__) from e
        verified = self.repo.get("self_model", SELF_MODEL_PRIMARY_ID)
        if verified is None or verified["version"] != expected_version + 1:
            raise VerificationError("self-model update no confirmado al releer")
        for k, v in clean.items():
            if verified.get(k) != v:
                raise VerificationError(f"self-model update no confirmado en campo {k}")
        return verified

    def self_model_version(self):
        current = self.repo.get("self_model", SELF_MODEL_PRIMARY_ID)
        return None if current is None else current.get("version")

    # ------------------------------------------------------------ learning
    def save_learning(self, data, actor="system", idempotency_key=None):
        fields = validate_learning_event(data)
        record = dict(fields, id=new_id("learn"), schema_version=LEARNING_SCHEMA_VERSION)
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str) or not 0 < len(idempotency_key.strip()) <= 200:
                raise ValidationError("idempotency_key debe ser texto de 1 a 200 caracteres")
            record["idempotency_key"] = idempotency_key.strip()

        try:
            with self.repo.transaction() as tx:
                stored, created = tx.create("learning_events", record)
                tx.append_audit({
                    "actor": actor,
                    "action": "learning.create" if created else "learning.create.already_synced",
                    "resource": "learning_events", "resource_id": stored["id"], "status": "success",
                    "detail": {"outcome": stored.get("outcome"), "source": stored.get("source")},
                })
        except PersistenceError as e:
            self._audit_failure_generic(actor, "learning.create", "learning_events", None, e)
            raise
        except Exception as e:
            self._audit_failure_generic(actor, "learning.create", "learning_events", None, e)
            raise StorageError(type(e).__name__) from e

        verified = self.repo.get("learning_events", stored["id"])
        if verified is None:
            raise VerificationError("learning no confirmado: el registro no se puede releer")
        return {"outcome": "created" if created else "already_synced", "record": verified}

    def get_learning(self, learning_id):
        return self.repo.get("learning_events", learning_id)

    def record_reuse(self, learning_id, actor="system"):
        current = self.repo.get("learning_events", learning_id)
        if current is None:
            raise NotFoundError(learning_id)
        now_iso = _now_iso()
        changes = {
            "reuse_count": int(current.get("reuse_count") or 0) + 1,
            "last_reused_at": now_iso,
        }
        try:
            with self.repo.transaction() as tx:
                updated = tx.update("learning_events", learning_id, changes, current["version"])
                tx.append_audit({
                    "actor": actor, "action": "learning.reuse", "resource": "learning_events",
                    "resource_id": learning_id, "status": "success",
                    "detail": {"new_reuse_count": updated["reuse_count"]},
                })
        except PersistenceError:
            raise
        except Exception as e:
            raise StorageError(type(e).__name__) from e
        return updated

    def search_learning(self, filters=None, limit=50, offset=0, order_by="created_at", descending=True):
        limit = max(1, min(int(limit), 200))
        return self.repo.search("learning_events", filters or {}, limit=limit,
                                offset=max(0, int(offset)), order_by=order_by, descending=descending)

    # ------------------------------------------------------------ graph
    def create_node(self, data, actor="system", idempotency_key=None):
        fields = validate_graph_node(data)
        record = dict(fields, id=new_id("node"), status="active", schema_version=GRAPH_NODE_SCHEMA_VERSION)
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str) or not 0 < len(idempotency_key.strip()) <= 200:
                raise ValidationError("idempotency_key debe ser texto de 1 a 200 caracteres")
            record["idempotency_key"] = idempotency_key.strip()

        try:
            with self.repo.transaction() as tx:
                stored, created = tx.create("graph_nodes", record)
                tx.append_audit({
                    "actor": actor,
                    "action": "graph.node.create" if created else "graph.node.create.already_synced",
                    "resource": "graph_nodes", "resource_id": stored["id"], "status": "success",
                    "detail": {"node_type": stored.get("node_type"), "label": stored.get("label")},
                })
        except PersistenceError as e:
            self._audit_failure_generic(actor, "graph.node.create", "graph_nodes", None, e)
            raise
        except Exception as e:
            self._audit_failure_generic(actor, "graph.node.create", "graph_nodes", None, e)
            raise StorageError(type(e).__name__) from e

        verified = self.repo.get("graph_nodes", stored["id"])
        if verified is None:
            raise VerificationError("nodo no confirmado: no se puede releer")
        return {"outcome": "created" if created else "already_synced", "record": verified}

    def get_node(self, node_id):
        return self.repo.get("graph_nodes", node_id)

    def create_edge(self, data, actor="system", idempotency_key=None):
        fields = validate_graph_edge(data)
        from_node = fields.get("from_node")
        to_node = fields.get("to_node")
        if not self.repo.exists("graph_nodes", from_node):
            raise NotFoundError(f"from_node no existe: {from_node}")
        if not self.repo.exists("graph_nodes", to_node):
            raise NotFoundError(f"to_node no existe: {to_node}")
        record = dict(fields, id=new_id("edge"), status="active", schema_version=GRAPH_EDGE_SCHEMA_VERSION)
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str) or not 0 < len(idempotency_key.strip()) <= 200:
                raise ValidationError("idempotency_key debe ser texto de 1 a 200 caracteres")
            record["idempotency_key"] = idempotency_key.strip()

        try:
            with self.repo.transaction() as tx:
                stored, created = tx.create("graph_edges", record)
                tx.append_audit({
                    "actor": actor,
                    "action": "graph.edge.create" if created else "graph.edge.create.already_synced",
                    "resource": "graph_edges", "resource_id": stored["id"], "status": "success",
                    "detail": {"from": from_node, "to": to_node, "relation": stored.get("relation_type")},
                })
        except PersistenceError as e:
            self._audit_failure_generic(actor, "graph.edge.create", "graph_edges", None, e)
            raise
        except Exception as e:
            self._audit_failure_generic(actor, "graph.edge.create", "graph_edges", None, e)
            raise StorageError(type(e).__name__) from e

        verified = self.repo.get("graph_edges", stored["id"])
        if verified is None:
            raise VerificationError("relacion no confirmada: no se puede releer")
        return {"outcome": "created" if created else "already_synced", "record": verified}

    def get_edge(self, edge_id):
        return self.repo.get("graph_edges", edge_id)

    def related_nodes(self, node_id, direction="both", limit=50):
        limit = max(1, min(int(limit), 200))
        edges = []
        if direction in ("from", "both"):
            edges.extend(self.repo.search("graph_edges", {"from_node": node_id, "status": "active"}, limit=limit))
        if direction in ("to", "both"):
            edges.extend(self.repo.search("graph_edges", {"to_node": node_id, "status": "active"}, limit=limit))
        return edges[:limit]

    def count_nodes(self, filters=None):
        return self.repo.count("graph_nodes", filters or {})

    def count_edges(self, filters=None):
        return self.repo.count("graph_edges", filters or {})

    # ------------------------------------------------------------ ciclo cognitivo
    def start_cycle(self, trigger, input_data=None, actor="system", idempotency_key=None):
        data = {
            "trigger": trigger,
            "input": input_data or {},
            "current_stage": "observe",
            "status": "in_progress",
        }
        fields = validate_cognitive_cycle(data)
        record = dict(fields, id=new_id("cycle"), schema_version=COGNITIVE_CYCLE_SCHEMA_VERSION)
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str) or not 0 < len(idempotency_key.strip()) <= 200:
                raise ValidationError("idempotency_key debe ser texto de 1 a 200 caracteres")
            record["idempotency_key"] = idempotency_key.strip()

        try:
            with self.repo.transaction() as tx:
                stored, created = tx.create("cognitive_cycles", record)
                tx.append_audit({
                    "actor": actor,
                    "action": "cognitive.cycle.create" if created else "cognitive.cycle.create.already_synced",
                    "resource": "cognitive_cycles", "resource_id": stored["id"], "status": "success",
                    "detail": {"trigger": trigger},
                })
        except PersistenceError as e:
            self._audit_failure_generic(actor, "cognitive.cycle.create", "cognitive_cycles", None, e)
            raise
        except Exception as e:
            self._audit_failure_generic(actor, "cognitive.cycle.create", "cognitive_cycles", None, e)
            raise StorageError(type(e).__name__) from e

        verified = self.repo.get("cognitive_cycles", stored["id"])
        if verified is None:
            raise VerificationError("ciclo no confirmado: no se puede releer tras crearlo")
        return {"outcome": "created" if created else "already_synced", "record": verified}

    def record_stage(self, cycle_id, stage, data=None, status="success", error=None, actor="system", idempotency_key=None):
        if stage not in COGNITIVE_STAGES:
            raise ValidationError(f"stage invalido: {stage!r}")
        cycle = self.repo.get("cognitive_cycles", cycle_id)
        if cycle is None:
            raise NotFoundError(f"ciclo no existe: {cycle_id}")
        if cycle.get("status") in ("completed", "failed", "aborted"):
            raise ValidationError(f"el ciclo ya esta {cycle['status']}: no admite nuevas etapas")

        event_data = {
            "cycle_id": cycle_id,
            "stage": stage,
            "status": status,
            "data": data or {},
        }
        if error is not None:
            event_data["error"] = error
        clean_event = validate_cognitive_event(event_data)
        event_record = dict(clean_event, id=new_id("cevent"), schema_version=COGNITIVE_EVENT_SCHEMA_VERSION)
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str) or not 0 < len(idempotency_key.strip()) <= 200:
                raise ValidationError("idempotency_key debe ser texto de 1 a 200 caracteres")
            event_record["idempotency_key"] = idempotency_key.strip()

        try:
            with self.repo.transaction() as tx:
                stored_event, created = tx.create("cognitive_events", event_record)
                updated_cycle = tx.update("cognitive_cycles", cycle_id,
                                          {"current_stage": stage},
                                          cycle["version"])
                tx.append_audit({
                    "actor": actor,
                    "action": "cognitive.stage.record" if created else "cognitive.stage.already_synced",
                    "resource": "cognitive_events", "resource_id": stored_event["id"], "status": "success",
                    "detail": {"cycle_id": cycle_id, "stage": stage, "event_status": status},
                })
        except PersistenceError as e:
            self._audit_failure_generic(actor, "cognitive.stage.record", "cognitive_events", cycle_id, e)
            raise
        except Exception as e:
            self._audit_failure_generic(actor, "cognitive.stage.record", "cognitive_events", cycle_id, e)
            raise StorageError(type(e).__name__) from e

        verified_event = self.repo.get("cognitive_events", stored_event["id"])
        if verified_event is None:
            raise VerificationError("evento no confirmado: no se puede releer")
        return {"event": verified_event, "cycle": updated_cycle}

    def complete_cycle(self, cycle_id, final_status="completed", actor="system"):
        if final_status not in ("completed", "failed", "aborted"):
            raise ValidationError("final_status debe ser completed, failed o aborted")
        cycle = self.repo.get("cognitive_cycles", cycle_id)
        if cycle is None:
            raise NotFoundError(cycle_id)
        if cycle.get("status") != "in_progress":
            raise ValidationError(f"el ciclo ya esta {cycle['status']}")
        changes = {
            "status": final_status,
            "completed_at": _now_iso(),
        }
        try:
            with self.repo.transaction() as tx:
                updated = tx.update("cognitive_cycles", cycle_id, changes, cycle["version"])
                tx.append_audit({
                    "actor": actor, "action": "cognitive.cycle.complete", "resource": "cognitive_cycles",
                    "resource_id": cycle_id, "status": "success",
                    "detail": {"final_status": final_status, "current_stage": updated.get("current_stage")},
                })
        except PersistenceError:
            raise
        except Exception as e:
            raise StorageError(type(e).__name__) from e
        return updated

    def get_cycle(self, cycle_id):
        return self.repo.get("cognitive_cycles", cycle_id)

    def list_cycle_events(self, cycle_id, limit=100):
        limit = max(1, min(int(limit), 500))
        return self.repo.search("cognitive_events", {"cycle_id": cycle_id}, limit=limit,
                                offset=0, order_by="created_at", descending=False)

    def get_cycle_with_events(self, cycle_id):
        cycle = self.repo.get("cognitive_cycles", cycle_id)
        if cycle is None:
            return None
        events = self.list_cycle_events(cycle_id)
        return {"cycle": cycle, "events": events}

    def count_cycles(self, filters=None):
        return self.repo.count("cognitive_cycles", filters or {})

    def count_cycle_events(self, filters=None):
        return self.repo.count("cognitive_events", filters or {})

    # ------------------------------------------------------------ V8-Fase8: tool registry
    def register_tool(self, data, actor="system", idempotency_key=None):
        """Registra una herramienta en el registry. Idempotente por name (indice unico).
        Si ya existe una tool con el mismo name, se actualiza la metadata (upsert manual)."""
        fields = validate_tool(data)
        # Buscar si ya existe por name
        existing = self.repo.search("tools", {"name": fields.get("name")}, limit=1)
        if existing:
            current = existing[0]
            changes = {k: v for k, v in fields.items() if k != "name"}
            if not changes:
                return {"outcome": "already_synced", "record": current}
            try:
                with self.repo.transaction() as tx:
                    updated = tx.update("tools", current["id"], changes, current["version"])
                    tx.append_audit({
                        "actor": actor, "action": "tool.update", "resource": "tools",
                        "resource_id": current["id"], "status": "success",
                        "detail": {"fields": sorted(changes)},
                    })
            except PersistenceError:
                raise
            except Exception as e:
                raise StorageError(type(e).__name__) from e
            return {"outcome": "updated", "record": updated}

        record = dict(fields, id=new_id("tool"), schema_version=TOOL_SCHEMA_VERSION)
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str) or not 0 < len(idempotency_key.strip()) <= 200:
                raise ValidationError("idempotency_key debe ser texto de 1 a 200 caracteres")
            record["idempotency_key"] = idempotency_key.strip()

        try:
            with self.repo.transaction() as tx:
                stored, created = tx.create("tools", record)
                tx.append_audit({
                    "actor": actor,
                    "action": "tool.create" if created else "tool.create.already_synced",
                    "resource": "tools", "resource_id": stored["id"], "status": "success",
                    "detail": {"name": stored.get("name"), "category": stored.get("category")},
                })
        except PersistenceError as e:
            self._audit_failure_generic(actor, "tool.create", "tools", None, e)
            raise
        except Exception as e:
            self._audit_failure_generic(actor, "tool.create", "tools", None, e)
            raise StorageError(type(e).__name__) from e

        verified = self.repo.get("tools", stored["id"])
        if verified is None:
            raise VerificationError("tool no confirmada: no se puede releer")
        return {"outcome": "created" if created else "already_synced", "record": verified}

    def get_tool_by_name(self, name):
        rows = self.repo.search("tools", {"name": name}, limit=1)
        return rows[0] if rows else None

    def get_tool(self, tool_id):
        return self.repo.get("tools", tool_id)

    def list_tools(self, category=None, status=None, limit=100):
        filters = {}
        if category:
            filters["category"] = category
        if status:
            filters["status"] = status
        limit = max(1, min(int(limit), 200))
        return self.repo.search("tools", filters, limit=limit, offset=0,
                                order_by="name", descending=False)

    def count_tools(self, filters=None):
        return self.repo.count("tools", filters or {})

    def log_invocation(self, tool_name, inputs, outputs, status, actor, duration_ms, error=None, idempotency_key=None):
        """Registra una invocacion en el log append-only. Siempre se escribe, exito o fallo."""
        data = {
            "tool_name": tool_name,
            "actor": actor,
            "inputs": inputs if isinstance(inputs, dict) else {},
            "outputs": outputs if isinstance(outputs, dict) else {},
            "status": status,
            "duration_ms": int(duration_ms),
        }
        if error is not None:
            data["error"] = error
        clean = validate_tool_invocation(data)
        record = dict(clean, id=new_id("inv"), schema_version=TOOL_INVOCATION_SCHEMA_VERSION)
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str) or not 0 < len(idempotency_key.strip()) <= 200:
                raise ValidationError("idempotency_key debe ser texto de 1 a 200 caracteres")
            record["idempotency_key"] = idempotency_key.strip()

        try:
            with self.repo.transaction() as tx:
                stored, created = tx.create("tool_invocations", record)
                tx.append_audit({
                    "actor": actor,
                    "action": "tool.invoke" if status == "success" else "tool.invoke.failed",
                    "resource": "tool_invocations", "resource_id": stored["id"],
                    "status": "success" if status == "success" else "failure",
                    "detail": {"tool_name": tool_name, "duration_ms": duration_ms,
                               "error_type": (error or {}).get("type") if error else None},
                })
        except PersistenceError as e:
            self._audit_failure_generic(actor, "tool.log_invocation", "tool_invocations", None, e)
            raise
        except Exception as e:
            self._audit_failure_generic(actor, "tool.log_invocation", "tool_invocations", None, e)
            raise StorageError(type(e).__name__) from e

        return {"outcome": "created" if created else "already_synced", "record": stored}

    def list_invocations(self, tool_name=None, status=None, actor=None, limit=50):
        filters = {}
        if tool_name:
            filters["tool_name"] = tool_name
        if status:
            filters["status"] = status
        if actor:
            filters["actor"] = actor
        limit = max(1, min(int(limit), 200))
        return self.repo.search("tool_invocations", filters, limit=limit, offset=0,
                                order_by="created_at", descending=True)

    def count_invocations(self, filters=None):
        return self.repo.count("tool_invocations", filters or {})
