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
    (
        "002_self_model",
        """
        CREATE TABLE self_model (
            id TEXT PRIMARY KEY,
            identity JSONB NOT NULL DEFAULT '{}'::jsonb,
            purpose JSONB NOT NULL DEFAULT '{}'::jsonb,
            capabilities JSONB NOT NULL DEFAULT '[]'::jsonb,
            tools JSONB NOT NULL DEFAULT '[]'::jsonb,
            models JSONB NOT NULL DEFAULT '[]'::jsonb,
            current_state JSONB NOT NULL DEFAULT '{}'::jsonb,
            knowledge_state JSONB NOT NULL DEFAULT '{}'::jsonb,
            uncertainties JSONB NOT NULL DEFAULT '[]'::jsonb,
            errors JSONB NOT NULL DEFAULT '[]'::jsonb,
            repairs JSONB NOT NULL DEFAULT '[]'::jsonb,
            evolution JSONB NOT NULL DEFAULT '[]'::jsonb,
            schema_version TEXT NOT NULL DEFAULT 'self_model.v1',
            version INTEGER NOT NULL DEFAULT 1,
            idempotency_key TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE UNIQUE INDEX self_model_idempotency_key_uq ON self_model (idempotency_key)
        """,
    ),
    (
        "003_learning_graph",
        """
        CREATE TABLE learning_events (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            event TEXT NOT NULL,
            lesson TEXT NOT NULL,
            knowledge_nodes JSONB NOT NULL DEFAULT '[]'::jsonb,
            relationships JSONB NOT NULL DEFAULT '[]'::jsonb,
            confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5 CHECK (confidence BETWEEN 0 AND 1),
            outcome TEXT NOT NULL DEFAULT 'unknown',
            reuse_count INTEGER NOT NULL DEFAULT 0 CHECK (reuse_count >= 0),
            last_reused_at TIMESTAMPTZ,
            schema_version TEXT NOT NULL DEFAULT 'learning.v1',
            version INTEGER NOT NULL DEFAULT 1,
            idempotency_key TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE UNIQUE INDEX learning_events_idempotency_key_uq ON learning_events (idempotency_key);
        CREATE INDEX learning_events_created_at_idx ON learning_events (created_at DESC);
        CREATE INDEX learning_events_outcome_idx ON learning_events (outcome, created_at DESC);
        CREATE INDEX learning_events_source_idx ON learning_events (source, created_at DESC);
        CREATE INDEX learning_events_reuse_idx ON learning_events (reuse_count DESC, created_at DESC);
        CREATE TABLE graph_nodes (
            id TEXT PRIMARY KEY,
            node_type TEXT NOT NULL CHECK (node_type IN ('concept','person','project','tool','experience','document','skill','error','solution','mission')),
            label TEXT NOT NULL,
            description TEXT,
            node_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            weight DOUBLE PRECISION NOT NULL DEFAULT 1.0 CHECK (weight >= 0),
            confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5 CHECK (confidence BETWEEN 0 AND 1),
            reuse_count INTEGER NOT NULL DEFAULT 0 CHECK (reuse_count >= 0),
            owner_scope TEXT NOT NULL DEFAULT 'owner',
            privacy_level TEXT NOT NULL DEFAULT 'PRIVATE' CHECK (privacy_level IN ('PRIVATE','SENSITIVE','SHAREABLE','COLLECTIVE')),
            status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived','deleted')),
            schema_version TEXT NOT NULL DEFAULT 'graph_node.v1',
            version INTEGER NOT NULL DEFAULT 1,
            idempotency_key TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_used_at TIMESTAMPTZ
        );
        CREATE UNIQUE INDEX graph_nodes_idempotency_key_uq ON graph_nodes (idempotency_key);
        CREATE INDEX graph_nodes_type_status_idx ON graph_nodes (node_type, status);
        CREATE INDEX graph_nodes_owner_scope_idx ON graph_nodes (owner_scope, status);
        CREATE INDEX graph_nodes_privacy_idx ON graph_nodes (privacy_level, status);
        CREATE INDEX graph_nodes_weight_idx ON graph_nodes (weight DESC, created_at DESC);
        CREATE INDEX graph_nodes_last_used_idx ON graph_nodes (last_used_at DESC NULLS LAST);
        CREATE TABLE graph_edges (
            id TEXT PRIMARY KEY,
            from_node TEXT NOT NULL,
            to_node TEXT NOT NULL,
            relation_type TEXT NOT NULL,
            weight DOUBLE PRECISION NOT NULL DEFAULT 1.0 CHECK (weight >= 0),
            confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5 CHECK (confidence BETWEEN 0 AND 1),
            frequency INTEGER NOT NULL DEFAULT 1 CHECK (frequency >= 1),
            origin TEXT NOT NULL DEFAULT 'unknown',
            success_count INTEGER NOT NULL DEFAULT 0 CHECK (success_count >= 0),
            failure_count INTEGER NOT NULL DEFAULT 0 CHECK (failure_count >= 0),
            status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived','deleted')),
            schema_version TEXT NOT NULL DEFAULT 'graph_edge.v1',
            version INTEGER NOT NULL DEFAULT 1,
            idempotency_key TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_used_at TIMESTAMPTZ
        );
        CREATE UNIQUE INDEX graph_edges_idempotency_key_uq ON graph_edges (idempotency_key);
        CREATE INDEX graph_edges_from_idx ON graph_edges (from_node, status);
        CREATE INDEX graph_edges_to_idx ON graph_edges (to_node, status);
        CREATE INDEX graph_edges_relation_idx ON graph_edges (relation_type, status);
        CREATE INDEX graph_edges_weight_idx ON graph_edges (weight DESC, frequency DESC)
        """,
    ),
]
