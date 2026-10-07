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


SELF_MODEL_PERSISTENT_CAPABILITY = {
    "name": "self_model_persistent",
    "description": "Self-Model persistente de Akira con singleton versionado, identidad autoritativa y proyecciones actuales de capabilities, tools y models.",
    "category": "identity",
    "kind": "composite",
    "implementation_state": "implemented",
    "verification_state": "unverified",
    "availability_state": "available",
    "maturity": "experimental",
    "cost_compatibility": "free",
    "dependencies": [
        {"kind": "service", "id": "PersistenceService.get_self_model", "required": True},
        {"kind": "service", "id": "PersistenceService.update_self_model", "required": True},
        {"kind": "storage", "id": "PostgreSQL.self_model", "required": True},
        {"kind": "authority", "id": "IdentityRoot", "required": True},
        {"kind": "registry", "id": "CapabilityEngine", "required": True},
    ],
    "limitations": [
        "Capabilities, tools y models son proyecciones derivadas y no son editables manualmente dentro del self-model.",
        "El self-model persistente conserva incertidumbres históricas, y el runtime self-knowledge prioriza fuentes autoritativas actuales.",
        "La verificación de escritura se cubre por el contrato de persistencia y el runtime no altera la identidad raíz.",
    ],
    "verification_spec": {
        "method": "selftest",
        "test_key": "self_model_persistent_contract",
        "freshness_policy": {
            "mode": "on_change",
            "max_age_seconds": None,
            "invalidate_on": [
                "build_change",
                "self_model_schema_change",
                "identity_root_change",
                "capability_registry_change",
            ],
        },
    },
    "provenance": {
        "source": "architecture_rebaseline_f2",
        "created_by": "system",
        "basis": [
            "persistence/core.py",
            "persistence/service.py",
            "persistence/selftest.py",
            "test_self_knowledge_contract.py",
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




COGNITIVE_CYCLE_PERSISTENT_CAPABILITY = {
    "name": "cognitive_cycle_persistent",
    "description": "Runtime cognitivo persistente de nueve etapas que observa, interpreta, razona, decide, actúa, observa el resultado, evalúa, aprende y actualiza el Self-Model con evidencia persistida e aislamiento por owner_scope.",
    "category": "cognitive",
    "kind": "composite",
    "implementation_state": "implemented",
    "verification_state": "unverified",
    "availability_state": "available",
    "maturity": "experimental",
    "cost_compatibility": "conditional",
    "dependencies": [
        {"kind": "service", "id": "PersistenceService.start_cycle", "required": True},
        {"kind": "service", "id": "PersistenceService.record_stage", "required": True},
        {"kind": "service", "id": "PersistenceService.complete_cycle", "required": True},
        {"kind": "storage", "id": "PostgreSQL.cognitive_cycles", "required": True},
        {"kind": "storage", "id": "PostgreSQL.cognitive_events", "required": True},
        {"kind": "security", "id": "owner_scope", "required": True},
        {"kind": "state_machine", "id": "COGNITIVE_STAGES", "required": True},
    ],
    "limitations": [
        "La verificación de la capacidad requiere una ejecución E2E real del ciclo; la existencia del código no constituye evidencia suficiente.",
        "La calidad de la inferencia depende de los proveedores externos disponibles; la persistencia y la máquina de estados son independientes de ellos.",
        "Los ciclos legacy con owner_scope='owner' se conservan como compatibilidad histórica.",
    ],
    "verification_spec": {
        "method": "e2e_test",
        "test_key": "cognitive_cycle_persistent_e2e",
        "freshness_policy": {
            "mode": "on_change",
            "max_age_seconds": None,
            "invalidate_on": [
                "build_change",
                "cognitive_runtime_change",
                "cognitive_schema_change",
                "ownership_change",
            ],
        },
    },
    "provenance": {
        "source": "architecture_rebaseline_f7",
        "created_by": "system",
        "basis": [
            "persistence/core.py",
            "persistence/service.py",
            "nexus.py",
            "test_cognitive_runtime_execution.py",
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


CONTROLLED_AUTONOMY_CAPABILITY = {
    "name": "controlled_autonomy_v1",
    "description": "Orquestacion autonoma controlada que observa, planifica, delega, propone, prueba y evalua cambios; tras aprobacion humana crea una rama aislada y un Draft PR sin escribir main, fusionar ni forzar push.",
    "category": "orchestration",
    "kind": "composite",
    "implementation_state": "implemented",
    "verification_state": "unverified",
    "availability_state": "available",
    "maturity": "experimental",
    "cost_compatibility": "conditional",
    "dependencies": [
        {"kind": "service", "id": "AutonomyService", "required": True},
        {"kind": "gateway", "id": "github_controlled", "required": True},
        {"kind": "verification", "id": "isolated_workspace_tests", "required": True},
        {"kind": "security", "id": "owner_scope", "required": True},
        {"kind": "approval", "id": "human_approval", "required": True},
        {"kind": "configuration", "id": "GITHUB_TOKEN", "required": True},
    ],
    "limitations": [
        "V1 solo permite AkiraGr2/akira-empresa y base main.",
        "No escribe main, no hace merge y no hace force-push.",
        "Los cambios se limitan a crear/modificar archivos de texto allowlisted y terminan en Draft PR.",
        "Una review de IA no sustituye la aprobacion humana.",
        "La verificacion de capacidad requiere una ejecucion productiva controlada; el selftest local no la marca como verified.",
    ],
    "verification_spec": {
        "method": "production_controlled_run",
        "test_key": "controlled_autonomy_v1_e2e",
        "freshness_policy": {
            "mode": "on_change",
            "max_age_seconds": None,
            "invalidate_on": [
                "build_change",
                "autonomy_schema_change",
                "github_gateway_change",
                "ownership_change",
            ],
        },
    },
    "provenance": {
        "source": "architecture_rebaseline_f14",
        "created_by": "system",
        "basis": [
            "persistence/autonomy.py",
            "autonomy_engine.py",
            "github_controlled.py",
            "test_controlled_autonomy_contract.py",
        ],
    },
}


KNOWLEDGE_PERSISTENT_CAPABILITY = {
    "name": "knowledge_persistent",
    "description": "Knowledge de primera clase persistido y verificable, separado de Memory y Learning, con provenance, estado de verificacion, versionado, ownership, privacidad y referencias controladas al Graph.",
    "category": "knowledge",
    "kind": "composite",
    "implementation_state": "implemented",
    "verification_state": "unverified",
    "availability_state": "available",
    "maturity": "experimental",
    "cost_compatibility": "free",
    "dependencies": [
        {"kind": "service", "id": "PersistenceService.save_knowledge", "required": True},
        {"kind": "service", "id": "PersistenceService.update_knowledge", "required": True},
        {"kind": "service", "id": "PersistenceService.verify_knowledge", "required": True},
        {"kind": "storage", "id": "PostgreSQL.knowledge_records", "required": True},
        {"kind": "security", "id": "owner_scope", "required": True},
        {"kind": "graph", "id": "GraphNode references", "required": True},
    ],
    "limitations": [
        "Knowledge no se materializa automaticamente desde cualquier memoria: requiere una operacion explicita y provenance.",
        "knowledge_records.related_nodes se valida contra nodos activos accesibles por owner_scope.",
        "Un knowledge verificado pierde esa verificacion cuando cambia su contenido factual y requiere nueva evidencia.",
        "La migracion 049 refuerza tambien las aristas del grafo con FKs RESTRICT; los datos historicos legacy se conservan.",
    ],
    "verification_spec": {
        "method": "selftest",
        "test_key": "knowledge_persistent_contract",
        "freshness_policy": {
            "mode": "on_change",
            "max_age_seconds": None,
            "invalidate_on": [
                "build_change",
                "dependency_change",
                "knowledge_schema_change",
                "graph_schema_change",
                "ownership_change",
            ],
        },
    },
    "provenance": {
        "source": "architecture_rebaseline_f4",
        "created_by": "system",
        "basis": [
            "persistence/core.py",
            "persistence/service.py",
            "persistence/postgres.py",
            "persistence/migrations.py",
            "test_knowledge_persistent_contract.py",
        ],
    },
}

BASE_CAPABILITIES = (SESSION_AUTH_CAPABILITY, SELF_MODEL_PERSISTENT_CAPABILITY, PERSISTENT_MEMORY_CAPABILITY, MEMORY_RECALL_CAPABILITY, LEARNING_PERSISTENT_CAPABILITY, GRAPH_PERSISTENT_CAPABILITY, KNOWLEDGE_PERSISTENT_CAPABILITY, COGNITIVE_CYCLE_PERSISTENT_CAPABILITY, EVOLUTION_ENGINE_CAPABILITY, CONTROLLED_AUTONOMY_CAPABILITY)
