"""Registro declarativo de rutas de modelos usados por AKIRA.

No afirma disponibilidad ni cuota: describe las rutas que el runtime conoce.
La evidencia de ejecución real vive en respuestas/ciclos y en Capability Engine.
"""
from __future__ import annotations

MODEL_ROUTE_SCHEMA_VERSION = "model_route.v1"

MODEL_ROUTES = (
    {"provider": "gemini", "model": "gemini-3.8-flash", "role": "primary_chat"},
    {"provider": "gemini", "model": "gemini-flash-latest", "role": "chat_fallback_variant"},
    {"provider": "groq", "model": "openai/gpt-oss-120b", "role": "fallback"},
    {"provider": "groq", "model": "openai/gpt-oss-20b", "role": "fallback"},
    {"provider": "groq", "model": "qwen/qwen3.8-27b", "role": "fallback"},
    {"provider": "openrouter", "model": "openrouter/free", "role": "fallback_dynamic"},
    {"provider": "mistral", "model": "mistral-small-latest", "role": "fallback"},
    {"provider": "gemini", "model": "gemini-embedding-2", "role": "memory_embedding"},
)


def model_registry_snapshot():
    return {
        "schema_version": MODEL_ROUTE_SCHEMA_VERSION,
        "routes": [dict(route) for route in MODEL_ROUTES],
    }

PRIMARY_CHAT_MODEL = "gemini-3.8-flash"
GEMINI_CHAT_FALLBACK_VARIANT = "gemini-flash-latest"
GROQ_FALLBACK_MODELS = ("openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b")
OPENROUTER_MODEL_ROUTE = "openrouter/free"
MISTRAL_MODEL_ROUTE = "mistral-small-latest"
MEMORY_EMBEDDING_MODEL = "gemini-embedding-2"
