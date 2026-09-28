"""Migraciones explicitas (Fase 3 s22). Nunca se edita una migracion ya aplicada: se agrega una nueva.
Regla del ejecutor: sentencias separadas por ';' (no usar ';' dentro de textos ni comentarios)."""

MIGRATIONS = [
    (
        "001_memories_audit",
        """
        CREATE TABLE memories (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            memory_type TEXT NOT NULL CHECK (memory_type IN ('episodic','semantic','procedural','working','user_context','system')),
            importance INTEGER NOT NULL DEFAULT 5 CHECK (importance BETWEEN 0 AND 10),
            confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5 CHECK (confidence BETWEEN 0 AND 1),
            source TEXT NOT NULL DEFAULT 'unknown',
            source_id TEXT,
            source_reference TEXT,
            created_by TEXT NOT NULL DEFAULT 'system',
            tags JSONB NOT NULL DEFAULT '[]'::jsonb,
            owner_scope TEXT NOT NULL DEFAULT 'owner',
            privacy_level TEXT NOT NULL DEFAULT 'PRIVATE' CHECK (privacy_level IN ('PRIVATE','SENSITIVE','SHAREABLE','COLLECTIVE')),
            status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived','deleted')),
            schema_version TEXT NOT NULL DEFAULT 'memory.v1',
            version INTEGER NOT NULL DEFAULT 1,
            idempotency_key TEXT,
            access_count INTEGER NOT NULL DEFAULT 0,
            last_accessed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE UNIQUE INDEX memories_idempotency_key_uq ON memories (idempotency_key);
        CREATE INDEX memories_scope_type_status_idx ON memories (owner_scope, memory_type, status);
        CREATE INDEX memories_importance_idx ON memories (importance DESC, created_at DESC);
        CREATE INDEX memories_last_accessed_idx ON memories (last_accessed_at);
        CREATE INDEX memories_privacy_status_idx ON memories (privacy_level, status);
        CREATE TABLE audit_log (
            id BIGSERIAL PRIMARY KEY,
            ts TIMESTAMPTZ NOT NULL DEFAULT now(),
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            resource TEXT NOT NULL,
            resource_id TEXT,
            status TEXT NOT NULL CHECK (status IN ('success','failure')),
            detail JSONB NOT NULL DEFAULT '{}'::jsonb
        );
        CREATE INDEX audit_actor_action_idx ON audit_log (actor, action, ts DESC)
        """,
    ),
]
