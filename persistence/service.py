"""PersistenceService: puerta unica a la persistencia de AKIRA.

V8-Fase5-9: self-model, learning, graph, cognitive, tools, agents.
Sub-fase 10.0: auto-conexion del grafo + nucleo Akira.
Sub-fase 10.2: misiones (CRUD + transiciones de estado validadas).
Sub-fase 10.7.2: persistencia de conversaciones (chats independientes + historial global).
"""
from __future__ import annotations

import datetime as _dt
import hashlib

from identity_root import get_identity_root
from persistence.capability import (
    CapabilityContractError,
    CAPABILITY_SCHEMA_VERSION,
    CAPABILITY_VERIFICATION_SCHEMA_VERSION,
    apply_verification_result,
    capability_state_snapshot,
    derive_effective_state,
    validate_capability,
    validate_capability_transition,
    validate_capability_verification,
)

from .model_registry import model_registry_snapshot

from .core import (AGENT_SCHEMA_VERSION, AGENT_TASK_SCHEMA_VERSION,
                   COGNITIVE_CYCLE_SCHEMA_VERSION, COGNITIVE_EVENT_SCHEMA_VERSION,
                   COGNITIVE_STAGES, CONVERSATION_MESSAGE_SCHEMA_VERSION,
                   CONVERSATION_SCHEMA_VERSION, GRAPH_EDGE_SCHEMA_VERSION,
                   GRAPH_NODE_SCHEMA_VERSION, HIVE_VISIBLE, LEARNING_SCHEMA_VERSION, RELATION_TYPES,
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
_SYNTHETIC_MEMORY_SOURCES = frozenset({"selftest", "semantic_selftest", "persistent_memory_selftest"})

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
    "identity": {"name": "Akira", "creator": "Jhon Grimm",
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
    "models": model_registry_snapshot()["routes"],
    "current_state": {}, "knowledge_state": {},
    "uncertainties": [
        {
            "id": "uncertainty_consciousness",
            "statement": "No hay pruebas de conciencia subjetiva.",
            "kind": "evidence",
            "status": "open",
            "evidence": [],
            "created_at": None,
        },
        {
            "id": "uncertainty_provider_quality",
            "statement": "La calidad de las respuestas depende del proveedor externo.",
            "kind": "capability",
            "status": "open",
            "evidence": [],
            "created_at": "2026-10-06T00:00:00+00:00",
        },
        {
            "id": "uncertainty_graph_consolidation",
            "statement": "El grafo tiene auto-conexion por tags, agentes y learning, pero falta consolidacion y pruning.",
            "kind": "knowledge",
            "status": "open",
            "evidence": [],
            "created_at": "2026-10-06T00:00:00+00:00",
        },
        {
            "id": "uncertainty_missions",
            "statement": "Los agentes existen; las misiones estan en construccion (Fase 10).",
            "kind": "capability",
            "status": "open",
            "evidence": [],
            "created_at": "2026-10-06T00:00:00+00:00",
        },
        {
            "id": "uncertainty_r2_write",
            "statement": "R2 tiene arquitectura preparada pero sin escritura real verificada.",
            "kind": "runtime",
            "status": "open",
            "evidence": [],
            "created_at": "2026-10-06T00:00:00+00:00",
        },
    ],
    "errors": [], "repairs": [], "evolution": [],
}

def _now_iso():
    return _dt.datetime.now(_dt.timezone.utc).isoformat()

LEGACY_OWNER_SCOPE = "owner"

def _scope_matches(record_scope, owner_scope):
    if owner_scope is None:
        return True
    requested = str(owner_scope).strip()
    stored = str(record_scope or "").strip()
    return bool(requested) and (stored == requested or stored == LEGACY_OWNER_SCOPE)

def _task_scope_filters(owner_scope):
    if owner_scope is None:
        return {}
    scope = str(owner_scope).strip()
    if not scope:
        raise ValidationError("owner_scope requerido")
    scopes = [scope]
    if scope != LEGACY_OWNER_SCOPE:
        scopes.append(LEGACY_OWNER_SCOPE)
    return {"owner_scope__in": scopes}

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

    def save_memory(self, data, actor="system", idempotency_key=None, owner_scope=None):
        fields = validate_memory(data)
        if owner_scope is not None:
            scope = str(owner_scope).strip()
            if not scope:
                raise ValidationError("owner_scope requerido")
            fields["owner_scope"] = scope
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
        if (
            verified is None
            or (
                owner_scope is not None
                and str(verified.get("owner_scope") or "").strip() != str(owner_scope).strip()
            )
        ):
            conflict = ConflictError("idempotency key pertenece a otro owner_scope")
            self._audit_failure_generic(actor, "memory.create", "memories", stored.get("id"), conflict)
            raise conflict
        if verified is None:
            raise VerificationError("escritura no confirmada")
        expected = stored if not created else fields
        for f in _COMPARE_FIELDS:
            if verified.get(f) != expected.get(f, verified.get(f)):
                raise VerificationError(f"campo {f} no coincide al releer")
        result = {"outcome": "created" if created else "already_synced", "record": verified}
        if created and str(verified.get("source") or "") not in {
            "learning_candidate", "learning_engine", "learning_promoted"
        } and str(verified.get("source") or "") not in _SYNTHETIC_MEMORY_SOURCES:
            try:
                self.auto_connect_memory_tags(
                    verified["id"],
                    actor=actor,
                    owner_scope=verified.get("owner_scope"),
                )
            except Exception as e:
                print(f"[auto-connect] memory_tags fallo: {type(e).__name__}: {str(e)[:200]}")
        return result

    def get_memory(self, memory_id, owner_scope=None):
        memory = self.repo.get("memories", memory_id)
        if memory is None or owner_scope is None:
            return memory
        return memory if _scope_matches(memory.get("owner_scope"), owner_scope) else None
    def get_memory_embedding(self, memory_id, owner_scope=None):
        memory = self.get_memory(memory_id, owner_scope=owner_scope)
        if memory is None:
            return None
        getter = getattr(self.repo, "get_memory_embedding", None)
        if getter is None:
            return None
        return getter(memory_id)

    def upsert_memory_embedding(self, memory_id, model, embedding, source_hash, owner_scope=None):
        memory = self.get_memory(memory_id, owner_scope=owner_scope)
        if memory is None:
            raise NotFoundError(memory_id)
        if memory.get("status") != "active":
            raise ValidationError("solo memorias activas pueden tener embedding")
        if not isinstance(embedding, (list, tuple)) or len(embedding) != 768:
            raise ValidationError("embedding debe tener 768 dimensiones")
        getter = getattr(self.repo, "upsert_memory_embedding", None)
        if getter is None:
            raise StorageError("vector_repository_not_available")
        return getter(memory_id, model, embedding, source_hash)

    def search_memory_semantic(self, embedding, model, limit=20, owner_scope=None):
        if not isinstance(embedding, (list, tuple)) or len(embedding) != 768:
            raise ValidationError("embedding debe tener 768 dimensiones")
        searcher = getattr(self.repo, "search_memory_embeddings", None)
        if searcher is None:
            return []
        if owner_scope is not None:
            return searcher(embedding, model, limit=limit, owner_scope=owner_scope)
        return searcher(embedding, model, limit=limit)

    def delete_memory_embedding(self, memory_id, owner_scope=None):
        memory = self.get_memory(memory_id, owner_scope=owner_scope)
        if memory is None:
            return False
        deleter = getattr(self.repo, "delete_memory_embedding", None)
        if deleter is None:
            return False
        return deleter(memory_id)

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
    def search_memory(self, filters=None, hive=False, limit=50, offset=0, order_by="created_at", descending=True, owner_scope=None):
        limit = max(1, min(int(limit), 200))
        base = self._memory_filters(filters, hive)
        if owner_scope is None:
            return self.repo.search("memories", base, limit=limit,
                                    offset=max(0, int(offset)), order_by=order_by, descending=descending)
        scope = str(owner_scope).strip()
        if not scope:
            raise ValidationError("owner_scope requerido")
        scoped = dict(base)
        scoped.pop("owner_scope", None)
        scoped.pop("owner_scope__in", None)
        allowed_scopes = [scope]
        if scope != LEGACY_OWNER_SCOPE:
            allowed_scopes.append(LEGACY_OWNER_SCOPE)
        scoped["owner_scope__in"] = allowed_scopes
        return self.repo.search(
            "memories",
            scoped,
            limit=limit,
            offset=max(0, int(offset)),
            order_by=order_by,
            descending=descending,
        )

    def count_memory(self, filters=None, hive=False, owner_scope=None):
        base = self._memory_filters(filters, hive)
        if owner_scope is None:
            return self.repo.count("memories", base)
        scope = str(owner_scope).strip()
        if not scope:
            raise ValidationError("owner_scope requerido")
        scoped = dict(base)
        scoped.pop("owner_scope", None)
        scoped.pop("owner_scope__in", None)
        allowed_scopes = [scope]
        if scope != LEGACY_OWNER_SCOPE:
            allowed_scopes.append(LEGACY_OWNER_SCOPE)
        scoped["owner_scope__in"] = allowed_scopes
        return self.repo.count("memories", scoped)
    def health(self): return self.repo.ping()

    def get_identity_root(self):
        return get_identity_root()

    def get_self_model(self):
        current = self.repo.get("self_model", SELF_MODEL_PRIMARY_ID)
        if current is not None:
            persisted_fields = (
                "purpose", "current_state", "knowledge_state",
                "uncertainties", "errors", "repairs", "evolution",
            )
            persisted = {field: current.get(field) for field in persisted_fields if field in current}
            validate_self_model(persisted, partial=True)
            current["identity"] = self.get_identity_root()
            current["capabilities"] = self.capabilities_for_self_model(limit=200)
            current["tools"] = [
                {
                    "name": t.get("name"),
                    "category": t.get("category"),
                    "status": t.get("status"),
                    "permissions": list(t.get("permissions") or []),
                }
                for t in self.repo.search(
                    "tools", {}, limit=200, order_by="name", descending=False,
                )
            ]
            current["models"] = model_registry_snapshot()["routes"]
            return current
        identity = self.get_identity_root()
        record = {"id": SELF_MODEL_PRIMARY_ID, "schema_version": SELF_MODEL_SCHEMA_VERSION,
                  "idempotency_key": f"{SELF_MODEL_PRIMARY_ID}_v1"}
        for field, value in _SELF_MODEL_DEFAULTS.items():
            record[field] = value
        record["uncertainties"] = [
            dict(item, created_at=_now_iso())
            if isinstance(item, dict) else item
            for item in (record.get("uncertainties") or [])
        ]
        record["identity"] = identity
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
        verified["identity"] = identity
        verified["capabilities"] = self.capabilities_for_self_model(limit=200)
        verified["tools"] = [
            {
                "name": t.get("name"),
                "category": t.get("category"),
                "status": t.get("status"),
                "permissions": list(t.get("permissions") or []),
            }
            for t in self.repo.search("tools", {}, limit=200, order_by="name", descending=False)
        ]
        verified["models"] = model_registry_snapshot()["routes"]
        return verified
    def update_self_model(self, changes, expected_version, actor="system"):
        if not isinstance(changes, dict):
            raise ValidationError("self-model changes debe ser un objeto")
        manual_derived = sorted(set(changes) & {"capabilities", "tools", "models"})
        if manual_derived:
            raise ValidationError(f"campos derivados, no editables: {manual_derived}")
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


    # ---------- CAPABILITY ENGINE ----------
    def create_capability(self, data, actor="system", idempotency_key=None):
        try:
            clean = validate_capability(data)
        except CapabilityContractError as exc:
            raise ValidationError(str(exc)) from exc
        if clean.get("verification_state") != "unverified":
            raise ValidationError("una capability nueva no puede declararse verified")
        try:
            state = capability_state_snapshot(clean)
            validate_capability_transition(state, state)
        except CapabilityContractError as exc:
            raise ValidationError(str(exc)) from exc
        record = dict(
            clean,
            id=new_id("cap"),
            schema_version=CAPABILITY_SCHEMA_VERSION,
            last_verification_id=None,
            last_verified_at=None,
        )
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str) or not 0 < len(idempotency_key.strip()) <= 200:
                raise ValidationError("idempotency_key debe ser texto de 1 a 200 caracteres")
            record["idempotency_key"] = idempotency_key.strip()
        try:
            with self.repo.transaction() as tx:
                stored, created = tx.create("capabilities", record)
                tx.append_audit({
                    "actor": actor,
                    "action": "capability.create" if created else "capability.create.already_synced",
                    "resource": "capabilities",
                    "resource_id": stored["id"],
                    "status": "success",
                    "detail": {"name": stored.get("name")},
                })
        except PersistenceError as exc:
            self._audit_failure_generic(actor, "capability.create", "capabilities", None, exc)
            raise
        except Exception as exc:
            self._audit_failure_generic(actor, "capability.create", "capabilities", None, exc)
            raise StorageError(type(exc).__name__) from exc
        verified = self.repo.get("capabilities", stored["id"])
        if verified is None:
            raise VerificationError("capability no confirmada")
        return {"outcome": "created" if created else "already_synced", "record": verified}

    def get_capability(self, capability_id):
        return self.repo.get("capabilities", capability_id)

    def list_capabilities(self, filters=None, limit=100, offset=0):
        limit = max(1, min(int(limit), 200))
        return self.repo.search(
            "capabilities",
            filters or {},
            limit=limit,
            offset=max(0, int(offset)),
            order_by="name",
            descending=False,
        )

    def get_capability_verifications(self, capability_id, limit=100, offset=0):
        if self.get_capability(capability_id) is None:
            raise NotFoundError(capability_id)
        limit = max(1, min(int(limit), 200))
        return self.repo.search(
            "capability_verifications",
            {"capability_id": capability_id},
            limit=limit,
            offset=max(0, int(offset)),
            order_by="created_at",
            descending=True,
        )

    def capability_state(self, capability_id):
        capability = self.get_capability(capability_id)
        if capability is None:
            raise NotFoundError(capability_id)
        state = capability_state_snapshot(capability)
        return {
            "capability": capability,
            "state": state,
            "effective_state": derive_effective_state(capability),
        }

    def capabilities_for_self_model(self, limit=200):
        rows = self.list_capabilities(limit=limit)
        return [
            {
                "name": row["name"],
                "effective_state": derive_effective_state(row),
                "implementation_state": row["implementation_state"],
                "verification_state": row["verification_state"],
                "availability_state": row["availability_state"],
                "maturity": row["maturity"],
                "cost_compatibility": row["cost_compatibility"],
                "last_verified_at": row.get("last_verified_at"),
            }
            for row in rows
        ]

    def self_knowledge_snapshot(self, owner_scope=None, limit=200):
        """Construye autoconocimiento operativo desde fuentes autoritativas en tiempo real."""
        identity_root = self.get_identity_root()
        capabilities = self.capabilities_for_self_model(limit=limit)
        agents = self.repo.search(
            "agents", {}, limit=min(max(int(limit), 1), 200),
            order_by="name", descending=False,
        )
        tools = self.repo.search(
            "tools", {}, limit=min(max(int(limit), 1), 200),
            order_by="name", descending=False,
        )
        memory_count = None
        if owner_scope is not None:
            memory_count = self.count_memory(owner_scope=owner_scope)

        return {
            "source": "runtime_authoritative_registry",
            "identity": identity_root,
            "identity_authority": "identity_root",
            "capabilities": capabilities,
            "agents": [
                {
                    "name": a.get("name"),
                    "role": a.get("role"),
                    "status": a.get("status"),
                    "allowed_tools": list(a.get("allowed_tools") or []),
                }
                for a in agents
            ],
            "tools": [
                {
                    "name": t.get("name"),
                    "category": t.get("category"),
                    "status": t.get("status"),
                    "permissions": list(t.get("permissions") or []),
                }
                for t in tools
            ],
            "memory_active_count": memory_count,
            "limitations": [
                "Los estados de capability proceden del Capability Engine y su evidencia persistida.",
                "La existencia de un agente o tool no demuestra por sí sola calidad E2E.",
                "Los proveedores/modelos externos son motores de inferencia y no la identidad de Akira.",
            ],
        }

    def record_capability_verification(self, capability_id, data, actor="system", idempotency_key=None):
        capability = self.get_capability(capability_id)
        if capability is None:
            raise NotFoundError(capability_id)
        try:
            event = validate_capability_verification(data)
            before = capability_state_snapshot(capability)
            after = apply_verification_result(capability, event)
            validate_capability_transition(before, after)
        except CapabilityContractError as exc:
            raise ValidationError(str(exc)) from exc

        record = dict(
            event,
            id=new_id("capver"),
            capability_id=capability_id,
            state_before=before,
            state_after=after,
            schema_version=CAPABILITY_VERIFICATION_SCHEMA_VERSION,
            version=1,
        )
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str) or not 0 < len(idempotency_key.strip()) <= 200:
                raise ValidationError("idempotency_key debe ser texto de 1 a 200 caracteres")
            record["idempotency_key"] = idempotency_key.strip()

        try:
            with self.repo.transaction() as tx:
                stored, created = tx.create("capability_verifications", record)
                if not created:
                    current = tx.get("capabilities", capability_id)
                    if current is None:
                        raise VerificationError("capability no encontrada al sincronizar verification")
                    return {
                        "outcome": "already_synced",
                        "record": stored,
                        "capability": current,
                        "effective_state": derive_effective_state(current),
                    }
                changes = {
                    "verification_state": after["verification_state"],
                    "availability_state": after["availability_state"],
                    "last_verification_id": stored["id"],
                }
                if (
                    event["event_type"] in ("verification", "revalidation")
                    and event["result"] == "pass"
                ):
                    changes["last_verified_at"] = _now_iso()
                updated = tx.update(
                    "capabilities",
                    capability_id,
                    changes,
                    capability["version"],
                )
                tx.append_audit({
                    "actor": actor,
                    "action": (
                        "capability.verification"
                        if event["result"] == "pass"
                        else (
                            "capability.verification.failed"
                            if event["result"] == "fail"
                            else "capability.verification.inconclusive"
                        )
                    ),
                    "resource": "capabilities",
                    "resource_id": capability_id,
                    "status": "success" if event["result"] == "pass" else "failure",
                    "detail": {
                        "verification_id": stored["id"],
                        "event_type": event["event_type"],
                        "result": event["result"],
                        "effective_state": derive_effective_state(updated),
                    },
                })
        except PersistenceError:
            raise
        except Exception as exc:
            self._audit_failure_generic(
                actor,
                "capability.verification",
                "capabilities",
                capability_id,
                exc,
            )
            raise StorageError(type(exc).__name__) from exc

        verified_capability = self.repo.get("capabilities", capability_id)
        verified_event = self.repo.get("capability_verifications", stored["id"])
        if verified_capability is None or verified_event is None:
            raise VerificationError("capability verification no confirmada")
        if verified_capability.get("version") != capability["version"] + 1:
            raise VerificationError("capability version no confirmada")
        if capability_state_snapshot(verified_capability) != after:
            raise VerificationError("estado de capability no coincide al releer")
        if verified_event.get("state_after") != after:
            raise VerificationError("state_after no coincide al releer")
        return {
            "outcome": "created",
            "record": verified_event,
            "capability": verified_capability,
            "effective_state": derive_effective_state(verified_capability),
        }

    def update_capability_availability(self, capability_id, availability_state, evidence,
                                       actor="system", idempotency_key=None):
        return self.record_capability_verification(
            capability_id,
            {
                "event_type": "availability_check",
                "test_key": "availability_check",
                "test_version": "v1",
                "result": "pass",
                "evidence": evidence,
                "observed_availability_state": availability_state,
                "actor": actor,
                "executor": actor,
                "evaluator": "system",
            },
            actor=actor,
            idempotency_key=idempotency_key,
        )

    def invalidate_capability(self, capability_id, evidence, actor="system", reason="",
                              idempotency_key=None):
        error = {"reason": reason[:1000]} if isinstance(reason, str) and reason.strip() else None
        return self.record_capability_verification(
            capability_id,
            {
                "event_type": "invalidation",
                "test_key": "capability_invalidation",
                "test_version": "v1",
                "result": "fail",
                "evidence": evidence,
                "error": error,
                "actor": actor,
                "executor": actor,
                "evaluator": "system",
            },
            actor=actor,
            idempotency_key=idempotency_key,
        )

    def save_learning(self, data, actor="system", idempotency_key=None, owner_scope=None):
        fields = validate_learning_event(data)
        scope = str(owner_scope).strip() if owner_scope is not None else LEGACY_OWNER_SCOPE
        if not scope:
            raise ValidationError("owner_scope requerido")
        record = dict(fields, owner_scope=scope, id=new_id("learn"), schema_version=LEARNING_SCHEMA_VERSION)
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
            try: self.auto_connect_learning(verified["id"], actor=actor, owner_scope=verified.get("owner_scope"))
            except Exception as e: print(f"[auto-connect] learning fallo: {type(e).__name__}: {str(e)[:200]}")
        return {"outcome": "created" if created else "already_synced", "record": verified}

    def update_learning(self, learning_id, changes, expected_version=None, actor="system", owner_scope=None):
        current = self.get_learning(learning_id, owner_scope=owner_scope)
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
        verified = self.get_learning(learning_id, owner_scope=owner_scope)
        if verified is None or verified["version"] != expected_version + 1:
            raise VerificationError("learning update no confirmado")
        return verified

    def add_learning_evidence(self, learning_id, evidence, expected_version=None, actor="system", owner_scope=None):
        current = self.get_learning(learning_id, owner_scope=owner_scope)
        if current is None:
            raise NotFoundError(learning_id)
        clean = validate_learning_event({"evidence": evidence}, partial=True)
        incoming = clean["evidence"]
        existing = list(current.get("evidence") or [])
        merged = existing + [item for item in incoming if item not in existing]
        if not incoming:
            raise ValidationError("evidence requerida")
        if expected_version is None:
            expected_version = current["version"]
        return self.update_learning(learning_id, {"evidence": merged},
                                     expected_version=expected_version, actor=actor,
                                     owner_scope=owner_scope)

    def update_learning_status(self, learning_id, status, expected_version=None, actor="system", owner_scope=None):
        current = self.get_learning(learning_id, owner_scope=owner_scope)
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
        if next_status in ("verified", "consolidated") and not (current.get("evidence") or []):
            raise ValidationError("no se puede verificar/consolidar un aprendizaje sin evidencia")
        if next_status == "consolidated":
            analysis = current.get("verification_analysis")
            verdict = analysis.get("verdict") if isinstance(analysis, dict) else None
            try:
                eval_confidence = float(analysis.get("confidence", 0.0)) if isinstance(analysis, dict) else 0.0
            except Exception:
                eval_confidence = 0.0
            if verdict != "supported" or eval_confidence < 0.70:
                raise ValidationError(
                    "no se puede consolidar un aprendizaje sin evaluacion supported con confianza >= 0.70"
                )
        if expected_version is None:
            expected_version = current["version"]
        if current.get("status") == clean["status"]:
            return current
        status_changes = dict(clean)
        if next_status in ("verified", "consolidated"):
            status_changes["verified_at"] = _now_iso()
            status_changes["verified_by"] = actor
        elif next_status in ("conflicted", "obsolete", "discarded"):
            status_changes["verified_at"] = None
            status_changes["verified_by"] = None
        try:
            with self.repo.transaction() as tx:
                updated = tx.update("learning_events", learning_id, status_changes, expected_version)
                tx.append_audit({"actor": actor, "action": "learning.status.update",
                    "resource": "learning_events", "resource_id": learning_id, "status": "success",
                    "detail": {"status": status_changes["status"], "new_version": updated["version"]}})
        except PersistenceError:
            raise
        except Exception as e:
            raise StorageError(type(e).__name__) from e
        verified = self.get_learning(learning_id, owner_scope=owner_scope)
        if verified is None or verified.get("status") != clean["status"]:
            raise VerificationError("learning status no confirmado")
        return verified

    def promote_learning_to_graph(self, learning_id, actor="learning-promotion", owner_scope=None):
        """Materializa un aprendizaje verificado/consolidado en memoria + grafo de forma idempotente."""
        learning = self.get_learning(learning_id, owner_scope=owner_scope)
        if learning is None:
            raise NotFoundError(learning_id)

        status = learning.get("status") or "candidate"
        if status != "consolidated":
            return {"promoted": False, "reason": "status_not_eligible", "status": status}
        if not (learning.get("evidence") or []):
            return {"promoted": False, "reason": "evidence_required", "status": status}
        analysis = learning.get("verification_analysis")
        verdict = analysis.get("verdict") if isinstance(analysis, dict) else None
        try:
            eval_confidence = float(analysis.get("confidence", 0.0)) if isinstance(analysis, dict) else 0.0
        except Exception:
            eval_confidence = 0.0
        if verdict != "supported" or eval_confidence < 0.70:
            return {
                "promoted": False,
                "reason": "verification_not_sufficient",
                "status": status,
            }

        effective_scope = str(owner_scope or learning.get("owner_scope") or LEGACY_OWNER_SCOPE).strip()
        source = str(learning.get("source") or "learning").strip()[:64]
        outcome = str(learning.get("outcome") or "unknown").strip()[:32]
        lesson = str(learning.get("lesson") or "").strip()
        context = learning.get("learning_context") if isinstance(learning.get("learning_context"), dict) else {}
        if not lesson:
            raise ValidationError("learning sin lesson")

        tags = context.get("tags") if isinstance(context.get("tags"), list) else ["learning", source, outcome]
        tags = [str(x).strip()[:64] for x in tags if str(x).strip()][:20]
        if "learning" not in tags:
            tags.insert(0, "learning")
        if source not in tags:
            tags.append(source)
        if outcome not in tags:
            tags.append(outcome)
        tags = list(dict.fromkeys(tags))[:20]

        memories = self.repo.search(
            "memories",
            {"source_id": learning_id, "status": "active"},
            limit=10,
            order_by="created_at",
            descending=True,
        )
        memory = memories[0] if memories else None
        if memory is None:
            memory_result = self.save_memory({
                "content": lesson,
                "memory_type": str(context.get("memory_type") or "semantic"),
                "importance": int(context.get("importance") or 7),
                "confidence": float(learning.get("confidence") or 0.5),
                "source": "learning_promoted",
                "source_id": learning_id,
                "source_reference": str(context.get("source_reference") or source)[:500],
                "tags": tags,
                "privacy_level": str(context.get("privacy_level") or "PRIVATE"),
                "owner_scope": effective_scope,
            }, actor=actor, idempotency_key=f"learning_promoted_mem:{learning_id}")
            memory = memory_result["record"]
        else:
            # A legacy candidate memory can become recallable after verification.
            # Bring its tags forward without changing its immutable provenance fields.
            current_tags = memory.get("tags") if isinstance(memory.get("tags"), list) else []
            merged_tags = list(dict.fromkeys([str(x).strip()[:64] for x in current_tags + tags if str(x).strip()]))[:20]
            if merged_tags != current_tags:
                try:
                    with self.repo.transaction() as tx:
                        memory = tx.update("memories", memory["id"], {"tags": merged_tags}, memory["version"])
                except Exception:
                    memory = self.repo.get("memories", memory["id"]) or memory

        node = None
        knowledge_nodes = []
        for value in (learning.get("knowledge_nodes") or []) + (context.get("knowledge_node_ids") or []):
            value = str(value).strip()
            if value and value not in knowledge_nodes:
                knowledge_nodes.append(value)
        # Reuse only a node explicitly materialized for THIS learning.
        # Context/source nodes (especially the permanent Akira core) are inputs,
        # not the learning node itself.
        for node_id in knowledge_nodes:
            candidate = self.get_node(node_id)
            metadata = (
                candidate.get("node_metadata")
                if isinstance(candidate, dict) and isinstance(candidate.get("node_metadata"), dict)
                else {}
            )
            if (
                candidate
                and candidate.get("status") == "active"
                and str(metadata.get("learning_id") or "") == str(learning_id)
                and str(candidate.get("label") or "").strip() != _CORE_NODE_LABEL
            ):
                node = candidate
                break

        node_type = str(context.get("node_type") or "").strip() or (
            "experience" if source in ("experience_feedback", "autonomous_experience", "cognitive_cycle") else "concept"
        )
        if node_type not in ("concept", "person", "project", "tool", "experience", "document", "skill", "error", "solution", "mission"):
            node_type = "experience" if source in ("experience_feedback", "autonomous_experience", "cognitive_cycle") else "concept"
        label = str(context.get("label") or lesson.splitlines()[-1].strip() or lesson[:120]).strip()[:120]

        if node is None:
            node_result = self.create_node({
                "node_type": node_type,
                "label": label,
                "description": lesson[:1000],
                "node_metadata": {
                    "knowledge_kind": "verified_learning",
                    "learning_id": learning_id,
                    "memory_id": memory.get("id"),
                    "learning_status": status,
                    "learning_source": source,
                    "suppress_tag_auto_connect": True,
                },
                "tags": tags,
                "weight": 1.0,
                "confidence": float(learning.get("confidence") or 0.5),
                "privacy_level": str(context.get("privacy_level") or "PRIVATE"),
                "owner_scope": effective_scope,
            }, actor=actor, idempotency_key=f"learning_graph_node:{learning_id}")
            node = node_result["record"]
        else:
            metadata = node.get("node_metadata") if isinstance(node.get("node_metadata"), dict) else {}
            metadata.update({
                "knowledge_kind": "verified_learning",
                "learning_id": learning_id,
                "memory_id": memory.get("id"),
                "learning_status": status,
                "learning_source": source,
            })
            try:
                updated_node = self.update_node(
                    node["id"],
                    {"node_metadata": metadata, "tags": tags},
                    expected_version=node["version"],
                    actor=actor,
                    owner_scope=effective_scope,
                )
                node = updated_node
            except (ConflictError, ValidationError):
                node = self.get_node(node["id"]) or node

        if node.get("id") not in knowledge_nodes:
            knowledge_nodes.append(node["id"])

        # Determine real graph context. Explicit relationships win; otherwise
        # connect the learning node to known source nodes using learned_from.
        relationship_specs = []
        for rel in (learning.get("relationships") or []):
            if not isinstance(rel, dict):
                continue
            from_node = str(rel.get("from_node") or "").strip()
            to_node = str(rel.get("to_node") or "").strip()
            relation_type = str(rel.get("relation_type") or "").strip()
            if not from_node or not to_node or relation_type not in RELATION_TYPES:
                continue
            relationship_specs.append({
                "from_node": from_node,
                "to_node": to_node,
                "relation_type": relation_type,
                "weight": float(rel.get("weight") or 0.8),
                "confidence": float(rel.get("confidence") or 0.7),
                "origin": str(rel.get("origin") or "learning")[:64],
            })

        mission_id = str(context.get("mission_id") or "").strip()
        if not relationship_specs:
            source_nodes = [x for x in knowledge_nodes if x != node["id"] and self.repo.exists("graph_nodes", x)]
            if not source_nodes and mission_id:
                mission_node_result = self.create_node({
                    "node_type": "mission",
                    "label": f"mission:{mission_id}"[:200],
                    "description": "Misión de la que se obtuvo este aprendizaje.",
                    "node_metadata": {
                        "mission_id": mission_id,
                        "learning_context": True,
                        "suppress_tag_auto_connect": True,
                    },
                    "tags": ["mission", "learning_source"],
                    "weight": 1.0,
                    "confidence": 0.5,
                    "privacy_level": "PRIVATE",
                }, actor=actor, idempotency_key=f"learning_mission_node:{mission_id}",
                   owner_scope=effective_scope)
                mission_node = mission_node_result["record"]
                source_nodes = [mission_node["id"]]
                if mission_node["id"] not in knowledge_nodes:
                    knowledge_nodes.append(mission_node["id"])
            for target in source_nodes[:10]:
                relationship_specs.append({
                    "from_node": node["id"],
                    "to_node": target,
                    "relation_type": "learned_from",
                    "weight": 0.8,
                    "confidence": float(learning.get("confidence") or 0.5),
                    "origin": "learning_promotion",
                })

        canonical_relationships = []
        edges = []
        for rel in relationship_specs:
            from_node = rel["from_node"] if rel["from_node"] != "__learning__" else node["id"]
            to_node = rel["to_node"] if rel["to_node"] != "__learning__" else node["id"]
            if from_node == to_node:
                continue
            if not self.repo.exists("graph_nodes", from_node) or not self.repo.exists("graph_nodes", to_node):
                continue
            idem_raw = f"{learning_id}:{from_node}:{to_node}:{rel['relation_type']}"
            idem = "learning_graph_edge:" + hashlib.sha256(idem_raw.encode("utf-8")).hexdigest()[:40]
            try:
                edge_result = self.create_edge({
                    "from_node": from_node,
                    "to_node": to_node,
                    "relation_type": rel["relation_type"],
                    "weight": max(0.0, min(1.0, rel["weight"])),
                    "confidence": max(0.0, min(1.0, rel["confidence"])),
                    "origin": rel["origin"],
                }, actor=actor, idempotency_key=idem, owner_scope=effective_scope)
                edge = edge_result["record"]
                edges.append(edge)
                canonical_relationships.append({
                    "from_node": from_node,
                    "to_node": to_node,
                    "relation_type": edge.get("relation_type"),
                    "weight": float(edge.get("weight") or rel["weight"]),
                    "confidence": float(edge.get("confidence") or rel["confidence"]),
                    "origin": edge.get("origin") or rel["origin"],
                })
            except (ValidationError, NotFoundError):
                continue
            except Exception:
                continue

        learning = self.get_learning(learning_id, owner_scope=effective_scope) or learning
        clean_relations = learning.get("relationships") if isinstance(learning.get("relationships"), list) else []
        relation_keys = set()
        merged_relations = []
        for rel in clean_relations:
            if isinstance(rel, dict):
                key = (str(rel.get("from_node") or ""), str(rel.get("to_node") or ""), str(rel.get("relation_type") or ""))
                if key in relation_keys:
                    continue
                relation_keys.add(key)
                merged_relations.append(rel)
            elif isinstance(rel, str):
                merged_relations.append(rel)
        for rel in canonical_relationships:
            key = (rel["from_node"], rel["to_node"], rel["relation_type"])
            if key not in relation_keys:
                merged_relations.append(rel)
                relation_keys.add(key)

        changes = {}
        if knowledge_nodes != (learning.get("knowledge_nodes") or []):
            changes["knowledge_nodes"] = knowledge_nodes
        if merged_relations != (learning.get("relationships") or []):
            changes["relationships"] = merged_relations
        new_context = dict(context)
        new_context.update({
            "promoted": True,
            "promoted_node_id": node["id"],
            "promoted_memory_id": memory.get("id"),
            "promoted_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        })
        if new_context != context:
            changes["learning_context"] = new_context
        if changes:
            learning = self.update_learning(
                learning_id,
                changes,
                expected_version=learning["version"],
                actor=actor,
                owner_scope=effective_scope,
            )

        try:
            self.record_audit(
                actor,
                "learning.graph.promote",
                "learning_events",
                learning_id,
                "success",
                {
                    "status": status,
                    "node_id": node.get("id"),
                    "memory_id": memory.get("id"),
                    "edges": [e.get("id") for e in edges],
                },
            )
        except Exception:
            pass

        return {
            "promoted": True,
            "status": status,
            "learning": learning,
            "node": node,
            "memory": memory,
            "edges": edges,
        }

    def cleanup_learning_materialization(self, learning_id, actor="learning-selftest", owner_scope=None):
        """Retira de forma acotada los artefactos de una prueba de materializacion."""
        learning = self.get_learning(learning_id, owner_scope=owner_scope)
        if learning is None:
            raise NotFoundError(learning_id)
        # Cleanup must only touch artifacts owned by THIS learning.
        # Never archive context/source nodes such as the permanent Akira core.
        learning_node_ids = set()
        for value in (learning.get("knowledge_nodes") or []):
            node_id = str(value).strip()
            if not node_id:
                continue
            node = self.get_node(node_id, owner_scope=effective_scope)
            metadata = (
                node.get("node_metadata")
                if isinstance(node, dict) and isinstance(node.get("node_metadata"), dict)
                else {}
            )
            if (
                node
                and str(metadata.get("learning_id") or "") == str(learning_id)
                and str(node.get("label") or "").strip() != _CORE_NODE_LABEL
            ):
                learning_node_ids.add(node_id)
        context = learning.get("learning_context") if isinstance(learning.get("learning_context"), dict) else {}
        promoted_node_id = str(context.get("promoted_node_id") or "").strip()
        if promoted_node_id:
            promoted_node = self.get_node(promoted_node_id, owner_scope=owner_scope)
            promoted_metadata = (
                promoted_node.get("node_metadata")
                if isinstance(promoted_node, dict) and isinstance(promoted_node.get("node_metadata"), dict)
                else {}
            )
            if (
                promoted_node
                and str(promoted_metadata.get("learning_id") or "") == str(learning_id)
                and str(promoted_node.get("label") or "").strip() != _CORE_NODE_LABEL
            ):
                learning_node_ids.add(promoted_node_id)
        archived_nodes = 0
        archived_memories = 0
        archived_edges = 0

        for node_id in sorted(learning_node_ids):
            node = self.get_node(node_id, owner_scope=owner_scope)
            if not node or node.get("status") != "active":
                continue
            metadata = node.get("node_metadata") if isinstance(node.get("node_metadata"), dict) else {}
            if str(metadata.get("learning_id") or "") != str(learning_id):
                continue
            try:
                self.update_node(node_id, {"status": "archived"}, expected_version=node["version"], actor=actor, owner_scope=owner_scope)
                archived_nodes += 1
            except Exception:
                pass

        memories = self.search_memory({"source_id": learning_id, "status": "active"}, limit=50, owner_scope=owner_scope)
        for memory in memories:
            try:
                with self.repo.transaction() as tx:
                    tx.update("memories", memory["id"], {"status": "archived"}, memory["version"])
                archived_memories += 1
            except Exception:
                pass

        if learning_node_ids:
            # Consulta solo las aristas incidentes a los nodos de esta
            # materializacion. Evita escanear todo el grafo activo durante
            # cada SELFTEST/cleanup.
            edge_map = {}
            for node_id in sorted(learning_node_ids):
                for field in ("from_node", "to_node"):
                    try:
                        rows = self.repo.search(
                            "graph_edges",
                            {"status": "active", **{field: node_id}},
                            limit=500,
                        )
                    except Exception:
                        rows = []
                    for edge in rows:
                        if owner_scope is None or self.get_edge(edge.get("id"), owner_scope=owner_scope) is not None:
                            edge_map[str(edge.get("id"))] = edge
            for edge in edge_map.values():
                if edge.get("origin") != "learning_promotion" and edge.get("origin") != "auto_connect":
                    continue
                try:
                    with self.repo.transaction() as tx:
                        tx.update("graph_edges", edge["id"], {"status": "archived"}, edge["version"])
                    archived_edges += 1
                except Exception:
                    pass

        return {
            "archived_nodes": archived_nodes,
            "archived_memories": archived_memories,
            "archived_edges": archived_edges,
        }

    def get_learning(self, learning_id, owner_scope=None):
        """Lee un aprendizaje respetando el ámbito del propietario cuando se suministra."""
        rec = self.repo.get("learning_events", learning_id)
        if rec is not None:
            return rec if _scope_matches(rec.get("owner_scope"), owner_scope) else None
        try:
            rows = self.repo.search("learning_events", {}, limit=300)
            for r in rows:
                if r.get("id") == learning_id and _scope_matches(r.get("owner_scope"), owner_scope):
                    return r
        except Exception:
            pass
        return None

    def record_reuse(self, learning_id, actor="system", owner_scope=None):
        current = self.get_learning(learning_id, owner_scope=owner_scope)
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
    def search_learning(self, filters=None, limit=50, offset=0, order_by="created_at", descending=True, owner_scope=None):
        limit = max(1, min(int(limit), 200))
        base = dict(filters or {})
        if owner_scope is None:
            return self.repo.search("learning_events", base, limit=limit,
                                    offset=max(0, int(offset)), order_by=order_by, descending=descending)
        scope = str(owner_scope).strip()
        rows = self.repo.search("learning_events", base, limit=max(limit, 200), offset=0,
                                order_by=order_by, descending=descending)
        return [r for r in rows if _scope_matches(r.get("owner_scope"), scope)][max(0, int(offset)):max(0, int(offset))+limit]

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
            metadata = verified.get("node_metadata") if isinstance(verified.get("node_metadata"), dict) else {}
            if not metadata.get("suppress_tag_auto_connect"):
                try: self.auto_connect_node_tags(verified["id"], actor=actor, owner_scope=verified.get("owner_scope"))
                except Exception as e: print(f"[auto-connect] node_tags fallo: {type(e).__name__}: {str(e)[:200]}")
            if str(verified.get("label", "")).strip() != _CORE_NODE_LABEL:
                try: self.connect_to_core(verified["id"], actor=actor, weight=0.25)
                except Exception as e: print(f"[core] connect fallo: {type(e).__name__}: {str(e)[:200]}")
        return {"outcome": "created" if created else "already_synced", "record": verified}

    def get_node(self, node_id, owner_scope=None):
        node = self.repo.get("graph_nodes", node_id)
        if node is None:
            return None
        if owner_scope is not None:
            scope = str(owner_scope).strip()
            if not scope:
                return None
            node_scope = str(node.get("owner_scope") or "").strip()
            is_core = str(node.get("label") or "").strip().lower() == _CORE_NODE_LABEL.lower()
            if node_scope != scope and not is_core:
                return None
        return node

    def update_node(self, node_id, changes, expected_version=None, actor="system", owner_scope=None):
        current = self.get_node(node_id, owner_scope=owner_scope)
        if current is None:
            raise NotFoundError(node_id)
        clean = validate_graph_node(changes, partial=True)
        if not clean:
            raise ValidationError("no hay cambios")
        if expected_version is None:
            expected_version = current["version"]
        try:
            with self.repo.transaction() as tx:
                updated = tx.update("graph_nodes", node_id, clean, expected_version)
                tx.append_audit({
                    "actor": actor,
                    "action": "graph.node.update",
                    "resource": "graph_nodes",
                    "resource_id": node_id,
                    "status": "success",
                    "detail": {"fields": sorted(clean), "new_version": updated["version"]},
                })
        except PersistenceError:
            raise
        except Exception as e:
            raise StorageError(type(e).__name__) from e
        verified = self.get_node(node_id, owner_scope=owner_scope)
        if verified is None or verified["version"] != expected_version + 1:
            raise VerificationError("graph node update no confirmado")
        return verified

    def archive_edge(self, edge_id, expected_version=None, actor="system", owner_scope=None):
        current = self.get_edge(edge_id, owner_scope=owner_scope)
        if current is None:
            raise NotFoundError(edge_id)
        if expected_version is None:
            expected_version = current["version"]
        if current.get("status") != "active":
            return current
        with self.repo.transaction() as tx:
            updated = tx.update("graph_edges", edge_id, {"status": "archived"}, expected_version)
            tx.append_audit({
                "actor": actor,
                "action": "graph.edge.archive",
                "resource": "graph_edges",
                "resource_id": edge_id,
                "status": "success",
                "detail": {"new_version": updated["version"]},
            })
        verified = self.get_edge(edge_id, owner_scope=owner_scope)
        if verified is None or verified.get("status") != "archived":
            raise VerificationError("archive edge no confirmado")
        return verified

    def create_edge(self, data, actor="system", idempotency_key=None, owner_scope=None):
        fields = validate_graph_edge(data)
        from_node = fields.get("from_node"); to_node = fields.get("to_node")
        from_record = self.repo.get("graph_nodes", from_node)
        to_record = self.repo.get("graph_nodes", to_node)
        if from_record is None:
            raise NotFoundError(f"from_node no existe: {from_node}")
        if to_record is None:
            raise NotFoundError(f"to_node no existe: {to_node}")

        if owner_scope is not None:
            scope = str(owner_scope).strip()
            if not scope:
                raise ValidationError("owner_scope requerido")
            def _accessible(node):
                node_scope = str(node.get("owner_scope") or "").strip()
                is_core = str(node.get("label") or "").strip().lower() == _CORE_NODE_LABEL.lower()
                return node_scope == scope or is_core
            if not _accessible(from_record) or not _accessible(to_record):
                raise NotFoundError("grafo fuera del owner_scope")
            from_core = str(from_record.get("label") or "").strip().lower() == _CORE_NODE_LABEL.lower()
            to_core = str(to_record.get("label") or "").strip().lower() == _CORE_NODE_LABEL.lower()
            from_scope = str(from_record.get("owner_scope") or "").strip()
            to_scope = str(to_record.get("owner_scope") or "").strip()
            if not (from_core or to_core) and from_scope != to_scope:
                raise ValidationError("no se permiten aristas entre owner_scope distintos")
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

    def get_edge(self, edge_id, owner_scope=None):
        edge = self.repo.get("graph_edges", edge_id)
        if edge is None or owner_scope is None:
            return edge
        scope = str(owner_scope).strip()
        if not scope:
            return None
        from_node = self.get_node(edge.get("from_node"), owner_scope=scope)
        to_node = self.get_node(edge.get("to_node"), owner_scope=scope)
        return edge if from_node is not None and to_node is not None else None

    def related_nodes(self, node_id, direction="both", limit=50, owner_scope=None):
        limit = max(1, min(int(limit), 200))
        if self.get_node(node_id, owner_scope=owner_scope) is None:
            return []
        edges = []
        if direction in ("from", "both"):
            edges.extend(self.repo.search("graph_edges", {"from_node": node_id, "status": "active"}, limit=limit))
        if direction in ("to", "both"):
            edges.extend(self.repo.search("graph_edges", {"to_node": node_id, "status": "active"}, limit=limit))
        if owner_scope is not None:
            scope = str(owner_scope).strip()
            edges = [e for e in edges if self.get_edge(e.get("id"), owner_scope=scope) is not None]
        return edges[:limit]
    def count_nodes(self, filters=None, owner_scope=None):
        if owner_scope is None:
            return self.repo.count("graph_nodes", filters or {})
        f = dict(filters or {})
        f["owner_scope"] = str(owner_scope).strip()
        return self.repo.count("graph_nodes", f)
    def count_edges(self, filters=None, owner_scope=None):
        if owner_scope is None:
            return self.repo.count("graph_edges", filters or {})
        return len(self.list_graph_edges(
            limit=5000, offset=0, order_by="weight", descending=True,
            owner_scope=owner_scope, filters=filters
        ))

    def list_graph_nodes(self, limit=500, offset=0, order_by="weight", descending=True, owner_scope=None):
        limit = max(1, min(int(limit), 2000))
        filters = {"status": "active"}
        if owner_scope is None:
            rows = self.repo.search(
                "graph_nodes", filters, limit=limit, offset=max(0, int(offset)),
                order_by=order_by, descending=descending
            )
        else:
            scope = str(owner_scope).strip()
            rows = self.repo.search(
                "graph_nodes",
                {"status": "active", "owner_scope": scope},
                limit=limit, offset=max(0, int(offset)),
                order_by=order_by, descending=descending
            )
            if scope != LEGACY_OWNER_SCOPE:
                legacy = self.repo.search(
                    "graph_nodes",
                    {"status": "active", "owner_scope": LEGACY_OWNER_SCOPE},
                    limit=limit, offset=0,
                    order_by=order_by, descending=descending
                )
                rows = rows + legacy
        if owner_scope is not None:
            core = self.repo.search(
                "graph_nodes", {"status": "active", "label": _CORE_NODE_LABEL}, limit=1
            )
            if core and all(str(r.get("id")) != str(core[0].get("id")) for r in rows):
                rows = [core[0]] + rows
        return rows[:limit]

    def list_graph_edges(self, limit=1000, offset=0, order_by="weight",
                         descending=True, owner_scope=None, filters=None):
        limit = max(1, min(int(limit), 5000))
        base_filters = dict(filters or {})
        base_filters.setdefault("status", "active")
        rows = self.repo.search(
            "graph_edges", base_filters, limit=limit, offset=max(0, int(offset)),
            order_by=order_by, descending=descending
        )
        if owner_scope is None:
            return rows
        scope = str(owner_scope).strip()
        return [
            edge for edge in rows
            if self.get_edge(edge.get("id"), owner_scope=scope) is not None
        ][:limit]

    def start_cycle(self, trigger, input_data=None, actor="system", idempotency_key=None, owner_scope=None):
        scope = str(owner_scope).strip() if owner_scope is not None else LEGACY_OWNER_SCOPE
        if not scope:
            raise ValidationError("owner_scope requerido")
        data = {"trigger": trigger, "input": input_data or {},
                "current_stage": "observe", "status": "in_progress"}
        fields = validate_cognitive_cycle(data)
        record = dict(fields, owner_scope=scope, id=new_id("cycle"), schema_version=COGNITIVE_CYCLE_SCHEMA_VERSION)
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

    def record_stage(self, cycle_id, stage, data=None, status="success", error=None, actor="system", idempotency_key=None, owner_scope=None):
        if stage not in COGNITIVE_STAGES: raise ValidationError(f"stage invalido: {stage!r}")
        cycle = self.get_cycle(cycle_id, owner_scope=owner_scope)
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

    def complete_cycle(self, cycle_id, final_status="completed", actor="system", owner_scope=None):
        if final_status not in ("completed", "failed", "aborted"):
            raise ValidationError("final_status debe ser completed, failed o aborted")
        cycle = self.get_cycle(cycle_id, owner_scope=owner_scope)
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
    def get_cycle(self, cycle_id, owner_scope=None):
        cycle = self.repo.get("cognitive_cycles", cycle_id)
        if cycle is None or owner_scope is None:
            return cycle
        return cycle if _scope_matches(cycle.get("owner_scope"), owner_scope) else None
    def list_cycle_events(self, cycle_id, limit=100, owner_scope=None):
        if self.get_cycle(cycle_id, owner_scope=owner_scope) is None:
            return []
        limit = max(1, min(int(limit), 500))
        return self.repo.search("cognitive_events", {"cycle_id": cycle_id}, limit=limit,
                                offset=0, order_by="created_at", descending=False)
    def get_cycle_with_events(self, cycle_id, owner_scope=None):
        cycle = self.get_cycle(cycle_id, owner_scope=owner_scope)
        if cycle is None: return None
        events = self.list_cycle_events(cycle_id, owner_scope=owner_scope)
        return {"cycle": cycle, "events": events}
    def count_cycles(self, filters=None, owner_scope=None):
        if owner_scope is None:
            return self.repo.count("cognitive_cycles", filters or {})
        rows = self.repo.search("cognitive_cycles", filters or {}, limit=5000)
        return sum(1 for r in rows if _scope_matches(r.get("owner_scope"), owner_scope))

    def list_cycles(self, limit=50, owner_scope=None):
        limit = max(1, min(int(limit), 200))
        rows = self.repo.search("cognitive_cycles", {}, limit=5000, offset=0,
                                order_by="created_at", descending=True)
        if owner_scope is not None:
            rows = [r for r in rows if _scope_matches(r.get("owner_scope"), owner_scope)]
        return rows[:limit]
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
                    memory_used=None, actor="system", idempotency_key=None, owner_scope=None, owner=None):
        agent = self.get_agent_by_name(agent_name)
        if agent is None: raise NotFoundError(f"agente no existe: {agent_name}")
        tool = self.get_tool_by_name(tool_name)
        if tool is None: raise NotFoundError(f"tool no existe: {tool_name}")
        allowed = agent.get("allowed_tools") or []
        if tool_name not in allowed:
            raise ValidationError(f"el agente {agent_name} no tiene permitido usar {tool_name}")
        data = {"agent_name": agent_name, "tool_name": tool_name, "status": "pending", "inputs": inputs or {}}
        if model is not None: data["model"] = model
        if mission_id is not None:
            mission = self.get_mission(mission_id, owner=owner) if owner is not None else self.get_mission(mission_id)
            if mission is None:
                raise NotFoundError(f"mision no existe: {mission_id}")
            data["mission_id"] = mission_id
        if memory_used is not None: data["memory_used"] = memory_used
        data["owner_scope"] = str(owner_scope).strip() if owner_scope is not None else LEGACY_OWNER_SCOPE
        if not data["owner_scope"]:
            raise ValidationError("owner_scope requerido")
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
        verification_filters = {"id": stored["id"]}
        verification_filters.update(_task_scope_filters(owner_scope))
        verification_rows = self.repo.search("agent_tasks", verification_filters, limit=1,
                                             offset=0, order_by="created_at", descending=True)
        verified = verification_rows[0] if verification_rows else None
        if verified is None: raise VerificationError("task no confirmada")
        return {"outcome": "created" if created else "already_synced", "record": verified}

    def start_task(self, task_id, actor="system", owner_scope=None):
        task = self.get_task(task_id, owner_scope=owner_scope)
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

    def complete_task(self, task_id, outputs=None, duration_ms=0, memory_used=None, actor="system", owner_scope=None):
        task = self.get_task(task_id, owner_scope=owner_scope)
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

    def fail_task(self, task_id, error, duration_ms=0, memory_used=None, actor="system", owner_scope=None):
        task = self.get_task(task_id, owner_scope=owner_scope)
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

    def get_task(self, task_id, owner_scope=None):
        """Obtiene una tarea y aplica el owner_scope en consulta cuando es posible."""
        rec = self.repo.get("agent_tasks", task_id)
        if rec is not None:
            return rec if owner_scope is None or _scope_matches(rec.get("owner_scope"), owner_scope) else None
        try:
            filters = {"id": task_id}
            filters.update(_task_scope_filters(owner_scope))
            rows = self.repo.search("agent_tasks", filters, limit=1, offset=0,
                                    order_by="created_at", descending=True)
            return rows[0] if rows else None
        except Exception:
            pass
        return None

    def list_tasks(self, agent_name=None, status=None, mission_id=None, limit=50, owner_scope=None):
        filters = {}
        if agent_name: filters["agent_name"] = agent_name
        if status: filters["status"] = status
        if mission_id: filters["mission_id"] = mission_id
        if owner_scope is not None: filters["owner_scope"] = str(owner_scope).strip()
        limit = max(1, min(int(limit), 200))
        return self.repo.search("agent_tasks", filters, limit=limit, offset=0,
                                order_by="created_at", descending=True)
    def count_tasks(self, filters=None): return self.repo.count("agent_tasks", filters or {})

    def _find_or_create_node(self, node_type, label, tags=None, actor="auto-connect", owner_scope=None):
        label = str(label).strip()[:200]
        if not label:
            return None
        try:
            filters = {"node_type": node_type, "status": "active", "label": label}
            if owner_scope is not None:
                filters["owner_scope"] = str(owner_scope).strip()
            rows = self.repo.search(
                "graph_nodes",
                filters,
                limit=20,
                order_by="created_at",
                descending=False,
            )
        except Exception:
            rows = []
        for r in rows:
            if str(r.get("label", "")).strip().lower() == label.lower():
                return r

        try:
            data = {"node_type": node_type, "label": label, "tags": tags or []}
            if owner_scope is not None:
                data["owner_scope"] = str(owner_scope).strip()
            result = self.create_node(data, actor=actor)
            return result["record"]
        except Exception:
            # A concurrent creator may have won the active-node unique guard.
            try:
                filters = {"node_type": node_type, "status": "active", "label": label}
                if owner_scope is not None:
                    filters["owner_scope"] = str(owner_scope).strip()
                rows = self.repo.search(
                    "graph_nodes",
                    filters,
                    limit=20,
                    order_by="created_at",
                    descending=False,
                )
                for existing in rows:
                    if str(existing.get("label", "")).strip().lower() == label.lower():
                        return existing
            except Exception:
                pass
            return None

    def _edge_exists(self, from_node, to_node, relation_type):
        rows = self.repo.search("graph_edges", {"from_node": from_node, "to_node": to_node,
                                                 "relation_type": relation_type, "status": "active"}, limit=1)
        return rows[0] if rows else None

    def _upsert_edge(self, from_node, to_node, relation_type, delta_weight=0.5,
                     actor="auto-connect", owner_scope=None):
        """Crea o refuerza una arista, sin permitir cruces entre ámbitos."""
        if from_node == to_node:
            return None
        from_record = self.repo.get("graph_nodes", from_node)
        to_record = self.repo.get("graph_nodes", to_node)
        if from_record is None or to_record is None:
            return None
        from_scope = str(from_record.get("owner_scope") or "").strip()
        to_scope = str(to_record.get("owner_scope") or "").strip()
        from_core = str(from_record.get("label") or "").strip().lower() == _CORE_NODE_LABEL.lower()
        to_core = str(to_record.get("label") or "").strip().lower() == _CORE_NODE_LABEL.lower()
        if owner_scope is not None:
            scope = str(owner_scope).strip()
            if not scope:
                return None
            if not ((from_scope == scope or from_core) and (to_scope == scope or to_core)):
                return None
        if not (from_core or to_core) and from_scope != to_scope:
            return None
        for _attempt in range(2):
            try:
                with self.repo.transaction() as tx:
                    stored = tx.upsert_graph_edge(
                        from_node,
                        to_node,
                        relation_type,
                        delta_weight=delta_weight,
                        confidence=0.5,
                        origin="auto_connect",
                    )
                    tx.append_audit({
                        "actor": actor,
                        "action": "graph.edge.upsert",
                        "resource": "graph_edges",
                        "resource_id": stored["id"],
                        "status": "success",
                        "detail": {
                            "from": from_node,
                            "to": to_node,
                            "relation": relation_type,
                            "frequency": stored.get("frequency"),
                            "weight": stored.get("weight"),
                        },
                    })
                    return stored
            except PersistenceError:
                existing = self._edge_exists(from_node, to_node, relation_type)
                if existing:
                    return existing
            except Exception:
                existing = self._edge_exists(from_node, to_node, relation_type)
                if existing:
                    return existing
        return None

    def auto_connect_node_tags(self, node_id, actor="auto-connect", owner_scope=None):
        node = self.repo.get("graph_nodes", node_id)
        if node is None or node.get("status") != "active": return {"connected": 0}
        my_tags = set(t.lower() for t in (node.get("tags") or []))
        if not my_tags: return {"connected": 0}
        my_privacy = node.get("privacy_level") or "PRIVATE"
        filters = {"status": "active", "privacy_level": my_privacy}
        scope = str(owner_scope or node.get("owner_scope") or "").strip()
        if scope:
            filters["owner_scope"] = scope
        candidates = self.repo.search("graph_nodes", filters, limit=200)
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
                                  delta_weight=min(weight, _AUTO_EDGE_MAX_WEIGHT), actor=actor,
                                  owner_scope=scope)
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

    def auto_connect_learning(self, learning_id, actor="auto-connect", owner_scope=None):
        learning = self.get_learning(learning_id, owner_scope=owner_scope)
        if learning is None: return {"connected": 0}
        knowledge_nodes = learning.get("knowledge_nodes") or []
        if not knowledge_nodes: return {"connected": 0}
        learning_node = self._find_or_create_node(
            "experience", f"learning:{learning_id}",
            tags=["learning", str(learning.get("source", "unknown"))], actor=actor,
            owner_scope=owner_scope or learning.get("owner_scope"))
        if not learning_node: return {"connected": 0}
        connected = 0
        for kn_id in knowledge_nodes:
            if not self.repo.exists("graph_nodes", kn_id): continue
            edge = self._upsert_edge(learning_node["id"], kn_id, "learned_from",
                                     delta_weight=_AUTO_LEARNING_WEIGHT, actor=actor)
            if edge: connected += 1
        return {"learning_node": learning_node["id"], "connected": connected}

    def auto_connect_memory_tags(self, memory_id, actor="auto-connect", owner_scope=None):
        memory = self.repo.get("memories", memory_id)
        if memory is not None and str(memory.get("source") or "") in _SYNTHETIC_MEMORY_SOURCES:
            return {"connected": 0}
        if memory is None or memory.get("status") != "active":
            return {"connected": 0}
        scope = str(owner_scope or memory.get("owner_scope") or "").strip()
        if owner_scope is not None and not scope:
            return {"connected": 0}
        tags = memory.get("tags") or []
        if not tags:
            return {"connected": 0}
        my_privacy = memory.get("privacy_level") or "PRIVATE"
        memory_node = self._find_or_create_node(
            "experience",
            f"memory:{memory_id}",
            tags=tags,
            actor=actor,
            owner_scope=scope or None,
        )
        if not memory_node:
            return {"connected": 0}
        my_tags = set(t.lower() for t in tags)
        filters = {"status": "active", "privacy_level": my_privacy}
        if scope:
            filters["owner_scope"] = scope
        candidates = self.repo.search("graph_nodes", filters, limit=200)
        connected = 0
        for candidate in candidates:
            if candidate["id"] == memory_node["id"]:
                continue
            other_tags = set(t.lower() for t in (candidate.get("tags") or []))
            shared = my_tags & other_tags
            if not shared:
                continue
            edge = self._upsert_edge(
                memory_node["id"],
                candidate["id"],
                "related_to",
                delta_weight=_AUTO_MEMORY_WEIGHT,
                actor=actor,
                owner_scope=scope or None,
            )
            if edge:
                connected += 1
            if connected >= _AUTO_MAX_CONNECTIONS:
                break
        return {"memory_node": memory_node["id"], "connected": connected}

    def reinforce_frequent_pairs(self, actor="auto-connect", limit_nodes=200, owner_scope=None):
        """Refuerza pares frecuentes de forma acotada y eficiente."""
        core = self.ensure_core_node(actor=actor)
        core_id = core["id"] if core else None
        reinforced = 0
        frequent_pairs = 0
        candidate_edges = 0
        max_pairs = 40
        max_edge_updates = 80

        try:
            memory_filters = {"status": "active"}
            scope = str(owner_scope).strip() if owner_scope is not None else ""
            if owner_scope is not None and not scope:
                return {"reinforced": 0, "frequent_pairs": 0, "candidate_edges": 0, "connected_to_core": 0, "core_id": None}
            if scope:
                memory_filters["owner_scope"] = scope
            memories = self.repo.search(
                "memories",
                memory_filters,
                limit=500,
                order_by="created_at",
                descending=True,
            )
            from collections import Counter
            pair_counter = Counter()
            for m in memories:
                tags = sorted(set(str(t).lower() for t in (m.get("tags") or [])))
                for i in range(len(tags)):
                    for j in range(i + 1, len(tags)):
                        pair_counter[(tags[i], tags[j])] += 1

            frecuentes = sorted(
                ((pair, n) for pair, n in pair_counter.items()
                 if n >= _AUTO_REINFORCE_MIN_FREQ),
                key=lambda item: (-item[1], item[0][0], item[0][1]),
            )[:max_pairs]
            frequent_pairs = len(frecuentes)

            node_filters = {"status": "active"}
            if scope:
                node_filters["owner_scope"] = scope
            nodes = self.repo.search(
                "graph_nodes",
                node_filters,
                limit=max(1, min(int(limit_nodes), 200)),
            )
            tags_index = {}
            for n in nodes:
                for t in (n.get("tags") or []):
                    tags_index.setdefault(str(t).lower(), []).append(n["id"])

            work = []
            seen = set()
            for (tag_a, tag_b), freq in frecuentes:
                for a in tags_index.get(tag_a, [])[:3]:
                    for b in tags_index.get(tag_b, [])[:3]:
                        if a == b:
                            continue
                        key = (a, b, "related_to")
                        if key in seen:
                            continue
                        seen.add(key)
                        work.append((
                            a, b,
                            min(
                                0.1 * (freq / _AUTO_REINFORCE_MIN_FREQ),
                                _AUTO_EDGE_MAX_WEIGHT,
                            ),
                        ))
                        if len(work) >= max_edge_updates:
                            break
                    if len(work) >= max_edge_updates:
                        break
                if len(work) >= max_edge_updates:
                    break

            candidate_edges = len(work)
            if work:
                with self.repo.transaction() as tx:
                    for a, b, delta in work:
                        tx.upsert_graph_edge(
                            a,
                            b,
                            "related_to",
                            delta_weight=delta,
                            confidence=0.5,
                            origin="auto_connect",
                        )
                        reinforced += 1

        except Exception as e:
            print(f"[reinforce] pares fallo: {type(e).__name__}: {str(e)[:200]}")

        # REFORZAR no recorre todos los nodos para conectarlos al core.
        # Las conexiones al core se resuelven en los flujos de autoconexion.
        connected_to_core = 0

        try:
            self.record_audit(
                actor,
                "graph.auto_connect.reinforce",
                "graph_edges",
                None,
                "success",
                {
                    "reinforced": reinforced,
                    "frequent_pairs": frequent_pairs,
                    "candidate_edges": candidate_edges,
                    "connected_to_core": connected_to_core,
                    "core_id": core_id,
                    "owner_scope": scope or None,
                    "bounded": True,
                    "max_pairs": max_pairs,
                    "max_edge_updates": max_edge_updates,
                },
            )
        except Exception:
            pass

        return {
            "reinforced": reinforced,
            "frequent_pairs": frequent_pairs,
            "candidate_edges": candidate_edges,
            "connected_to_core": connected_to_core,
            "core_id": core_id,
        }

    def ensure_core_node(self, actor="system"):
        # Exact lookup: the core must not disappear just because the graph has
        # grown beyond the arbitrary default page size.
        try:
            rows = self.repo.search(
                "graph_nodes",
                {"status": "active", "label": _CORE_NODE_LABEL},
                limit=20,
                order_by="created_at",
                descending=False,
            )
        except Exception:
            return None
        for n in rows:
            metadata = n.get("node_metadata") if isinstance(n.get("node_metadata"), dict) else {}
            tags = set(str(t).strip().lower() for t in (n.get("tags") or []))
            if (
                str(n.get("label", "")).strip() == _CORE_NODE_LABEL
                and not metadata.get("learning_id")
                and {"core", "akira", "nucleo"}.issubset(tags)
            ):
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
            # If another transaction won the single-core unique guard, reuse it.
            try:
                rows = self.repo.search(
                    "graph_nodes",
                    {"status": "active", "label": _CORE_NODE_LABEL},
                    limit=20,
                    order_by="created_at",
                    descending=False,
                )
                for existing in rows:
                    metadata = existing.get("node_metadata") if isinstance(existing.get("node_metadata"), dict) else {}
                    tags = set(str(t).strip().lower() for t in (existing.get("tags") or []))
                    if (
                        str(existing.get("label", "")).strip() == _CORE_NODE_LABEL
                        and not metadata.get("learning_id")
                        and {"core", "akira", "nucleo"}.issubset(tags)
                    ):
                        return existing
            except Exception:
                pass
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

    def create_mission(self, data, actor="system", idempotency_key=None, owner=None):
        fields = validate_mission(data)
        if owner is not None:
            fields["created_by"] = str(owner).strip()
        elif "created_by" not in fields:
            fields["created_by"] = actor
        if not fields.get("created_by"):
            raise ValidationError("created_by requerido")
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

    def get_mission(self, mission_id, owner=None):
        """Obtiene una misión, acotada por propietario cuando se indica."""
        rec = self.repo.get("missions", mission_id)
        if rec is not None:
            return rec if owner is None or rec.get("created_by") == owner else None
        try:
            filters = {"created_by": owner} if owner is not None else {}
            rows = self.repo.search("missions", filters, limit=300)
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

    def update_mission_status(self, mission_id, new_status, expected_version, actor="system", owner=None):
        current = self.get_mission(mission_id, owner=owner)
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
        verified = self.get_mission(mission_id, owner=owner)
        if (verified is None or verified["version"] != expected_version + 1
                or verified.get("status") != new_status):
            raise VerificationError("cambio de estado no confirmado al releer")
        return verified

    def update_mission_plan(self, mission_id, plan, expected_version, actor="system", owner=None):
        if not isinstance(plan, dict):
            raise ValidationError("plan debe ser un objeto (dict)")
        current = self.get_mission(mission_id, owner=owner)
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
        verified = self.get_mission(mission_id, owner=owner)
        if verified is None or verified["version"] != expected_version + 1 or verified.get("plan") != plan:
            raise VerificationError("plan no confirmado al releer")
        return verified

    def complete_mission(self, mission_id, result=None, learning_refs=None, actor="system", owner=None):
        current = self.get_mission(mission_id, owner=owner)
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
        return self.get_mission(mission_id, owner=owner)

    def fail_mission(self, mission_id, error, actor="system", owner=None):
        current = self.get_mission(mission_id, owner=owner)
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
        return self.get_mission(mission_id, owner=owner)

    def cancel_mission(self, mission_id, reason=None, actor="system", owner=None):
        current = self.get_mission(mission_id, owner=owner)
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
        return self.get_mission(mission_id, owner=owner)

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

    def get_conversation(self, conversation_id, owner=None):
        """Obtiene una conversación y, si se indica owner, la acota al propietario."""
        rec = self.repo.get("conversations", conversation_id)
        if rec is not None:
            if owner is not None and rec.get("created_by") != owner:
                return None
            return rec
        try:
            filters = {}
            if owner is not None:
                filters["created_by"] = owner
            rows = self.repo.search("conversations", filters, limit=300)
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

    def update_conversation(self, conversation_id, changes, expected_version, actor="system", owner=None):
        """Actualiza titulo o status, opcionalmente limitado al propietario."""
        clean = validate_conversation(changes, partial=True)
        current = self.get_conversation(conversation_id, owner=owner)
        if current is None:
            raise NotFoundError(conversation_id)
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

    def archive_conversation(self, conversation_id, expected_version=None, actor="system", owner=None):
        if expected_version is None:
            current = self.get_conversation(conversation_id, owner=owner)
            if current is None: raise NotFoundError(conversation_id)
            expected_version = current["version"]
        return self.update_conversation(
            conversation_id, {"status": "archived"}, expected_version, actor, owner=owner
        )

    def add_message(self, conversation_id, role, content, model=None,
                    memories_used=None, duration_ms=0, error=None, actor="system",
                    idempotency_key=None, owner=None):
        """Añade un mensaje a una conversacion. En la MISMA transaccion:
        - crea el mensaje (append-only)
        - actualiza conversations.message_count +1
        - actualiza conversations.last_message_at al ahora
        Devuelve {"record": mensaje, "conversation": conversacion_actualizada}."""
        current_conv = self.get_conversation(conversation_id, owner=owner)
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

    def list_messages(self, conversation_id, limit=200, offset=0, owner=None):
        """Mensajes de una conversación, opcionalmente acotados a su propietario."""
        if owner is not None and self.get_conversation(conversation_id, owner=owner) is None:
            raise NotFoundError(conversation_id)
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        return self.repo.search("conversation_messages", {"conversation_id": conversation_id},
                                limit=limit, offset=offset, order_by="created_at", descending=False)

    def count_messages(self, conversation_id, owner=None):
        if owner is not None and self.get_conversation(conversation_id, owner=owner) is None:
            raise NotFoundError(conversation_id)
        return self.repo.count("conversation_messages", {"conversation_id": conversation_id})
