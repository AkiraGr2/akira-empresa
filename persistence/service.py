"""PersistenceService: unica puerta de entrada para guardar y recuperar estado de AKIRA (Fase 4).

Secuencia de toda escritura importante: VALIDATE -> WRITE -> COMMIT -> VERIFY -> RETURN SUCCESS.
Si algo falla se lanza una excepcion: nunca se devuelve exito ("guardado") sobre una escritura no confirmada.
El servicio guarda y recupera; NO decide relevancia, significado ni que aprender (eso es Memory Engine).
"""
from __future__ import annotations

from .core import (HIVE_VISIBLE, MEMORY_SCHEMA_VERSION, ConflictError, NotFoundError, PersistenceError,
                   StorageError, ValidationError, VerificationError, new_id, validate_memory)

_COMPARE_FIELDS = ("content", "memory_type", "importance", "confidence", "tags", "privacy_level",
                   "source", "owner_scope")


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
