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
KNOWLEDGE_SCHEMA_VERSION = "knowledge.v1"
KNOWLEDGE_VERIFICATION_STATUSES = ("unknown", "unverified", "partially_verified", "verified", "deprecated", "contradicted")

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
AGENT_TASK_STATUSES = ("pending", "running", "completed", "failed", "cancelled")

AGENT_ROLES = (
    "researcher", "memorizer", "graph_builder", "learner",
    "internal", "developer", "tester", "reviewer", "autonomy_orchestrator", "generic",
)

MISSION_SCHEMA_VERSION = "mission.v1"
MISSION_STATUSES = (
    "created", "planning", "running", "paused", "waiting_approval",
    "completed", "failed", "cancelled",
)
MISSION_FLOW_TYPES = ("generic",)

EVOLUTION_SCHEMA_VERSION = "evolution.v1"
EVOLUTION_STATUSES = (
    "detected", "researching", "designing", "prototyping",
    "testing", "evaluating", "applied", "rejected", "failed",