"""AKIRA V8-A - Persistence core: errores, esquema de entidades, validacion e interfaz del repositorio.

Regla (Fase 4): ningun modulo cognitivo escribe directo en la base.
Flujo: Modulo cognitivo -> PersistenceService -> PersistenceRepository -> Storage.
Fase 10.7.2: entidades conversations y conversation_messages para persistencia de chats.
"""
from __future__ import annotations

import uuid
import datetime as _dt
from abc import ABC, abstractmethod

class PersistenceError(Exception):
    """Base de todos los errores de persistencia."""

class ValidationError(PersistenceError):
    """El registro no cumple el esquema. No se escribio nada."""

class NotFoundError(PersistenceError):
    """El registro no existe."""

class ConflictError(PersistenceError):
    """Version esperada distinta de la real (otro proceso modifico el registro)."""

class VerificationError(PersistenceError):
    """La escritura se hizo pero la relectura no coincide: estado NO confirmado."""

class StorageError(PersistenceError):
    """Fallo del almacenamiento (conexion, SQL, timeout)."""

MEMORY_TYPES = ("episodic", "semantic", "procedural", "working", "user_context", "system")
PRIVACY_LEVELS = ("PRIVATE", "SENSITIVE", "SHAREABLE", "COLLECTIVE")
HIVE_VISIBLE = ("SHAREABLE", "COLLECTIVE")
STATUSES = ("active", "archived", "deleted")
MEMORY_SCHEMA_VERSION = "memory.v1"

SELF_MODEL_PRIMARY_ID = "akira_primary"
SELF_MODEL_SCHEMA_VERSION = "self_model.v2"

LEARNING_SCHEMA_VERSION = "learning.v3"
LEARNING_STATUSES = ("candidate", "verified", "consolidated", "conflicted", "obsolete", "discarded")
GRAPH_NODE_SCHEMA_VERSION = "graph_node.v1"
GRAPH_EDGE_SCHEMA_VERSION = "graph_edge.v1"

LEARNING_OUTCOMES = ("success", "failure", "partial", "unknown")

NODE_TYPES = (
    "concept", "person", "project", "tool", "experience",
    "document", "skill", "error", "solution", "mission",
)

RELATION_TYPES = (
    "uses", "used_by", "related_to", "causes", "caused_by",
    "improves", "improved_by", "contains", "part_of",
    "precedes", "follows", "solves", "solved_by", "learned_from",
)

COGNITIVE_CYCLE_SCHEMA_VERSION = "cognitive_cycle.v1"
COGNITIVE_EVENT_SCHEMA_VERSION = "cognitive_event.v1"

COGNITIVE_STAGES = (
    "observe", "interpret", "reason", "decide", "act",
    "observe_result", "evaluate", "learn", "update_self_model",
)

COGNITIVE_CYCLE_STATUSES = ("in_progress", "completed", "failed", "aborted")

TOOL_SCHEMA_VERSION = "tool.v1"
TOOL_INVOCATION_SCHEMA_VERSION = "tool_invocation.v1"

TOOL_STATUSES = ("available", "disabled", "deprecated")
TOOL_CATEGORIES = (
    "web", "memory", "knowledge", "code", "files", "documents",
    "image", "apis", "computer", "internal", "general",
)

AGENT_SCHEMA_VERSION = "agent.v1"
AGENT_TASK_SCHEMA_VERSION = "agent_task.v1"

AGENT_STATUSES = ("idle", "busy", "disabled", "error")
AGENT_TASK_STATUSES = ("pending", "running", "completed", "failed")

AGENT_ROLES = (
    "researcher", "memorizer", "graph_builder", "learner",
    "internal", "developer", "tester", "reviewer", "generic",
)

MISSION_SCHEMA_VERSION = "mission.v1"
MISSION_STATUSES = (
    "created", "planning", "running", "paused", "waiting_approval",
    "completed", "failed", "cancelled",
)
MISSION_FLOW_TYPES = ("generic",)

# Fase 10.7.2: persistencia de conversaciones.
CONVERSATION_SCHEMA_VERSION = "conversation.v1"
CONVERSATION_MESSAGE_SCHEMA_VERSION = "conversation_message.v1"
CONVERSATION_STATUSES = ("active", "archived", "deleted")
MESSAGE_ROLES = ("user", "assistant", "system")

def new_id(prefix: str) -> str:
    """Formato Fase 3: <tipo>_<uuid>."""
    return f"{prefix}_{uuid.uuid4().hex}"

