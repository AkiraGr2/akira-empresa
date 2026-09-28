"""Repositorio en memoria: SOLO para probar la logica del servicio (validacion, idempotencia, versiones,
privacidad, rollback). NO demuestra persistencia real: eso lo demuestra Postgres tras un reinicio."""
from __future__ import annotations

import copy
from contextlib import contextmanager
from datetime import datetime, timezone

from .core import (ConflictError, NotFoundError, PersistenceRepository, ValidationError,
                   entity_spec, normalize_filters)


def _now():
    return datetime.now(timezone.utc).isoformat()


class InMemoryRepository(PersistenceRepository):
    def __init__(self):
        self._data = {"memories": {}}
        self._audit = []

    # -- helpers
    def _match(self, entity, rec, filters):
        for kind, field, value in normalize_filters(entity, filters):
            if kind == "eq" and rec.get(field) != value:
                return False
            if kind == "in" and rec.get(field) not in value:
                return False
            if kind == "text" and value.lower() not in rec["content"].lower():
                return False
            if kind == "tag" and value not in rec.get("tags", []):
                return False
        return True

    # -- interface
    def create(self, entity, record):
        spec = entity_spec(entity)
        table = self._data[entity]
        key = record.get("idempotency_key")
        if spec["idempotent"] and key is not None:
            for existing in table.values():
                if existing.get("idempotency_key") == key:
                    return copy.deepcopy(existing), False
        if record["id"] in table:
            raise ValidationError("id duplicado")
        now = _now()
        stored = {c: None for c in spec["columns"]}
        stored.update(copy.deepcopy(record))
        stored.update(version=1, created_at=now, updated_at=now, access_count=0, last_accessed_at=None)
        table[stored["id"]] = stored
        return copy.deepcopy(stored), True

    def get(self, entity, record_id):
        entity_spec(entity)
        rec = self._data[entity].get(record_id)
        return copy.deepcopy(rec) if rec else None

    def update(self, entity, record_id, changes, expected_version):
        spec = entity_spec(entity)
        bad = sorted(set(changes) - set(spec["mutable"]))
        if bad or not changes:
            raise ValidationError(f"cambios no permitidos o vacios: {bad}")
        rec = self._data[entity].get(record_id)
        if rec is None:
            raise NotFoundError(record_id)
        if rec["version"] != expected_version:
            raise ConflictError(f"version esperada {expected_version}, real {rec['version']}")
        rec.update(copy.deepcopy(changes))
        rec["version"] += 1
        rec["updated_at"] = _now()
        return copy.deepcopy(rec)

    def delete(self, entity, record_id):
        return self._data[entity].pop(record_id, None) is not None

    def exists(self, entity, record_id):
        return record_id in self._data[entity]

    def search(self, entity, filters=None, limit=50, offset=0, order_by="created_at", descending=True):
        spec = entity_spec(entity)
        if order_by not in spec["orderable"]:
            raise ValidationError(f"order_by no permitido: {order_by}")
        rows = [r for r in self._data[entity].values() if self._match(entity, r, filters)]
        rows.sort(key=lambda r: (r.get(order_by) is None, r.get(order_by), r["id"]), reverse=descending)
        return copy.deepcopy(rows[offset:offset + limit])

    def count(self, entity, filters=None):
        return sum(1 for r in self._data[entity].values() if self._match(entity, r, filters))

    @contextmanager
    def transaction(self):
        snapshot = copy.deepcopy((self._data, self._audit))
        try:
            yield self
        except BaseException:
            self._data, self._audit = snapshot
            raise

    def append_audit(self, entry):
        row = dict(entry)
        row["ts"] = _now()
        self._audit.append(copy.deepcopy(row))

    def audit_search(self, actor=None, action_prefix=None, limit=20):
        rows = [r for r in reversed(self._audit)
                if (actor is None or r["actor"] == actor)
                and (action_prefix is None or r["action"].startswith(action_prefix))]
        return copy.deepcopy(rows[:limit])

    def ping(self):
        return {"ok": True, "backend": "memory"}
