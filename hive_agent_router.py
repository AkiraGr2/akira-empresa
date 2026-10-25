# -*- coding: utf-8 -*-
"""
AKIRA HIVE AGENT ROUTER (267 Specialized Agents & Division Commanders Engine)
Orchestrates the 8 Core Division Commanders and 267 Specialized Hive Agents.
Zero-cost, in-memory, highly scalable.
"""
import os
import json
import re
from pathlib import Path

CATALOG_PATH = Path(__file__).parent / "data" / "hive_agents_catalog.json"

_catalog_cache = None

# ==============================================================================
# COMMANDER HIERARCHY (Comandantes de División de AKIRA)
# ==============================================================================
COMMANDERS = {
    "luna": {
        "id": "commander-luna",
        "name": "Luna",
        "title": "Comandante de Operaciones & Misiones Autónomas",
        "avatar": "🌙",
        "role": "operations_commander",
        "color": "#00f2fe",
        "divisions": ["project-management", "specialized"],
        "description": "Supervisa la orquestación global de misiones, asignación de recursos y cumplimiento de objetivos de punta a punta.",
        "directive": "Garantizar ejecución impecable, seguimiento de cronogramas y resolución proactiva de bloqueos."
    },
    "nexo": {
        "id": "commander-nexo",
        "name": "Nexo",
        "title": "Comandante de Integración, Negocios & Upwork Bidding",
        "avatar": "💼",
        "role": "business_commander",
        "color": "#10b981",
        "divisions": ["sales", "finance", "support"],
        "description": "Lidera la monetización, generación de propuestas ganadoras en Upwork, análisis financiero y soporte al cliente.",
        "directive": "Maximizar tasa de conversión en licitaciones de Upwork, optimizar márgenes y conectar valor real para clientes."
    },
    "atlas": {
        "id": "commander-atlas",
        "name": "Atlas",
        "title": "Comandante de Ingeniería & Desarrollo de Software",
        "avatar": "⚡",
        "role": "engineering_commander",
        "color": "#3b82f6",
        "divisions": ["engineering", "game-development", "spatial-computing"],
        "description": "Comanda a 88 especialistas en backend, frontend, devops, computación espacial y arquitectura cloud.",
        "directive": "Código de producción robusto, arquitectura desacoplada, alta concurrencia y cero deuda técnica."
    },
    "aura": {
        "id": "commander-aura",
        "name": "Aura",
        "title": "Comandante de Crecimiento & Marketing Digital",
        "avatar": "🔥",
        "role": "growth_commander",
        "color": "#f97316",
        "divisions": ["marketing", "paid-media"],
        "description": "Dirige las estrategias de adquisición de tráfico, copywriting persuasivo, SEO y campañas de conversión.",
        "directive": "Captar atención de alto impacto, diseñar mensajes que conviertan y construir presencia de marca sólida."
    },
    "vigil": {
        "id": "commander-vigil",
        "name": "Vigil",
        "title": "Comandante de Ciberseguridad & Resiliencia",
        "avatar": "🛡️",
        "role": "security_commander",
        "color": "#ef4444",
        "divisions": ["security"],
        "description": "Protege la integridad del sistema, audita vulnerabilidades, controla accesos y blinda criptográficamente la colmena.",
        "directive": "Defensa en profundidad, auditoría continua de endpoints y protección estricta de datos del propietario."
    },
    "cronos": {
        "id": "commander-cronos",
        "name": "Cronos",
        "title": "Comandante de Estrategia & Producto",
        "avatar": "🧭",
        "role": "product_commander",
        "color": "#d946ef",
        "divisions": ["product", "gis"],
        "description": "Estructura el roadmap de producto, priorización de funcionalidades, geolocalización y visión a largo plazo.",
        "directive": "Alinear cada desarrollo con las necesidades reales del usuario y garantizar un flujo de valor continuo."
    },
    "argos": {
        "id": "commander-argos",
        "name": "Argos",
        "title": "Comandante de Calidad, Testing & QA de Misión Crítica",
        "avatar": "👁️",
        "role": "qa_commander",
        "color": "#f59e0b",
        "divisions": ["testing", "academic"],
        "description": "Supervisa pruebas automatizadas, consistencia científica, validación de regresión y verificación de contratos.",
        "directive": "Cero bugs en producción, validación de tolerancias y evidencia verificable antes de cada despliegue."
    },
    "akira": {
        "id": "commander-akira-core",
        "name": "Akira Core",
        "title": "Comandante Suprema de la Colmena",
        "avatar": "👑",
        "role": "supreme_orchestrator",
        "color": "#a855f7",
        "divisions": ["all"],
        "description": "Núcleo cognitivo unificado que sintetiza el autoconocimiento de todos los comandantes y 267 especialistas.",
        "directive": "Servir a Jhon Grimm con máxima lealtad, autoconocimiento preciso y ejecución estratégica total."
    }
}

# Division to Commander Mapping
DIVISION_TO_COMMANDER = {
    "project-management": "luna",
    "specialized": "luna",
    "sales": "nexo",
    "finance": "nexo",
    "support": "nexo",
    "engineering": "atlas",
    "game-development": "atlas",
    "spatial-computing": "atlas",
    "marketing": "aura",
    "paid-media": "aura",
    "design": "aura",
    "security": "vigil",
    "product": "cronos",
    "gis": "cronos",
    "testing": "argos",
    "academic": "argos",
    "research": "argos",
    "healthcare": "argos"
}

def get_commander_for_division(division: str) -> dict:
    comm_key = DIVISION_TO_COMMANDER.get(division, "akira")
    return COMMANDERS.get(comm_key, COMMANDERS["akira"])

