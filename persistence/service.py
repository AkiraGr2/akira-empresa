"""PersistenceService: puerta unica a la persistencia de AKIRA.

V8-Fase5-9: self-model, learning, graph, cognitive, tools, agents.
Sub-fase 10.0: auto-conexion del grafo + nucleo Akira.
Sub-fase 10.2: misiones (CRUD + transiciones de estado validadas).
Sub-fase 10.7.2: persistencia de conversaciones (chats independientes + historial global).
"""
from __future__ import annotations

import datetime as _dt

from .core import (AGENT_SCHEMA_VERSION, AGENT_TASK_SCHEMA_VERSION,
                   COGNITIVE_CYCLE_SCHEMA_VERSION, COGNITIVE_EVENT_SCHEMA_VERSION,
                   COGNITIVE_STAGES, CONVERSATION_MESSAGE_SCHEMA_VERSION,
                   CONVERSATION_SCHEMA_VERSION, GRAPH_EDGE_SCHEMA_VERSION,
                   GRAPH_NODE_SCHEMA_VERSION, HIVE_VISIBLE, LEARNING_SCHEMA_VERSION,
                   MEMORY_SCHEMA_VERSION, MISSION_SCHEMA_VERSION, MISSION_STATUSES,
                   SELF_MODEL_PRIMARY_ID, SELF_MODEL_SCHEMA_VERSION,
                   TOOL_INVOCATION_SCHEMA_VERSION, TOOL_SCHEMA_VERSION,
                   ConflictError, NotFoundError, PersistenceError, StorageError,
                   ValidationError, VerificationError, entity_spec, new_id,
                   validate_agent, validate_agent_task, validate_cognitive_cycle,
                   validate_cognitive_event, validate_conversation,
                   validate_conversation_message, validate_graph_edge,
                   validate_graph_node, validate_learning_event, validate_memory,
                   validate_mission, validate_self_model, validate_tool,
                   validate_tool_invocation)

_COMPARE_FIELDS = ("content", "memory_type", "importance", "confidence", "tags", "privacy_level",
                   "source", "owner_scope")

_AUTO_MIN_WEIGHT = 0.3
_AUTO_MAX_CONNECTIONS = 5
_AUTO_TAG_WEIGHT_BASE = 0.5
_AUTO_TAG_WEIGHT_PER_EXTRA = 0.15
_AUTO_AGENT_TOOL_WEIGHT = 0.6
_AUTO_LEARNING_WEIGHT = 0.8
_AUTO_MEMORY_WEIGHT = 0.4
_AUTO_EDGE_MAX_WEIGHT = 1.0
_AUTO_REINFORCE_MIN_FREQ = 5

_CORE_NODE_LABEL = "Akira"
_CORE_NODE_TAGS = ["core", "akira", "nucleo"]
_CORE_NODE_WEIGHT = 10.0
_CORE_EDGE_WEIGHT = 0.6

MISSION_STATUS_TRANSITIONS = {
    "created":          ("planning", "cancelled"),
    "planning":         ("waiting_approval", "failed", "cancelled"),
    "waiting_approval": ("running", "cancelled"),
    "running":          ("completed", "failed", "paused"),
    "paused":           ("running", "cancelled", "failed"),
    "completed":        (),
    "failed":           (),
    "cancelled":        (),
}

_SELF_MODEL_DEFAULTS = {
    "identity": {"name": "Akira", "version": "V7.3", "creator": "Jhon Grimm",
                 "language": "es-CO",
                 "essence": "Colmena cognitiva personal. Persistente, verificable, honesta sobre sus capacidades."},
    "purpose": {"primary": "Asistir a Jhon Grimm como colmena cognitiva persistente.",
                "derived": ["recordar de verdad", "recuperar sin inventar",
                            "aprender de la experiencia", "no aparentar mas capacidad de la real"]},
    "capabilities": [
        {"name": "chat", "status": "verified"}, {"name": "streaming", "status": "verified"},
        {"name": "persistent_memory", "status": "verified"}, {"name": "memory_recall", "status": "verified"},
        {"name": "session_auth", "status": "verified"}, {"name": "identity_filter", "status": "verified"},
        {"name": "pdf_extraction", "status": "verified"}, {"name": "voice_dictation", "status": "verified"},
        {"name": "image_generation", "status": "verified"}, {"name": "file_creation", "status": "verified"},
        {"name": "multi_key_pool", "status": "verified"}, {"name": "non_blocking_chat", "status": "verified"},
        {"name": "self_model_persistent", "status": "verified"}, {"name": "learning_persistent", "status": "verified"},
        {"name": "graph_persistent", "status": "verified"}, {"name": "graph_auto_connect", "status": "verified"},
        {"name": "cognitive_cycle_persistent", "status": "verified"}, {"name": "tool_registry", "status": "verified"},
        {"name": "agents_persistent", "status": "verified"}, {"name": "missions", "status": "partial"},
        {"name": "conversations_persistent", "status": "partial"},
        {"name": "self_repair_full", "status": "not_implemented"}, {"name": "evolution_engine", "status": "not_implemented"},
        {"name": "hive", "status": "not_implemented"}, {"name": "knowledge_graph_full", "status": "partial"},
    ],
    "tools": [
        {"name": "postgres", "role": "persistencia", "status": "verified"},
        {"name": "gemini", "role": "inferencia_primaria", "status": "verified"},
        {"name": "groq", "role": "inferencia_fallback", "status": "verified"},
        {"name": "google_auth", "role": "identidad", "status": "verified"},
        {"name": "pymupdf", "role": "pdf", "status": "verified"},
        {"name": "pollinations", "role": "imagen", "status": "verified"},
        {"name": "tool_registry", "role": "herramientas", "status": "verified"},
        {"name": "agents", "role": "agentes", "status": "verified"},
        {"name": "r2", "role": "almacenamiento", "status": "partial"},
    ],
    "models": [
        {"provider": "gemini", "model": "gemini-3.8-flash", "role": "primario"},
        {"provider": "groq", "model": "openai/gpt-oss-120b", "role": "fallback"},
    ],
    "current_state": {}, "knowledge_state": {},
    "uncertainties": [
        "No hay pruebas de conciencia subjetiva.",
        "La calidad de las respuestas depende del proveedor externo.",
        "El grafo tiene auto-conexion por tags, agentes y learning, pero falta consolidacion y pruning.",
        "Los agentes existen; las misiones estan en construccion (Fase 10).",
        "R2 tiene arquitectura preparada pero sin escritura real verificada.",
    ],
    "errors": [], "repairs": [], "evolution": [],
}

def _now_iso():
    return _dt.datetime.now(_dt.timezone.utc).isoformat()

