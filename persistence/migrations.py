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
]