def get_commanders_catalog() -> dict:
    return COMMANDERS

def get_hive_catalog():
    global _catalog_cache
    if _catalog_cache is not None:
        return _catalog_cache
    
    if CATALOG_PATH.exists():
        try:
            with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                _catalog_cache = json.load(f)
                return _catalog_cache
        except Exception as e:
            print(f"[HiveRouter] Error loading catalog: {e}")
    
    return {"total_agents": 0, "divisions": {}, "agents": []}

def normalize_text(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[áàäâ]", "a", text)
    text = re.sub(r"[éèëê]", "e", text)
    text = re.sub(r"[íìïî]", "i", text)
    text = re.sub(r"[óòöô]", "o", text)
    text = re.sub(r"[úùüû]", "u", text)
    text = re.sub(r"[ñ]", "n", text)
    return text

def auto_select_agents(task: str, limit: int = 3, division_filter: str = None) -> list:
    """
    Intelligently inspects the user task/objective and matches the best specialist
    agents from the 267 Hive catalog, linking each to its respective Division Commander.
    """
    catalog = get_hive_catalog()
    agents = catalog.get("agents", [])
    if not agents or not task:
        return []

    norm_task = normalize_text(task)
    words = set(re.findall(r"\b\w{3,}\b", norm_task))

    scored = []
    for agent in agents:
        div = agent.get("division", "")
        if division_filter and div != division_filter:
            continue

        score = 0
        agent_name_norm = normalize_text(agent.get("name", ""))
        agent_desc_norm = normalize_text(agent.get("description", ""))
        agent_vibe_norm = normalize_text(agent.get("vibe", ""))
        keywords = [normalize_text(k) for k in agent.get("keywords", [])]

        # Name match
        for w in words:
            if w in agent_name_norm or agent_name_norm in w:
                score += 20
            elif any(w.startswith(k[:4]) or k.startswith(w[:4]) for k in keywords if len(k) >= 4):
                score += 10
            elif w in agent_desc_norm:
                score += 4
            elif w in agent_vibe_norm:
                score += 3

        # Direct phrase boosts
        if agent_name_norm in norm_task:
            score += 40

        # Substring keyword checks
        for k in keywords:
            if len(k) >= 4 and k in norm_task:
                score += 8

        # Division level affinity boosts
        div_triggers = {
            "engineering": ["codig", "code", "backend", "frontend", "api", "database", "base de datos", "sql", "bug", "docker", "server", "python", "javascript", "react", "desarroll", "arquitect", "fullstack", "mobile", "app"],
            "design": ["disen", "design", "ui", "ux", "pantall", "interfaz", "color", "logo", "estil", "css", "visual", "layout", "figma", "web"],
            "marketing": ["market", "seo", "trafic", "vent", "redes", "tiktok", "instagram", "contenid", "copywrit", "publicid", "growth", "audienc", "viral", "copy"],
            "product": ["product", "roadmap", "feature", "especific", "backlog", "mvp", "usuari", "feedback", "requisit"],
            "project-management": ["proyect", "scrum", "sprint", "tarea", "plazo", "organiz", "cronogram", "entreg", "agil", "coordin"],
            "security": ["segurid", "secur", "vulnerab", "cifrad", "auth", "token", "jwt", "hack", "proteg", "auditor", "pentest"],
            "testing": ["test", "prueb", "qa", "calidad", "valid", "verific", "unitari", "e2e", "cobertur"],
            "finance": ["finanz", "diner", "presupuest", "monetiz", "cost", "rentabil", "upwork", "factur", "gananc", "invers"],
            "sales": ["vent", "client", "lead", "cierre", "propuest", "bid", "upwork", "pitch", "ofert", "prospecc", "freelance"],
            "support": ["soport", "atencion", "ticket", "ayud", "operacion", "usuario"],
            "research": ["investig", "research", "paper", "estudi", "analis", "tendenc", "benchmark"],
            "spatial-computing": ["3d", "vr", "ar", "xr", "three", "espacial", "inmersiv", "metavers"],
            "game-development": ["jueg", "game", "unity", "gameplay", "motor"],
            "gis": ["mapa", "coordenad", "gps", "geolocaliz", "ruta", "google map"]
        }

        triggers = div_triggers.get(div, [])
        for trig in triggers:
            if trig in norm_task:
                score += 8

        if score > 0:
            scored.append({
                "agent": agent,
                "score": score
            })

    scored.sort(key=lambda x: x["score"], reverse=True)

    # Return top N agents with Commander linkage
    results = []
    seen_ids = set()
    for item in scored:
        ag = item["agent"]
        if ag["id"] in seen_ids:
            continue
        seen_ids.add(ag["id"])
        
        div = ag.get("division", "")
        commander = get_commander_for_division(div)
        
        results.append({
            "id": ag["id"],
            "name": ag["name"],
            "division": div,
            "division_label": ag.get("division_label", div.title()),
            "division_color": ag.get("division_color", "#00f2fe"),
            "emoji": ag.get("emoji", "🤖"),
            "description": ag.get("description", ""),
            "vibe": ag.get("vibe", ""),
            "score": item["score"],
            "commander": {
                "name": commander["name"],
                "title": commander["title"],
                "avatar": commander["avatar"]
            },
            "dispatch_directive": f"Comandante {commander['name']} convoca al Especialista {ag['name']} ({ag.get('division_label', div)}) — {ag.get('vibe', '')}"
        })
        if len(results) >= limit:
            break

    return results

def get_agent_by_id(agent_id: str) -> dict:
    catalog = get_hive_catalog()
    for ag in catalog.get("agents", []):
        if ag["id"] == agent_id:
            return ag
    return None
