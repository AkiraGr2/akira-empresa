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
    (
        "014_learning_evidence",
        """
        ALTER TABLE learning_events ADD COLUMN evidence JSONB NOT NULL DEFAULT '[]'::jsonb;
        ALTER TABLE learning_events ADD COLUMN verified_at TIMESTAMPTZ;
        ALTER TABLE learning_events ADD COLUMN verified_by TEXT;
        CREATE INDEX learning_events_verified_idx ON learning_events (verified_at DESC)
        """,
    ),
    (
        "015_learning_verification_analysis",
        """
        ALTER TABLE learning_events ADD COLUMN verification_analysis JSONB NOT NULL DEFAULT '{}'::jsonb;
        CREATE INDEX learning_events_verification_analysis_idx ON learning_events ((verification_analysis->>'verdict'))
        """,
    ),
    (
        "016_learning_context",
        """
        ALTER TABLE learning_events ADD COLUMN learning_context JSONB NOT NULL DEFAULT '{}'::jsonb
        """,
    ),
    (
        "017_memory_embeddings",
        """
        CREATE EXTENSION IF NOT EXISTS vector;
        CREATE TABLE memory_embeddings (
            memory_id TEXT PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE,
            model TEXT NOT NULL,
            dimensions INTEGER NOT NULL CHECK (dimensions >= 128 AND dimensions <= 3072),
            embedding vector(768) NOT NULL,
            source_hash TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX memory_embeddings_model_idx ON memory_embeddings (model);
        CREATE INDEX memory_embeddings_hnsw_idx ON memory_embeddings USING hnsw (embedding vector_cosine_ops)
        """,
    ),
    (
        "018_graph_integrity_hardening",
        """
        CREATE TEMP TABLE _graph_edge_dedup AS
        SELECT id,
               row_number() OVER (
                   PARTITION BY from_node,to_node,relation_type
                   ORDER BY created_at ASC,id ASC
               ) AS rn,
               sum(coalesce(frequency,1)) OVER (
                   PARTITION BY from_node,to_node,relation_type
               ) AS total_frequency,
               max(weight) OVER (
                   PARTITION BY from_node,to_node,relation_type
               ) AS max_weight,
               max(confidence) OVER (
                   PARTITION BY from_node,to_node,relation_type
               ) AS max_confidence,
               sum(coalesce(success_count,0)) OVER (
                   PARTITION BY from_node,to_node,relation_type
               ) AS total_success,
               sum(coalesce(failure_count,0)) OVER (
                   PARTITION BY from_node,to_node,relation_type
               ) AS total_failure,
               max(last_used_at) OVER (
                   PARTITION BY from_node,to_node,relation_type
               ) AS max_last_used
        FROM graph_edges
        WHERE status='active';
        UPDATE graph_edges e
        SET frequency=d.total_frequency,
            weight=d.max_weight,
            confidence=d.max_confidence,
            success_count=d.total_success,
            failure_count=d.total_failure,
            last_used_at=d.max_last_used,
            updated_at=now(),
            version=e.version+1
        FROM _graph_edge_dedup d
        WHERE e.id=d.id AND d.rn=1;
        UPDATE graph_edges e
        SET status='archived',
            updated_at=now(),
            version=e.version+1
        FROM _graph_edge_dedup d
        WHERE e.id=d.id AND d.rn>1;
        DROP TABLE _graph_edge_dedup;
        CREATE UNIQUE INDEX IF NOT EXISTS graph_edges_active_unique_relation_uq
            ON graph_edges (from_node,to_node,relation_type)
            WHERE status='active';
        CREATE UNIQUE INDEX IF NOT EXISTS graph_nodes_single_active_akira_uq
            ON graph_nodes ((lower(label)))
            WHERE status='active' AND lower(label)='akira';
        """,
    ),
    (
        "019_graph_node_uniqueness",
        """
        CREATE UNIQUE INDEX IF NOT EXISTS graph_nodes_active_type_label_uq
            ON graph_nodes (node_type, lower(label))
            WHERE status='active'
        """,
    ),

    (
        "020_rls_hardening",
        """
        ALTER TABLE public.agent_tasks, public.agents, public.audit_log, public.cognitive_cycles, public.cognitive_events, public.conversation_messages, public.conversations, public.graph_edges, public.graph_nodes, public.learning_events, public.memories, public.memory_embeddings, public.missions, public.schema_migrations, public.self_model, public.tool_invocations, public.tools ENABLE ROW LEVEL SECURITY;
        REVOKE ALL ON TABLE public.agent_tasks, public.agents, public.audit_log, public.cognitive_cycles, public.cognitive_events, public.conversation_messages, public.conversations, public.graph_edges, public.graph_nodes, public.learning_events, public.memories, public.memory_embeddings, public.missions, public.schema_migrations, public.self_model, public.tool_invocations, public.tools FROM anon, authenticated;
        ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER, MAINTAIN ON TABLES FROM anon, authenticated;
        CREATE POLICY "akira_deny_anon_authenticated_select" ON public.agent_tasks AS RESTRICTIVE FOR SELECT TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_insert" ON public.agent_tasks AS RESTRICTIVE FOR INSERT TO anon, authenticated WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_update" ON public.agent_tasks AS RESTRICTIVE FOR UPDATE TO anon, authenticated USING (false) WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_delete" ON public.agent_tasks AS RESTRICTIVE FOR DELETE TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_select" ON public.agents AS RESTRICTIVE FOR SELECT TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_insert" ON public.agents AS RESTRICTIVE FOR INSERT TO anon, authenticated WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_update" ON public.agents AS RESTRICTIVE FOR UPDATE TO anon, authenticated USING (false) WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_delete" ON public.agents AS RESTRICTIVE FOR DELETE TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_select" ON public.audit_log AS RESTRICTIVE FOR SELECT TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_insert" ON public.audit_log AS RESTRICTIVE FOR INSERT TO anon, authenticated WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_update" ON public.audit_log AS RESTRICTIVE FOR UPDATE TO anon, authenticated USING (false) WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_delete" ON public.audit_log AS RESTRICTIVE FOR DELETE TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_select" ON public.cognitive_cycles AS RESTRICTIVE FOR SELECT TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_insert" ON public.cognitive_cycles AS RESTRICTIVE FOR INSERT TO anon, authenticated WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_update" ON public.cognitive_cycles AS RESTRICTIVE FOR UPDATE TO anon, authenticated USING (false) WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_delete" ON public.cognitive_cycles AS RESTRICTIVE FOR DELETE TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_select" ON public.cognitive_events AS RESTRICTIVE FOR SELECT TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_insert" ON public.cognitive_events AS RESTRICTIVE FOR INSERT TO anon, authenticated WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_update" ON public.cognitive_events AS RESTRICTIVE FOR UPDATE TO anon, authenticated USING (false) WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_delete" ON public.cognitive_events AS RESTRICTIVE FOR DELETE TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_select" ON public.conversation_messages AS RESTRICTIVE FOR SELECT TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_insert" ON public.conversation_messages AS RESTRICTIVE FOR INSERT TO anon, authenticated WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_update" ON public.conversation_messages AS RESTRICTIVE FOR UPDATE TO anon, authenticated USING (false) WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_delete" ON public.conversation_messages AS RESTRICTIVE FOR DELETE TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_select" ON public.conversations AS RESTRICTIVE FOR SELECT TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_insert" ON public.conversations AS RESTRICTIVE FOR INSERT TO anon, authenticated WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_update" ON public.conversations AS RESTRICTIVE FOR UPDATE TO anon, authenticated USING (false) WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_delete" ON public.conversations AS RESTRICTIVE FOR DELETE TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_select" ON public.graph_edges AS RESTRICTIVE FOR SELECT TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_insert" ON public.graph_edges AS RESTRICTIVE FOR INSERT TO anon, authenticated WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_update" ON public.graph_edges AS RESTRICTIVE FOR UPDATE TO anon, authenticated USING (false) WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_delete" ON public.graph_edges AS RESTRICTIVE FOR DELETE TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_select" ON public.graph_nodes AS RESTRICTIVE FOR SELECT TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_insert" ON public.graph_nodes AS RESTRICTIVE FOR INSERT TO anon, authenticated WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_update" ON public.graph_nodes AS RESTRICTIVE FOR UPDATE TO anon, authenticated USING (false) WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_delete" ON public.graph_nodes AS RESTRICTIVE FOR DELETE TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_select" ON public.learning_events AS RESTRICTIVE FOR SELECT TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_insert" ON public.learning_events AS RESTRICTIVE FOR INSERT TO anon, authenticated WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_update" ON public.learning_events AS RESTRICTIVE FOR UPDATE TO anon, authenticated USING (false) WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_delete" ON public.learning_events AS RESTRICTIVE FOR DELETE TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_select" ON public.memories AS RESTRICTIVE FOR SELECT TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_insert" ON public.memories AS RESTRICTIVE FOR INSERT TO anon, authenticated WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_update" ON public.memories AS RESTRICTIVE FOR UPDATE TO anon, authenticated USING (false) WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_delete" ON public.memories AS RESTRICTIVE FOR DELETE TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_select" ON public.memory_embeddings AS RESTRICTIVE FOR SELECT TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_insert" ON public.memory_embeddings AS RESTRICTIVE FOR INSERT TO anon, authenticated WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_update" ON public.memory_embeddings AS RESTRICTIVE FOR UPDATE TO anon, authenticated USING (false) WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_delete" ON public.memory_embeddings AS RESTRICTIVE FOR DELETE TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_select" ON public.missions AS RESTRICTIVE FOR SELECT TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_insert" ON public.missions AS RESTRICTIVE FOR INSERT TO anon, authenticated WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_update" ON public.missions AS RESTRICTIVE FOR UPDATE TO anon, authenticated USING (false) WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_delete" ON public.missions AS RESTRICTIVE FOR DELETE TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_select" ON public.schema_migrations AS RESTRICTIVE FOR SELECT TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_insert" ON public.schema_migrations AS RESTRICTIVE FOR INSERT TO anon, authenticated WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_update" ON public.schema_migrations AS RESTRICTIVE FOR UPDATE TO anon, authenticated USING (false) WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_delete" ON public.schema_migrations AS RESTRICTIVE FOR DELETE TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_select" ON public.self_model AS RESTRICTIVE FOR SELECT TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_insert" ON public.self_model AS RESTRICTIVE FOR INSERT TO anon, authenticated WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_update" ON public.self_model AS RESTRICTIVE FOR UPDATE TO anon, authenticated USING (false) WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_delete" ON public.self_model AS RESTRICTIVE FOR DELETE TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_select" ON public.tool_invocations AS RESTRICTIVE FOR SELECT TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_insert" ON public.tool_invocations AS RESTRICTIVE FOR INSERT TO anon, authenticated WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_update" ON public.tool_invocations AS RESTRICTIVE FOR UPDATE TO anon, authenticated USING (false) WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_delete" ON public.tool_invocations AS RESTRICTIVE FOR DELETE TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_select" ON public.tools AS RESTRICTIVE FOR SELECT TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_insert" ON public.tools AS RESTRICTIVE FOR INSERT TO anon, authenticated WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_update" ON public.tools AS RESTRICTIVE FOR UPDATE TO anon, authenticated USING (false) WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_delete" ON public.tools AS RESTRICTIVE FOR DELETE TO anon, authenticated USING (false)
        """
    ),

    (
        "021_learning_owner_scope",
        """
        ALTER TABLE learning_events ADD COLUMN owner_scope TEXT NOT NULL DEFAULT 'owner';
        CREATE INDEX learning_events_owner_scope_idx ON learning_events (owner_scope, status, created_at DESC)
        """
    ),

    (
        "022_cognitive_owner_scope",
        """
        ALTER TABLE cognitive_cycles ADD COLUMN owner_scope TEXT NOT NULL DEFAULT 'owner';
        CREATE INDEX cognitive_cycles_owner_scope_idx ON cognitive_cycles (owner_scope, status, started_at DESC)
        """
    ),

    (
        "023_agent_task_owner_scope",
        """
        ALTER TABLE agent_tasks ADD COLUMN owner_scope TEXT NOT NULL DEFAULT 'owner';
        CREATE INDEX agent_tasks_owner_scope_idx ON agent_tasks (owner_scope, status, created_at DESC)
        """
    ),

    (
        "024_memory_tools_owner_only",
        """
        UPDATE tools
        SET permissions = '[\"owner\"]'::jsonb, updated_at = now()
        WHERE name IN ('memory_save', 'memory_search')
        """
    ),
    (
        "025_memory_tools_owner_reassert",
        """
        UPDATE tools
        SET permissions = '[\"owner\"]'::jsonb, updated_at = now()
        WHERE name IN ('memory_save', 'memory_search')
        """
    ),
    (
        "026_identity_root_self_model",
        """
        CREATE TABLE IF NOT EXISTS identity_root (
            id TEXT PRIMARY KEY,
            canonical_name TEXT NOT NULL CHECK (canonical_name = 'Akira'),
            creator TEXT NOT NULL CHECK (creator = 'Jhon Grimm'),
            essence TEXT NOT NULL CHECK (essence = 'Colmena cognitiva personal. Persistente, verificable, honesta sobre sus capacidades.'),
            language TEXT NOT NULL CHECK (language = 'es-CO'),
            root_schema_version TEXT NOT NULL CHECK (root_schema_version = 'identity_root.v1'),
            status TEXT NOT NULL DEFAULT 'active' CHECK (status = 'active'),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        INSERT INTO identity_root (
            id, canonical_name, creator, essence, language, root_schema_version, status
        )
        VALUES (
            'akira_primary',
            'Akira',
            'Jhon Grimm',
            'Colmena cognitiva personal. Persistente, verificable, honesta sobre sus capacidades.',
            'es-CO',
            'identity_root.v1',
            'active'
        )
        ON CONFLICT (id) DO NOTHING;
        UPDATE self_model
        SET identity = jsonb_build_object(
            'name', 'Akira',
            'creator', 'Jhon Grimm',
            'essence', 'Colmena cognitiva personal. Persistente, verificable, honesta sobre sus capacidades.',
            'language', 'es-CO'
        ),
        updated_at = now()
        WHERE id = 'akira_primary'
        """
    ),
    (
        "027_identity_root_db_guard",
        """
        ALTER TABLE identity_root
        ADD CONSTRAINT identity_root_singleton CHECK (id = 'akira_primary');
        CREATE RULE identity_root_no_update
        AS ON UPDATE TO identity_root
        DO INSTEAD NOTHING;
        CREATE RULE identity_root_no_delete
        AS ON DELETE TO identity_root
        DO INSTEAD NOTHING
        """
    ),
    (
        "028_capability_engine",
        """
        CREATE TABLE capabilities (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL CHECK (category IN ('identity','memory','knowledge','learning','graph','cognitive','tooling','agents','missions','security','storage','multimedia','orchestration','repair','evolution','hive','external','general')),
            kind TEXT NOT NULL CHECK (kind IN ('intrinsic','tool_backed','provider_dependent','composite')),
            implementation_state TEXT NOT NULL DEFAULT 'not_implemented' CHECK (implementation_state IN ('not_implemented','partial','implemented','deprecated')),
            verification_state TEXT NOT NULL DEFAULT 'unverified' CHECK (verification_state IN ('unverified','verified','stale','failed')),
            availability_state TEXT NOT NULL DEFAULT 'unavailable' CHECK (availability_state IN ('available','degraded','blocked','unavailable')),
            maturity TEXT NOT NULL DEFAULT 'experimental' CHECK (maturity IN ('experimental','stable')),
            cost_compatibility TEXT NOT NULL DEFAULT 'unknown' CHECK (cost_compatibility IN ('free','conditional','paid_required','unknown')),
            dependencies JSONB NOT NULL DEFAULT '[]'::jsonb,
            limitations JSONB NOT NULL DEFAULT '[]'::jsonb,
            verification_spec JSONB NOT NULL DEFAULT '{}'::jsonb,
            provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
            version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
            schema_version TEXT NOT NULL DEFAULT 'capability.v1',
            last_verification_id TEXT,
            last_verified_at TIMESTAMPTZ,
            idempotency_key TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT capabilities_name_uq UNIQUE (name),
            CONSTRAINT capabilities_not_false_verified CHECK (
                implementation_state <> 'not_implemented'
                OR verification_state <> 'verified'
            ),
            CONSTRAINT capabilities_not_false_available CHECK (
                implementation_state <> 'not_implemented'
                OR availability_state <> 'available'
            ),
            CONSTRAINT capabilities_stable_requires_implementation CHECK (
                maturity <> 'stable'
                OR implementation_state <> 'not_implemented'
            )
        );
        CREATE UNIQUE INDEX capabilities_idempotency_key_uq ON capabilities (idempotency_key);
        CREATE INDEX capabilities_category_state_idx ON capabilities (category, implementation_state, verification_state);
        CREATE INDEX capabilities_availability_idx ON capabilities (availability_state, updated_at DESC);
        CREATE INDEX capabilities_cost_idx ON capabilities (cost_compatibility, updated_at DESC);
        CREATE INDEX capabilities_last_verified_idx ON capabilities (last_verified_at DESC NULLS LAST);
        CREATE TABLE capability_verifications (
            id TEXT PRIMARY KEY,
            capability_id TEXT NOT NULL REFERENCES capabilities(id) ON DELETE RESTRICT,
            event_type TEXT NOT NULL CHECK (event_type IN ('verification','revalidation','availability_check','invalidation')),
            test_key TEXT NOT NULL,
            test_version TEXT NOT NULL DEFAULT 'v1',
            result TEXT NOT NULL CHECK (result IN ('pass','fail','inconclusive','not_run')),
            evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
            environment JSONB NOT NULL DEFAULT '{}'::jsonb,
            dependency_snapshot JSONB NOT NULL DEFAULT '[]'::jsonb,
            runtime_version TEXT NOT NULL,
            build_ref TEXT NOT NULL,
            actor TEXT NOT NULL,
            executor TEXT NOT NULL,
            evaluator TEXT NOT NULL,
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            finished_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            error JSONB,
            observed_availability_state TEXT CHECK (observed_availability_state IS NULL OR observed_availability_state IN ('available','degraded','blocked','unavailable')),
            state_before JSONB NOT NULL,
            state_after JSONB NOT NULL,
            schema_version TEXT NOT NULL DEFAULT 'capability_verification.v1',
            version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
            idempotency_key TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE UNIQUE INDEX capability_verifications_idempotency_key_uq ON capability_verifications (idempotency_key);
        CREATE INDEX capability_verifications_capability_time_idx ON capability_verifications (capability_id, created_at DESC);
        CREATE INDEX capability_verifications_result_idx ON capability_verifications (result, created_at DESC);
        CREATE INDEX capability_verifications_test_idx ON capability_verifications (test_key, created_at DESC);
        ALTER TABLE capabilities
            ADD CONSTRAINT capabilities_last_verification_fk
            FOREIGN KEY (last_verification_id)
            REFERENCES capability_verifications(id)
            ON DELETE RESTRICT;
        ALTER TABLE public.capabilities ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.capability_verifications ENABLE ROW LEVEL SECURITY;
        REVOKE ALL ON TABLE public.capabilities, public.capability_verifications FROM anon, authenticated;
        CREATE POLICY "akira_deny_anon_authenticated_select" ON public.capabilities AS RESTRICTIVE FOR SELECT TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_insert" ON public.capabilities AS RESTRICTIVE FOR INSERT TO anon, authenticated WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_update" ON public.capabilities AS RESTRICTIVE FOR UPDATE TO anon, authenticated USING (false) WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_delete" ON public.capabilities AS RESTRICTIVE FOR DELETE TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_select" ON public.capability_verifications AS RESTRICTIVE FOR SELECT TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_insert" ON public.capability_verifications AS RESTRICTIVE FOR INSERT TO anon, authenticated WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_update" ON public.capability_verifications AS RESTRICTIVE FOR UPDATE TO anon, authenticated USING (false) WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_delete" ON public.capability_verifications AS RESTRICTIVE FOR DELETE TO anon, authenticated USING (false);
        CREATE RULE capabilities_no_delete
            AS ON DELETE TO public.capabilities
            DO INSTEAD NOTHING;
        CREATE RULE capability_verifications_no_update
            AS ON UPDATE TO public.capability_verifications
            DO INSTEAD NOTHING;
        CREATE RULE capability_verifications_no_delete
            AS ON DELETE TO public.capability_verifications
            DO INSTEAD NOTHING
        """
    ),

    (
        "029_specialized_agents_v1",
        """
        INSERT INTO tools (
            id, name, description, category, permissions, inputs_schema,
            outputs_schema, limits_json, risks, status, schema_version
        )
        VALUES (
            'tool_developer_propose',
            'developer_propose',
            'Genera una propuesta de cambio de codigo sin escribir en GitHub.',
            'code',
            '["owner"]'::jsonb,
            '{"repo":"str","paths":"list","instruction":"str","queries":"list"}'::jsonb,
            '{"proposal":"dict"}'::jsonb,
            '{"max_paths":4,"max_instruction":4000}'::jsonb,
            '["inferencia externa","propuesta de codigo"]'::jsonb,
            'available',
            'tool.v1'
        )
        ON CONFLICT (name) DO UPDATE SET
            description = EXCLUDED.description,
            category = EXCLUDED.category,
            permissions = EXCLUDED.permissions,
            inputs_schema = EXCLUDED.inputs_schema,
            outputs_schema = EXCLUDED.outputs_schema,
            limits_json = EXCLUDED.limits_json,
            risks = EXCLUDED.risks,
            updated_at = now();

        INSERT INTO tools (
            id, name, description, category, permissions, inputs_schema,
            outputs_schema, limits_json, risks, status, schema_version
        )
        VALUES (
            'tool_python_test',
            'python_test',
            'Ejecuta pruebas Python seleccionadas sin shell.',
            'code',
            '["owner"]'::jsonb,
            '{"tests":"list","compile_paths":"list"}'::jsonb,
            '{"status":"str","tests":"list"}'::jsonb,
            '{"max_tests":6,"timeout_s":45}'::jsonb,
            '["ejecucion de pruebas del repositorio"]'::jsonb,
            'available',
            'tool.v1'
        )
        ON CONFLICT (name) DO UPDATE SET
            description = EXCLUDED.description,
            category = EXCLUDED.category,
            permissions = EXCLUDED.permissions,
            inputs_schema = EXCLUDED.inputs_schema,
            outputs_schema = EXCLUDED.outputs_schema,
            limits_json = EXCLUDED.limits_json,
            risks = EXCLUDED.risks,
            updated_at = now();

        INSERT INTO tools (
            id, name, description, category, permissions, inputs_schema,
            outputs_schema, limits_json, risks, status, schema_version
        )
        VALUES (
            'tool_code_review',
            'code_review',
            'Revisa una propuesta de codigo contra el repositorio y evidencia de pruebas, sin escribir.',
            'code',
            '["owner"]'::jsonb,
            '{"repo":"str","paths":"list","proposal":"dict","test_results":"dict"}'::jsonb,
            '{"review":"dict"}'::jsonb,
            '{"max_paths":4,"max_proposal_chars":24000}'::jsonb,
            '["inferencia externa","revision de codigo"]'::jsonb,
            'available',
            'tool.v1'
        )
        ON CONFLICT (name) DO UPDATE SET
            description = EXCLUDED.description,
            category = EXCLUDED.category,
            permissions = EXCLUDED.permissions,
            inputs_schema = EXCLUDED.inputs_schema,
            outputs_schema = EXCLUDED.outputs_schema,
            limits_json = EXCLUDED.limits_json,
            risks = EXCLUDED.risks,
            updated_at = now();

        INSERT INTO agents (
            id, name, role, description, allowed_tools, status, schema_version
        )
        VALUES (
            'agent_developer',
            'developer',
            'Prepara propuestas de cambios de codigo sin escribir directamente en GitHub.',
            'developer',
            '["github_repo_read","developer_propose"]'::jsonb,
            'idle',
            'agent.v1'
        )
        ON CONFLICT (name) DO UPDATE SET
            role = EXCLUDED.role,
            description = EXCLUDED.description,
            allowed_tools = EXCLUDED.allowed_tools,
            updated_at = now();

        INSERT INTO agents (
            id, name, role, description, allowed_tools, status, schema_version
        )
        VALUES (
            'agent_tester',
            'tester',
            'Ejecuta pruebas seleccionadas y reporta evidencia reproducible.',
            'tester',
            '["github_repo_read","python_test"]'::jsonb,
            'idle',
            'agent.v1'
        )
        ON CONFLICT (name) DO UPDATE SET
            role = EXCLUDED.role,
            description = EXCLUDED.description,
            allowed_tools = EXCLUDED.allowed_tools,
            updated_at = now();

        INSERT INTO agents (
            id, name, role, description, allowed_tools, status, schema_version
        )
        VALUES (
            'agent_reviewer',
            'reviewer',
            'Revisa propuestas de codigo y evidencia de pruebas sin aplicar cambios.',
            'reviewer',
            '["github_repo_read","python_test","code_review"]'::jsonb,
            'idle',
            'agent.v1'
        )
        ON CONFLICT (name) DO UPDATE SET
            role = EXCLUDED.role,
            description = EXCLUDED.description,
            allowed_tools = EXCLUDED.allowed_tools,
            updated_at = now()
        """
    ),


    (
        "030_identity_root_rls_hardening",
        """
        ALTER TABLE public.identity_root ENABLE ROW LEVEL SECURITY;
        REVOKE ALL ON TABLE public.identity_root FROM anon, authenticated;
        CREATE POLICY "akira_deny_anon_authenticated_select"
            ON public.identity_root AS RESTRICTIVE FOR SELECT TO anon, authenticated
            USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_insert"
            ON public.identity_root AS RESTRICTIVE FOR INSERT TO anon, authenticated
            WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_update"
            ON public.identity_root AS RESTRICTIVE FOR UPDATE TO anon, authenticated
            USING (false) WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_delete"
            ON public.identity_root AS RESTRICTIVE FOR DELETE TO anon, authenticated
            USING (false)
        """
    ),


    (
        "031_self_knowledge_runtime_capability",
        """
        INSERT INTO capabilities (
            id, name, description, category, kind,
            implementation_state, verification_state, availability_state,
            maturity, cost_compatibility, dependencies, limitations,
            verification_spec, provenance, schema_version, idempotency_key
        )
        VALUES (
            'cap_self_knowledge_runtime',
            'self_knowledge_runtime',
            'Autoconocimiento operativo reproducible derivado de Identity Root, Capability Engine y registros autoritativos de agentes y tools.',
            'knowledge',
            'composite',
            'implemented',
            'unverified',
            'available',
            'experimental',
            'free',
            '[{"id":"IdentityRoot","kind":"authority","required":true},{"id":"CapabilityEngine","kind":"registry","required":true},{"id":"PersistenceService.self_knowledge_snapshot","kind":"service","required":true},{"id":"PostgreSQL.capabilities","kind":"storage","required":true},{"id":"PostgreSQL.agents","kind":"storage","required":true},{"id":"PostgreSQL.tools","kind":"storage","required":true},{"id":"owner_scope","kind":"security","required":true}]'::jsonb,
            '["No demuestra por sí sola ejecución E2E de los agentes especializados.","El self-model histórico puede contener declaraciones heredadas y el snapshot runtime prioriza fuentes autoritativas.","La métrica memory_active_count es un conteo del ámbito solicitado y no expone contenido de memoria."]'::jsonb,
            '{
                "method":"selftest",
                "test_key":"self_knowledge_runtime_contract",
                "freshness_policy":{
                    "mode":"on_change",
                    "max_age_seconds":null,
                    "invalidate_on":[
                        "build_change",
                        "identity_root_change",
                        "capability_registry_change",
                        "agent_registry_change",
                        "tool_registry_change",
                        "owner_scope_change"
                    ]
                }
            }'::jsonb,
            '{"source":"architecture_rebaseline_v13","created_by":"system"}'::jsonb,
            'capability.v1',
            'bootstrap:capability:self_knowledge_runtime:v1'
        )
        ON CONFLICT (name) DO UPDATE SET
            description = EXCLUDED.description,
            category = EXCLUDED.category,
            kind = EXCLUDED.kind,
            implementation_state = EXCLUDED.implementation_state,
            availability_state = EXCLUDED.availability_state,
            maturity = EXCLUDED.maturity,
            cost_compatibility = EXCLUDED.cost_compatibility,
            dependencies = EXCLUDED.dependencies,
            limitations = EXCLUDED.limitations,
            verification_spec = EXCLUDED.verification_spec,
            provenance = EXCLUDED.provenance,
            schema_version = EXCLUDED.schema_version,
            updated_at = now()
        """
    ),


    (
        "032_self_model_semantic_contract_v2",
        """
        UPDATE public.self_model
        SET
            uncertainties = COALESCE(
                (
                    SELECT jsonb_agg(
                        CASE
                            WHEN jsonb_typeof(item) = 'string' THEN
                                jsonb_build_object(
                                    'id', 'legacy_uncertainty_' || md5(item::text),
                                    'statement', item #>> '{}',
                                    'kind', 'other',
                                    'status', 'open',
                                    'evidence', '[]'::jsonb,
                                    'created_at', to_jsonb(updated_at)
                                )
                            ELSE item
                        END
                    )
                    FROM jsonb_array_elements(uncertainties) AS item
                ),
                '[]'::jsonb
            ),
            current_state = current_state || jsonb_build_object(
                'last_observed_at',
                COALESCE(current_state -> 'last_cycle_at', to_jsonb(updated_at))
            ),
            schema_version = 'self_model.v2',
            version = version + 1,
            updated_at = now()
        WHERE id = 'akira_primary'
          AND schema_version = 'self_model.v1';

        INSERT INTO public.audit_log (
            actor, action, resource, resource_id, status, detail
        )
        SELECT
            'system',
            'self_model.semantic_contract_migrate',
            'self_model',
            id,
            'success',
            jsonb_build_object(
                'from_schema', 'self_model.v1',
                'to_schema', 'self_model.v2',
                'reason', 'semantic_contract_v2'
            )
        FROM public.self_model
        WHERE id = 'akira_primary'
          AND schema_version = 'self_model.v2'
        """
    ),


    (
        "033_self_model_uncertainty_semantics",
        """
        UPDATE public.self_model
        SET
            uncertainties = (
                SELECT COALESCE(
                    jsonb_agg(
                        item || jsonb_build_object(
                            'kind',
                            CASE
                                WHEN item ->> 'id' = 'legacy_uncertainty_49fe4a27ee84a15f7e48b0d63f0f7393' THEN 'evidence'
                                WHEN item ->> 'id' = 'legacy_uncertainty_e4ded42eae594597a0cd67ad85ee240d' THEN 'capability'
                                WHEN item ->> 'id' = 'legacy_uncertainty_c4564edd285b4240665393f0fee2ec97' THEN 'knowledge'
                                WHEN item ->> 'id' = 'legacy_uncertainty_48e1e5e3b82d26e6ff57f16ee7c9b7ce' THEN 'capability'
                                WHEN item ->> 'id' = 'legacy_uncertainty_b1e5f1e39e767c2d129faf2a010ba651' THEN 'runtime'
                                ELSE COALESCE(item ->> 'kind', 'other')
                            END
                        )
                    ),
                    '[]'::jsonb
                )
                FROM jsonb_array_elements(uncertainties) AS item
            ),
            version = version + 1,
            updated_at = now()
        WHERE id = 'akira_primary'
          AND schema_version = 'self_model.v2';

        INSERT INTO public.audit_log (
            actor, action, resource, resource_id, status, detail
        )
        SELECT
            'system',
            'self_model.uncertainty_semantics_refine',
            'self_model',
            id,
            'success',
            jsonb_build_object(
                'schema', schema_version,
                'reason', 'map legacy uncertainty kinds'
            )
        FROM public.self_model
        WHERE id = 'akira_primary'
          AND schema_version = 'self_model.v2'
        """
    ),

    (
        "034_memory_owner_scoped_idempotency",
        """
        DROP INDEX IF EXISTS memories_idempotency_key_uq;
        CREATE UNIQUE INDEX memories_owner_idempotency_key_uq
            ON public.memories (owner_scope, idempotency_key)
        """
    ),

    (
        "035_graph_owner_scoped_uniqueness",
        """
        DROP INDEX IF EXISTS graph_nodes_idempotency_key_uq;
        CREATE UNIQUE INDEX graph_nodes_owner_idempotency_key_uq
            ON public.graph_nodes (owner_scope, idempotency_key);

        DROP INDEX IF EXISTS graph_nodes_active_type_label_uq;
        CREATE UNIQUE INDEX graph_nodes_owner_active_type_label_uq
            ON public.graph_nodes (owner_scope, node_type, lower(label))
            WHERE status = 'active';

        DROP INDEX IF EXISTS graph_edges_idempotency_key_uq;
        CREATE UNIQUE INDEX graph_edges_endpoint_idempotency_key_uq
            ON public.graph_edges (from_node, to_node, relation_type, idempotency_key);
        """
    ),

    (
        "036_learning_owner_scoped_uniqueness",
        """
        DROP INDEX IF EXISTS learning_events_idempotency_key_uq;
        CREATE UNIQUE INDEX learning_events_owner_idempotency_key_uq
            ON public.learning_events (owner_scope, idempotency_key);
        """
    ),

    (
        "037_cognitive_owner_scoped_idempotency",
        """
        DROP INDEX IF EXISTS cognitive_cycles_idempotency_key_uq;
        CREATE UNIQUE INDEX cognitive_cycles_owner_idempotency_key_uq
            ON public.cognitive_cycles (owner_scope, idempotency_key);

        DROP INDEX IF EXISTS cognitive_events_idempotency_key_uq;
        CREATE UNIQUE INDEX cognitive_events_cycle_idempotency_key_uq
            ON public.cognitive_events (cycle_id, idempotency_key);
        """
    ),

    (
        "038_agent_task_owner_scoped_idempotency",
        """
        DROP INDEX IF EXISTS agent_tasks_idempotency_key_uq;
        CREATE UNIQUE INDEX agent_tasks_owner_idempotency_key_uq
            ON public.agent_tasks (owner_scope, idempotency_key);
        """
    ),

    (
        "039_mission_owner_scoped_idempotency",
        """
        DROP INDEX IF EXISTS missions_idempotency_key_uq;
        CREATE UNIQUE INDEX missions_created_by_idempotency_key_uq
            ON public.missions (created_by, idempotency_key);
        """
    ),

    (
        "040_repair_engine_v1_capability",
        """
        INSERT INTO public.capabilities (
            id, name, description, category, kind,
            implementation_state, verification_state, availability_state,
            maturity, cost_compatibility, dependencies, limitations,
            verification_spec, provenance, schema_version, idempotency_key
        )
        VALUES (
            'cap_repair_engine_v1',
            'repair_engine_v1',
            'Motor de reparación controlada de estado con lifecycle persistente, sandbox, tests, evaluación, aprobación explícita, aplicación allowlisted y aprendizaje posterior.',
            'repair',
            'composite',
            'implemented',
            'unverified',
            'available',
            'experimental',
            'free',
            '[{"id":"IdentityRoot","kind":"authority","required":true},{"id":"SelfModel","kind":"state","required":true},{"id":"PersistenceService.repair","kind":"service","required":true},{"id":"specialized_agent_tools","kind":"verification","required":true},{"id":"owner_scope","kind":"security","required":true}]'::jsonb,
            '["V1 solo repara estado persistente explícitamente allowlisted.","No ejecuta escritura arbitraria de código ni mutación automática de GitHub.","Toda aplicación requiere sandbox, tests, evaluación y aprobación explícita."]'::jsonb,
            '{"method":"selftest","test_key":"repair_engine_v1_contract","freshness_policy":{"mode":"on_change","max_age_seconds":null,"invalidate_on":["build_change","repair_code_change","self_model_change","owner_scope_change"]}}'::jsonb,
            '{"source":"architecture_rebaseline_f12","created_by":"system"}'::jsonb,
            'capability.v1',
            'bootstrap:capability:repair_engine_v1:v1'
        )
        ON CONFLICT (name) DO UPDATE SET
            description = EXCLUDED.description,
            category = EXCLUDED.category,
            kind = EXCLUDED.kind,
            implementation_state = EXCLUDED.implementation_state,
            availability_state = EXCLUDED.availability_state,
            maturity = EXCLUDED.maturity,
            cost_compatibility = EXCLUDED.cost_compatibility,
            dependencies = EXCLUDED.dependencies,
            limitations = EXCLUDED.limitations,
            verification_spec = EXCLUDED.verification_spec,
            provenance = EXCLUDED.provenance,
            schema_version = EXCLUDED.schema_version,
            updated_at = now()
        """
    ),

    (
        "041_evolution_engine_v1",
        """
        CREATE TABLE IF NOT EXISTS public.evolution_records (
            id TEXT PRIMARY KEY,
            target_component TEXT NOT NULL,
            detected_need TEXT NOT NULL,
            research_reference TEXT NOT NULL DEFAULT '',
            design TEXT NOT NULL DEFAULT '',
            prototype_reference TEXT NOT NULL DEFAULT '',
            tests JSONB NOT NULL DEFAULT '[]'::jsonb,
            evaluation JSONB NOT NULL DEFAULT '{}'::jsonb,
            decision JSONB NOT NULL DEFAULT '{}'::jsonb,
            change_reference TEXT NOT NULL DEFAULT '',
            learning_reference TEXT NOT NULL DEFAULT '',
            failure_reason TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'detected'
                CHECK (status IN ('detected','researching','designing','prototyping',
                                  'testing','evaluating','applied','rejected','failed')),
            owner_scope TEXT NOT NULL DEFAULT 'owner',
            created_by TEXT NOT NULL,
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            schema_version TEXT NOT NULL DEFAULT 'evolution.v1',
            version INTEGER NOT NULL DEFAULT 1,
            idempotency_key TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE UNIQUE INDEX IF NOT EXISTS evolution_owner_idempotency_key_uq
            ON public.evolution_records (owner_scope, idempotency_key);

        CREATE INDEX IF NOT EXISTS evolution_owner_status_idx
            ON public.evolution_records (owner_scope, status, created_at DESC);
        CREATE INDEX IF NOT EXISTS evolution_target_idx
            ON public.evolution_records (target_component, created_at DESC);

        ALTER TABLE public.evolution_records ENABLE ROW LEVEL SECURITY;

        DROP POLICY IF EXISTS "akira_deny_anon_authenticated_select" ON public.evolution_records;
        DROP POLICY IF EXISTS "akira_deny_anon_authenticated_insert" ON public.evolution_records;
        DROP POLICY IF EXISTS "akira_deny_anon_authenticated_update" ON public.evolution_records;
        DROP POLICY IF EXISTS "akira_deny_anon_authenticated_delete" ON public.evolution_records;

        CREATE POLICY "akira_deny_anon_authenticated_select"
            ON public.evolution_records AS RESTRICTIVE
            FOR SELECT TO anon USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_insert"
            ON public.evolution_records AS RESTRICTIVE
            FOR INSERT TO anon WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_update"
            ON public.evolution_records AS RESTRICTIVE
            FOR UPDATE TO anon USING (false) WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_delete"
            ON public.evolution_records AS RESTRICTIVE
            FOR DELETE TO anon USING (false);

        INSERT INTO public.audit_log (
            actor, action, resource, resource_id, status, detail
        ) VALUES (
            'system',
            'evolution.schema.v1',
            'evolution_records',
            NULL,
            'success',
            '{"schema":"evolution.v1","scope":"controlled_lifecycle","github_write":false}'::jsonb
        )
        ON CONFLICT DO NOTHING
        """
    ),

    (
        "042_evolution_idempotency_index_hardening",
        """
        DROP INDEX IF EXISTS public.evolution_owner_idempotency_key_uq;
        CREATE UNIQUE INDEX evolution_owner_idempotency_key_uq
            ON public.evolution_records (owner_scope, idempotency_key);

        INSERT INTO public.audit_log (
            actor, action, resource, resource_id, status, detail
        ) VALUES (
            'system',
            'evolution.idempotency_index_harden',
            'evolution_records',
            NULL,
            'success',
            '{"unique_scope":["owner_scope","idempotency_key"],"partial":false}'::jsonb
        )
        ON CONFLICT DO NOTHING
        """
    ),

    (
        "043_mission_task_cancellation_state",
        """
        ALTER TABLE public.agent_tasks
            DROP CONSTRAINT IF EXISTS agent_tasks_status_check;
        ALTER TABLE public.agent_tasks
            ADD CONSTRAINT agent_tasks_status_check
            CHECK (status IN ('pending','running','completed','failed','cancelled'));

        INSERT INTO public.audit_log (
            actor, action, resource, resource_id, status, detail
        ) VALUES (
            'system',
            'mission.task.cancellation_schema',
            'agent_tasks',
            NULL,
            'success',
            '{"status":"cancelled","mission_terminal_invariant":true}'::jsonb
        )
        ON CONFLICT DO NOTHING
        """
    ),

    (
        "044_reconcile_legacy_cancelled_mission_tasks",
        """
        INSERT INTO public.audit_log (
            actor, action, resource, resource_id, status, detail
        )
        SELECT
            'system',
            'mission.task.legacy_reconcile',
            'agent_tasks',
            t.id,
            'success',
            jsonb_build_object(
                'mission_id', t.mission_id,
                'from', t.status,
                'to', 'cancelled',
                'reason', 'legacy_cancelled_mission_reconciliation'
            )
        FROM public.agent_tasks t
        JOIN public.missions m ON m.id = t.mission_id
        WHERE m.status = 'cancelled'
          AND t.status IN ('pending','running');

        UPDATE public.agent_tasks t
        SET status = 'cancelled',
            outputs = COALESCE(t.outputs, '{}'::jsonb) || jsonb_build_object(
                'cancel_reason', 'legacy_cancelled_mission_reconciliation'
            ),
            completed_at = COALESCE(t.completed_at, now()),
            updated_at = now()
        FROM public.missions m
        WHERE m.id = t.mission_id
          AND m.status = 'cancelled'
          AND t.status IN ('pending','running')
        """
    ),
    (
        "045_controlled_autonomy_v1",
        """
        CREATE TABLE IF NOT EXISTS public.autonomy_runs (
            id TEXT PRIMARY KEY,
            goal TEXT NOT NULL,
            repository TEXT NOT NULL,
            base_branch TEXT NOT NULL DEFAULT 'main',
            base_commit_sha TEXT NOT NULL DEFAULT '',
            branch_name TEXT NOT NULL DEFAULT '',
            paths JSONB NOT NULL DEFAULT '[]'::jsonb,
            instruction TEXT NOT NULL,
            queries JSONB NOT NULL DEFAULT '[]'::jsonb,
            requested_tests JSONB NOT NULL DEFAULT '[]'::jsonb,
            plan JSONB NOT NULL DEFAULT '{}'::jsonb,
            proposal JSONB NOT NULL DEFAULT '{}'::jsonb,
            sandbox JSONB NOT NULL DEFAULT '{}'::jsonb,
            tests JSONB NOT NULL DEFAULT '{}'::jsonb,
            evaluation JSONB NOT NULL DEFAULT '{}'::jsonb,
            decision JSONB NOT NULL DEFAULT '{}'::jsonb,
            action JSONB NOT NULL DEFAULT '{}'::jsonb,
            learning_reference TEXT NOT NULL DEFAULT '',
            failure_reason TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'observing'
                CHECK (status IN (
                    'observing','planning','delegating','proposed','sandboxed','tested',
                    'evaluating','awaiting_approval','acting','external_applied',
                    'evaluated','learned','completed','rejected','failed','cancelled'
                )),
            owner_scope TEXT NOT NULL DEFAULT 'owner',
            created_by TEXT NOT NULL,
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            schema_version TEXT NOT NULL DEFAULT 'autonomy.v1',
            version INTEGER NOT NULL DEFAULT 1,
            idempotency_key TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE UNIQUE INDEX IF NOT EXISTS autonomy_owner_idempotency_key_uq
            ON public.autonomy_runs (owner_scope, idempotency_key);
        CREATE INDEX IF NOT EXISTS autonomy_owner_status_idx
            ON public.autonomy_runs (owner_scope, status, created_at DESC);
        CREATE INDEX IF NOT EXISTS autonomy_repository_status_idx
            ON public.autonomy_runs (repository, base_branch, status, created_at DESC);

        ALTER TABLE public.autonomy_runs ENABLE ROW LEVEL SECURITY;

        DROP POLICY IF EXISTS "akira_deny_anon_autonomy_select" ON public.autonomy_runs;
        DROP POLICY IF EXISTS "akira_deny_anon_autonomy_insert" ON public.autonomy_runs;
        DROP POLICY IF EXISTS "akira_deny_anon_autonomy_update" ON public.autonomy_runs;
        DROP POLICY IF EXISTS "akira_deny_anon_autonomy_delete" ON public.autonomy_runs;

        CREATE POLICY "akira_deny_anon_autonomy_select"
            ON public.autonomy_runs AS RESTRICTIVE
            FOR SELECT TO anon USING (false);
        CREATE POLICY "akira_deny_anon_autonomy_insert"
            ON public.autonomy_runs AS RESTRICTIVE
            FOR INSERT TO anon WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_autonomy_update"
            ON public.autonomy_runs AS RESTRICTIVE
            FOR UPDATE TO anon USING (false) WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_autonomy_delete"
            ON public.autonomy_runs AS RESTRICTIVE
            FOR DELETE TO anon USING (false);

        INSERT INTO public.audit_log (
            actor, action, resource, resource_id, status, detail
        ) VALUES (
            'system',
            'autonomy.schema.v1',
            'autonomy_runs',
            NULL,
            'success',
            '{"schema":"autonomy.v1","scope":"controlled_autonomy","main_write":false,"merge":false,"human_approval":true}'::jsonb
        )
        ON CONFLICT DO NOTHING
        """
    ),
    (
        "047_self_model_f2_coherence",
        """
        INSERT INTO capabilities (
            id, name, description, category, kind,
            implementation_state, verification_state, availability_state,
            maturity, cost_compatibility, dependencies, limitations,
            verification_spec, provenance, schema_version, idempotency_key
        )
        VALUES (
            'cap_self_model_persistent',
            'self_model_persistent',
            'Self-Model persistente de Akira con singleton versionado, identidad autoritativa y proyecciones actuales de capabilities, tools y models.',
            'identity',
            'composite',
            'implemented',
            'unverified',
            'available',
            'experimental',
            'free',
            '[{"kind":"service","id":"PersistenceService.get_self_model","required":true},{"kind":"service","id":"PersistenceService.update_self_model","required":true},{"kind":"storage","id":"PostgreSQL.self_model","required":true},{"kind":"authority","id":"IdentityRoot","required":true},{"kind":"registry","id":"CapabilityEngine","required":true}]'::jsonb,
            '["Capabilities, tools y models son proyecciones derivadas y no se editan manualmente.","El self-model conserva incertidumbres históricas y la proyección runtime usa fuentes autoritativas actuales."]'::jsonb,
            '{
                "method":"selftest",
                "test_key":"self_model_persistent_contract",
                "freshness_policy":{"mode":"on_change","max_age_seconds":null,
                "invalidate_on":["build_change","self_model_schema_change","identity_root_change","capability_registry_change"]}
            }'::jsonb,
            '{"source":"architecture_rebaseline_f2","created_by":"system"}'::jsonb,
            'capability.v1',
            'bootstrap:capability:self_model_persistent:v1'
        )
        ON CONFLICT (name) DO UPDATE SET
            description = EXCLUDED.description,
            category = EXCLUDED.category,
            kind = EXCLUDED.kind,
            implementation_state = EXCLUDED.implementation_state,
            availability_state = EXCLUDED.availability_state,
            maturity = EXCLUDED.maturity,
            cost_compatibility = EXCLUDED.cost_compatibility,
            dependencies = EXCLUDED.dependencies,
            limitations = EXCLUDED.limitations,
            verification_spec = EXCLUDED.verification_spec,
            provenance = EXCLUDED.provenance,
            schema_version = EXCLUDED.schema_version,
            updated_at = now();

        UPDATE public.self_model
        SET
            knowledge_state = jsonb_build_object(
                'last_observed_at', now(),
                'sources', jsonb_build_array(
                    jsonb_build_object('id','IdentityRoot','kind','authority','observed_at',now()),
                    jsonb_build_object('id','CapabilityEngine','kind','registry','observed_at',COALESCE((SELECT max(updated_at) FROM public.capabilities),now())),
                    jsonb_build_object('id','AgentRegistry','kind','registry','observed_at',COALESCE((SELECT max(updated_at) FROM public.agents),now())),
                    jsonb_build_object('id','ToolRegistry','kind','registry','observed_at',COALESCE((SELECT max(updated_at) FROM public.tools),now())),
                    jsonb_build_object('id','MissionEngine','kind','registry','observed_at',COALESCE((SELECT max(updated_at) FROM public.missions),now())),
                    jsonb_build_object('id','LearningStore','kind','storage','observed_at',COALESCE((SELECT max(updated_at) FROM public.learning_events),now())),
                    jsonb_build_object('id','EvolutionStore','kind','storage','observed_at',COALESCE((SELECT max(updated_at) FROM public.evolution_records),now())),
                    jsonb_build_object('id','AutonomyStore','kind','storage','observed_at',COALESCE((SELECT max(updated_at) FROM public.autonomy_runs),now())),
                    jsonb_build_object('id','CognitiveRuntime','kind','storage','observed_at',COALESCE((SELECT max(updated_at) FROM public.cognitive_cycles),now()))
                ),
                'notes', 'Estado observado desde fuentes autoritativas. Capabilities, tools y models se proyectan en runtime y no se duplican como autoridad persistida.'
            ),
            version = version + 1,
            updated_at = now()
        WHERE id = 'akira_primary';

        UPDATE public.self_model
        SET
            uncertainties = (
                SELECT jsonb_agg(item ORDER BY item->>'id')
                FROM (
                    SELECT
                        jsonb_set(
                            item,
                            '{status}',
                            '"superseded"'::jsonb
                        )
                        || jsonb_build_object(
                            'evidence', jsonb_build_array(
                                'La implementación actual de Mission Engine existe y mantiene registros persistentes en PostgreSQL.',
                                'La arquitectura vigente ya no usa Fase 10 como descripción canónica.'
                            )
                        ) AS item
                    FROM jsonb_array_elements(uncertainties) item
                    WHERE item->>'statement' = 'Los agentes existen' || chr(59) || ' las misiones estan en construccion (Fase 10).'
                    UNION ALL
                    SELECT item
                    FROM jsonb_array_elements(uncertainties) item
                    WHERE item->>'statement' <> 'Los agentes existen' || chr(59) || ' las misiones estan en construccion (Fase 10).'
                    UNION ALL
                    SELECT jsonb_build_object(
                        'id','uncertainty_missions_current_state',
                        'statement','Mission Engine esta implementado, pero existen misiones en estados activos, fallidos y completados, y la salud operacional del flujo debe seguir verificandose.',
                        'kind','capability',
                        'status','open',
                        'evidence',jsonb_build_array(
                            'Consulta autoritativa de public.missions durante la rebaselina F2.'
                        ),
                        'created_at',now()
                    )
                ) all_items
            ),
            version = version + 1,
            updated_at = now()
        WHERE id = 'akira_primary';

        INSERT INTO public.audit_log (actor, action, resource, resource_id, status, detail)
        VALUES (
            'system',
            'self_model.f2_coherence_rebaseline',
            'self_model',
            'akira_primary',
            'success',
            jsonb_build_object(
                'schema_version','self_model.v2',
                'reason','F2 canonical self-model coherence',
                'capability','self_model_persistent'
            )
        );
        """
    ),

    (
        "048_self_model_capability_contract_sync",
        """
        UPDATE public.capabilities
        SET
            description = 'Self-Model persistente de Akira con singleton versionado, identidad autoritativa y proyecciones actuales de capabilities, tools y models.',
            category = 'identity',
            kind = 'composite',
            implementation_state = 'implemented',
            maturity = 'experimental',
            cost_compatibility = 'free',
            dependencies = '[{"kind":"service","id":"PersistenceService.get_self_model","required":true},{"kind":"service","id":"PersistenceService.update_self_model","required":true},{"kind":"storage","id":"PostgreSQL.self_model","required":true},{"kind":"authority","id":"IdentityRoot","required":true},{"kind":"registry","id":"CapabilityEngine","required":true}]'::jsonb,
            limitations = '["Capabilities, tools y models son proyecciones derivadas y no son editables manualmente dentro del self-model.","El self-model persistente conserva incertidumbres históricas, y el runtime self-knowledge prioriza fuentes autoritativas actuales.","La verificación de escritura se cubre por el contrato de persistencia y el runtime no altera la identidad raíz."]'::jsonb,
            verification_spec = '{"method":"selftest","test_key":"self_model_persistent_contract","freshness_policy":{"mode":"on_change","max_age_seconds":null,"invalidate_on":["build_change","self_model_schema_change","identity_root_change","capability_registry_change"]}}'::jsonb,
            provenance = '{"source":"architecture_rebaseline_f2","created_by":"system","basis":["persistence/core.py","persistence/service.py","persistence/selftest.py","test_self_knowledge_contract.py"]}'::jsonb,
            schema_version = 'capability.v1',
            idempotency_key = 'bootstrap:capability:self_model_persistent:v1',
            updated_at = now()
        WHERE name = 'self_model_persistent';

        INSERT INTO public.audit_log (
            actor, action, resource, resource_id, status, detail
        )
        VALUES (
            'system',
            'self_model.capability_contract_sync',
            'capabilities',
            'cap_self_model_persistent',
            'success',
            jsonb_build_object(
                'reason','align_seed_catalog_with_persisted_contract',
                'capability','self_model_persistent'
            )
        );
        """
    ),

    (
        "046_controlled_autonomy_runtime_registry",
        """
        INSERT INTO public.tools (
            id, name, description, category, permissions,
            inputs_schema, outputs_schema, limits_json, risks,
            status, schema_version, version
        )
        VALUES (
            'tool_controlled_autonomy_start',
            'controlled_autonomy_start',
            'Inicia la autonomia controlada F14 hasta una compuerta de aprobacion humana, sin aprobar ni aplicar cambios.',
            'code',
            '["owner"]'::jsonb,
            '{"goal":"str","repository":"str","base_branch":"str","paths":"list","instruction":"str","queries":"list","tests":"list","idempotency_key":"str"}'::jsonb,
            '{"autonomy":"dict"}'::jsonb,
            '{"max_paths":4,"max_instruction":4000,"max_files":4}'::jsonb,
            '["propone y prueba cambios de codigo","requiere aprobacion humana antes de escribir GitHub"]'::jsonb,
            'available',
            'tool.v1',
            1
        )
        ON CONFLICT (name) DO NOTHING;

        SELECT 1 / CASE
            WHEN status = 'available'
             AND permissions = '["owner"]'::jsonb
            THEN 1
            ELSE 0
        END
        FROM public.tools
        WHERE name = 'controlled_autonomy_start';

        INSERT INTO public.agents (
            id, name, role, description, allowed_tools,
            status, schema_version, version
        )
        VALUES (
            'agent_autonomy_orchestrator',
            'autonomy_orchestrator',
            'autonomy_orchestrator',
            'Orquesta autonomia controlada hasta aprobacion humana, sin poder aprobar ni aplicar el cambio.',
            '["controlled_autonomy_start"]'::jsonb,
            'idle',
            'agent.v1',
            1
        )
        ON CONFLICT (name) DO NOTHING;

        SELECT 1 / CASE
            WHEN 'controlled_autonomy_start' = ANY (
                SELECT jsonb_array_elements_text(allowed_tools)
            )
            THEN 1
            ELSE 0
        END
        FROM public.agents
        WHERE name = 'autonomy_orchestrator';

        INSERT INTO public.audit_log (
            actor, action, resource, resource_id, status, detail
        )
        SELECT
            'system',
            'autonomy.runtime_registry.v1',
            'tools',
            'tool_controlled_autonomy_start',
            'success',
            '{"tool":"controlled_autonomy_start","agent":"autonomy_orchestrator","owner_only":true,"human_approval_before_external_write":true}'::jsonb
        WHERE NOT EXISTS (
            SELECT 1
            FROM public.audit_log
            WHERE actor = 'system'
              AND action = 'autonomy.runtime_registry.v1'
              AND resource = 'tools'
              AND resource_id = 'tool_controlled_autonomy_start'
        )
        """
    ),
    (
        "049_knowledge_first_class_and_graph_fk",
        """
        CREATE TABLE knowledge_records (
            id TEXT PRIMARY KEY,
            concept TEXT NOT NULL,
            content TEXT NOT NULL,
            domain TEXT NOT NULL,
            source TEXT NOT NULL,
            source_id TEXT,
            source_reference TEXT,
            created_by TEXT NOT NULL,
            confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5 CHECK (confidence BETWEEN 0 AND 1),
            verification_status TEXT NOT NULL DEFAULT 'unverified'
                CHECK (verification_status IN ('unknown','unverified','partially_verified','verified','deprecated','contradicted')),
            evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
            tags JSONB NOT NULL DEFAULT '[]'::jsonb,
            related_nodes JSONB NOT NULL DEFAULT '[]'::jsonb,
            owner_scope TEXT NOT NULL DEFAULT 'owner',
            privacy_level TEXT NOT NULL DEFAULT 'PRIVATE'
                CHECK (privacy_level IN ('PRIVATE','SENSITIVE','SHAREABLE','COLLECTIVE')),
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active','archived','deleted')),
            schema_version TEXT NOT NULL DEFAULT 'knowledge.v1',
            version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
            idempotency_key TEXT,
            last_verified_at TIMESTAMPTZ,
            verified_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT knowledge_verified_requires_evidence CHECK (
                verification_status <> 'verified'
                OR (
                    jsonb_array_length(evidence) > 0
                    AND last_verified_at IS NOT NULL
                    AND verified_by IS NOT NULL
                    AND length(trim(verified_by)) > 0
                )
            ),
            CONSTRAINT knowledge_unverified_has_no_verifier CHECK (
                verification_status = 'verified'
                OR (
                    last_verified_at IS NULL
                    AND verified_by IS NULL
                )
            )
        );
        CREATE UNIQUE INDEX knowledge_owner_idempotency_key_uq
            ON knowledge_records (owner_scope, idempotency_key);
        CREATE INDEX knowledge_owner_status_idx
            ON knowledge_records (owner_scope, status);
        CREATE INDEX knowledge_verification_idx
            ON knowledge_records (verification_status, updated_at DESC);
        CREATE INDEX knowledge_domain_idx
            ON knowledge_records (domain, status);
        CREATE INDEX knowledge_source_idx
            ON knowledge_records (source, created_at DESC);
        CREATE INDEX knowledge_confidence_idx
            ON knowledge_records (confidence DESC, updated_at DESC);
        CREATE INDEX knowledge_tags_idx
            ON knowledge_records USING GIN (tags);

        ALTER TABLE public.graph_edges
            ADD CONSTRAINT graph_edges_from_node_fk
            FOREIGN KEY (from_node) REFERENCES public.graph_nodes(id) ON DELETE RESTRICT;
        ALTER TABLE public.graph_edges
            ADD CONSTRAINT graph_edges_to_node_fk
            FOREIGN KEY (to_node) REFERENCES public.graph_nodes(id) ON DELETE RESTRICT;

        ALTER TABLE public.knowledge_records ENABLE ROW LEVEL SECURITY;
        REVOKE ALL ON TABLE public.knowledge_records FROM anon, authenticated;
        CREATE POLICY "akira_deny_anon_authenticated_select"
            ON public.knowledge_records AS RESTRICTIVE
            FOR SELECT TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_insert"
            ON public.knowledge_records AS RESTRICTIVE
            FOR INSERT TO anon, authenticated WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_update"
            ON public.knowledge_records AS RESTRICTIVE
            FOR UPDATE TO anon, authenticated USING (false) WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_delete"
            ON public.knowledge_records AS RESTRICTIVE
            FOR DELETE TO anon, authenticated USING (false);

        INSERT INTO public.audit_log (
            actor, action, resource, resource_id, status, detail
        )
        VALUES (
            'system',
            'knowledge.schema.f4_v1',
            'knowledge_records',
            NULL,
            'success',
            jsonb_build_object(
                'schema_version','knowledge.v1',
                'graph_foreign_keys',true,
                'on_delete','restrict',
                'reason','first_class_knowledge_and_graph_integrity'
            )
        );
        """
    ),
    (
        "050_runtime_build_state",
        """
        CREATE TABLE runtime_state (
            key TEXT PRIMARY KEY,
            value JSONB NOT NULL DEFAULT '{}'::jsonb,
            version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        ALTER TABLE public.runtime_state ENABLE ROW LEVEL SECURITY;
        REVOKE ALL ON TABLE public.runtime_state FROM anon, authenticated;
        CREATE POLICY "akira_deny_anon_authenticated_select"
            ON public.runtime_state AS RESTRICTIVE
            FOR SELECT TO anon, authenticated USING (false);
        CREATE POLICY "akira_deny_anon_authenticated_insert"
            ON public.runtime_state AS RESTRICTIVE
            FOR INSERT TO anon, authenticated WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_update"
            ON public.runtime_state AS RESTRICTIVE
            FOR UPDATE TO anon, authenticated USING (false) WITH CHECK (false);
        CREATE POLICY "akira_deny_anon_authenticated_delete"
            ON public.runtime_state AS RESTRICTIVE
            FOR DELETE TO anon, authenticated USING (false);
        """
    ),
    (
        "051_cognitive_cycle_persistent_capability",
        """
        INSERT INTO public.capabilities (
            id, name, description, category, kind,
            implementation_state, verification_state, availability_state,
            maturity, cost_compatibility, dependencies, limitations,
            verification_spec, provenance, schema_version, idempotency_key
        )
        VALUES (
            'cap_cognitive_cycle_persistent',
            'cognitive_cycle_persistent',
            'Runtime cognitivo persistente de nueve etapas que observa, interpreta, razona, decide, actúa, observa el resultado, evalúa, aprende y actualiza el Self-Model con evidencia persistida e aislamiento por owner_scope.',
            'cognitive',
            'composite',
            'implemented',
            'unverified',
            'available',
            'experimental',
            'conditional',
            '[{"kind":"service","id":"PersistenceService.start_cycle","required":true},{"kind":"service","id":"PersistenceService.record_stage","required":true},{"kind":"service","id":"PersistenceService.complete_cycle","required":true},{"kind":"storage","id":"PostgreSQL.cognitive_cycles","required":true},{"kind":"storage","id":"PostgreSQL.cognitive_events","required":true},{"kind":"security","id":"owner_scope","required":true},{"kind":"state_machine","id":"COGNITIVE_STAGES","required":true}]'::jsonb,
            '["La verificación de la capacidad requiere una ejecución E2E real del ciclo: la existencia del código no constituye evidencia suficiente.","La calidad de la inferencia depende de los proveedores externos disponibles. La persistencia y la máquina de estados son independientes de ellos.","Los ciclos legacy con owner_scope=owner se conservan como compatibilidad histórica."]'::jsonb,
            '{"method":"e2e_test","test_key":"cognitive_cycle_persistent_e2e","freshness_policy":{"mode":"on_change","max_age_seconds":null,"invalidate_on":["build_change","cognitive_runtime_change","cognitive_schema_change","ownership_change"]}}'::jsonb,
            '{"source":"architecture_rebaseline_f7","created_by":"system","basis":["persistence/core.py","persistence/service.py","nexus.py","test_cognitive_runtime_execution.py"]}'::jsonb,
            'capability.v1',
            'bootstrap:capability:cognitive_cycle_persistent:v1'
        )
        ON CONFLICT (name) DO UPDATE SET
            description = EXCLUDED.description,
            category = EXCLUDED.category,
            kind = EXCLUDED.kind,
            implementation_state = EXCLUDED.implementation_state,
            availability_state = EXCLUDED.availability_state,
            maturity = EXCLUDED.maturity,
            cost_compatibility = EXCLUDED.cost_compatibility,
            dependencies = EXCLUDED.dependencies,
            limitations = EXCLUDED.limitations,
            verification_spec = EXCLUDED.verification_spec,
            provenance = EXCLUDED.provenance,
            schema_version = EXCLUDED.schema_version,
            updated_at = now()
        """
    ),
    (
        "052_cognitive_cycle_persistent_capability_contract_sync",
        """
        UPDATE public.capabilities
        SET
            limitations = '["La verificación de la capacidad requiere una ejecución E2E real del ciclo: la existencia del código no constituye evidencia suficiente.","La calidad de la inferencia depende de los proveedores externos disponibles. La persistencia y la máquina de estados son independientes de ellos.","Los ciclos legacy con owner_scope=''owner'' se conservan como compatibilidad histórica."]'::jsonb,
            updated_at = now()
        WHERE name = 'cognitive_cycle_persistent';

        SELECT 1 / CASE
            WHEN EXISTS (
                SELECT 1
                FROM public.capabilities
                WHERE name = 'cognitive_cycle_persistent'
                  AND limitations = '["La verificación de la capacidad requiere una ejecución E2E real del ciclo: la existencia del código no constituye evidencia suficiente.","La calidad de la inferencia depende de los proveedores externos disponibles. La persistencia y la máquina de estados son independientes de ellos.","Los ciclos legacy con owner_scope=''owner'' se conservan como compatibilidad histórica."]'::jsonb
            )
            THEN 1
            ELSE 0
        END
        """
    )
]
