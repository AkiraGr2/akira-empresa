"""AKIRA V8-A - Persistence core: errores, esquema de entidades, validacion e interfaz del repositorio.

Regla (Fase 4): ningun modulo cognitivo escribe directo en la base.
Flujo: Modulo cognitivo -> PersistenceService -> PersistenceRepository -> Storage.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod


# ---------------------------------------------------------------- errores
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


# ---------------------------------------------------------------- constantes
MEMORY_TYPES = ("episodic", "semantic", "procedural", "working", "user_context", "system")
PRIVACY_LEVELS = ("PRIVATE", "SENSITIVE", "SHAREABLE", "COLLECTIVE")
HIVE_VISIBLE = ("SHAREABLE", "COLLECTIVE")  # PRIVATE y SENSITIVE nunca entran al Hive
STATUSES = ("active", "archived", "deleted")
MEMORY_SCHEMA_VERSION = "memory.v1"

# V8-Fase5: self-model es una entidad singleton (id fijo "akira_primary").
SELF_MODEL_PRIMARY_ID = "akira_primary"
SELF_MODEL_SCHEMA_VERSION = "self_model.v1"


def new_id(prefix: str) -> str:
    """Formato Fase 3: <tipo>_<uuid>."""
    return f"{prefix}_{uuid.uuid4().hex}"


# ---------------------------------------------------------------- esquema de entidades
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
    },
    # V8-Fase5: self-model persistente. Una sola fila con id="akira_primary".
    # Todos los campos cognitivos son JSONB (estructurados, no texto).
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
            "identity", "purpose", "capabilities", "tools", "models",
            "current_state", "knowledge_state", "uncertainties", "errors",
            "repairs", "evolution",
        ),
        "filterable": ("id", "idempotency_key"),
        "in_filterable": (),
        "orderable": ("created_at", "updated_at"),
        "idempotent": True,
    },
}


def entity_spec(entity: str) -> dict:
    try:
        return ENTITIES[entity]
    except KeyError:
        raise ValidationError(f"entidad desconocida: {entity!r}") from None


# ---------------------------------------------------------------- validacion
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


_MEMORY_INPUT = {
    "content", "memory_type", "importance", "confidence", "source", "source_id",
    "source_reference", "created_by", "tags", "owner_scope", "privacy_level",
}
_MEMORY_UPDATABLE = {
    "content", "memory_type", "importance", "confidence", "source_reference", "tags", "privacy_level",
}


def validate_memory(data, partial: bool = False) -> dict:
    """Valida un MemoryRecord (Fase 3 s4). partial=True para cambios de update.

    Rechaza campos desconocidos y campos que solo el sistema controla (id, version, timestamps).
    La privacidad por defecto es PRIVATE.
    """
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


# V8-Fase5: validador del self-model. Los campos son JSONB estructurados,
# no texto libre. Acepta dicts para los "objetos" y listas para los "listados".
_SELF_MODEL_OBJECT_FIELDS = ("identity", "purpose", "current_state", "knowledge_state")
_SELF_MODEL_LIST_FIELDS = ("capabilities", "tools", "models", "uncertainties", "errors", "repairs", "evolution")
_SELF_MODEL_UPDATABLE = frozenset(_SELF_MODEL_OBJECT_FIELDS + _SELF_MODEL_LIST_FIELDS)


def validate_self_model(data, partial: bool = False) -> dict:
    """Valida cambios sobre el self-model.

    Reglas:
      - Solo acepta los 11 campos JSONB declarados.
      - Los 4 campos "objeto" (identity, purpose, current_state, knowledge_state) deben ser dict.
      - Los 7 campos "lista" (capabilities, tools, models, ...) deben ser list.
      - No admite dict vacio: si no hay cambios reales, es un error.
    partial se acepta por simetria con validate_memory, pero aqui no hay modo
    "creacion completa": el self-model siempre se actualiza por partes.
    """
    if not isinstance(data, dict):
        raise ValidationError("el registro debe ser un objeto")
    if not data:
        raise ValidationError("no hay cambios")
    extra = sorted(set(data) - _SELF_MODEL_UPDATABLE)
    if extra:
        raise ValidationError(f"campos no permitidos: {extra}")
    out = {}
    for field in _SELF_MODEL_OBJECT_FIELDS:
        if field in data:
            v = data[field]
            if not isinstance(v, dict):
                raise ValidationError(f"{field} debe ser un objeto (dict)")
            out[field] = v
    for field in _SELF_MODEL_LIST_FIELDS:
        if field in data:
            v = data[field]
            if not isinstance(v, list):
                raise ValidationError(f"{field} debe ser una lista")
            out[field] = v
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
            if entity != "memories":
                raise ValidationError("tag solo esta disponible para memories")
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


# ---------------------------------------------------------------- interfaz del repositorio
class PersistenceRepository(ABC):
    """Contrato de almacenamiento (Fase 4 s3). Sin logica cognitiva: solo guardar y recuperar."""

    @abstractmethod
    def create(self, entity: str, record: dict):
        """Inserta. Devuelve (registro_guardado, creado_bool). Con idempotency_key repetida devuelve el existente y False."""

    @abstractmethod
    def get(self, entity: str, record_id: str):
        """Devuelve el registro o None."""

    @abstractmethod
    def update(self, entity: str, record_id: str, changes: dict, expected_version: int) -> dict:
        """Actualiza con bloqueo optimista. NotFoundError o ConflictError si corresponde."""

    @abstractmethod
    def delete(self, entity: str, record_id: str) -> bool:
        """Borrado fisico. Reservado a politicas de retencion: el servicio usa archived."""

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
    def transaction(self):
        """Context manager: `with repo.transaction() as tx:` ; commit al salir, rollback ante excepcion."""

    @abstractmethod
    def append_audit(self, entry: dict) -> None:
        """Auditoria (que hizo el sistema), separada de la memoria."""

    @abstractmethod
    def audit_search(self, actor=None, action_prefix=None, limit: int = 20) -> list: ...

    @abstractmethod
    def ping(self) -> dict: ...
