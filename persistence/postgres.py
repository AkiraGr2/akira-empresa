"""Repositorio PostgreSQL (Neon) con psycopg 3.

- SQL directo, sin ORM. Nombres de tabla/columna salen de una lista blanca (core.ENTITIES); los valores van parametrizados.
- Funciona con la URL directa de Neon y con la URL pooler (prepare_threshold=None).
- Cada `pool.connection()` hace commit al salir bien y rollback si hay excepcion.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .core import (ConflictError, NotFoundError, PersistenceRepository, StorageError,
                   ValidationError, entity_spec, normalize_filters)
from .migrations import MIGRATIONS

_MIGRATION_LOCK_ID = 8100001


def _out(row):
    if row is None:
        return None
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


def _like_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def make_pool(database_url: str):
    """Pool pequeno (plan gratis). Neon suspende el computo por inactividad: se valida la conexion al prestarla."""
    from psycopg_pool import ConnectionPool
    return ConnectionPool(
        database_url,
        min_size=1,
        max_size=4,
        open=False,
        timeout=30,
        max_idle=240,
        max_lifetime=1800,
        check=ConnectionPool.check_connection,
        kwargs={"connect_timeout": 15, "prepare_threshold": None},
    )


def migrate(pool) -> list:
    """Aplica migraciones pendientes en UNA transaccion, con candado para que dos procesos no migren a la vez."""
    applied_now = []
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (_MIGRATION_LOCK_ID,))
            cur.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
            )
            cur.execute("SELECT version FROM schema_migrations")
            done = {r[0] for r in cur.fetchall()}
            for version, sql in MIGRATIONS:
                if version in done:
                    continue
                for stmt in (s.strip() for s in sql.split(";")):
                    if stmt:
                        cur.execute(stmt)
                cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
                applied_now.append(version)
    return applied_now


class PostgresRepository(PersistenceRepository):
    def __init__(self, pool=None, conn=None):
        if pool is None and conn is None:
            raise ValueError("se requiere pool o conn")
        self._pool = pool
        self._conn = conn  # no None solo dentro de transaction()

    # -- infraestructura
    @contextmanager
    def _cursor(self):
        try:
            if self._conn is not None:
                with self._conn.cursor(row_factory=dict_row) as cur:
                    yield cur
            else:
                with self._pool.connection() as conn:
                    with conn.cursor(row_factory=dict_row) as cur:
                        yield cur
        except psycopg.Error as e:
            raise StorageError(type(e).__name__) from e

    @contextmanager
    def transaction(self):
        if self._conn is not None:  # ya estamos dentro de una transaccion
            yield self
            return
        try:
            with self._pool.connection() as conn:
                yield PostgresRepository(conn=conn)
        except psycopg.Error as e:
            raise StorageError(type(e).__name__) from e

    @staticmethod
    def _where(entity, filters):
        clauses, params = [], []
        for kind, field, value in normalize_filters(entity, filters):
            if kind == "eq":
                clauses.append(f"{field} = %s")
                params.append(value)
            elif kind == "in":
                clauses.append(f"{field} = ANY(%s::text[])")
                params.append(list(value))
            elif kind == "text":
                clauses.append("content ILIKE %s ESCAPE '\\'")
                params.append("%" + _like_escape(value) + "%")
            elif kind == "tag":
                clauses.append("tags @> %s")
                params.append(Jsonb([value]))
        return (" WHERE " + " AND ".join(clauses)) if clauses else "", params

    # -- CRUD
    def create(self, entity, record):
        spec = entity_spec(entity)
        cols = [c for c in spec["columns"] if c in record]
        vals = [Jsonb(record[c]) if c in spec["json_columns"] else record[c] for c in cols]
        sql = (f"INSERT INTO {spec['table']} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) "
               "ON CONFLICT (idempotency_key) DO NOTHING RETURNING *")
        with self._cursor() as cur:
            cur.execute(sql, vals)
            row = cur.fetchone()
            if row is not None:
                return _out(row), True
            key = record.get("idempotency_key")
            cur.execute(f"SELECT * FROM {spec['table']} WHERE idempotency_key = %s", (key,))
            existing = cur.fetchone()
        if existing is None:
            raise StorageError("insert sin efecto y sin registro existente")
        return _out(existing), False

    def get(self, entity, record_id):
        spec = entity_spec(entity)
        with self._cursor() as cur:
            cur.execute(f"SELECT * FROM {spec['table']} WHERE id = %s", (record_id,))
            return _out(cur.fetchone())

    def update(self, entity, record_id, changes, expected_version):
        spec = entity_spec(entity)
        bad = sorted(set(changes) - set(spec["mutable"]))
        if bad or not changes:
            raise ValidationError(f"cambios no permitidos o vacios: {bad}")
        sets = [f"{c} = %s" for c in changes]
        vals = [Jsonb(v) if c in spec["json_columns"] else v for c, v in changes.items()]
        sql = (f"UPDATE {spec['table']} SET {', '.join(sets)}, version = version + 1, updated_at = now() "
               "WHERE id = %s AND version = %s RETURNING *")
        with self._cursor() as cur:
            cur.execute(sql, vals + [record_id, expected_version])
            row = cur.fetchone()
            if row is None:
                cur.execute(f"SELECT version FROM {spec['table']} WHERE id = %s", (record_id,))
                cur_row = cur.fetchone()
                if cur_row is None:
                    raise NotFoundError(record_id)
                raise ConflictError(f"version esperada {expected_version}, real {cur_row['version']}")
        return _out(row)

    def delete(self, entity, record_id):
        spec = entity_spec(entity)
        with self._cursor() as cur:
            cur.execute(f"DELETE FROM {spec['table']} WHERE id = %s", (record_id,))
            return cur.rowcount > 0

    def exists(self, entity, record_id):
        spec = entity_spec(entity)
        with self._cursor() as cur:
            cur.execute(f"SELECT 1 AS x FROM {spec['table']} WHERE id = %s", (record_id,))
            return cur.fetchone() is not None

    def search(self, entity, filters=None, limit=50, offset=0, order_by="created_at", descending=True):
        spec = entity_spec(entity)
        if order_by not in spec["orderable"]:
            raise ValidationError(f"order_by no permitido: {order_by}")
        where, params = self._where(entity, filters)
        direction = "DESC" if descending else "ASC"
        sql = (f"SELECT * FROM {spec['table']}{where} ORDER BY {order_by} {direction} NULLS LAST, id "
               "LIMIT %s OFFSET %s")
        with self._cursor() as cur:
            cur.execute(sql, params + [int(limit), int(offset)])
            return [_out(r) for r in cur.fetchall()]

    def count(self, entity, filters=None):
        spec = entity_spec(entity)
        where, params = self._where(entity, filters)
        with self._cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {spec['table']}{where}", params)
            return int(cur.fetchone()["n"])

    @staticmethod
    def _vector_literal(values):
        if not isinstance(values, (list, tuple)) or not values:
            raise ValidationError("embedding debe ser una lista no vacia")
        return "[" + ",".join(f"{float(v):.9g}" for v in values) + "]"

    def get_memory_embedding(self, memory_id):
        with self._cursor() as cur:
            cur.execute(
                "SELECT memory_id, model, dimensions, source_hash, created_at, updated_at "
                "FROM memory_embeddings WHERE memory_id = %s",
                (memory_id,),
            )
            return _out(cur.fetchone())

    def upsert_memory_embedding(self, memory_id, model, embedding, source_hash):
        vector = self._vector_literal(embedding)
        dimensions = len(embedding)
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO memory_embeddings
                    (memory_id, model, dimensions, embedding, source_hash)
                VALUES (%s, %s, %s, %s::vector, %s)
                ON CONFLICT (memory_id) DO UPDATE SET
                    model = EXCLUDED.model,
                    dimensions = EXCLUDED.dimensions,
                    embedding = EXCLUDED.embedding,
                    source_hash = EXCLUDED.source_hash,
                    updated_at = now()
                RETURNING memory_id, model, dimensions, source_hash, created_at, updated_at
                """,
                (memory_id, model, dimensions, vector, source_hash),
            )
            row = cur.fetchone()
        return _out(row)

    def search_memory_embeddings(self, embedding, model, limit=20):
        vector = self._vector_literal(embedding)
        limit = max(1, min(int(limit), 100))
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT me.memory_id,
                       1 - (me.embedding <=> %s::vector) AS semantic_score
                FROM memory_embeddings me
                JOIN memories m ON m.id = me.memory_id
                WHERE me.model = %s
                  AND m.status = 'active'
                ORDER BY me.embedding <=> %s::vector
                LIMIT %s
                """,
                (vector, model, vector, limit),
            )
            return [_out(row) for row in cur.fetchall()]

    def delete_memory_embedding(self, memory_id):
        with self._cursor() as cur:
            cur.execute("DELETE FROM memory_embeddings WHERE memory_id = %s", (memory_id,))
            return cur.rowcount > 0

    # -- auditoria
    def append_audit(self, entry):
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO audit_log (actor, action, resource, resource_id, status, detail) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (entry["actor"], entry["action"], entry["resource"], entry.get("resource_id"),
                 entry["status"], Jsonb(entry.get("detail") or {})),
            )

    def audit_search(self, actor=None, action_prefix=None, limit=20):
        clauses, params = [], []
        if actor is not None:
            clauses.append("actor = %s")
            params.append(actor)
        if action_prefix is not None:
            clauses.append("action LIKE %s ESCAPE '\\'")
            params.append(_like_escape(action_prefix) + "%")
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._cursor() as cur:
            cur.execute(
                "SELECT ts, actor, action, resource, resource_id, status, detail FROM audit_log"
                f"{where} ORDER BY id DESC LIMIT %s", params + [int(limit)])
            return [_out(r) for r in cur.fetchall()]

    def ping(self):
        with self._cursor() as cur:
            cur.execute("SELECT version FROM schema_migrations ORDER BY version")
            return {"ok": True, "backend": "postgres", "migrations": [r["version"] for r in cur.fetchall()]}
