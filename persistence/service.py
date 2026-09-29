"""PersistenceService: unica puerta de entrada para guardar y recuperar estado de AKIRA (Fase 4).

Secuencia de toda escritura importante: VALIDATE -> WRITE -> COMMIT -> VERIFY -> RETURN SUCCESS.
Si algo falla se lanza una excepcion: nunca se devuelve exito ("guardado") sobre una escritura no confirmada.
El servicio guarda y recupera; NO decide relevancia, significado ni que aprender (eso es Memory Engine).

V8-Fase5: agrega soporte para self-model persistente (singleton con id="akira_primary").
"""
from __future__ import annotations

from .core import (HIVE_VISIBLE, MEMORY_SCHEMA_VERSION, SELF_MODEL_PRIMARY_ID,
                   SELF_MODEL_SCHEMA_VERSION, ConflictError, NotFoundError, PersistenceError,
                   StorageError, ValidationError, VerificationError, new_id, validate_memory,
                   validate_self_model)

_COMPARE_FIELDS = ("content", "memory_type", "importance", "confidence", "tags", "privacy_level",
                   "source", "owner_scope")

# V8-Fase5: valores iniciales del self-model. Se crean la primera vez que se lee.
# Son datos reales, verificables, sin placeholders ni afirmaciones no comprobables.
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
        {"name": "agents", "status": "not_implemented"},
        {"name": "missions", "status": "not_implemented"},
        {"name": "self_repair_full", "status": "not_implemented"},
        {"name": "evolution_engine", "status": "not_implemented"},
        {"name": "hive", "status": "not_implemented"},
        {"name": "knowledge_graph", "status": "not_implemented"},
    ],
    "tools": [
        {"name": "postgres", "role": "persistencia", "status": "verified"},
        {"name": "gemini", "role": "inferencia_primaria", "status": "verified"},
        {"name": "groq", "role": "inferencia_fallback", "status": "verified"},
        {"name": "google_auth", "role": "identidad", "status": "verified"},
        {"name": "pymupdf", "role": "pdf", "status": "verified"},
        {"name": "pollinations", "role": "imagen", "status": "verified"},
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
        "El grafo neuronal real todavia no existe.",
        "Los agentes y misiones todavia no existen.",
        "R2 tiene arquitectura preparada pero sin escritura real verificada.",
    ],
    "errors": [],
    "repairs": [],
    "evolution": [],
}


