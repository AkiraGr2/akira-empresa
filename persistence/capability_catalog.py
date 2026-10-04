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

BASE_CAPABILITIES = (SESSION_AUTH_CAPABILITY, PERSISTENT_MEMORY_CAPABILITY, MEMORY_RECALL_CAPABILITY)