ENTITIES = {
    "memories": {
        "table": "memories",
        "columns": (
            "id", "content", "memory_type", "importance", "confidence", "source", "source_id",
            "source_reference", "created_by", "tags", "owner_scope", "privacy_level", "status",
            "schema_version", "idempotency_key",
        ),
        "json_columns": ("tags",),
        "mutable": (
            "content", "memory_type", "importance", "confidence", "source_reference", "tags",
            "privacy_level", "status",
        ),
        "filterable": (
            "id", "memory_type", "privacy_level", "status", "owner_scope", "source", "source_id",
            "created_by", "idempotency_key", "importance",
        ),
        "in_filterable": ("memory_type", "privacy_level", "status", "owner_scope", "source"),
        "orderable": ("created_at", "updated_at", "importance", "last_accessed_at"),
        "idempotent": True,
        "idempotency_scope": ("owner_scope",),
    },
    "self_model": {
        "table": "self_model",
        "columns": (
            "id", "identity", "purpose", "capabilities", "tools", "models",
            "current_state", "knowledge_state", "uncertainties", "errors",
            "repairs", "evolution", "schema_version", "idempotency_key",
        ),
        "json_columns": (
            "identity", "purpose", "capabilities", "tools", "models",
            "current_state", "knowledge_state", "uncertainties", "errors",
            "repairs", "evolution",
        ),
        "mutable": (
            "purpose",
            "current_state", "knowledge_state", "uncertainties", "errors",
            "repairs", "evolution",
        ),
        "filterable": ("id", "idempotency_key"),
        "in_filterable": (),
        "orderable": ("created_at", "updated_at"),
        "idempotent": True,
    },
    "identity_root": {
        "table": "identity_root",
        "columns": (
            "id", "canonical_name", "creator", "essence", "language",
            "root_schema_version", "status", "created_at",
        ),
        "json_columns": (),
        "mutable": (),
        "filterable": ("id", "canonical_name", "creator", "language", "status"),
        "in_filterable": ("status",),
        "orderable": ("created_at",),
        "idempotent": False,
    },
    "capabilities": {
        "table": "capabilities",
        "columns": (
            "id", "name", "description", "category", "kind",
            "implementation_state", "verification_state", "availability_state",
            "maturity", "cost_compatibility",
            "dependencies", "limitations", "verification_spec", "provenance",
            "version", "schema_version", "last_verification_id", "last_verified_at",
            "idempotency_key", "created_at", "updated_at",
        ),
        "json_columns": ("dependencies", "limitations", "verification_spec", "provenance"),
        "mutable": (
            "description", "category", "kind",
            "implementation_state", "verification_state", "availability_state",
            "maturity", "cost_compatibility",
            "dependencies", "limitations", "verification_spec", "provenance",
            "last_verification_id", "last_verified_at",
        ),
        "filterable": (
            "id", "name", "category", "kind", "implementation_state",
            "verification_state", "availability_state", "maturity",
            "cost_compatibility", "idempotency_key",
        ),
        "in_filterable": (
            "category", "kind", "implementation_state", "verification_state",
            "availability_state", "maturity", "cost_compatibility",
        ),
        "orderable": ("created_at", "updated_at", "last_verified_at", "name"),
        "idempotent": True,
    },
    "capability_verifications": {
        "table": "capability_verifications",
        "columns": (
            "id", "capability_id", "event_type", "test_key", "test_version", "result",
            "evidence", "environment", "dependency_snapshot",
            "runtime_version", "build_ref", "actor", "executor", "evaluator",
            "started_at", "finished_at", "error", "observed_availability_state",
            "state_before", "state_after", "schema_version", "version",
            "idempotency_key", "created_at",
        ),
        "json_columns": (
            "evidence", "environment", "dependency_snapshot", "error",
            "state_before", "state_after",
        ),
        "mutable": (),
        "filterable": ("id", "capability_id", "event_type", "test_key", "result", "idempotency_key"),
        "in_filterable": ("event_type", "test_key", "result"),
        "orderable": ("created_at",),
        "idempotent": True,
        "conflict_strategy": "advisory_precheck",
    },
    "learning_events": {
        "table": "learning_events",
        "columns": (
            "id", "source", "event", "lesson", "knowledge_nodes", "relationships",
            "confidence", "outcome", "status", "evidence", "verification_analysis", "learning_context", "verified_at", "verified_by", "reuse_count", "last_reused_at",
            "owner_scope", "schema_version", "idempotency_key",
        ),
        "json_columns": ("knowledge_nodes", "relationships", "evidence", "verification_analysis", "learning_context"),
        "mutable": (
            "source", "event", "lesson", "knowledge_nodes", "relationships",
            "confidence", "outcome", "status", "evidence", "verification_analysis", "learning_context", "verified_at", "verified_by", "reuse_count", "last_reused_at",
        ),
        "filterable": ("id", "source", "outcome", "status", "idempotency_key"),
        "in_filterable": ("source", "outcome", "status"),
        "orderable": ("created_at", "updated_at", "reuse_count", "last_reused_at"),
        "idempotent": True,
        "idempotency_scope": ("owner_scope",),
    },
    "graph_nodes": {
        "table": "graph_nodes",
        "columns": (
            "id", "node_type", "label", "description", "node_metadata", "tags",
            "weight", "confidence", "reuse_count", "owner_scope", "privacy_level",
            "status", "schema_version", "idempotency_key", "last_used_at",
        ),
        "json_columns": ("node_metadata", "tags"),
        "mutable": (
            "label", "description", "node_metadata", "tags", "weight", "confidence",
            "reuse_count", "privacy_level", "status", "last_used_at",
        ),
        "filterable": (
            "id", "node_type", "label", "owner_scope", "privacy_level", "status", "idempotency_key",
        ),
        "in_filterable": ("node_type", "owner_scope", "privacy_level", "status"),
        "orderable": ("created_at", "updated_at", "weight", "reuse_count", "last_used_at"),
        "idempotent": True,
        "idempotency_scope": ("owner_scope",),
    },
    "graph_edges": {
        "table": "graph_edges",
        "columns": (
            "id", "from_node", "to_node", "relation_type", "weight", "confidence",
            "frequency", "origin", "success_count", "failure_count", "status",
            "schema_version", "idempotency_key", "last_used_at",
        ),
        "json_columns": (),
        "mutable": (
            "relation_type", "weight", "confidence", "frequency", "origin",
            "success_count", "failure_count", "status", "last_used_at",
        ),
        "filterable": (
            "id", "from_node", "to_node", "relation_type", "origin", "status", "idempotency_key",
        ),
        "in_filterable": ("relation_type", "origin", "status"),
        "orderable": ("created_at", "updated_at", "weight", "frequency", "last_used_at"),
        "idempotent": True,
        "idempotency_scope": ("from_node", "to_node", "relation_type"),
    },
    "cognitive_cycles": {
        "table": "cognitive_cycles",
        "columns": (
            "id", "trigger", "input", "current_stage", "status",
            "owner_scope", "completed_at", "schema_version", "idempotency_key",
        ),
        "json_columns": ("input",),
        "mutable": ("current_stage", "status", "completed_at"),
        "filterable": ("id", "trigger", "status", "current_stage", "idempotency_key"),
        "in_filterable": ("trigger", "status", "current_stage"),
        "orderable": ("created_at", "updated_at", "started_at", "completed_at"),
        "idempotent": True,
    },
    "cognitive_events": {
        "table": "cognitive_events",
        "columns": (
            "id", "cycle_id", "stage", "status", "data", "error",
            "schema_version", "idempotency_key",
        ),
        "json_columns": ("data", "error"),
        "mutable": (),
        "filterable": ("id", "cycle_id", "stage", "status", "idempotency_key"),
        "in_filterable": ("cycle_id", "stage", "status"),
        "orderable": ("created_at", "updated_at"),
        "idempotent": True,
    },
    "tools": {
        "table": "tools",
        "columns": (
            "id", "name", "description", "category", "permissions",
            "inputs_schema", "outputs_schema", "limits_json", "risks",
            "status", "schema_version", "idempotency_key",
        ),
        "json_columns": (
            "permissions", "inputs_schema", "outputs_schema", "limits_json", "risks",
        ),
        "mutable": (
            "description", "category", "permissions", "inputs_schema", "outputs_schema",
            "limits_json", "risks", "status",
        ),
        "filterable": ("id", "name", "category", "status", "idempotency_key"),
        "in_filterable": ("category", "status"),
        "orderable": ("created_at", "updated_at", "name"),
        "idempotent": True,
    },
    "tool_invocations": {
        "table": "tool_invocations",
        "columns": (
            "id", "tool_name", "actor", "inputs", "outputs", "status",
            "error", "duration_ms", "schema_version", "idempotency_key",
        ),
        "json_columns": ("inputs", "outputs", "error"),
        "mutable": (),
        "filterable": ("id", "tool_name", "actor", "status", "idempotency_key"),
        "in_filterable": ("tool_name", "actor", "status"),
        "orderable": ("created_at", "updated_at", "duration_ms"),
        "idempotent": True,
    },
    "agents": {
        "table": "agents",
        "columns": (
            "id", "name", "role", "description", "allowed_tools", "status",
            "current_task_id", "current_action", "tasks_completed", "tasks_failed",
            "last_active_at", "schema_version", "idempotency_key",
        ),
        "json_columns": ("allowed_tools",),
        "mutable": (
            "description", "allowed_tools", "status", "current_task_id", "current_action",
            "tasks_completed", "tasks_failed", "last_active_at",
        ),
        "filterable": ("id", "name", "role", "status", "idempotency_key"),
        "in_filterable": ("role", "status"),
        "orderable": ("created_at", "updated_at", "tasks_completed", "last_active_at", "name"),
        "idempotent": True,
    },
    "agent_tasks": {
        "table": "agent_tasks",
        "columns": (
            "id", "agent_name", "tool_name", "status", "model", "mission_id",
            "owner_scope", "inputs", "outputs", "memory_used", "error", "duration_ms",
            "started_at", "completed_at", "schema_version", "idempotency_key",
        ),
        "json_columns": ("inputs", "outputs", "memory_used", "error"),
        "mutable": (
            "status", "model", "mission_id", "outputs", "memory_used", "error",
            "duration_ms", "started_at", "completed_at",
        ),
        "filterable": ("id", "agent_name", "tool_name", "status", "mission_id", "owner_scope", "idempotency_key"),
        "in_filterable": ("agent_name", "tool_name", "status", "owner_scope"),
        "orderable": ("created_at", "updated_at", "duration_ms", "started_at", "completed_at"),
        "idempotent": True,
    },
    "missions": {
        "table": "missions",
        "columns": (
            "id", "title", "objective", "description", "status", "priority",
            "created_by", "authorized_by", "flow_type", "flow_config",
            "plan", "parent_mission_id", "success_criteria", "result",
            "learning_refs", "schema_version", "idempotency_key",
            "started_at", "completed_at",
        ),
        "json_columns": ("flow_config", "plan", "result", "learning_refs"),
        "mutable": (
            "title", "objective", "description", "status", "priority",
            "authorized_by", "flow_config", "plan", "success_criteria",
            "result", "learning_refs", "started_at", "completed_at",
        ),
        "filterable": (
            "id", "status", "priority", "flow_type", "created_by",
            "parent_mission_id", "idempotency_key",
        ),
        "in_filterable": ("status", "flow_type", "created_by"),
        "orderable": ("created_at", "updated_at", "priority", "started_at", "completed_at"),
        "idempotent": True,
    },
    # Fase 10.7.2: persistencia de conversaciones.
    "conversations": {
        "table": "conversations",
        "columns": (
            "id", "title", "created_by", "status", "message_count",
            "last_message_at", "schema_version", "idempotency_key",
        ),
        "json_columns": (),
        "mutable": ("title", "status", "message_count", "last_message_at"),
        "filterable": ("id", "status", "created_by", "idempotency_key"),
        "in_filterable": ("status", "created_by"),
        "orderable": ("created_at", "updated_at", "last_message_at"),
        "idempotent": True,
    },
    "conversation_messages": {
        "table": "conversation_messages",
        "columns": (
            "id", "conversation_id", "role", "content", "model",
            "memories_used", "error", "duration_ms",
            "schema_version", "idempotency_key",
        ),
        "json_columns": ("memories_used", "error"),
        "mutable": (),
        "filterable": ("id", "conversation_id", "role", "idempotency_key"),
        "in_filterable": ("conversation_id", "role"),
        "orderable": ("created_at", "updated_at", "duration_ms"),
        "idempotent": True,
    },
}