class PersistenceService:
    def __init__(self, repo):
        self.repo = repo

    # ------------------------------------------------------------ auditoria
    def record_audit(self, actor, action, resource, resource_id=None, status="success", detail=None):
        self.repo.append_audit({"actor": actor, "action": action, "resource": resource,
                                "resource_id": resource_id, "status": status, "detail": detail or {}})

    def _audit_failure(self, actor, action, resource_id, error):
        try:  # mejor esfuerzo: si la base esta caida esto tambien puede fallar
            self.record_audit(actor, action, "memories", resource_id, "failure",
                              {"error_type": type(error).__name__})
        except Exception:
            pass

    def recent_audit(self, actor=None, action_prefix=None, limit=20):
        return self.repo.audit_search(actor=actor, action_prefix=action_prefix, limit=limit)

    # ------------------------------------------------------------ memoria
    def save_memory(self, data, actor="system", idempotency_key=None):
        """Guarda una memoria. Devuelve {"outcome": "created"|"already_synced", "record": {...}, ...}."""
        fields = validate_memory(data)                                    # VALIDATE
        if "created_by" not in fields:
            fields["created_by"] = actor
        record = dict(fields, id=new_id("mem"), status="active", schema_version=MEMORY_SCHEMA_VERSION)
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str) or not 0 < len(idempotency_key.strip()) <= 200:
                raise ValidationError("idempotency_key debe ser texto de 1 a 200 caracteres")
            record["idempotency_key"] = idempotency_key.strip()

        try:
            with self.repo.transaction() as tx:                            # WRITE (+ auditoria, misma transaccion)
                stored, created = tx.create("memories", record)
                tx.append_audit({
                    "actor": actor,
                    "action": "memory.create" if created else "memory.create.already_synced",
                    "resource": "memories", "resource_id": stored["id"], "status": "success",
                    "detail": {"privacy_level": stored["privacy_level"], "memory_type": stored["memory_type"]},
                })
        except PersistenceError as e:                                      # COMMIT ocurre al salir del with
            self._audit_failure(actor, "memory.create", None, e)
            raise
        except Exception as e:
            self._audit_failure(actor, "memory.create", None, e)
            raise StorageError(type(e).__name__) from e

        verified = self.repo.get("memories", stored["id"])                 # VERIFY: relectura independiente
        if verified is None:
            raise VerificationError("escritura no confirmada: el registro no se puede releer")
        expected = stored if not created else fields
        for f in _COMPARE_FIELDS:
            if verified.get(f) != expected.get(f, verified.get(f)):
                raise VerificationError(f"escritura no confirmada: el campo {f} no coincide al releer")
        result = {"outcome": "created" if created else "already_synced", "record": verified}   # RETURN SUCCESS
        if not created:
            result["matches_request"] = all(verified.get(f) == fields.get(f) for f in fields if f in verified)
        return result

    def get_memory(self, memory_id):
        """Devuelve el registro o None."""
        return self.repo.get("memories", memory_id)

    def exists_memory(self, memory_id):
        return self.repo.exists("memories", memory_id)

    def update_memory(self, memory_id, changes, expected_version, actor="system"):
        """Actualiza con bloqueo optimista. ConflictError si otro proceso cambio la version."""
        clean = validate_memory(changes, partial=True)
        return self._update(memory_id, clean, expected_version, actor, "memory.update")

    def archive_memory(self, memory_id, expected_version=None, actor="system"):
        """Borrado logico: status=archived (la informacion cognitiva no se borra fisicamente)."""
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
            self._audit_failure(actor, action, memory_id, e)
            raise
        except Exception as e:
            self._audit_failure(actor, action, memory_id, e)
            raise StorageError(type(e).__name__) from e
        verified = self.repo.get("memories", memory_id)
        if (verified is None or verified["version"] != expected_version + 1
                or any(verified.get(k) != v for k, v in changes.items())):
            raise VerificationError("actualizacion no confirmada al releer")
        return verified

    # ------------------------------------------------------------ busqueda
    def _memory_filters(self, filters, hive):
        f = dict(filters or {})
        if "status" not in f and "status__in" not in f:
            f["status"] = "active"
        if hive:  # la visibilidad del Hive la impone el servicio: PRIVATE/SENSITIVE nunca entran
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

    # ------------------------------------------------------------ V8-Fase5: self-model
    def get_self_model(self):
        """Devuelve el self-model persistente. Si no existe, lo crea con valores iniciales.

        Reglas (Contrato V8 s2):
          - Recuperable tras reinicio: viene de Postgres, no de memoria del proceso.
          - No inventa: si el campo esta vacio, esta vacio. No hay "consciente: true".
          - Autoreparable: si la fila no existe, se crea con _SELF_MODEL_DEFAULTS.
        """
        current = self.repo.get("self_model", SELF_MODEL_PRIMARY_ID)
        if current is not None:
            return current
        # Crear por primera vez. La tabla tiene idempotency_key unica; si otro proceso
        # se adelanta, el repo devuelve la existente y created=False.
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
        """Actualiza el self-model con bloqueo optimista.

        Solo acepta los 11 campos JSONB declarados en validate_self_model.
        La version esperada debe coincidir; si no, ConflictError.
        """
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
        """Devuelve la version actual del self-model sin crearlo (None si no existe)."""
        current = self.repo.get("self_model", SELF_MODEL_PRIMARY_ID)
        return None if current is None else current.get("version")
