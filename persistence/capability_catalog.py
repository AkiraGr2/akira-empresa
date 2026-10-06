"""Catálogo mínimo de capacidades canónicas de AKIRA.

Este archivo define solo capacidades que tienen implementación identificable.
El estado de verificación siempre inicia como unverified; la evidencia posterior
determina si puede pasar a verified.
"""

SESSION_AUTH_CAPABILITY = {
    "name": "session_auth",
    "description": "Autenticación de sesión propia firmada y validada por el backend, con identidad de propietario derivada exclusivamente de una sesión verificada.",
    "category": "security",
    "kind": "provider_dependent",
    "implementation_state": "implemented",
    "verification_state": "unverified",
    "availability_state": "available",
    "maturity": "experimental",
    "cost_compatibility": "conditional",
    "dependencies": [
        {"kind": "module", "id": "akira_auth.py", "required": True},
        {"kind": "configuration", "id": "AKIRA_SESSION_SECRET", "required": True},
        {"kind": "configuration", "id": "OWNER_EMAILS", "required": True},
        {"kind": "identity_provider", "id": "Google", "required": True},
    ],
    "limitations": [
        "La emisión inicial depende de una credencial de identidad válida de Google.",
        "Sin AKIRA_SESSION_SECRET no se pueden emitir sesiones propias.",
        "La propiedad se decide en servidor y no debe confiar en datos enviados por el cliente.",
    ],
    "verification_spec": {
        "method": "selftest",
        "test_key": "session_auth_contract",
        "freshness_policy": {
            "mode": "on_change",
            "max_age_seconds": None,
            "invalidate_on": [
                "build_change",
                "dependency_change",
                "auth_configuration_change",
            ],
        },
    },
    "provenance": {
        "source": "architecture_rebaseline",
        "created_by": "system",
        "basis": [
            "akira_auth.py",
            "test_authorization_contract.py",
            "test_route_security_contract.py",
            "test_session_auth_contract.py",
        ],
    },
}

PERSISTENT_MEMORY_CAPABILITY = {
    "name": "persistent_memory",
    "description": "Persistencia de memorias reales mediante el servicio de persistencia, con relectura confirmada, idempotencia, versionado, archivado, privacidad y aislamiento por owner_scope.",
    "category": "memory",
    "kind": "composite",
    "implementation_state": "implemented",
    "verification_state": "unverified",
    "availability_state": "available",
    "maturity": "experimental",
    "cost_compatibility": "conditional",
    "dependencies": [
        {"kind": "service", "id": "PersistenceService.save_memory", "required": True},
        {"kind": "storage", "id": "PostgreSQL.memories", "required": True},
        {"kind": "security", "id": "owner_scope", "required": True},
    ],
    "limitations": [
        "La recuperación semántica mediante embeddings pertenece a memory_recall y no a esta capability.",
        "El ámbito legacy 'owner' se conserva como compatibilidad para datos históricos.",
        "La disponibilidad efectiva depende del almacenamiento persistente configurado.",
    ],
    "verification_spec": {
        "method": "selftest",
        "test_key": "persistent_memory_contract",
        "freshness_policy": {
            "mode": "on_change",
            "max_age_seconds": None,
            "invalidate_on": [
                "build_change",
                "dependency_change",
                "memory_schema_change",
                "ownership_change",
            ],
        },
    },
    "provenance": {
        "source": "architecture_rebaseline",
        "created_by": "system",
        "basis": [
            "persistence/core.py",
            "persistence/service.py",
            "persistence/selftest.py",
            "test_persistent_memory_contract.py",
        ],
    },
}


