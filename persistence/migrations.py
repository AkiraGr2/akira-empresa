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
    (
        "004_cognitive_cycle",
        """
        CREATE TABLE cognitive_cycles (
            id TEXT PRIMARY KEY,
            trigger TEXT NOT NULL,
            input JSONB NOT NULL DEFAULT '{}'::jsonb,
            current_stage TEXT NOT NULL DEFAULT 'observe',
            status TEXT NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress','completed','failed','aborted')),
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            completed_at TIMESTAMPTZ,
            schema_version TEXT NOT NULL DEFAULT 'cognitive_cycle.v1',
            version INTEGER NOT NULL DEFAULT 1,
            idempotency_key TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE UNIQUE INDEX cognitive_cycles_idempotency_key_uq ON cognitive_cycles (idempotency_key);
        CREATE INDEX cognitive_cycles_status_idx ON cognitive_cycles (status, started_at DESC);
        CREATE INDEX cognitive_cycles_trigger_idx ON cognitive_cycles (trigger, started_at DESC);
        CREATE TABLE cognitive_events (
            id BIGSERIAL PRIMARY KEY,
            cycle_id TEXT NOT NULL,
            stage TEXT NOT NULL CHECK (stage IN ('observe','interpret','reason','decide','act','observe_result','evaluate','learn','update_self_model')),
            status TEXT NOT NULL DEFAULT 'success' CHECK (status IN ('success','failure')),
            data JSONB NOT NULL DEFAULT '{}'::jsonb,
            error JSONB,
            ts TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX cognitive_events_cycle_idx ON cognitive_events (cycle_id, ts ASC);
        CREATE INDEX cognitive_events_stage_idx ON cognitive_events (stage, ts DESC)
        """,
    ),
    (
        "005_cognitive_events_idempotency",
        """
        ALTER TABLE cognitive_events ADD COLUMN idempotency_key TEXT;
        CREATE UNIQUE INDEX cognitive_events_idempotency_key_uq ON cognitive_events (idempotency_key)
        """,
    ),
    (
        "006_cognitive_events_textid",
        """
        DROP TABLE cognitive_events;
        CREATE TABLE cognitive_events (
            id TEXT PRIMARY KEY,
            cycle_id TEXT NOT NULL,
            stage TEXT NOT NULL CHECK (stage IN ('observe','interpret','reason','decide','act','observe_result','evaluate','learn','update_self_model')),
            status TEXT NOT NULL DEFAULT 'success' CHECK (status IN ('success','failure')),
            data JSONB NOT NULL DEFAULT '{}'::jsonb,
            error JSONB,
            schema_version TEXT NOT NULL DEFAULT 'cognitive_event.v1',
            version INTEGER NOT NULL DEFAULT 1,
            idempotency_key TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE UNIQUE INDEX cognitive_events_idempotency_key_uq ON cognitive_events (idempotency_key);
        CREATE INDEX cognitive_events_cycle_idx ON cognitive_events (cycle_id, created_at ASC);
        CREATE INDEX cognitive_events_stage_idx ON cognitive_events (stage, created_at DESC)
        """,
    ),
    (
        "007_tools_registry",
        """
        CREATE TABLE tools (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            permissions JSONB NOT NULL DEFAULT '[]'::jsonb,
            inputs_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
            outputs_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
            limits_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            risks JSONB NOT NULL DEFAULT '[]'::jsonb,
            status TEXT NOT NULL DEFAULT 'available' CHECK (status IN ('available','disabled','deprecated')),
            schema_version TEXT NOT NULL DEFAULT 'tool.v1',
            version INTEGER NOT NULL DEFAULT 1,
            idempotency_key TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE UNIQUE INDEX tools_idempotency_key_uq ON tools (idempotency_key);
        CREATE UNIQUE INDEX tools_name_uq ON tools (name);
        CREATE INDEX tools_category_status_idx ON tools (category, status);
        CREATE TABLE tool_invocations (
            id TEXT PRIMARY KEY,
            tool_name TEXT NOT NULL,
            actor TEXT NOT NULL DEFAULT 'system',
            inputs JSONB NOT NULL DEFAULT '{}'::jsonb,
            outputs JSONB NOT NULL DEFAULT '{}'::jsonb,
            status TEXT NOT NULL DEFAULT 'success' CHECK (status IN ('success','failure')),
            error JSONB,
            duration_ms INTEGER NOT NULL DEFAULT 0 CHECK (duration_ms >= 0),
            schema_version TEXT NOT NULL DEFAULT 'tool_invocation.v1',
            version INTEGER NOT NULL DEFAULT 1,
            idempotency_key TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE UNIQUE INDEX tool_invocations_idempotency_key_uq ON tool_invocations (idempotency_key);
        CREATE INDEX tool_invocations_tool_idx ON tool_invocations (tool_name, created_at DESC);
        CREATE INDEX tool_invocations_status_idx ON tool_invocations (status, created_at DESC);
        CREATE INDEX tool_invocations_actor_idx ON tool_invocations (actor, created_at DESC)
        """,
    ),
    (
        "008_agents",
        """
        CREATE TABLE agents (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            description TEXT NOT NULL,
            allowed_tools JSONB NOT NULL DEFAULT '[]'::jsonb,
            status TEXT NOT NULL DEFAULT 'idle' CHECK (status IN ('idle','busy','disabled','error')),
            current_task_id TEXT,
            tasks_completed INTEGER NOT NULL DEFAULT 0 CHECK (tasks_completed >= 0),
            tasks_failed INTEGER NOT NULL DEFAULT 0 CHECK (tasks_failed >= 0),
            last_active_at TIMESTAMPTZ,
            schema_version TEXT NOT NULL DEFAULT 'agent.v1',
            version INTEGER NOT NULL DEFAULT 1,
            idempotency_key TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE UNIQUE INDEX agents_idempotency_key_uq ON agents (idempotency_key);
        CREATE UNIQUE INDEX agents_name_uq ON agents (name);
        CREATE INDEX agents_role_status_idx ON agents (role, status);
        CREATE TABLE agent_tasks (
            id TEXT PRIMARY KEY,
            agent_name TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','completed','failed')),
            inputs JSONB NOT NULL DEFAULT '{}'::jsonb,
            outputs JSONB NOT NULL DEFAULT '{}'::jsonb,
            error JSONB,
            duration_ms INTEGER NOT NULL DEFAULT 0 CHECK (duration_ms >= 0),
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            schema_version TEXT NOT NULL DEFAULT 'agent_task.v1',
            version INTEGER NOT NULL DEFAULT 1,
            idempotency_key TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE UNIQUE INDEX agent_tasks_idempotency_key_uq ON agent_tasks (idempotency_key);
        CREATE INDEX agent_tasks_agent_idx ON agent_tasks (agent_name, created_at DESC);
        CREATE INDEX agent_tasks_status_idx ON agent_tasks (status, created_at DESC);
        CREATE INDEX agent_tasks_tool_idx ON agent_tasks (tool_name, created_at DESC)
        """,
    ),
    (
        "009_agents_contract_v8",
        """
        ALTER TABLE agents ADD COLUMN current_action TEXT;
        ALTER TABLE agent_tasks ADD COLUMN model TEXT;
        ALTER TABLE agent_tasks ADD COLUMN mission_id TEXT;
        ALTER TABLE agent_tasks ADD COLUMN memory_used JSONB NOT NULL DEFAULT '[]'::jsonb;
        CREATE INDEX agent_tasks_mission_idx ON agent_tasks (mission_id, created_at DESC)
        """,
    ),
    (
        "010_graph_tags",
        """
        ALTER TABLE graph_nodes ADD COLUMN tags JSONB NOT NULL DEFAULT '[]'::jsonb;
        CREATE INDEX graph_nodes_tags_idx ON graph_nodes USING GIN (tags)
        """,
    ),
    (
        "011_missions",
        """
        CREATE TABLE missions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            objective TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'created' CHECK (status IN ('created','planning','running','paused','waiting_approval','completed','failed','cancelled')),
            priority INTEGER NOT NULL DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
            created_by TEXT NOT NULL,
            authorized_by TEXT,
            flow_type TEXT NOT NULL DEFAULT 'generic',
            flow_config JSONB NOT NULL DEFAULT '{}'::jsonb,
            plan JSONB NOT NULL DEFAULT '{}'::jsonb,
            parent_mission_id TEXT,
            success_criteria TEXT,
            result JSONB NOT NULL DEFAULT '{}'::jsonb,
            learning_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
            schema_version TEXT NOT NULL DEFAULT 'mission.v1',
            version INTEGER NOT NULL DEFAULT 1,
            idempotency_key TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ
        );
        CREATE UNIQUE INDEX missions_idempotency_key_uq ON missions (idempotency_key);
        CREATE INDEX missions_status_idx ON missions (status, created_at DESC);
        CREATE INDEX missions_priority_idx ON missions (priority DESC, created_at DESC);
        CREATE INDEX missions_flow_type_idx ON missions (flow_type, created_at DESC);
        CREATE INDEX missions_parent_idx ON missions (parent_mission_id);
        CREATE INDEX missions_created_by_idx ON missions (created_by, created_at DESC)
        """,
    ),
    (
        "012_conversations",
        """
        CREATE TABLE conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_by TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived','deleted')),
            message_count INTEGER NOT NULL DEFAULT 0 CHECK (message_count >= 0),
            last_message_at TIMESTAMPTZ,
            schema_version TEXT NOT NULL DEFAULT 'conversation.v1',
            version INTEGER NOT NULL DEFAULT 1,
            idempotency_key TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE UNIQUE INDEX conversations_idempotency_key_uq ON conversations (idempotency_key);
        CREATE INDEX conversations_created_by_idx ON conversations (created_by, last_message_at DESC NULLS LAST);
        CREATE INDEX conversations_status_idx ON conversations (status, created_at DESC);
        CREATE TABLE conversation_messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('user','assistant','system')),
            content TEXT NOT NULL,
            model TEXT,
            memories_used JSONB NOT NULL DEFAULT '[]'::jsonb,
            error JSONB,
            duration_ms INTEGER NOT NULL DEFAULT 0 CHECK (duration_ms >= 0),
            schema_version TEXT NOT NULL DEFAULT 'conversation_message.v1',
            version INTEGER NOT NULL DEFAULT 1,
            idempotency_key TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE UNIQUE INDEX conversation_messages_idempotency_key_uq ON conversation_messages (idempotency_key);
        CREATE INDEX conversation_messages_conv_idx ON conversation_messages (conversation_id, created_at ASC);
        CREATE INDEX conversation_messages_role_idx ON conversation_messages (conversation_id, role, created_at ASC)
        """,
    ),
    (
        "013_learning_status",
        """
        ALTER TABLE learning_events ADD COLUMN status TEXT NOT NULL DEFAULT 'candidate' CHECK (status IN ('candidate','verified','consolidated','conflicted','obsolete','discarded'));
        CREATE INDEX learning_events_status_idx ON learning_events (status, created_at DESC)
        """,
    ),
]