class PersistenceService:
    def __init__(self, repo):
        self.repo = repo

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
                tx.append_audit({"actor": actor,
                    "action": "memory.create" if created else "memory.create.already_synced",
                    "resource": "memories", "resource_id": stored["id"], "status": "success",
                    "detail": {"privacy_level": stored["privacy_level"], "memory_type": stored["memory_type"]}})
        except PersistenceError as e:
            self._audit_failure_generic(actor, "memory.create", "memories", None, e); raise
        except Exception as e:
            self._audit_failure_generic(actor, "memory.create", "memories", None, e)
            raise StorageError(type(e).__name__) from e
        verified = self.repo.get("memories", stored["id"])
        if verified is None:
            raise VerificationError("escritura no confirmada")
        expected = stored if not created else fields
        for f in _COMPARE_FIELDS:
            if verified.get(f) != expected.get(f, verified.get(f)):
                raise VerificationError(f"campo {f} no coincide al releer")
        result = {"outcome": "created" if created else "already_synced", "record": verified}
        if created:
            try: self.auto_connect_memory_tags(verified["id"], actor=actor)
            except Exception as e: print(f"[auto-connect] memory_tags fallo: {type(e).__name__}: {str(e)[:200]}")
        return result

    def get_memory(self, memory_id): return self.repo.get("memories", memory_id)
    def exists_memory(self, memory_id): return self.repo.exists("memories", memory_id)
    def update_memory(self, memory_id, changes, expected_version, actor="system"):
        clean = validate_memory(changes, partial=True)
        return self._update(memory_id, clean, expected_version, actor, "memory.update")
    def archive_memory(self, memory_id, expected_version=None, actor="system"):
        if expected_version is None:
            current = self.repo.get("memories", memory_id)
            if current is None: raise NotFoundError(memory_id)
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
            self._audit_failure_generic(actor, action, "memories", memory_id, e); raise
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
        if "status" not in f and "status__in" not in f: f["status"] = "active"
        if hive:
            f.pop("privacy_level", None); f["privacy_level__in"] = list(HIVE_VISIBLE)
        return f
    def search_memory(self, filters=None, hive=False, limit=50, offset=0, order_by="created_at", descending=True):
        limit = max(1, min(int(limit), 200))
        return self.repo.search("memories", self._memory_filters(filters, hive), limit=limit,
                                offset=max(0, int(offset)), order_by=order_by, descending=descending)
    def count_memory(self, filters=None, hive=False):
        return self.repo.count("memories", self._memory_filters(filters, hive))
    def health(self): return self.repo.ping()

    def get_self_model(self):
        current = self.repo.get("self_model", SELF_MODEL_PRIMARY_ID)
        if current is not None: return current
        record = {"id": SELF_MODEL_PRIMARY_ID, "schema_version": SELF_MODEL_SCHEMA_VERSION,
                  "idempotency_key": f"{SELF_MODEL_PRIMARY_ID}_v1"}
        for field, value in _SELF_MODEL_DEFAULTS.items(): record[field] = value
        try:
            with self.repo.transaction() as tx:
                stored, created = tx.create("self_model", record)
                tx.append_audit({"actor": "system", "action": "self_model.create",
                    "resource": "self_model", "resource_id": stored["id"], "status": "success",
                    "detail": {"created": created, "schema_version": SELF_MODEL_SCHEMA_VERSION}})
        except PersistenceError: raise
        except Exception as e: raise StorageError(type(e).__name__) from e
        verified = self.repo.get("self_model", SELF_MODEL_PRIMARY_ID)
        if verified is None: raise VerificationError("self-model no confirmado")
        return verified
    def update_self_model(self, changes, expected_version, actor="system"):
        clean = validate_self_model(changes, partial=True)
        if isinstance(expected_version, bool) or not isinstance(expected_version, int) or expected_version < 1:
            raise ValidationError("expected_version debe ser un entero >= 1")
        try:
            with self.repo.transaction() as tx:
                updated = tx.update("self_model", SELF_MODEL_PRIMARY_ID, clean, expected_version)
                tx.append_audit({"actor": actor, "action": "self_model.update", "resource": "self_model",
                    "resource_id": SELF_MODEL_PRIMARY_ID, "status": "success",
                    "detail": {"fields": sorted(clean), "new_version": updated["version"]}})
        except PersistenceError: raise
        except Exception as e: raise StorageError(type(e).__name__) from e
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
                tx.append_audit({"actor": actor,
                    "action": "learning.create" if created else "learning.create.already_synced",
                    "resource": "learning_events", "resource_id": stored["id"], "status": "success",
                    "detail": {"outcome": stored.get("outcome"), "source": stored.get("source")}})
        except PersistenceError as e:
            self._audit_failure_generic(actor, "learning.create", "learning_events", None, e); raise
        except Exception as e:
            self._audit_failure_generic(actor, "learning.create", "learning_events", None, e)
            raise StorageError(type(e).__name__) from e
        verified = self.repo.get("learning_events", stored["id"])
        if verified is None: raise VerificationError("learning no confirmado")
        if created:
            try: self.auto_connect_learning(verified["id"], actor=actor)
            except Exception as e: print(f"[auto-connect] learning fallo: {type(e).__name__}: {str(e)[:200]}")
        return {"outcome": "created" if created else "already_synced", "record": verified}

    def update_learning(self, learning_id, changes, expected_version=None, actor="system"):
        current = self.get_learning(learning_id)
        if current is None:
            raise NotFoundError(learning_id)
        clean = validate_learning_event(changes, partial=True)
        if not clean:
            raise ValidationError("no hay cambios")
        if expected_version is None:
            expected_version = current["version"]
        try:
            with self.repo.transaction() as tx:
                updated = tx.update("learning_events", learning_id, clean, expected_version)
                tx.append_audit({"actor": actor, "action": "learning.update",
                    "resource": "learning_events", "resource_id": learning_id, "status": "success",
                    "detail": {"fields": sorted(clean), "new_version": updated["version"]}})
        except PersistenceError:
            raise
        except Exception as e:
            raise StorageError(type(e).__name__) from e
        verified = self.repo.get("learning_events", learning_id)
        if verified is None or verified["version"] != expected_version + 1:
            raise VerificationError("learning update no confirmado")
        return verified

    def update_learning_status(self, learning_id, status, expected_version=None, actor="system"):
        current = self.get_learning(learning_id)
        if current is None:
            raise NotFoundError(learning_id)
        clean = validate_learning_event({"status": status}, partial=True)
        next_status = clean["status"]
        current_status = current.get("status") or "candidate"
        transitions = {
            "candidate": {"verified", "conflicted", "discarded"},
            "verified": {"consolidated", "conflicted", "obsolete"},
            "consolidated": {"conflicted", "obsolete"},
            "conflicted": {"verified", "discarded"},
            "obsolete": {"verified", "discarded"},
            "discarded": set(),
        }
        if next_status != current_status and next_status not in transitions.get(current_status, set()):
            raise ValidationError(f"transicion de learning no permitida: {current_status} -> {next_status}")
        if expected_version is None:
            expected_version = current["version"]
        if current.get("status") == clean["status"]:
            return current
        try:
            with self.repo.transaction() as tx:
                updated = tx.update("learning_events", learning_id, clean, expected_version)
                tx.append_audit({"actor": actor, "action": "learning.status.update",
                    "resource": "learning_events", "resource_id": learning_id, "status": "success",
                    "detail": {"status": clean["status"], "new_version": updated["version"]}})
        except PersistenceError:
            raise
        except Exception as e:
            raise StorageError(type(e).__name__) from e
        verified = self.repo.get("learning_events", learning_id)
        if verified is None or verified.get("status") != clean["status"]:
            raise VerificationError("learning status no confirmado")
        return verified

    def get_learning(self, learning_id):
        """Fix Neon+pooler: WHERE id a veces falla. Fallback a search sin filtro."""
        rec = self.repo.get("learning_events", learning_id)
        if rec is not None:
            return rec
        try:
            rows = self.repo.search("learning_events", {}, limit=300)
            for r in rows:
                if r.get("id") == learning_id:
                    return r
        except Exception:
            pass
        return None

    def record_reuse(self, learning_id, actor="system"):
        current = self.repo.get("learning_events", learning_id)
        if current is None: raise NotFoundError(learning_id)
        changes = {"reuse_count": int(current.get("reuse_count") or 0) + 1, "last_reused_at": _now_iso()}
        try:
            with self.repo.transaction() as tx:
                updated = tx.update("learning_events", learning_id, changes, current["version"])
                tx.append_audit({"actor": actor, "action": "learning.reuse",
                    "resource": "learning_events", "resource_id": learning_id, "status": "success",
                    "detail": {"new_reuse_count": updated["reuse_count"]}})
        except PersistenceError: raise
        except Exception as e: raise StorageError(type(e).__name__) from e
        return updated
    def search_learning(self, filters=None, limit=50, offset=0, order_by="created_at", descending=True):
        limit = max(1, min(int(limit), 200))
        return self.repo.search("learning_events", filters or {}, limit=limit,
                                offset=max(0, int(offset)), order_by=order_by, descending=descending)

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
                tx.append_audit({"actor": actor,
                    "action": "graph.node.create" if created else "graph.node.create.already_synced",
                    "resource": "graph_nodes", "resource_id": stored["id"], "status": "success",
                    "detail": {"node_type": stored.get("node_type"), "label": stored.get("label")}})
        except PersistenceError as e:
            self._audit_failure_generic(actor, "graph.node.create", "graph_nodes", None, e); raise
        except Exception as e:
            self._audit_failure_generic(actor, "graph.node.create", "graph_nodes", None, e)
            raise StorageError(type(e).__name__) from e
        verified = self.repo.get("graph_nodes", stored["id"])
        if verified is None: raise VerificationError("nodo no confirmado")
        if created:
            try: self.auto_connect_node_tags(verified["id"], actor=actor)
            except Exception as e: print(f"[auto-connect] node_tags fallo: {type(e).__name__}: {str(e)[:200]}")
            if str(verified.get("label", "")).strip() != _CORE_NODE_LABEL:
                try: self.connect_to_core(verified["id"], actor=actor, weight=0.25)
                except Exception as e: print(f"[core] connect fallo: {type(e).__name__}: {str(e)[:200]}")
        return {"outcome": "created" if created else "already_synced", "record": verified}

    def get_node(self, node_id): return self.repo.get("graph_nodes", node_id)

    def create_edge(self, data, actor="system", idempotency_key=None):
        fields = validate_graph_edge(data)
        from_node = fields.get("from_node"); to_node = fields.get("to_node")
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
                tx.append_audit({"actor": actor,
                    "action": "graph.edge.create" if created else "graph.edge.create.already_synced",
                    "resource": "graph_edges", "resource_id": stored["id"], "status": "success",
                    "detail": {"from": from_node, "to": to_node, "relation": stored.get("relation_type")}})
        except PersistenceError as e:
            self._audit_failure_generic(actor, "graph.edge.create", "graph_edges", None, e); raise
        except Exception as e:
            self._audit_failure_generic(actor, "graph.edge.create", "graph_edges", None, e)
            raise StorageError(type(e).__name__) from e
        verified = self.repo.get("graph_edges", stored["id"])
        if verified is None: raise VerificationError("relacion no confirmada")
        return {"outcome": "created" if created else "already_synced", "record": verified}

    def get_edge(self, edge_id): return self.repo.get("graph_edges", edge_id)

    def related_nodes(self, node_id, direction="both", limit=50):
        limit = max(1, min(int(limit), 200))
        edges = []
        if direction in ("from", "both"):
            edges.extend(self.repo.search("graph_edges", {"from_node": node_id, "status": "active"}, limit=limit))
        if direction in ("to", "both"):
            edges.extend(self.repo.search("graph_edges", {"to_node": node_id, "status": "active"}, limit=limit))
        return edges[:limit]
    def count_nodes(self, filters=None): return self.repo.count("graph_nodes", filters or {})
    def count_edges(self, filters=None): return self.repo.count("graph_edges", filters or {})
    def list_graph_nodes(self, limit=500, offset=0, order_by="weight", descending=True):
        limit = max(1, min(int(limit), 2000))
        return self.repo.search("graph_nodes", {"status": "active"}, limit=limit,
                                offset=max(0, int(offset)), order_by=order_by, descending=descending)
    def list_graph_edges(self, limit=1000, offset=0, order_by="weight", descending=True):
        limit = max(1, min(int(limit), 5000))
        return self.repo.search("graph_edges", {"status": "active"}, limit=limit,
                                offset=max(0, int(offset)), order_by=order_by, descending=descending)

    def start_cycle(self, trigger, input_data=None, actor="system", idempotency_key=None):
        data = {"trigger": trigger, "input": input_data or {},
                "current_stage": "observe", "status": "in_progress"}
        fields = validate_cognitive_cycle(data)
        record = dict(fields, id=new_id("cycle"), schema_version=COGNITIVE_CYCLE_SCHEMA_VERSION)
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str) or not 0 < len(idempotency_key.strip()) <= 200:
                raise ValidationError("idempotency_key debe ser texto de 1 a 200 caracteres")
            record["idempotency_key"] = idempotency_key.strip()
        try:
            with self.repo.transaction() as tx:
                stored, created = tx.create("cognitive_cycles", record)
                tx.append_audit({"actor": actor,
                    "action": "cognitive.cycle.create" if created else "cognitive.cycle.create.already_synced",
                    "resource": "cognitive_cycles", "resource_id": stored["id"], "status": "success",
                    "detail": {"trigger": trigger}})
        except PersistenceError as e:
            self._audit_failure_generic(actor, "cognitive.cycle.create", "cognitive_cycles", None, e); raise
        except Exception as e:
            self._audit_failure_generic(actor, "cognitive.cycle.create", "cognitive_cycles", None, e)
            raise StorageError(type(e).__name__) from e
        verified = self.repo.get("cognitive_cycles", stored["id"])
        if verified is None: raise VerificationError("ciclo no confirmado")
        return {"outcome": "created" if created else "already_synced", "record": verified}

    def record_stage(self, cycle_id, stage, data=None, status="success", error=None, actor="system", idempotency_key=None):
        if stage not in COGNITIVE_STAGES: raise ValidationError(f"stage invalido: {stage!r}")
        cycle = self.repo.get("cognitive_cycles", cycle_id)
        if cycle is None: raise NotFoundError(f"ciclo no existe: {cycle_id}")
        if cycle.get("status") in ("completed", "failed", "aborted"):
            raise ValidationError(f"el ciclo ya esta {cycle['status']}")
        event_data = {"cycle_id": cycle_id, "stage": stage, "status": status, "data": data or {}}
        if error is not None: event_data["error"] = error
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
                                          {"current_stage": stage}, cycle["version"])
                tx.append_audit({"actor": actor,
                    "action": "cognitive.stage.record" if created else "cognitive.stage.already_synced",
                    "resource": "cognitive_events", "resource_id": stored_event["id"], "status": "success",
                    "detail": {"cycle_id": cycle_id, "stage": stage, "event_status": status}})
        except PersistenceError as e:
            self._audit_failure_generic(actor, "cognitive.stage.record", "cognitive_events", cycle_id, e); raise
        except Exception as e:
            self._audit_failure_generic(actor, "cognitive.stage.record", "cognitive_events", cycle_id, e)
            raise StorageError(type(e).__name__) from e
        verified_event = self.repo.get("cognitive_events", stored_event["id"])
        if verified_event is None: raise VerificationError("evento no confirmado")
        return {"event": verified_event, "cycle": updated_cycle}

    def complete_cycle(self, cycle_id, final_status="completed", actor="system"):
        if final_status not in ("completed", "failed", "aborted"):
            raise ValidationError("final_status debe ser completed, failed o aborted")
        cycle = self.repo.get("cognitive_cycles", cycle_id)
        if cycle is None: raise NotFoundError(cycle_id)
        if cycle.get("status") != "in_progress": raise ValidationError(f"el ciclo ya esta {cycle['status']}")
        changes = {"status": final_status, "completed_at": _now_iso()}
        try:
            with self.repo.transaction() as tx:
                updated = tx.update("cognitive_cycles", cycle_id, changes, cycle["version"])
                tx.append_audit({"actor": actor, "action": "cognitive.cycle.complete",
                    "resource": "cognitive_cycles", "resource_id": cycle_id, "status": "success",
                    "detail": {"final_status": final_status, "current_stage": updated.get("current_stage")}})
        except PersistenceError: raise
        except Exception as e: raise StorageError(type(e).__name__) from e
        return updated
    def get_cycle(self, cycle_id): return self.repo.get("cognitive_cycles", cycle_id)
    def list_cycle_events(self, cycle_id, limit=100):
        limit = max(1, min(int(limit), 500))
        return self.repo.search("cognitive_events", {"cycle_id": cycle_id}, limit=limit,
                                offset=0, order_by="created_at", descending=False)
    def get_cycle_with_events(self, cycle_id):
        cycle = self.repo.get("cognitive_cycles", cycle_id)
        if cycle is None: return None
        events = self.list_cycle_events(cycle_id)
        return {"cycle": cycle, "events": events}
    def count_cycles(self, filters=None): return self.repo.count("cognitive_cycles", filters or {})
    def count_cycle_events(self, filters=None): return self.repo.count("cognitive_events", filters or {})

    def register_tool(self, data, actor="system", idempotency_key=None):
        fields = validate_tool(data)
        existing = self.repo.search("tools", {"name": fields.get("name")}, limit=1)
        if existing:
            current = existing[0]
            mutable = set(entity_spec("tools")["mutable"])
            changes = {k: v for k, v in fields.items() if k in mutable}
            if not changes: return {"outcome": "already_synced", "record": current}
            try:
                with self.repo.transaction() as tx:
                    updated = tx.update("tools", current["id"], changes, current["version"])
                    tx.append_audit({"actor": actor, "action": "tool.update", "resource": "tools",
                        "resource_id": current["id"], "status": "success",
                        "detail": {"fields": sorted(changes)}})
            except PersistenceError: raise
            except Exception as e: raise StorageError(type(e).__name__) from e
            return {"outcome": "updated", "record": updated}
        record = dict(fields, id=new_id("tool"), schema_version=TOOL_SCHEMA_VERSION)
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str) or not 0 < len(idempotency_key.strip()) <= 200:
                raise ValidationError("idempotency_key debe ser texto de 1 a 200 caracteres")
            record["idempotency_key"] = idempotency_key.strip()
        try:
            with self.repo.transaction() as tx:
                stored, created = tx.create("tools", record)
                tx.append_audit({"actor": actor,
                    "action": "tool.create" if created else "tool.create.already_synced",
                    "resource": "tools", "resource_id": stored["id"], "status": "success",
                    "detail": {"name": stored.get("name"), "category": stored.get("category")}})
        except PersistenceError as e:
            self._audit_failure_generic(actor, "tool.create", "tools", None, e); raise
        except Exception as e:
            self._audit_failure_generic(actor, "tool.create", "tools", None, e)
            raise StorageError(type(e).__name__) from e
        verified = self.repo.get("tools", stored["id"])
        if verified is None: raise VerificationError("tool no confirmada")
        return {"outcome": "created" if created else "already_synced", "record": verified}

    def get_tool_by_name(self, name):
        rows = self.repo.search("tools", {"name": name}, limit=1)
        return rows[0] if rows else None
    def get_tool(self, tool_id): return self.repo.get("tools", tool_id)
    def list_tools(self, category=None, status=None, limit=100):
        filters = {}
        if category: filters["category"] = category
        if status: filters["status"] = status
        limit = max(1, min(int(limit), 200))
        return self.repo.search("tools", filters, limit=limit, offset=0, order_by="name", descending=False)
    def count_tools(self, filters=None): return self.repo.count("tools", filters or {})

    def log_invocation(self, tool_name, inputs, outputs, status, actor, duration_ms, error=None, idempotency_key=None):
        data = {"tool_name": tool_name, "actor": actor,
                "inputs": inputs if isinstance(inputs, dict) else {},
                "outputs": outputs if isinstance(outputs, dict) else {},
                "status": status, "duration_ms": int(duration_ms)}
        if error is not None: data["error"] = error
        clean = validate_tool_invocation(data)
        record = dict(clean, id=new_id("inv"), schema_version=TOOL_INVOCATION_SCHEMA_VERSION)
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str) or not 0 < len(idempotency_key.strip()) <= 200:
                raise ValidationError("idempotency_key debe ser texto de 1 a 200 caracteres")
            record["idempotency_key"] = idempotency_key.strip()
        try:
            with self.repo.transaction() as tx:
                stored, created = tx.create("tool_invocations", record)
                tx.append_audit({"actor": actor,
                    "action": "tool.invoke" if status == "success" else "tool.invoke.failed",
                    "resource": "tool_invocations", "resource_id": stored["id"],
                    "status": "success" if status == "success" else "failure",
                    "detail": {"tool_name": tool_name, "duration_ms": duration_ms,
                               "error_type": (error or {}).get("type") if error else None}})
        except PersistenceError as e:
            self._audit_failure_generic(actor, "tool.log_invocation", "tool_invocations", None, e); raise
        except Exception as e:
            self._audit_failure_generic(actor, "tool.log_invocation", "tool_invocations", None, e)
            raise StorageError(type(e).__name__) from e
        return {"outcome": "created" if created else "already_synced", "record": stored}

    def list_invocations(self, tool_name=None, status=None, actor=None, limit=50):
        filters = {}
        if tool_name: filters["tool_name"] = tool_name
        if status: filters["status"] = status
        if actor: filters["actor"] = actor
        limit = max(1, min(int(limit), 200))
        return self.repo.search("tool_invocations", filters, limit=limit, offset=0,
                                order_by="created_at", descending=True)
    def count_invocations(self, filters=None): return self.repo.count("tool_invocations", filters or {})

    def register_agent(self, data, actor="system", idempotency_key=None):
        fields = validate_agent(data)
        existing = self.repo.search("agents", {"name": fields.get("name")}, limit=1)
        if existing:
            current = existing[0]
            mutable = set(entity_spec("agents")["mutable"])
            changes = {k: v for k, v in fields.items() if k in mutable}
            if not changes: return {"outcome": "already_synced", "record": current}
            try:
                with self.repo.transaction() as tx:
                    updated = tx.update("agents", current["id"], changes, current["version"])
                    tx.append_audit({"actor": actor, "action": "agent.update", "resource": "agents",
                        "resource_id": current["id"], "status": "success",
                        "detail": {"fields": sorted(changes)}})
            except PersistenceError: raise
            except Exception as e: raise StorageError(type(e).__name__) from e
            return {"outcome": "updated", "record": updated}
        record = dict(fields, id=new_id("agent"), schema_version=AGENT_SCHEMA_VERSION)
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str) or not 0 < len(idempotency_key.strip()) <= 200:
                raise ValidationError("idempotency_key debe ser texto de 1 a 200 caracteres")
            record["idempotency_key"] = idempotency_key.strip()
        try:
            with self.repo.transaction() as tx:
                stored, created = tx.create("agents", record)
                tx.append_audit({"actor": actor,
                    "action": "agent.create" if created else "agent.create.already_synced",
                    "resource": "agents", "resource_id": stored["id"], "status": "success",
                    "detail": {"name": stored.get("name"), "role": stored.get("role")}})
        except PersistenceError as e:
            self._audit_failure_generic(actor, "agent.create", "agents", None, e); raise
        except Exception as e:
            self._audit_failure_generic(actor, "agent.create", "agents", None, e)
            raise StorageError(type(e).__name__) from e
        verified = self.repo.get("agents", stored["id"])
        if verified is None: raise VerificationError("agente no confirmado")
        return {"outcome": "created" if created else "already_synced", "record": verified}

    def get_agent_by_name(self, name):
        rows = self.repo.search("agents", {"name": name}, limit=1)
        return rows[0] if rows else None
    def get_agent(self, agent_id): return self.repo.get("agents", agent_id)
    def list_agents(self, role=None, status=None, limit=100):
        filters = {}
        if role: filters["role"] = role
        if status: filters["status"] = status
        limit = max(1, min(int(limit), 200))
        return self.repo.search("agents", filters, limit=limit, offset=0, order_by="name", descending=False)
    def count_agents(self, filters=None): return self.repo.count("agents", filters or {})

    def update_agent(self, agent_name, changes, actor="system"):
        current = self.get_agent_by_name(agent_name)
        if current is None: raise NotFoundError(f"agente no existe: {agent_name}")
        clean = validate_agent(changes, partial=True)
        try:
            with self.repo.transaction() as tx:
                updated = tx.update("agents", current["id"], clean, current["version"])
                tx.append_audit({"actor": actor, "action": "agent.update", "resource": "agents",
                    "resource_id": current["id"], "status": "success",
                    "detail": {"fields": sorted(clean)}})
        except PersistenceError: raise
        except Exception as e: raise StorageError(type(e).__name__) from e
        return updated

    def create_task(self, agent_name, tool_name, inputs=None, model=None, mission_id=None,
                    memory_used=None, actor="system", idempotency_key=None):
        agent = self.get_agent_by_name(agent_name)
        if agent is None: raise NotFoundError(f"agente no existe: {agent_name}")
        tool = self.get_tool_by_name(tool_name)
        if tool is None: raise NotFoundError(f"tool no existe: {tool_name}")
        allowed = agent.get("allowed_tools") or []
        if tool_name not in allowed:
            raise ValidationError(f"el agente {agent_name} no tiene permitido usar {tool_name}")
        data = {"agent_name": agent_name, "tool_name": tool_name, "status": "pending", "inputs": inputs or {}}
        if model is not None: data["model"] = model
        if mission_id is not None: data["mission_id"] = mission_id
        if memory_used is not None: data["memory_used"] = memory_used
        fields = validate_agent_task(data)
        record = dict(fields, id=new_id("task"), schema_version=AGENT_TASK_SCHEMA_VERSION)
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str) or not 0 < len(idempotency_key.strip()) <= 200:
                raise ValidationError("idempotency_key debe ser texto de 1 a 200 caracteres")
            record["idempotency_key"] = idempotency_key.strip()
        try:
            with self.repo.transaction() as tx:
                stored, created = tx.create("agent_tasks", record)
                tx.append_audit({"actor": actor,
                    "action": "agent.task.create" if created else "agent.task.create.already_synced",
                    "resource": "agent_tasks", "resource_id": stored["id"], "status": "success",
                    "detail": {"agent": agent_name, "tool": tool_name,
                               "mission_id": mission_id, "model": model}})
        except PersistenceError as e:
            self._audit_failure_generic(actor, "agent.task.create", "agent_tasks", None, e); raise
        except Exception as e:
            self._audit_failure_generic(actor, "agent.task.create", "agent_tasks", None, e)
            raise StorageError(type(e).__name__) from e
        verified = self.repo.get("agent_tasks", stored["id"])
        if verified is None: raise VerificationError("task no confirmada")
        return {"outcome": "created" if created else "already_synced", "record": verified}

    def start_task(self, task_id, actor="system"):
        task = self.repo.get("agent_tasks", task_id)
        if task is None: raise NotFoundError(task_id)
        if task.get("status") != "pending": raise ValidationError(f"tarea ya esta {task['status']}")
        changes = {"status": "running", "started_at": _now_iso()}
        current_action = f"ejecutando {task['tool_name']}"[:200]
        try:
            with self.repo.transaction() as tx:
                updated = tx.update("agent_tasks", task_id, changes, task["version"])
                agent = self.get_agent_by_name(task["agent_name"])
                if agent:
                    tx.update("agents", agent["id"],
                              {"status": "busy", "current_task_id": task_id,
                               "current_action": current_action, "last_active_at": _now_iso()},
                              agent["version"])
                tx.append_audit({"actor": actor, "action": "agent.task.start",
                    "resource": "agent_tasks", "resource_id": task_id, "status": "success",
                    "detail": {"agent": task["agent_name"], "tool": task["tool_name"]}})
        except PersistenceError: raise
        except Exception as e: raise StorageError(type(e).__name__) from e
        try: self.auto_connect_agent_tool(task["agent_name"], task["tool_name"], actor=actor)
        except Exception as e: print(f"[auto-connect] agent_tool fallo: {type(e).__name__}: {str(e)[:200]}")
        return updated

    def complete_task(self, task_id, outputs=None, duration_ms=0, memory_used=None, actor="system"):
        task = self.repo.get("agent_tasks", task_id)
        if task is None: raise NotFoundError(task_id)
        if task.get("status") not in ("pending", "running"):
            raise ValidationError(f"tarea ya esta {task['status']}")
        changes = {"status": "completed", "outputs": outputs or {},
                   "duration_ms": int(duration_ms), "completed_at": _now_iso()}
        if memory_used is not None: changes["memory_used"] = memory_used
        try:
            with self.repo.transaction() as tx:
                updated = tx.update("agent_tasks", task_id, changes, task["version"])
                agent = self.get_agent_by_name(task["agent_name"])
                if agent:
                    new_completed = int(agent.get("tasks_completed") or 0) + 1
                    tx.update("agents", agent["id"],
                              {"status": "idle", "current_task_id": None, "current_action": None,
                               "tasks_completed": new_completed, "last_active_at": _now_iso()},
                              agent["version"])
                tx.append_audit({"actor": actor, "action": "agent.task.complete",
                    "resource": "agent_tasks", "resource_id": task_id, "status": "success",
                    "detail": {"agent": task["agent_name"], "duration_ms": duration_ms}})
        except PersistenceError: raise
        except Exception as e: raise StorageError(type(e).__name__) from e
        return updated

    def fail_task(self, task_id, error, duration_ms=0, memory_used=None, actor="system"):
        task = self.repo.get("agent_tasks", task_id)
        if task is None: raise NotFoundError(task_id)
        if task.get("status") not in ("pending", "running"):
            raise ValidationError(f"tarea ya esta {task['status']}")
        err_dict = error if isinstance(error, dict) else {"message": str(error)[:200]}
        changes = {"status": "failed", "error": err_dict,
                   "duration_ms": int(duration_ms), "completed_at": _now_iso()}
        if memory_used is not None: changes["memory_used"] = memory_used
        try:
            with self.repo.transaction() as tx:
                updated = tx.update("agent_tasks", task_id, changes, task["version"])
                agent = self.get_agent_by_name(task["agent_name"])
                if agent:
                    new_failed = int(agent.get("tasks_failed") or 0) + 1
                    tx.update("agents", agent["id"],
                              {"status": "error", "current_task_id": None, "current_action": None,
                               "tasks_failed": new_failed, "last_active_at": _now_iso()},
                              agent["version"])
                tx.append_audit({"actor": actor, "action": "agent.task.fail",
                    "resource": "agent_tasks", "resource_id": task_id, "status": "failure",
                    "detail": {"agent": task["agent_name"]}})
        except PersistenceError: raise
        except Exception as e: raise StorageError(type(e).__name__) from e
        return updated

    def get_task(self, task_id):
        """Fix Neon+pooler: WHERE id a veces falla. Fallback a search sin filtro."""
        rec = self.repo.get("agent_tasks", task_id)
        if rec is not None:
            return rec
        try:
            rows = self.repo.search("agent_tasks", {}, limit=300)
            for r in rows:
                if r.get("id") == task_id:
                    return r
        except Exception:
            pass
        return None

    def list_tasks(self, agent_name=None, status=None, mission_id=None, limit=50):
        filters = {}
        if agent_name: filters["agent_name"] = agent_name
        if status: filters["status"] = status
        if mission_id: filters["mission_id"] = mission_id
        limit = max(1, min(int(limit), 200))
        return self.repo.search("agent_tasks", filters, limit=limit, offset=0,
                                order_by="created_at", descending=True)
    def count_tasks(self, filters=None): return self.repo.count("agent_tasks", filters or {})

    def _find_or_create_node(self, node_type, label, tags=None, actor="auto-connect"):
        label = str(label).strip()[:200]
        if not label: return None
        rows = self.repo.search("graph_nodes", {"node_type": node_type, "status": "active"}, limit=200)
        for r in rows:
            if str(r.get("label", "")).strip().lower() == label.lower():
                return r
        try:
            result = self.create_node({"node_type": node_type, "label": label, "tags": tags or []}, actor=actor)
            return result["record"]
        except Exception:
            return None

    def _edge_exists(self, from_node, to_node, relation_type):
        rows = self.repo.search("graph_edges", {"from_node": from_node, "to_node": to_node,
                                                 "relation_type": relation_type, "status": "active"}, limit=1)
        return rows[0] if rows else None

    def _upsert_edge(self, from_node, to_node, relation_type, delta_weight=0.5, actor="auto-connect"):
        if from_node == to_node: return None
        existing = self._edge_exists(from_node, to_node, relation_type)
        if existing:
            new_freq = int(existing.get("frequency") or 1) + 1
            new_weight = min(_AUTO_EDGE_MAX_WEIGHT, float(existing.get("weight") or 0.5) + delta_weight * 0.5)
            changes = {"frequency": new_freq, "weight": new_weight, "last_used_at": _now_iso()}
            try:
                with self.repo.transaction() as tx:
                    return tx.update("graph_edges", existing["id"], changes, existing["version"])
            except Exception:
                return None
        try:
            data = {"from_node": from_node, "to_node": to_node, "relation_type": relation_type,
                    "weight": delta_weight, "confidence": 0.5, "origin": "auto_connect"}
            r = self.create_edge(data, actor=actor)
            return r["record"]
        except Exception:
            return None

    def auto_connect_node_tags(self, node_id, actor="auto-connect"):
        node = self.repo.get("graph_nodes", node_id)
        if node is None or node.get("status") != "active": return {"connected": 0}
        my_tags = set(t.lower() for t in (node.get("tags") or []))
        if not my_tags: return {"connected": 0}
        my_privacy = node.get("privacy_level") or "PRIVATE"
        candidates = self.repo.search("graph_nodes", {"status": "active", "privacy_level": my_privacy}, limit=200)
        scored = []
        for c in candidates:
            if c["id"] == node_id: continue
            other_tags = set(t.lower() for t in (c.get("tags") or []))
            if not other_tags: continue
            shared = my_tags & other_tags
            if not shared: continue
            weight = _AUTO_TAG_WEIGHT_BASE + (_AUTO_TAG_WEIGHT_PER_EXTRA * (len(shared) - 1))
            scored.append((weight, c["id"], len(shared)))
        scored.sort(reverse=True)
        created = 0
        for weight, other_id, _s in scored[:_AUTO_MAX_CONNECTIONS]:
            r = self._upsert_edge(node_id, other_id, "related_to",
                                  delta_weight=min(weight, _AUTO_EDGE_MAX_WEIGHT), actor=actor)
            if r: created += 1
        return {"connected": created}

    def auto_connect_agent_tool(self, agent_name, tool_name, actor="auto-connect"):
        agent_node = self._find_or_create_node("person", f"agent:{agent_name}",
                                                tags=["agent", agent_name], actor=actor)
        tool_node = self._find_or_create_node("tool", f"tool:{tool_name}",
                                               tags=["tool", tool_name], actor=actor)
        if not agent_node or not tool_node: return {"connected": 0}
        edge = self._upsert_edge(agent_node["id"], tool_node["id"], "uses",
                                 delta_weight=_AUTO_AGENT_TOOL_WEIGHT, actor=actor)
        return {"agent_node": agent_node["id"], "tool_node": tool_node["id"],
                "edge": edge["id"] if edge else None}

    def auto_connect_learning(self, learning_id, actor="auto-connect"):
        learning = self.repo.get("learning_events", learning_id)
        if learning is None: return {"connected": 0}
        knowledge_nodes = learning.get("knowledge_nodes") or []
        if not knowledge_nodes: return {"connected": 0}
        learning_node = self._find_or_create_node(
            "experience", f"learning:{learning_id}",
            tags=["learning", str(learning.get("source", "unknown"))], actor=actor)
        if not learning_node: return {"connected": 0}
        connected = 0
        for kn_id in knowledge_nodes:
            if not self.repo.exists("graph_nodes", kn_id): continue
            edge = self._upsert_edge(learning_node["id"], kn_id, "learned_from",
                                     delta_weight=_AUTO_LEARNING_WEIGHT, actor=actor)
            if edge: connected += 1
        return {"learning_node": learning_node["id"], "connected": connected}

    def auto_connect_memory_tags(self, memory_id, actor="auto-connect"):
        memory = self.repo.get("memories", memory_id)
        if memory is None or memory.get("status") != "active": return {"connected": 0}
        tags = memory.get("tags") or []
        if not tags: return {"connected": 0}
        my_privacy = memory.get("privacy_level") or "PRIVATE"
        memory_node = self._find_or_create_node("experience", f"memory:{memory_id}", tags=tags, actor=actor)
        if not memory_node: return {"connected": 0}
        my_tags = set(t.lower() for t in tags)
        candidates = self.repo.search("graph_nodes", {"status": "active", "privacy_level": my_privacy}, limit=200)
        connected = 0
        for c in candidates:
            if c["id"] == memory_node["id"]: continue
            other_tags = set(t.lower() for t in (c.get("tags") or []))
            shared = my_tags & other_tags
            if not shared: continue
            edge = self._upsert_edge(memory_node["id"], c["id"], "related_to",
                                     delta_weight=_AUTO_MEMORY_WEIGHT, actor=actor)
            if edge: connected += 1
            if connected >= _AUTO_MAX_CONNECTIONS: break
        return {"memory_node": memory_node["id"], "connected": connected}

    def reinforce_frequent_pairs(self, actor="auto-connect", limit_nodes=200):
        core = self.ensure_core_node(actor=actor)
        core_id = core["id"] if core else None
        reinforced = 0
        frequent_pairs = 0
        try:
            memories = self.repo.search("memories", {"status": "active"}, limit=500,
                                        order_by="created_at", descending=True)
            from collections import Counter
            pair_counter = Counter()
            for m in memories:
                tags = sorted(set(t.lower() for t in (m.get("tags") or [])))
                for i in range(len(tags)):
                    for j in range(i + 1, len(tags)):
                        pair_counter[(tags[i], tags[j])] += 1
            frecuentes = [(pair, n) for pair, n in pair_counter.items() if n >= _AUTO_REINFORCE_MIN_FREQ]
            frequent_pairs = len(frecuentes)
            nodes = self.repo.search("graph_nodes", {"status": "active"}, limit=limit_nodes)
            tags_index = {}
            for n in nodes:
                for t in (n.get("tags") or []):
                    tags_index.setdefault(t.lower(), []).append(n["id"])
            for (tag_a, tag_b), freq in frecuentes:
                for a in tags_index.get(tag_a, [])[:3]:
                    for b in tags_index.get(tag_b, [])[:3]:
                        if a == b: continue
                        edge = self._upsert_edge(a, b, "related_to",
                                                 delta_weight=0.1 * (freq / _AUTO_REINFORCE_MIN_FREQ),
                                                 actor=actor)
                        if edge: reinforced += 1
        except Exception as e:
            print(f"[reinforce] pares fallo: {type(e).__name__}: {str(e)[:200]}")
        connected_to_core = 0
        if core_id:
            try:
                nodes = self.repo.search("graph_nodes", {"status": "active"}, limit=500)
                for n in nodes:
                    if n["id"] == core_id: continue
                    if (self._edge_exists(n["id"], core_id, "part_of") or
                        self._edge_exists(core_id, n["id"], "part_of")):
                        continue
                    r = self.connect_to_core(n["id"], actor=actor, weight=_CORE_EDGE_WEIGHT)
                    if r: connected_to_core += 1
            except Exception as e:
                print(f"[reinforce] conexion al nucleo fallo: {type(e).__name__}: {str(e)[:200]}")
        try:
            self.record_audit(actor, "graph.auto_connect.reinforce", "graph_edges",
                              None, "success", {"reinforced": reinforced,
                                                "frequent_pairs": frequent_pairs,
                                                "connected_to_core": connected_to_core,
                                                "core_id": core_id})
        except Exception:
            pass
        return {"reinforced": reinforced, "frequent_pairs": frequent_pairs,
                "connected_to_core": connected_to_core, "core_id": core_id}

    def ensure_core_node(self, actor="system"):
        try:
            rows = self.repo.search("graph_nodes", {"status": "active"}, limit=500)
        except Exception:
            return None
        for n in rows:
            if str(n.get("label", "")).strip() == _CORE_NODE_LABEL:
                return n
        try:
            r = self.create_node({
                "node_type": "project", "label": _CORE_NODE_LABEL,
                "description": "Nucleo del grafo cognitivo de Akira. Todo se conecta aqui.",
                "tags": list(_CORE_NODE_TAGS), "weight": _CORE_NODE_WEIGHT,
                "confidence": 1.0, "privacy_level": "PRIVATE",
            }, actor=actor)
            return r["record"]
        except Exception as e:
            print(f"[core] ensure_core_node fallo: {type(e).__name__}: {str(e)[:200]}")
            return None

    def connect_to_core(self, node_id, actor="system", weight=None):
        core = self.ensure_core_node(actor=actor)
        if not core or core["id"] == node_id: return None
        w = _CORE_EDGE_WEIGHT if weight is None else weight
        try:
            existing = self._edge_exists(node_id, core["id"], "part_of")
            if existing: return existing
            return self._upsert_edge(node_id, core["id"], "part_of", delta_weight=w, actor=actor)
        except Exception:
            return None

    def _validate_mission_transition(self, current, new):
        if current == new:
            return
        allowed = MISSION_STATUS_TRANSITIONS.get(current)
        if allowed is None:
            raise ValidationError(f"estado actual desconocido: {current!r}")
        if new not in allowed:
            raise ValidationError(f"transicion invalida: {current} -> {new} "
                                  f"(permitidos desde {current}: {list(allowed) or 'ninguno'})")

    def create_mission(self, data, actor="system", idempotency_key=None):
        fields = validate_mission(data)
        if "created_by" not in fields:
            fields["created_by"] = actor
        record = dict(fields, id=new_id("mission"), schema_version=MISSION_SCHEMA_VERSION)
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str) or not 0 < len(idempotency_key.strip()) <= 200:
                raise ValidationError("idempotency_key debe ser texto de 1 a 200 caracteres")
            record["idempotency_key"] = idempotency_key.strip()
        try:
            with self.repo.transaction() as tx:
                stored, created = tx.create("missions", record)
                tx.append_audit({"actor": actor,
                    "action": "mission.create" if created else "mission.create.already_synced",
                    "resource": "missions", "resource_id": stored["id"], "status": "success",
                    "detail": {"title": stored.get("title"), "flow_type": stored.get("flow_type"),
                               "priority": stored.get("priority")}})
        except PersistenceError as e:
            self._audit_failure_generic(actor, "mission.create", "missions", None, e); raise
        except Exception as e:
            self._audit_failure_generic(actor, "mission.create", "missions", None, e)
            raise StorageError(type(e).__name__) from e
        verified = self.repo.get("missions", stored["id"])
        if verified is None: raise VerificationError("mision no confirmada")
        return {"outcome": "created" if created else "already_synced", "record": verified}

    def get_mission(self, mission_id):
        """Fix Neon+pooler: WHERE id a veces falla. Fallback a search sin filtro."""
        rec = self.repo.get("missions", mission_id)
        if rec is not None:
            return rec
        try:
            rows = self.repo.search("missions", {}, limit=300)
            for r in rows:
                if r.get("id") == mission_id:
                    return r
        except Exception:
            pass
        return None

    def list_missions(self, status=None, flow_type=None, created_by=None, limit=50, offset=0,
                      order_by="created_at", descending=True):
        filters = {}
        if status: filters["status"] = status
        if flow_type: filters["flow_type"] = flow_type
        if created_by: filters["created_by"] = created_by
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))
        return self.repo.search("missions", filters, limit=limit, offset=offset,
                                order_by=order_by, descending=descending)

    def count_missions(self, filters=None):
        return self.repo.count("missions", filters or {})

    def update_mission_status(self, mission_id, new_status, expected_version, actor="system"):
        current = self.repo.get("missions", mission_id)
        if current is None: raise NotFoundError(mission_id)
        if new_status not in MISSION_STATUSES:
            raise ValidationError(f"status invalido: {new_status!r}")
        self._validate_mission_transition(current.get("status"), new_status)
        changes = {"status": new_status}
        if new_status == "running" and not current.get("started_at"):
            changes["started_at"] = _now_iso()
        if new_status in ("completed", "failed", "cancelled") and not current.get("completed_at"):
            changes["completed_at"] = _now_iso()
        try:
            with self.repo.transaction() as tx:
                updated = tx.update("missions", mission_id, changes, expected_version)
                tx.append_audit({"actor": actor,
                    "action": f"mission.status.{new_status}",
                    "resource": "missions", "resource_id": mission_id, "status": "success",
                    "detail": {"from": current.get("status"), "to": new_status,
                               "new_version": updated["version"]}})
        except PersistenceError as e:
            self._audit_failure_generic(actor, f"mission.status.{new_status}", "missions", mission_id, e); raise
        except Exception as e:
            self._audit_failure_generic(actor, f"mission.status.{new_status}", "missions", mission_id, e)
            raise StorageError(type(e).__name__) from e
        verified = self.repo.get("missions", mission_id)
        if (verified is None or verified["version"] != expected_version + 1
                or verified.get("status") != new_status):
            raise VerificationError("cambio de estado no confirmado al releer")
        return verified

    def update_mission_plan(self, mission_id, plan, expected_version, actor="system"):
        if not isinstance(plan, dict):
            raise ValidationError("plan debe ser un objeto (dict)")
        current = self.repo.get("missions", mission_id)
        if current is None: raise NotFoundError(mission_id)
        try:
            with self.repo.transaction() as tx:
                updated = tx.update("missions", mission_id, {"plan": plan}, expected_version)
                tx.append_audit({"actor": actor, "action": "mission.plan.update",
                    "resource": "missions", "resource_id": mission_id, "status": "success",
                    "detail": {"new_version": updated["version"],
                               "steps": len(plan.get("steps") or [])}})
        except PersistenceError as e:
            self._audit_failure_generic(actor, "mission.plan.update", "missions", mission_id, e); raise
        except Exception as e:
            self._audit_failure_generic(actor, "mission.plan.update", "missions", mission_id, e)
            raise StorageError(type(e).__name__) from e
        verified = self.repo.get("missions", mission_id)
        if verified is None or verified["version"] != expected_version + 1 or verified.get("plan") != plan:
            raise VerificationError("plan no confirmado al releer")
        return verified

    def complete_mission(self, mission_id, result=None, learning_refs=None, actor="system"):
        current = self.repo.get("missions", mission_id)
        if current is None: raise NotFoundError(mission_id)
        changes = {"status": "completed"}
        if result is not None:
            if not isinstance(result, dict):
                raise ValidationError("result debe ser un objeto (dict)")
            changes["result"] = result
        if learning_refs is not None:
            if not isinstance(learning_refs, list) or not all(isinstance(x, str) for x in learning_refs):
                raise ValidationError("learning_refs debe ser lista de textos")
            changes["learning_refs"] = learning_refs
        if not current.get("completed_at"):
            changes["completed_at"] = _now_iso()
        self._validate_mission_transition(current.get("status"), "completed")
        try:
            with self.repo.transaction() as tx:
                updated = tx.update("missions", mission_id, changes, current["version"])
                tx.append_audit({"actor": actor, "action": "mission.complete",
                    "resource": "missions", "resource_id": mission_id, "status": "success",
                    "detail": {"learning_refs_count": len(learning_refs or [])}})
        except PersistenceError as e:
            self._audit_failure_generic(actor, "mission.complete", "missions", mission_id, e); raise
        except Exception as e:
            self._audit_failure_generic(actor, "mission.complete", "missions", mission_id, e)
            raise StorageError(type(e).__name__) from e
        return self.repo.get("missions", mission_id)

    def fail_mission(self, mission_id, error, actor="system"):
        current = self.repo.get("missions", mission_id)
        if current is None: raise NotFoundError(mission_id)
        err_dict = error if isinstance(error, dict) else {"message": str(error)[:500]}
        changes = {"status": "failed", "result": {"error": err_dict}}
        if not current.get("completed_at"):
            changes["completed_at"] = _now_iso()
        self._validate_mission_transition(current.get("status"), "failed")
        try:
            with self.repo.transaction() as tx:
                updated = tx.update("missions", mission_id, changes, current["version"])
                tx.append_audit({"actor": actor, "action": "mission.fail",
                    "resource": "missions", "resource_id": mission_id, "status": "failure",
                    "detail": {"error_type": err_dict.get("type")}})
        except PersistenceError as e:
            self._audit_failure_generic(actor, "mission.fail", "missions", mission_id, e); raise
        except Exception as e:
            self._audit_failure_generic(actor, "mission.fail", "missions", mission_id, e)
            raise StorageError(type(e).__name__) from e
        return self.repo.get("missions", mission_id)

    def cancel_mission(self, mission_id, reason=None, actor="system"):
        current = self.repo.get("missions", mission_id)
        if current is None: raise NotFoundError(mission_id)
        changes = {"status": "cancelled"}
        if reason:
            changes["result"] = {"cancel_reason": str(reason)[:500]}
        if not current.get("completed_at"):
            changes["completed_at"] = _now_iso()
        self._validate_mission_transition(current.get("status"), "cancelled")
        try:
            with self.repo.transaction() as tx:
                updated = tx.update("missions", mission_id, changes, current["version"])
                tx.append_audit({"actor": actor, "action": "mission.cancel",
                    "resource": "missions", "resource_id": mission_id, "status": "success",
                    "detail": {"from": current.get("status"), "reason": (str(reason)[:200] if reason else None)}})
        except PersistenceError as e:
            self._audit_failure_generic(actor, "mission.cancel", "missions", mission_id, e); raise
        except Exception as e:
            self._audit_failure_generic(actor, "mission.cancel", "missions", mission_id, e)
            raise StorageError(type(e).__name__) from e
        return self.repo.get("missions", mission_id)

    # ============================================================
    # V8-Fase10.7.2: CONVERSACIONES
    # ============================================================
    def create_conversation(self, data, actor="system", idempotency_key=None):
        """Crea una conversacion. El title lo calcula el endpoint (primeros 50 chars del primer mensaje).
        created_by se auto-rellena desde el actor si no viene."""
        fields = validate_conversation(data)
        if "created_by" not in fields:
            fields["created_by"] = actor
        record = dict(fields, id=new_id("conv"), schema_version=CONVERSATION_SCHEMA_VERSION)
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str) or not 0 < len(idempotency_key.strip()) <= 200:
                raise ValidationError("idempotency_key debe ser texto de 1 a 200 caracteres")
            record["idempotency_key"] = idempotency_key.strip()
        try:
            with self.repo.transaction() as tx:
                stored, created = tx.create("conversations", record)
                tx.append_audit({"actor": actor,
                    "action": "conversation.create" if created else "conversation.create.already_synced",
                    "resource": "conversations", "resource_id": stored["id"], "status": "success",
                    "detail": {"title": stored.get("title"), "created_by": stored.get("created_by")}})
        except PersistenceError as e:
            self._audit_failure_generic(actor, "conversation.create", "conversations", None, e); raise
        except Exception as e:
            self._audit_failure_generic(actor, "conversation.create", "conversations", None, e)
            raise StorageError(type(e).__name__) from e
        verified = self.repo.get("conversations", stored["id"])
        if verified is None: raise VerificationError("conversacion no confirmada")
        return {"outcome": "created" if created else "already_synced", "record": verified}

    def get_conversation(self, conversation_id):
        """Fix Neon+pooler: WHERE id a veces falla. Fallback a search sin filtro."""
        rec = self.repo.get("conversations", conversation_id)
        if rec is not None:
            return rec
        try:
            rows = self.repo.search("conversations", {}, limit=300)
            for r in rows:
                if r.get("id") == conversation_id:
                    return r
        except Exception:
            pass
        return None

    def list_conversations(self, created_by=None, status=None, limit=50, offset=0,
                           order_by="last_message_at", descending=True):
        """Lista conversaciones del usuario. Por defecto ordena por last_message_at DESC
        (mas recientes primero). Si status=None, trae solo 'active'."""
        filters = {}
        if created_by: filters["created_by"] = created_by
        filters["status"] = status if status else "active"
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))
        return self.repo.search("conversations", filters, limit=limit, offset=offset,
                                order_by=order_by, descending=descending)

    def count_conversations(self, filters=None):
        return self.repo.count("conversations", filters or {})

    def update_conversation(self, conversation_id, changes, expected_version, actor="system"):
        """Actualiza titulo o status. No se puede cambiar created_by."""
        clean = validate_conversation(changes, partial=True)
        if isinstance(expected_version, bool) or not isinstance(expected_version, int) or expected_version < 1:
            raise ValidationError("expected_version debe ser un entero >= 1")
        try:
            with self.repo.transaction() as tx:
                updated = tx.update("conversations", conversation_id, clean, expected_version)
                tx.append_audit({"actor": actor, "action": "conversation.update",
                    "resource": "conversations", "resource_id": conversation_id, "status": "success",
                    "detail": {"fields": sorted(clean), "new_version": updated["version"]}})
        except NotFoundError as e:
            self._audit_failure_generic(actor, "conversation.update", "conversations", conversation_id, e); raise
        except PersistenceError as e:
            self._audit_failure_generic(actor, "conversation.update", "conversations", conversation_id, e); raise
        except Exception as e:
            self._audit_failure_generic(actor, "conversation.update", "conversations", conversation_id, e)
            raise StorageError(type(e).__name__) from e
        verified = self.repo.get("conversations", conversation_id)
        if (verified is None or verified["version"] != expected_version + 1
                or any(verified.get(k) != v for k, v in clean.items())):
            raise VerificationError("actualizacion de conversacion no confirmada")
        return verified

    def archive_conversation(self, conversation_id, expected_version=None, actor="system"):
        if expected_version is None:
            current = self.repo.get("conversations", conversation_id)
            if current is None: raise NotFoundError(conversation_id)
            expected_version = current["version"]
        return self.update_conversation(conversation_id, {"status": "archived"}, expected_version, actor)

    def add_message(self, conversation_id, role, content, model=None,
                    memories_used=None, duration_ms=0, error=None, actor="system",
                    idempotency_key=None):
        """Añade un mensaje a una conversacion. En la MISMA transaccion:
        - crea el mensaje (append-only)
        - actualiza conversations.message_count +1
        - actualiza conversations.last_message_at al ahora
        Devuelve {"record": mensaje, "conversation": conversacion_actualizada}."""
        current_conv = self.get_conversation(conversation_id)
        if current_conv is None:
            raise NotFoundError(f"conversacion no existe: {conversation_id}")
        if current_conv.get("status") != "active":
            raise ValidationError(f"la conversacion esta {current_conv.get('status')}")

        data = {"conversation_id": conversation_id, "role": role,
                "content": content, "duration_ms": int(duration_ms)}
        if model is not None: data["model"] = model
        if memories_used is not None: data["memories_used"] = memories_used
        if error is not None: data["error"] = error
        fields = validate_conversation_message(data)
        record = dict(fields, id=new_id("msg"), schema_version=CONVERSATION_MESSAGE_SCHEMA_VERSION)
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str) or not 0 < len(idempotency_key.strip()) <= 200:
                raise ValidationError("idempotency_key debe ser texto de 1 a 200 caracteres")
            record["idempotency_key"] = idempotency_key.strip()

        now_iso = _now_iso()
        new_count = int(current_conv.get("message_count") or 0) + 1

        try:
            with self.repo.transaction() as tx:
                stored_msg, created = tx.create("conversation_messages", record)
                updated_conv = tx.update("conversations", conversation_id,
                                         {"message_count": new_count, "last_message_at": now_iso},
                                         current_conv["version"])
                tx.append_audit({"actor": actor,
                    "action": "conversation.message.create" if created else "conversation.message.create.already_synced",
                    "resource": "conversation_messages", "resource_id": stored_msg["id"],
                    "status": "success",
                    "detail": {"conversation_id": conversation_id, "role": role,
                               "duration_ms": int(duration_ms),
                               "has_error": error is not None}})
        except PersistenceError as e:
            self._audit_failure_generic(actor, "conversation.message.create", "conversation_messages", None, e); raise
        except Exception as e:
            self._audit_failure_generic(actor, "conversation.message.create", "conversation_messages", None, e)
            raise StorageError(type(e).__name__) from e

        verified_msg = self.repo.get("conversation_messages", stored_msg["id"])
        if verified_msg is None: raise VerificationError("mensaje no confirmado")
        return {"record": verified_msg, "conversation": updated_conv}

    def list_messages(self, conversation_id, limit=200, offset=0):
        """Mensajes de una conversacion, orden ascendente (cronologico)."""
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        return self.repo.search("conversation_messages", {"conversation_id": conversation_id},
                                limit=limit, offset=offset, order_by="created_at", descending=False)

    def count_messages(self, conversation_id):
        return self.repo.count("conversation_messages", {"conversation_id": conversation_id})