MEMORY_RECALL_CAPABILITY = {
    "name": "memory_recall",
    "description": "Recuperación híbrida de memorias activas: búsqueda léxica como respaldo, búsqueda semántica mediante Gemini Embedding 2 + pgvector y aislamiento por owner_scope.",
    "category": "memory",
    "kind": "provider_dependent",
    "implementation_state": "implemented",
    "verification_state": "unverified",
    "availability_state": "available",
    "maturity": "experimental",
    "cost_compatibility": "conditional",
    "dependencies": [
        {"kind": "service", "id": "PersistenceService.search_memory", "required": True},
        {"kind": "service", "id": "PersistenceService.search_memory_semantic", "required": True},
        {"kind": "storage", "id": "PostgreSQL.memory_embeddings", "required": True},
        {"kind": "extension", "id": "pgvector", "required": True},
        {"kind": "provider", "id": "gemini-embedding-2", "required": True},
        {"kind": "security", "id": "owner_scope", "required": True},
    ],
    "limitations": [
        "La rama semántica depende de disponibilidad, cuotas y limites del proveedor externo; la rama léxica conserva degradación segura.",
        "La calidad semántica depende del modelo de embeddings y de la consistencia del corpus indexado.",
        "Las memorias legacy con owner_scope='owner' se conservan como compatibilidad histórica.",
    ],
    "verification_spec": {
        "method": "selftest",
        "test_key": "memory_recall_contract",
        "freshness_policy": {
            "mode": "on_change",
            "max_age_seconds": None,
            "invalidate_on": [
                "build_change",
                "dependency_change",
                "embedding_model_change",
                "memory_schema_change",
                "ownership_change",
            ],
        },
    },
    "provenance": {
        "source": "architecture_rebaseline",
        "created_by": "system",
        "basis": [
            "nexus.py",
            "persistence/memory_recall.py",
            "persistence/service.py",
            "persistence/postgres.py",
            "persistence/migrations.py",
        ],
    },
}


LEARNING_PERSISTENT_CAPABILITY = {
    "name": "learning_persistent",
    "description": "Persistencia verificable del aprendizaje de AKIRA: candidatos, evidencia, evaluacion, transiciones de estado, reutilizacion y aislamiento por owner_scope.",
    "category": "learning",
    "kind": "composite",
    "implementation_state": "implemented",
    "verification_state": "unverified",
    "availability_state": "available",
    "maturity": "experimental",
    "cost_compatibility": "conditional",
    "dependencies": [
        {"kind": "service", "id": "PersistenceService.save_learning", "required": True},
        {"kind": "service", "id": "PersistenceService.add_learning_evidence", "required": True},
        {"kind": "service", "id": "PersistenceService.update_learning_status", "required": True},
        {"kind": "service", "id": "PersistenceService.record_reuse", "required": True},
        {"kind": "storage", "id": "PostgreSQL.learning_events", "required": True},
        {"kind": "security", "id": "owner_scope", "required": True},
    ],
    "limitations": [
        "La evaluacion factual puede depender de proveedores externos; la persistencia y las reglas de estado no dependen de ellos.",
        "Los registros historicos learning.v1 y learning.v2 se conservan como compatibilidad; las nuevas escrituras usan learning.v3.",
        "La consolidacion exige evidencia y una evaluacion supported con confianza >= 0.70.",
        "La materializacion posterior en memoria y grafo es una integracion separada y debe verificarse por su propio contrato.",
    ],
    "verification_spec": {
        "method": "selftest",
        "test_key": "learning_persistent_contract",
        "freshness_policy": {
            "mode": "on_change",
            "max_age_seconds": None,
            "invalidate_on": [
                "build_change",
                "dependency_change",
                "learning_schema_change",
                "ownership_change",
            ],
        },
    },
    "provenance": {
        "source": "architecture_rebaseline",
        "created_by": "system",
        "basis": [
            "persistence/core.py",
            "persistence/service.py",
            "persistence/selftest.py",
            "nexus.py",
        ],
    },
}


