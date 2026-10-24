# -*- coding: utf-8 -*-
"""
AKIRA HIVE AGENT ROUTER (267 Specialized Agents Engine)
Auto-selects and dispatches expert agent personas based on task requirements.
Zero-cost, in-memory, highly scalable.
"""
import os
import json
import re
from pathlib import Path

CATALOG_PATH = Path(__file__).parent / "data" / "hive_agents_catalog.json"

_catalog_cache = None

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
    agents from the 267 Hive catalog.
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
            "engineering": ["codig", "code", "backend", "frontend", "api", "database", "base de datos", "sql", "bug", "docker", "server", "python", "javascript", "desarroll", "arquitect"],
            "design": ["disen", "design", "ui", "ux", "pantall", "interfaz", "color", "logo", "estil", "css", "visual", "layout", "figma", "web"],
            "marketing": ["market", "seo", "trafic", "vent", "redes", "tiktok", "instagram", "contenid", "copywrit", "publicid", "growth", "audienc", "viral"],
            "product": ["product", "roadmap", "feature", "especific", "backlog", "mvp", "usuari", "feedback", "requisit"],
            "project-management": ["proyect", "scrum", "sprint", "tarea", "plazo", "organiz", "cronogram", "entreg", "agil"],
            "security": ["segurid", "secur", "vulnerab", "cifrad", "auth", "token", "jwt", "hack", "proteg", "auditor"],
            "testing": ["test", "prueb", "qa", "calidad", "valid", "verific", "unitari", "e2e"],
            "finance": ["finanz", "diner", "presupuest", "monetiz", "cost", "rentabil", "upwork", "factur", "gananc"],
            "sales": ["vent", "client", "lead", "cierre", "propuest", "bid", "upwork", "pitch", "ofert", "prospecc"],
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

    # Return top N agents
    results = []
    seen_ids = set()
    for item in scored:
        ag = item["agent"]
        if ag["id"] in seen_ids:
            continue
        seen_ids.add(ag["id"])
        
        results.append({
            "id": ag["id"],
            "name": ag["name"],
            "division": ag["division"],
            "division_label": ag["division_label"],
            "division_color": ag["division_color"],
            "emoji": ag["emoji"],
            "description": ag["description"],
            "vibe": ag["vibe"],
            "score": item["score"],
            "mission_summary": ag.get("mission_summary", ""),
            "dispatch_directive": f"Especialista convocado: {ag['name']} ({ag['division_label']}) — {ag['vibe']}"
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