def entity_spec(entity: str) -> dict:
    try:
        return ENTITIES[entity]
    except KeyError:
        raise ValidationError(f"entidad desconocida: {entity!r}") from None

def _str(name, value, max_len, allow_empty=False):
    if not isinstance(value, str):
        raise ValidationError(f"{name} debe ser texto")
    value = value.strip()
    if not value and not allow_empty:
        raise ValidationError(f"{name} no puede estar vacio")
    if len(value) > max_len:
        raise ValidationError(f"{name} supera {max_len} caracteres")
    return value

def _int_0_10(name, value):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10:
        raise ValidationError(f"{name} debe ser un entero entre 0 y 10")
    return value

def _float_0_1(name, value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise ValidationError(f"{name} debe ser un numero entre 0 y 1")
    return float(value)

def _non_negative_int(name, value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{name} debe ser un entero >= 0")
    return value

def _non_negative_float(name, value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValidationError(f"{name} debe ser un numero >= 0")
    return float(value)

def _tags(value):
    if not isinstance(value, list) or len(value) > 30:
        raise ValidationError("tags debe ser una lista de maximo 30 textos")
    out = []
    for t in value:
        t = _str("tag", t, 64)
        if t not in out:
            out.append(t)
    return out

def _choice(name, value, options):
    if value not in options:
        raise ValidationError(f"{name} debe ser uno de {list(options)}")
    return value

def _string_list(name, value, max_items=50, max_len=256):
    if not isinstance(value, list) or len(value) > max_items:
        raise ValidationError(f"{name} debe ser una lista de maximo {max_items} textos")
    return [_str(name[:-1] if name.endswith('s') else name, x, max_len) for x in value]

def _optional_str(name, value, max_len):
    """Texto opcional: acepta None o cadena vacia -> None. Si no, valida longitud."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(f"{name} debe ser texto o None")
    value = value.strip()
    if not value:
        return None
    if len(value) > max_len:
        raise ValidationError(f"{name} supera {max_len} caracteres")
    return value

_MEMORY_INPUT = {
    "content", "memory_type", "importance", "confidence", "source", "source_id",
    "source_reference", "created_by", "tags", "owner_scope", "privacy_level",
}
_MEMORY_UPDATABLE = {
    "content", "memory_type", "importance", "confidence", "source_reference", "tags", "privacy_level",
}

def validate_memory(data, partial: bool = False) -> dict:
    if not isinstance(data, dict):
        raise ValidationError("el registro debe ser un objeto")
    allowed = _MEMORY_UPDATABLE if partial else _MEMORY_INPUT
    extra = sorted(set(data) - allowed)
    if extra:
        raise ValidationError(f"campos no permitidos: {extra}")
    if partial and not data:
        raise ValidationError("no hay cambios")
    if not partial:
        for req in ("content", "memory_type"):
            if req not in data:
                raise ValidationError(f"falta el campo obligatorio {req}")

    out = {}
    if "content" in data:
        out["content"] = _str("content", data["content"], 20000)
    if "memory_type" in data:
        out["memory_type"] = _choice("memory_type", data["memory_type"], MEMORY_TYPES)
    if "importance" in data or not partial:
        out["importance"] = _int_0_10("importance", data.get("importance", 5))
    if "confidence" in data or not partial:
        out["confidence"] = _float_0_1("confidence", data.get("confidence", 0.5))
    if "privacy_level" in data or not partial:
        out["privacy_level"] = _choice("privacy_level", data.get("privacy_level", "PRIVATE"), PRIVACY_LEVELS)
    if "tags" in data or not partial:
        out["tags"] = _tags(data.get("tags", []))
    if "source_reference" in data:
        out["source_reference"] = _str("source_reference", data["source_reference"], 256)
    if not partial:
        out["source"] = _str("source", data.get("source", "unknown"), 64)
        out["owner_scope"] = _str("owner_scope", data.get("owner_scope", "owner"), 64)
        if data.get("source_id") is not None:
            out["source_id"] = _str("source_id", data["source_id"], 256)
        if data.get("created_by") is not None:
            out["created_by"] = _str("created_by", data["created_by"], 64)
    return out

_SELF_MODEL_OBJECT_FIELDS = ("identity", "purpose", "current_state", "knowledge_state")
_SELF_MODEL_LIST_FIELDS = ("capabilities", "tools", "models", "uncertainties", "errors", "repairs", "evolution")
_SELF_MODEL_PROTECTED_FIELDS = frozenset({"identity"})
_SELF_MODEL_DERIVED_FIELDS = frozenset({"capabilities", "tools", "models"})
_SELF_MODEL_UPDATABLE = frozenset(
    set(_SELF_MODEL_OBJECT_FIELDS + _SELF_MODEL_LIST_FIELDS)
    - set(_SELF_MODEL_PROTECTED_FIELDS)
    - set(_SELF_MODEL_DERIVED_FIELDS)
)

_SELF_MODEL_UNCERTAINTY_STATUSES = ("open", "resolved", "superseded")
_SELF_MODEL_UNCERTAINTY_KINDS = ("capability", "knowledge", "runtime", "evidence", "other")
_SELF_MODEL_ERROR_STATUSES = ("open", "resolved", "ignored")
_SELF_MODEL_REPAIR_STATUSES = ("proposed", "approved", "running", "completed", "failed", "cancelled")
_SELF_MODEL_EVOLUTION_STATUSES = ("proposed", "approved", "implemented", "rejected", "deferred")

def _self_model_text(name, value, maximum=500, allow_empty=False):
    if not isinstance(value, str):
        raise ValidationError(f"{name} debe ser texto")
    value = value.strip()
    if not allow_empty and not value:
        raise ValidationError(f"{name} no puede estar vacio")
    if len(value) > maximum:
        raise ValidationError(f"{name} supera el maximo de {maximum} caracteres")
    return value

def _self_model_iso(name, value):
    value = _self_model_text(name, value, 64)
    try:
        _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError(f"{name} debe ser fecha ISO-8601") from exc
    return value

def _self_model_record_list(field, value, allowed, *, max_items=50):
    if not isinstance(value, list):
        raise ValidationError(f"{field} debe ser una lista")
    if len(value) > max_items:
        raise ValidationError(f"{field} admite maximo {max_items} elementos")
    out = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValidationError(f"{field}[{index}] debe ser un objeto")
        extra = sorted(set(item) - set(allowed))
        if extra:
            raise ValidationError(f"{field}[{index}] contiene campos no permitidos: {extra}")
        out.append(item)
    return out

def _validate_self_model_current_state(value):
    if not isinstance(value, dict):
        raise ValidationError("current_state debe ser un objeto (dict)")
    allowed = {"last_cycle_id", "last_cycle_at", "last_cycle_trigger", "last_cycle_model", "cycles_completed", "last_observed_at"}
    extra = sorted(set(value) - allowed)
    if extra:
        raise ValidationError(f"current_state contiene campos no permitidos: {extra}")
    out = dict(value)
    if "last_cycle_id" in out:
        out["last_cycle_id"] = _self_model_text("current_state.last_cycle_id", out["last_cycle_id"], 128)
    for key in ("last_cycle_at", "last_observed_at"):
        if key in out:
            out[key] = _self_model_iso(f"current_state.{key}", out[key])
    if "last_cycle_trigger" in out:
        out["last_cycle_trigger"] = _self_model_text("current_state.last_cycle_trigger", out["last_cycle_trigger"], 64)
    if "last_cycle_model" in out:
        out["last_cycle_model"] = _self_model_text("current_state.last_cycle_model", out["last_cycle_model"], 128)
    if "cycles_completed" in out:
        value = out["cycles_completed"]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValidationError("current_state.cycles_completed debe ser entero >= 0")
        out["cycles_completed"] = value
    return out

def _validate_self_model_knowledge_state(value):
    if not isinstance(value, dict):
        raise ValidationError("knowledge_state debe ser un objeto (dict)")
    allowed = {"last_observed_at", "sources", "notes"}
    extra = sorted(set(value) - allowed)
    if extra:
        raise ValidationError(f"knowledge_state contiene campos no permitidos: {extra}")
    out = dict(value)
    if "last_observed_at" in out:
        out["last_observed_at"] = _self_model_iso("knowledge_state.last_observed_at", out["last_observed_at"])
    if "sources" in out:
        sources = _self_model_record_list("knowledge_state.sources", out["sources"], {"id", "kind", "observed_at"}, max_items=20)
        normalized = []
        for item in sources:
            normalized.append({
                "id": _self_model_text("knowledge_state.sources.id", item.get("id"), 128),
                "kind": _self_model_text("knowledge_state.sources.kind", item.get("kind"), 64),
                "observed_at": _self_model_iso("knowledge_state.sources.observed_at", item.get("observed_at")),
            })
        out["sources"] = normalized
    if "notes" in out:
        out["notes"] = _self_model_text("knowledge_state.notes", out["notes"], 2000, allow_empty=True)
    return out

def _validate_self_model_uncertainties(value):
    allowed = {"id", "statement", "kind", "status", "evidence", "created_at", "resolved_at"}
    items = _self_model_record_list("uncertainties", value, allowed)
    out = []
    for item in items:
        status = _self_model_text("uncertainties.status", item.get("status"), 32)
        if status not in _SELF_MODEL_UNCERTAINTY_STATUSES:
            raise ValidationError(f"uncertainties.status invalido: {status!r}")
        kind = _self_model_text("uncertainties.kind", item.get("kind"), 32)
        if kind not in _SELF_MODEL_UNCERTAINTY_KINDS:
            raise ValidationError(f"uncertainties.kind invalido: {kind!r}")
        normalized = {
            "id": _self_model_text("uncertainties.id", item.get("id"), 128),
            "statement": _self_model_text("uncertainties.statement", item.get("statement"), 2000),
            "kind": kind,
            "status": status,
            "evidence": item.get("evidence", []),
            "created_at": _self_model_iso("uncertainties.created_at", item.get("created_at")),
        }
        if not isinstance(normalized["evidence"], list) or len(normalized["evidence"]) > 10:
            raise ValidationError("uncertainties.evidence debe ser lista de maximo 10 elementos")
        normalized["evidence"] = [_self_model_text("uncertainties.evidence", e, 500) for e in normalized["evidence"]]
        if status == "resolved":
            if item.get("resolved_at") is None:
                raise ValidationError("uncertainties.resolved_at requerido cuando status=resolved")
            normalized["resolved_at"] = _self_model_iso("uncertainties.resolved_at", item["resolved_at"])
        elif item.get("resolved_at") is not None:
            raise ValidationError("uncertainties.resolved_at solo aplica cuando status=resolved")
        out.append(normalized)
    return out

def _validate_self_model_errors(value):
    allowed = {"id", "type", "message", "status", "occurrences", "first_seen_at", "last_seen_at", "evidence"}
    items = _self_model_record_list("errors", value, allowed)
    out = []
    for item in items:
        status = _self_model_text("errors.status", item.get("status"), 32)
        if status not in _SELF_MODEL_ERROR_STATUSES:
            raise ValidationError(f"errors.status invalido: {status!r}")
        occurrences = item.get("occurrences", 1)
        if isinstance(occurrences, bool) or not isinstance(occurrences, int) or occurrences < 1:
            raise ValidationError("errors.occurrences debe ser entero >= 1")
        evidence = item.get("evidence", [])
        if not isinstance(evidence, list) or len(evidence) > 10:
            raise ValidationError("errors.evidence debe ser lista de maximo 10 elementos")
        out.append({
            "id": _self_model_text("errors.id", item.get("id"), 128),
            "type": _self_model_text("errors.type", item.get("type"), 128),
            "message": _self_model_text("errors.message", item.get("message"), 2000),
            "status": status,
            "occurrences": occurrences,
            "first_seen_at": _self_model_iso("errors.first_seen_at", item.get("first_seen_at")),
            "last_seen_at": _self_model_iso("errors.last_seen_at", item.get("last_seen_at")),
            "evidence": [_self_model_text("errors.evidence", e, 500) for e in evidence],
        })
    return out

def _validate_self_model_repairs(value):
    allowed = {"id", "target", "reason", "status", "proposed_at", "started_at", "completed_at", "evidence", "result"}
    items = _self_model_record_list("repairs", value, allowed)
    out = []
    for item in items:
        status = _self_model_text("repairs.status", item.get("status"), 32)
        if status not in _SELF_MODEL_REPAIR_STATUSES:
            raise ValidationError(f"repairs.status invalido: {status!r}")
        normalized = {
            "id": _self_model_text("repairs.id", item.get("id"), 128),
            "target": _self_model_text("repairs.target", item.get("target"), 256),
            "reason": _self_model_text("repairs.reason", item.get("reason"), 2000),
            "status": status,
            "proposed_at": _self_model_iso("repairs.proposed_at", item.get("proposed_at")),
            "evidence": item.get("evidence", []),
            "result": _self_model_text("repairs.result", item.get("result", ""), 2000, allow_empty=True),
        }
        if status in ("running", "completed", "failed") and item.get("started_at") is None:
            raise ValidationError("repairs.started_at requerido para status activo/final")
        if status == "completed" and item.get("completed_at") is None:
            raise ValidationError("repairs.completed_at requerido cuando status=completed")
        if status not in ("completed", "failed", "cancelled") and item.get("completed_at") is not None:
            raise ValidationError("repairs.completed_at solo aplica a estados finalizados")
        for key in ("started_at", "completed_at"):
            if key in item and item.get(key) is not None:
                normalized[key] = _self_model_iso(f"repairs.{key}", item[key])
        if not isinstance(normalized["evidence"], list) or len(normalized["evidence"]) > 10:
            raise ValidationError("repairs.evidence debe ser lista de maximo 10 elementos")
        normalized["evidence"] = [_self_model_text("repairs.evidence", e, 500) for e in normalized["evidence"]]
        out.append(normalized)
    return out

def _validate_self_model_evolution(value):
    allowed = {"id", "proposal", "rationale", "status", "proposed_at", "implemented_at", "evidence"}
    items = _self_model_record_list("evolution", value, allowed)
    out = []
    for item in items:
        status = _self_model_text("evolution.status", item.get("status"), 32)
        if status not in _SELF_MODEL_EVOLUTION_STATUSES:
            raise ValidationError(f"evolution.status invalido: {status!r}")
        normalized = {
            "id": _self_model_text("evolution.id", item.get("id"), 128),
            "proposal": _self_model_text("evolution.proposal", item.get("proposal"), 2000),
            "rationale": _self_model_text("evolution.rationale", item.get("rationale"), 2000),
            "status": status,
            "proposed_at": _self_model_iso("evolution.proposed_at", item.get("proposed_at")),
            "evidence": item.get("evidence", []),
        }
        if status == "implemented":
            if item.get("implemented_at") is None:
                raise ValidationError("evolution.implemented_at requerido cuando status=implemented")
            normalized["implemented_at"] = _self_model_iso("evolution.implemented_at", item["implemented_at"])
        elif item.get("implemented_at") is not None:
            raise ValidationError("evolution.implemented_at solo aplica cuando status=implemented")
        if not isinstance(normalized["evidence"], list) or len(normalized["evidence"]) > 10:
            raise ValidationError("evolution.evidence debe ser lista de maximo 10 elementos")
        normalized["evidence"] = [_self_model_text("evolution.evidence", e, 500) for e in normalized["evidence"]]
        out.append(normalized)
    return out

def validate_self_model(data, partial: bool = False) -> dict:
    if not isinstance(data, dict):
        raise ValidationError("el registro debe ser un objeto")
    if not data:
        raise ValidationError("no hay cambios")
    extra = sorted(set(data) - _SELF_MODEL_UPDATABLE)
    if extra:
        derived = sorted(set(extra) & set(_SELF_MODEL_DERIVED_FIELDS))
        if derived:
            raise ValidationError(f"campos derivados, no editables: {derived}")
        raise ValidationError(f"campos no permitidos: {extra}")
    out = {}
    for field in _SELF_MODEL_OBJECT_FIELDS:
        if field not in data:
            continue
        value = data[field]
        if field == "current_state":
            out[field] = _validate_self_model_current_state(value)
        elif field == "knowledge_state":
            out[field] = _validate_self_model_knowledge_state(value)
        else:
            if not isinstance(value, dict):
                raise ValidationError(f"{field} debe ser un objeto (dict)")
            out[field] = value
    if "models" in data:
        models = _self_model_record_list("models", data["models"], {"provider", "model", "role"})
        out["models"] = [{
            "provider": _self_model_text("models.provider", item.get("provider"), 64),
            "model": _self_model_text("models.model", item.get("model"), 128),
            "role": _self_model_text("models.role", item.get("role"), 64),
        } for item in models]
    for field, fn in (
        ("uncertainties", _validate_self_model_uncertainties),
        ("errors", _validate_self_model_errors),
        ("repairs", _validate_self_model_repairs),
        ("evolution", _validate_self_model_evolution),
    ):
        if field in data:
            out[field] = fn(data[field])
    return out

_LEARNING_INPUT = {
    "source", "event", "lesson", "knowledge_nodes", "relationships",
    "confidence", "outcome", "status", "evidence", "verification_analysis",
    "learning_context", "verified_at", "verified_by", "reuse_count", "last_reused_at",
}
_LEARNING_UPDATABLE = {
    "source", "event", "lesson", "knowledge_nodes", "relationships",
    "confidence", "outcome", "status", "evidence", "verification_analysis",
    "learning_context", "verified_at", "verified_by", "reuse_count", "last_reused_at",
}

def _learning_evidence(value):
    if not isinstance(value, list):
        raise ValidationError("evidence debe ser una lista")
    if len(value) > 20:
        raise ValidationError("evidence admite maximo 20 elementos")
    out = []
    for item in value:
        if not isinstance(item, dict):
            raise ValidationError("cada evidencia debe ser un objeto")
        allowed = {"type", "title", "reference", "note"}
        extra = sorted(set(item) - allowed)
        if extra:
            raise ValidationError(f"campos de evidencia no permitidos: {extra}")
        typ = _str("evidence.type", item.get("type", "unknown"), 32)
        title = _str("evidence.title", item.get("title", ""), 200)
        reference = _str("evidence.reference", item.get("reference", ""), 500)
        note = _str("evidence.note", item.get("note", ""), 1000)
        if not title or not reference:
            raise ValidationError("cada evidencia requiere title y reference")
        out.append({"type": typ, "title": title, "reference": reference, "note": note})
    return out

def _learning_relationships(value):
    if not isinstance(value, list) or len(value) > 100:
        raise ValidationError("relationships debe ser una lista de maximo 100 elementos")
    out = []
    for item in value:
        if isinstance(item, str):
            # Compatibilidad con registros historicos que guardan solo IDs.
            out.append(_str("relationship", item, 256))
            continue
        if not isinstance(item, dict):
            raise ValidationError("cada relationship debe ser un objeto o un ID historico")
        allowed = {"from_node", "to_node", "relation_type", "weight", "confidence", "origin"}
        extra = sorted(set(item) - allowed)
        if extra:
            raise ValidationError(f"campos de relationship no permitidos: {extra}")
        from_node = _str("relationship.from_node", item.get("from_node", ""), 256)
        to_node = _str("relationship.to_node", item.get("to_node", ""), 256)
        relation_type = _str("relationship.relation_type", item.get("relation_type", ""), 64)
        if not from_node or not to_node or not relation_type:
            raise ValidationError("cada relationship requiere from_node, to_node y relation_type")
        weight = _non_negative_float("relationship.weight", item.get("weight", 1.0))
        confidence = _float_0_1("relationship.confidence", item.get("confidence", 0.5))
        origin = _str("relationship.origin", item.get("origin", "learning"), 64)
        out.append({
            "from_node": from_node,
            "to_node": to_node,
            "relation_type": relation_type,
            "weight": weight,
            "confidence": confidence,
            "origin": origin,
        })
    return out

def validate_learning_event(data, partial: bool = False) -> dict:
    if not isinstance(data, dict):
        raise ValidationError("el registro debe ser un objeto")
    allowed = _LEARNING_UPDATABLE if partial else _LEARNING_INPUT
    extra = sorted(set(data) - allowed)
    if extra:
        raise ValidationError(f"campos no permitidos: {extra}")
    if partial and not data:
        raise ValidationError("no hay cambios")
    if not partial:
        for req in ("source", "event", "lesson"):
            if req not in data:
                raise ValidationError(f"falta el campo obligatorio {req}")

    out = {}
    if "source" in data or not partial:
        out["source"] = _str("source", data.get("source", "unknown"), 64)
    if "event" in data:
        out["event"] = _str("event", data["event"], 500)
    if "lesson" in data:
        out["lesson"] = _str("lesson", data["lesson"], 5000)
    if "knowledge_nodes" in data or not partial:
        out["knowledge_nodes"] = _string_list("knowledge_nodes", data.get("knowledge_nodes", []), 100, 256)
    if "relationships" in data or not partial:
        out["relationships"] = _learning_relationships(data.get("relationships", []))
    if "confidence" in data or not partial:
        out["confidence"] = _float_0_1("confidence", data.get("confidence", 0.5))
    if "outcome" in data or not partial:
        out["outcome"] = _choice("outcome", data.get("outcome", "unknown"), LEARNING_OUTCOMES)
    if "status" in data or not partial:
        out["status"] = _choice("status", data.get("status", "candidate"), LEARNING_STATUSES)
    if "evidence" in data or not partial:
        out["evidence"] = _learning_evidence(data.get("evidence", []))
    if "learning_context" in data or not partial:
        value = data.get("learning_context", {})
        if not isinstance(value, dict):
            raise ValidationError("learning_context debe ser un objeto (dict)")
        out["learning_context"] = value
    if "verification_analysis" in data:
        analysis = data["verification_analysis"]
        if not isinstance(analysis, dict):
            raise ValidationError("verification_analysis debe ser un objeto")
        out["verification_analysis"] = analysis
    if "verified_at" in data:
        out["verified_at"] = _str("verified_at", data["verified_at"], 64)
    if "verified_by" in data:
        out["verified_by"] = _str("verified_by", data["verified_by"], 256)
    if "reuse_count" in data:
        out["reuse_count"] = _non_negative_int("reuse_count", data["reuse_count"])
    if "last_reused_at" in data:
        out["last_reused_at"] = _str("last_reused_at", data["last_reused_at"], 64)
    return out

_NODE_INPUT = {
    "node_type", "label", "description", "node_metadata", "tags", "weight", "confidence",
    "reuse_count", "owner_scope", "privacy_level", "status", "last_used_at",
}
_NODE_UPDATABLE = {
    "label", "description", "node_metadata", "tags", "weight", "confidence",
    "reuse_count", "privacy_level", "status", "last_used_at",
}

def validate_graph_node(data, partial: bool = False) -> dict:
    if not isinstance(data, dict):
        raise ValidationError("el registro debe ser un objeto")
    allowed = _NODE_UPDATABLE if partial else _NODE_INPUT
    extra = sorted(set(data) - allowed)
    if extra:
        raise ValidationError(f"campos no permitidos: {extra}")
    if partial and not data:
        raise ValidationError("no hay cambios")
    if not partial:
        for req in ("node_type", "label"):
            if req not in data:
                raise ValidationError(f"falta el campo obligatorio {req}")

    out = {}
    if "node_type" in data:
        out["node_type"] = _choice("node_type", data["node_type"], NODE_TYPES)
    if "label" in data:
        out["label"] = _str("label", data["label"], 200)
    if "description" in data:
        out["description"] = _str("description", data["description"], 2000, allow_empty=True)
    if "node_metadata" in data:
        v = data["node_metadata"]
        if not isinstance(v, dict):
            raise ValidationError("node_metadata debe ser un objeto (dict)")
        out["node_metadata"] = v
    if "tags" in data or not partial:
        out["tags"] = _tags(data.get("tags", []))
    if "weight" in data or not partial:
        out["weight"] = _non_negative_float("weight", data.get("weight", 1.0))
    if "confidence" in data or not partial:
        out["confidence"] = _float_0_1("confidence", data.get("confidence", 0.5))
    if "reuse_count" in data:
        out["reuse_count"] = _non_negative_int("reuse_count", data["reuse_count"])
    if "owner_scope" in data or not partial:
        out["owner_scope"] = _str("owner_scope", data.get("owner_scope", "owner"), 64)
    if "privacy_level" in data or not partial:
        out["privacy_level"] = _choice("privacy_level", data.get("privacy_level", "PRIVATE"), PRIVACY_LEVELS)
    if "status" in data:
        out["status"] = _choice("status", data["status"], STATUSES)
    if "last_used_at" in data:
        out["last_used_at"] = _str("last_used_at", data["last_used_at"], 64)
    return out

_EDGE_INPUT = {
    "from_node", "to_node", "relation_type", "weight", "confidence",
    "frequency", "origin", "success_count", "failure_count", "status", "last_used_at",
}
_EDGE_UPDATABLE = {
    "relation_type", "weight", "confidence", "frequency", "origin",
    "success_count", "failure_count", "status", "last_used_at",
}

def validate_graph_edge(data, partial: bool = False) -> dict:
    if not isinstance(data, dict):
        raise ValidationError("el registro debe ser un objeto")
    allowed = _EDGE_UPDATABLE if partial else _EDGE_INPUT
    extra = sorted(set(data) - allowed)
    if extra:
        raise ValidationError(f"campos no permitidos: {extra}")
    if partial and not data:
        raise ValidationError("no hay cambios")
    if not partial:
        for req in ("from_node", "to_node", "relation_type"):
            if req not in data:
                raise ValidationError(f"falta el campo obligatorio {req}")

    out = {}
    if "from_node" in data:
        out["from_node"] = _str("from_node", data["from_node"], 256)
    if "to_node" in data:
        out["to_node"] = _str("to_node", data["to_node"], 256)
    if "relation_type" in data:
        out["relation_type"] = _choice("relation_type", data["relation_type"], RELATION_TYPES)
    if "weight" in data or not partial:
        out["weight"] = _non_negative_float("weight", data.get("weight", 1.0))
    if "confidence" in data or not partial:
        out["confidence"] = _float_0_1("confidence", data.get("confidence", 0.5))
    if "frequency" in data or not partial:
        freq = data.get("frequency", 1)
        if isinstance(freq, bool) or not isinstance(freq, int) or freq < 1:
            raise ValidationError("frequency debe ser un entero >= 1")
        out["frequency"] = freq
    if "origin" in data or not partial:
        out["origin"] = _str("origin", data.get("origin", "unknown"), 64)
    if "success_count" in data:
        out["success_count"] = _non_negative_int("success_count", data["success_count"])
    if "failure_count" in data:
        out["failure_count"] = _non_negative_int("failure_count", data["failure_count"])
    if "status" in data:
        out["status"] = _choice("status", data["status"], STATUSES)
    if "last_used_at" in data:
        out["last_used_at"] = _str("last_used_at", data["last_used_at"], 64)
    return out

_CYCLE_INPUT = {"trigger", "input", "current_stage", "status", "completed_at"}
_CYCLE_UPDATABLE = {"current_stage", "status", "completed_at"}

def validate_cognitive_cycle(data, partial: bool = False) -> dict:
    if not isinstance(data, dict):
        raise ValidationError("el registro debe ser un objeto")
    allowed = _CYCLE_UPDATABLE if partial else _CYCLE_INPUT
    extra = sorted(set(data) - allowed)
    if extra:
        raise ValidationError(f"campos no permitidos: {extra}")
    if partial and not data:
        raise ValidationError("no hay cambios")
    if not partial and "trigger" not in data:
        raise ValidationError("falta el campo obligatorio trigger")

    out = {}
    if "trigger" in data:
        out["trigger"] = _str("trigger", data["trigger"], 64)
    if "input" in data:
        v = data["input"]
        if not isinstance(v, dict):
            raise ValidationError("input debe ser un objeto (dict)")
        out["input"] = v
    if "current_stage" in data or not partial:
        out["current_stage"] = _choice("current_stage", data.get("current_stage", "observe"), COGNITIVE_STAGES)
    if "status" in data or not partial:
        out["status"] = _choice("status", data.get("status", "in_progress"), COGNITIVE_CYCLE_STATUSES)
    if "completed_at" in data:
        out["completed_at"] = _str("completed_at", data["completed_at"], 64)
    return out

_EVENT_INPUT = {"cycle_id", "stage", "status", "data", "error"}

def validate_cognitive_event(data, partial: bool = False) -> dict:
    if partial:
        raise ValidationError("cognitive_events es append-only: no admite actualizaciones")
    if not isinstance(data, dict):
        raise ValidationError("el registro debe ser un objeto")
    extra = sorted(set(data) - _EVENT_INPUT)
    if extra:
        raise ValidationError(f"campos no permitidos: {extra}")
    for req in ("cycle_id", "stage"):
        if req not in data:
            raise ValidationError(f"falta el campo obligatorio {req}")

    out = {}
    out["cycle_id"] = _str("cycle_id", data["cycle_id"], 64)
    out["stage"] = _choice("stage", data["stage"], COGNITIVE_STAGES)
    out["status"] = _choice("status", data.get("status", "success"), ("success", "failure"))
    v = data.get("data", {})
    if not isinstance(v, dict):
        raise ValidationError("data debe ser un objeto (dict)")
    out["data"] = v
    if data.get("error") is not None:
        e = data["error"]
        if not isinstance(e, dict):
            raise ValidationError("error debe ser un objeto (dict) o None")
        out["error"] = e
    return out

_TOOL_INPUT = {
    "name", "description", "category", "permissions", "inputs_schema",
    "outputs_schema", "limits_json", "risks", "status",
}
_TOOL_UPDATABLE = {
    "description", "category", "permissions", "inputs_schema", "outputs_schema",
    "limits_json", "risks", "status",
}

def validate_tool(data, partial: bool = False) -> dict:
    if not isinstance(data, dict):
        raise ValidationError("el registro debe ser un objeto")
    allowed = _TOOL_UPDATABLE if partial else _TOOL_INPUT
    extra = sorted(set(data) - allowed)
    if extra:
        raise ValidationError(f"campos no permitidos: {extra}")
    if partial and not data:
        raise ValidationError("no hay cambios")
    if not partial:
        for req in ("name", "description"):
            if req not in data:
                raise ValidationError(f"falta el campo obligatorio {req}")

    out = {}
    if "name" in data:
        nm = _str("name", data["name"], 64)
        if not all(c.isalnum() or c in "_-" for c in nm):
            raise ValidationError("name solo admite letras, numeros, guion y guion bajo")
        out["name"] = nm
    if "description" in data:
        out["description"] = _str("description", data["description"], 1000)
    if "category" in data or not partial:
        out["category"] = _choice("category", data.get("category", "general"), TOOL_CATEGORIES)
    if "permissions" in data or not partial:
        out["permissions"] = _string_list("permissions", data.get("permissions", []), 20, 64)
    if "inputs_schema" in data or not partial:
        v = data.get("inputs_schema", {})
        if not isinstance(v, dict):
            raise ValidationError("inputs_schema debe ser un objeto (dict)")
        out["inputs_schema"] = v
    if "outputs_schema" in data or not partial:
        v = data.get("outputs_schema", {})
        if not isinstance(v, dict):
            raise ValidationError("outputs_schema debe ser un objeto (dict)")
        out["outputs_schema"] = v
    if "limits_json" in data or not partial:
        v = data.get("limits_json", {})
        if not isinstance(v, dict):
            raise ValidationError("limits_json debe ser un objeto (dict)")
        out["limits_json"] = v
    if "risks" in data or not partial:
        out["risks"] = _string_list("risks", data.get("risks", []), 20, 256)
    if "status" in data or not partial:
        out["status"] = _choice("status", data.get("status", "available"), TOOL_STATUSES)
    return out

_INVOCATION_INPUT = {
    "tool_name", "actor", "inputs", "outputs", "status", "error", "duration_ms",
}

def validate_tool_invocation(data, partial: bool = False) -> dict:
    if partial:
        raise ValidationError("tool_invocations es append-only: no admite actualizaciones")
    if not isinstance(data, dict):
        raise ValidationError("el registro debe ser un objeto")
    extra = sorted(set(data) - _INVOCATION_INPUT)
    if extra:
        raise ValidationError(f"campos no permitidos: {extra}")
    if "tool_name" not in data:
        raise ValidationError("falta el campo obligatorio tool_name")

    out = {}
    out["tool_name"] = _str("tool_name", data["tool_name"], 64)
    out["actor"] = _str("actor", data.get("actor", "system"), 64)
    v = data.get("inputs", {})
    if not isinstance(v, dict):
        raise ValidationError("inputs debe ser un objeto (dict)")
    out["inputs"] = v
    v = data.get("outputs", {})
    if not isinstance(v, dict):
        raise ValidationError("outputs debe ser un objeto (dict)")
    out["outputs"] = v
    out["status"] = _choice("status", data.get("status", "success"), ("success", "failure"))
    if data.get("error") is not None:
        e = data["error"]
        if not isinstance(e, dict):
            raise ValidationError("error debe ser un objeto (dict) o None")
        out["error"] = e
    out["duration_ms"] = _non_negative_int("duration_ms", data.get("duration_ms", 0))
    return out

_AGENT_INPUT = {
    "name", "role", "description", "allowed_tools", "status",
    "current_task_id", "current_action", "tasks_completed", "tasks_failed", "last_active_at",
}
_AGENT_UPDATABLE = {
    "description", "allowed_tools", "status", "current_task_id", "current_action",
    "tasks_completed", "tasks_failed", "last_active_at",
}

def validate_agent(data, partial: bool = False) -> dict:
    if not isinstance(data, dict):
        raise ValidationError("el registro debe ser un objeto")
    allowed = _AGENT_UPDATABLE if partial else _AGENT_INPUT
    extra = sorted(set(data) - allowed)
    if extra:
        raise ValidationError(f"campos no permitidos: {extra}")
    if partial and not data:
        raise ValidationError("no hay cambios")
    if not partial:
        for req in ("name", "role", "description"):
            if req not in data:
                raise ValidationError(f"falta el campo obligatorio {req}")

    out = {}
    if "name" in data:
        nm = _str("name", data["name"], 64)
        if not all(c.isalnum() or c in "_-" for c in nm):
            raise ValidationError("name solo admite letras, numeros, guion y guion bajo")
        out["name"] = nm
    if "role" in data:
        out["role"] = _choice("role", data["role"], AGENT_ROLES)
    if "description" in data:
        out["description"] = _str("description", data["description"], 1000)
    if "allowed_tools" in data or not partial:
        out["allowed_tools"] = _string_list("allowed_tools", data.get("allowed_tools", []), 30, 64)
    if "status" in data or not partial:
        out["status"] = _choice("status", data.get("status", "idle"), AGENT_STATUSES)
    if "current_task_id" in data:
        out["current_task_id"] = _optional_str("current_task_id", data["current_task_id"], 64)
    if "current_action" in data:
        out["current_action"] = _optional_str("current_action", data["current_action"], 200)
    if "tasks_completed" in data:
        out["tasks_completed"] = _non_negative_int("tasks_completed", data["tasks_completed"])
    if "tasks_failed" in data:
        out["tasks_failed"] = _non_negative_int("tasks_failed", data["tasks_failed"])
    if "last_active_at" in data:
        out["last_active_at"] = _optional_str("last_active_at", data["last_active_at"], 64)
    return out

_TASK_INPUT = {
    "agent_name", "tool_name", "status", "model", "mission_id",
    "owner_scope", "inputs", "outputs", "memory_used", "error", "duration_ms",
    "started_at", "completed_at",
}
_TASK_UPDATABLE = {
    "status", "model", "mission_id", "outputs", "memory_used", "error",
    "duration_ms", "started_at", "completed_at",
}

def validate_agent_task(data, partial: bool = False) -> dict:
    if not isinstance(data, dict):
        raise ValidationError("el registro debe ser un objeto")
    allowed = _TASK_UPDATABLE if partial else _TASK_INPUT
    extra = sorted(set(data) - allowed)
    if extra:
        raise ValidationError(f"campos no permitidos: {extra}")
    if partial and not data:
        raise ValidationError("no hay cambios")
    if not partial:
        for req in ("agent_name", "tool_name"):
            if req not in data:
                raise ValidationError(f"falta el campo obligatorio {req}")

    out = {}
    if "agent_name" in data:
        out["agent_name"] = _str("agent_name", data["agent_name"], 64)
    if "tool_name" in data:
        out["tool_name"] = _str("tool_name", data["tool_name"], 64)
    if "status" in data or not partial:
        out["status"] = _choice("status", data.get("status", "pending"), AGENT_TASK_STATUSES)
    if "model" in data:
        out["model"] = _optional_str("model", data["model"], 64)
    if "mission_id" in data:
        out["mission_id"] = _optional_str("mission_id", data["mission_id"], 64)
    if "owner_scope" in data:
        out["owner_scope"] = _str("owner_scope", data["owner_scope"], 64)
    if "inputs" in data or not partial:
        v = data.get("inputs", {})
        if not isinstance(v, dict):
            raise ValidationError("inputs debe ser un objeto (dict)")
        out["inputs"] = v
    if "outputs" in data or not partial:
        v = data.get("outputs", {})
        if not isinstance(v, dict):
            raise ValidationError("outputs debe ser un objeto (dict)")
        out["outputs"] = v
    if "memory_used" in data or not partial:
        out["memory_used"] = _string_list("memory_used", data.get("memory_used", []), 100, 256)
    if "error" in data:
        if data["error"] is None:
            out["error"] = None
        else:
            e = data["error"]
            if not isinstance(e, dict):
                raise ValidationError("error debe ser un objeto (dict) o None")
            out["error"] = e
    if "duration_ms" in data:
        out["duration_ms"] = _non_negative_int("duration_ms", data["duration_ms"])
    if "started_at" in data:
        out["started_at"] = _optional_str("started_at", data["started_at"], 64)
    if "completed_at" in data:
        out["completed_at"] = _optional_str("completed_at", data["completed_at"], 64)
    return out

_MISSION_INPUT = {
    "title", "objective", "description", "status", "priority",
    "created_by", "authorized_by", "flow_type", "flow_config",
    "plan", "parent_mission_id", "success_criteria", "result",
    "learning_refs", "started_at", "completed_at",
}
_MISSION_UPDATABLE = {
    "title", "objective", "description", "status", "priority",
    "authorized_by", "flow_config", "plan", "success_criteria",
    "result", "learning_refs", "started_at", "completed_at",
}

def validate_mission(data, partial: bool = False) -> dict:
    """Valida un registro de mision. Obligatorios al crear: title, objective.
    created_by lo agrega el servicio desde el actor si no viene."""
    if not isinstance(data, dict):
        raise ValidationError("el registro debe ser un objeto")
    allowed = _MISSION_UPDATABLE if partial else _MISSION_INPUT
    extra = sorted(set(data) - allowed)
    if extra:
        raise ValidationError(f"campos no permitidos: {extra}")
    if partial and not data:
        raise ValidationError("no hay cambios")
    if not partial:
        for req in ("title", "objective"):
            if req not in data:
                raise ValidationError(f"falta el campo obligatorio {req}")

    out = {}
    if "title" in data:
        out["title"] = _str("title", data["title"], 200)
    if "objective" in data:
        out["objective"] = _str("objective", data["objective"], 2000)
    if "description" in data:
        out["description"] = _optional_str("description", data["description"], 5000)
    if "status" in data or not partial:
        out["status"] = _choice("status", data.get("status", "created"), MISSION_STATUSES)
    if "priority" in data or not partial:
        priority = data.get("priority", 5)
        if isinstance(priority, bool) or not isinstance(priority, int) or not 1 <= priority <= 10:
            raise ValidationError("priority debe ser un entero entre 1 y 10")
        out["priority"] = priority
    if "created_by" in data:
        out["created_by"] = _str("created_by", data["created_by"], 200)
    if "authorized_by" in data:
        out["authorized_by"] = _optional_str("authorized_by", data["authorized_by"], 200)
    if "flow_type" in data or not partial:
        out["flow_type"] = _choice("flow_type", data.get("flow_type", "generic"), MISSION_FLOW_TYPES)
    if "flow_config" in data or not partial:
        v = data.get("flow_config", {})
        if not isinstance(v, dict):
            raise ValidationError("flow_config debe ser un objeto (dict)")
        out["flow_config"] = v
    if "plan" in data or not partial:
        v = data.get("plan", {})
        if not isinstance(v, dict):
            raise ValidationError("plan debe ser un objeto (dict)")
        out["plan"] = v
    if "parent_mission_id" in data:
        out["parent_mission_id"] = _optional_str("parent_mission_id", data["parent_mission_id"], 64)
    if "success_criteria" in data:
        out["success_criteria"] = _optional_str("success_criteria", data["success_criteria"], 2000)
    if "result" in data or not partial:
        v = data.get("result", {})
        if not isinstance(v, dict):
            raise ValidationError("result debe ser un objeto (dict)")
        out["result"] = v
    if "learning_refs" in data or not partial:
        out["learning_refs"] = _string_list("learning_refs", data.get("learning_refs", []), 100, 256)
    if "started_at" in data:
        out["started_at"] = _optional_str("started_at", data["started_at"], 64)
    if "completed_at" in data:
        out["completed_at"] = _optional_str("completed_at", data["completed_at"], 64)
    return out

# Fase 10.7.2: validadores de conversaciones.
_CONVERSATION_INPUT = {"title", "created_by", "status", "message_count", "last_message_at"}
_CONVERSATION_UPDATABLE = {"title", "status", "message_count", "last_message_at"}

def validate_conversation(data, partial: bool = False) -> dict:
    """Valida una conversacion. Al crear, created_by se auto-rellena desde el actor
    si no viene, y title se genera a partir del primer mensaje."""
    if not isinstance(data, dict):
        raise ValidationError("el registro debe ser un objeto")
    allowed = _CONVERSATION_UPDATABLE if partial else _CONVERSATION_INPUT
    extra = sorted(set(data) - allowed)
    if extra:
        raise ValidationError(f"campos no permitidos: {extra}")
    if partial and not data:
        raise ValidationError("no hay cambios")
    if not partial and "title" not in data:
        raise ValidationError("falta el campo obligatorio title")

    out = {}
    if "title" in data:
        out["title"] = _str("title", data["title"], 200)
    if "created_by" in data:
        out["created_by"] = _str("created_by", data["created_by"], 200)
    if "status" in data or not partial:
        out["status"] = _choice("status", data.get("status", "active"), CONVERSATION_STATUSES)
    if "message_count" in data:
        out["message_count"] = _non_negative_int("message_count", data["message_count"])
    if "last_message_at" in data:
        out["last_message_at"] = _optional_str("last_message_at", data["last_message_at"], 64)
    return out

_MESSAGE_INPUT = {
    "conversation_id", "role", "content", "model",
    "memories_used", "error", "duration_ms",
}

def validate_conversation_message(data, partial: bool = False) -> dict:
    """Valida un mensaje. Es append-only: una vez escrito, no se edita."""
    if partial:
        raise ValidationError("conversation_messages es append-only: no admite actualizaciones")
    if not isinstance(data, dict):
        raise ValidationError("el registro debe ser un objeto")
    extra = sorted(set(data) - _MESSAGE_INPUT)
    if extra:
        raise ValidationError(f"campos no permitidos: {extra}")
    for req in ("conversation_id", "role", "content"):
        if req not in data:
            raise ValidationError(f"falta el campo obligatorio {req}")

    out = {}
    out["conversation_id"] = _str("conversation_id", data["conversation_id"], 64)
    out["role"] = _choice("role", data["role"], MESSAGE_ROLES)
    out["content"] = _str("content", data["content"], 50000)
    if data.get("model") is not None:
        out["model"] = _optional_str("model", data["model"], 64)
    if data.get("memories_used") is not None:
        out["memories_used"] = _string_list("memories_used", data["memories_used"], 100, 256)
    if data.get("error") is not None:
        e = data["error"]
        if not isinstance(e, dict):
            raise ValidationError("error debe ser un objeto (dict) o None")
        out["error"] = e
    if "duration_ms" in data:
        out["duration_ms"] = _non_negative_int("duration_ms", data["duration_ms"])
    return out

def normalize_filters(entity: str, filters):
    """Devuelve [(tipo, campo, valor)]. Solo campos en lista blanca; nunca se interpola texto del usuario en SQL."""
    spec = entity_spec(entity)
    out = []
    for key, value in (filters or {}).items():
        if value is None:
            raise ValidationError(f"filtro {key} sin valor")
        if key == "text_contains":
            if entity != "memories":
                raise ValidationError("text_contains solo esta disponible para memories")
            out.append(("text", "content", _str("text_contains", value, 200)))
        elif key == "tag":
            if entity not in ("memories", "graph_nodes"):
                raise ValidationError("tag solo esta disponible para memories y graph_nodes")
            out.append(("tag", "tags", _str("tag", value, 64)))
        elif key.endswith("__in"):
            field = key[:-4]
            if field not in spec["in_filterable"]:
                raise ValidationError(f"filtro no permitido: {key}")
            if not isinstance(value, (list, tuple)) or not value or not all(isinstance(v, str) for v in value):
                raise ValidationError(f"{key} debe ser una lista no vacia de textos")
            out.append(("in", field, list(value)))
        elif key in spec["filterable"]:
            out.append(("eq", key, value))
        else:
            raise ValidationError(f"filtro no permitido: {key}")
    return out

class PersistenceRepository(ABC):
    """Contrato de almacenamiento (Fase 4 s3). Sin logica cognitiva: solo guardar y recuperar."""

    @abstractmethod
    def create(self, entity: str, record: dict): ...

    @abstractmethod
    def get(self, entity: str, record_id: str): ...

    @abstractmethod
    def update(self, entity: str, record_id: str, changes: dict, expected_version: int) -> dict: ...

    @abstractmethod
    def delete(self, entity: str, record_id: str) -> bool: ...

    @abstractmethod
    def exists(self, entity: str, record_id: str) -> bool: ...

    @abstractmethod
    def search(self, entity: str, filters=None, limit: int = 50, offset: int = 0,
               order_by: str = "created_at", descending: bool = True) -> list: ...

    def list(self, entity: str, limit: int = 50, offset: int = 0) -> list:
        return self.search(entity, None, limit=limit, offset=offset)

    @abstractmethod
    def count(self, entity: str, filters=None) -> int: ...

    @abstractmethod
    def transaction(self): ...

    @abstractmethod
    def append_audit(self, entry: dict) -> None: ...

    @abstractmethod
    def audit_search(self, actor=None, action_prefix=None, limit: int = 20) -> list: ...

    @abstractmethod
    def ping(self) -> dict: ...