GRAPH_PERSISTENT_CAPABILITY = {
    "name": "graph_persistent",
    "description": "Persistencia verificable de nodos y relaciones del grafo de Akira, con versionado, idempotencia, aislamiento por owner_scope, integridad de extremos y archivado de relaciones.",
    "category": "graph",
    "kind": "composite",
    "implementation_state": "implemented",
    "verification_state": "unverified",
    "availability_state": "available",
    "maturity": "experimental",
    "cost_compatibility": "conditional",
    "dependencies": [
        {"kind": "service", "id": "PersistenceService.create_node", "required": True},
        {"kind": "service", "id": "PersistenceService.get_node", "required": True},
        {"kind": "service", "id": "PersistenceService.update_node", "required": True},
        {"kind": "service", "id": "PersistenceService.create_edge", "required": True},
        {"kind": "service", "id": "PersistenceService.get_edge", "required": True},
        {"kind": "service", "id": "PersistenceService.archive_edge", "required": True},
        {"kind": "storage", "id": "PostgreSQL.graph_nodes", "required": True},
        {"kind": "storage", "id": "PostgreSQL.graph_edges", "required": True},
        {"kind": "security", "id": "owner_scope", "required": True},
    ],
    "limitations": [
        "La API pública actual no expone actualización arbitraria de aristas ni archivado de nodos como operaciones de primer nivel; esas operaciones no forman parte del contrato de esta verificación.",
        "La visibilidad de registros legacy con owner_scope='owner' se conserva por compatibilidad histórica y no representa un modelo multi-propietario aislado para esos datos legacy.",
        "La integridad referencial de extremos depende de la capa de servicio; la base actual no declara FKs entre graph_edges y graph_nodes.",
        "Las conexiones automáticas por tags y al núcleo son una capacidad separada y no constituyen por sí mismas evidencia de graph_persistent.",
    ],
    "verification_spec": {
        "method": "selftest",
        "test_key": "graph_persistent_contract",
        "freshness_policy": {
            "mode": "on_change",
            "max_age_seconds": None,
            "invalidate_on": [
                "build_change",
                "dependency_change",
                "graph_schema_change",
                "ownership_change",
            ],
        },
    },
    "provenance": {
        "source": "architecture_audit_v12",
        "created_by": "system",
        "basis": [
            "persistence/core.py",
            "persistence/service.py",
            "persistence/postgres.py",
            "persistence/migrations.py",
            "nexus.py",
            "persistence/selftest.py",
        ],
    },
}



EVOLUTION_ENGINE_CAPABILITY = {
    "name": "evolution_engine_v1",
    "description": "Motor de evolución controlada y auditable: registra necesidad, investigación, diseño, prototipo, pruebas, evaluación, aprobación humana y referencia de cambio sin autoescritura de código.",
    "category": "evolution",
    "kind": "composite",
    "implementation_state": "implemented",
    "verification_state": "unverified",
    "availability_state": "available",
    "maturity": "experimental",
    "cost_compatibility": "free",
    "dependencies": [
        {"kind": "service", "id": "PersistenceService.create_evolution", "required": True},
        {"kind": "service", "id": "PersistenceService.advance_evolution", "required": True},
        {"kind": "service", "id": "PersistenceService.approve_evolution", "required": True},
        {"kind": "service", "id": "PersistenceService.apply_evolution", "required": True},
        {"kind": "storage", "id": "PostgreSQL.evolution_records", "required": True},
        {"kind": "security", "id": "owner_scope", "required": True},
        {"kind": "approval", "id": "human_approval", "required": True},
    ],
    "limitations": [
        "F13 no escribe código ni muta GitHub automáticamente.",
        "La aplicación requiere una referencia de cambio real y aprobación humana explícita.",
        "Una propuesta, review o salida de un modelo no constituye evidencia de implementación.",
    ],
    "verification_spec": {
        "method": "selftest",
        "test_key": "evolution_engine_v1_contract",
        "freshness_policy": {
            "mode": "on_change",
            "max_age_seconds": None,
            "invalidate_on": [
                "build_change",
                "dependency_change",
                "evolution_schema_change",
                "ownership_change",
            ],
        },
    },
    "provenance": {
        "source": "architecture_rebaseline_f13",
        "created_by": "system",
        "basis": [
            "persistence/core.py",
            "persistence/service.py",
            "persistence/migrations.py",
            "persistence/selftest.py",
        ],
    },
}

BASE_CAPABILITIES = (SESSION_AUTH_CAPABILITY, PERSISTENT_MEMORY_CAPABILITY, MEMORY_RECALL_CAPABILITY, LEARNING_PERSISTENT_CAPABILITY, GRAPH_PERSISTENT_CAPABILITY, EVOLUTION_ENGINE_CAPABILITY)
