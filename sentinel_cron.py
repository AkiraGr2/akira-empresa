"""
Sentinel Cron & Proactive Intelligence Monitor (Improvement 7)
==============================================================
Autonomous proactive surveillance engine for Akira.
Sweeps technical radars, RSS/Atom feeds, and high-value opportunities (e.g. Upwork, Python, AI).

Features:
- Persistent zero-cost deduplication registry (data/sentinel_seen.json).
- Multi-channel radar: Web queries and XML/RSS feeds.
- Automatic dispatch to Telegram channel / Director Jhon Grimm on discovery.
- Resilient to network outages, zero unhandled exceptions.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger("akira.sentinel")

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SEEN_REGISTRY_PATH = os.path.join(DATA_DIR, "sentinel_seen.json")
MAX_SEEN_CACHE = 2500

DEFAULT_RADAR_TOPICS = [
    "Python 3.13 release novedades",
    "FastAPI security advisory",
    "OpenAI Anthropic Google Gemini updates",
]


def _ensure_data_dir() -> None:
    """Ensures the data directory exists."""
    if not os.path.exists(DATA_DIR):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
        except Exception as exc:
            logger.warning("No se pudo crear data dir: %s", exc)


def load_seen_registry(path: str = SEEN_REGISTRY_PATH) -> Set[str]:
    """Loads the set of previously seen item hashes/IDs."""
    _ensure_data_dir()
    if not os.path.exists(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return set(data)
            elif isinstance(data, dict):
                return set(data.get("seen_ids", []))
    except Exception as exc:
        logger.warning("Error leyendo sentinel seen registry: %s", exc)
    return set()


def save_seen_registry(seen_ids: Set[str], path: str = SEEN_REGISTRY_PATH) -> None:
    """Saves the seen IDs, keeping only the most recent MAX_SEEN_CACHE elements."""
    _ensure_data_dir()
    try:
        ids_list = list(seen_ids)[-MAX_SEEN_CACHE:]
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"seen_ids": ids_list, "updated_at": datetime.datetime.now().isoformat()}, f, indent=2)
    except Exception as exc:
        logger.warning("Error guardando sentinel seen registry: %s", exc)


def compute_item_id(title: str, link: str = "") -> str:
    """Generates a unique deterministic ID for an intelligence item."""
    basis = f"{title.strip().lower()}|{link.strip().lower()}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


def format_sentinel_briefing(new_items: List[Dict[str, Any]]) -> str:
    """Formats new items into a sleek, executive Markdown briefing for Director Jhon Grimm."""
    if not new_items:
        return "🛡️ **CENTINELA AKIRA**: Sin novedades críticas en el radar actual."

    lines = [
        "🛡️ **ALERTA DE INTELIGENCIA PROACTIVA | CENTINELA AKIRA**",
        f"📅 *{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        f"Se han interceptado **{len(new_items)}** hallazgos nuevos en el radar:\n",
    ]

    for idx, item in enumerate(new_items, 1):
        title = item.get("title", "Sin título")
        link = item.get("link", "")
        source = item.get("source", "Radar")
        snippet = item.get("snippet", "")
        if len(snippet) > 180:
            snippet = snippet[:177] + "..."

        lines.append(f"**{idx}. [{source}] {title}**")
        if snippet:
            lines.append(f"> {snippet}")
        if link and link.startswith("http"):
            lines.append(f"🔗 [Acceder al recurso]({link})")
        lines.append("")

    lines.append("💼 *Directiva J.A.R.V.I.S. activa: Monitoreo continuo sin costo.*")
    return "\n".join(lines)


def run_sentinel_sweep(
    topics: Optional[List[str]] = None,
    feed_urls: Optional[List[str]] = None,
    send_telegram: bool = False,
    chat_id: Optional[str] = None,
    search_fn: Optional[Callable[[str, int], List[Dict[str, Any]]]] = None,
    fetch_fn: Optional[Callable[[str], Dict[str, Any]]] = None,
    registry_path: str = SEEN_REGISTRY_PATH,
) -> Dict[str, Any]:
    """
    Executes a comprehensive intelligence sweep across web search topics and RSS feeds.
    Deduplicates against sentinel_seen.json and optionally dispatches via Telegram.
    """
    active_topics = topics if topics is not None else DEFAULT_RADAR_TOPICS
    active_feeds = feed_urls or []

    seen_ids = load_seen_registry(registry_path)
    new_items: List[Dict[str, Any]] = []
    total_scanned = 0

    # 1. Sweep Web Topics
    if active_topics:
        if search_fn is None:
            try:
                from web_engine import search_duckduckgo_html
                search_fn = search_duckduckgo_html
            except Exception as exc:
                logger.warning("Web search engine no disponible para Sentinel: %s", exc)
                search_fn = lambda q, n: []

        for topic in active_topics:
            try:
                results = search_fn(topic, 3)
                for res in results:
                    total_scanned += 1
                    t = res.get("title", "")
                    l = res.get("link", "")
                    s = res.get("snippet", "")
                    if not t:
                        continue
                    item_id = compute_item_id(t, l)
                    if item_id not in seen_ids:
                        seen_ids.add(item_id)
                        new_items.append({
                            "id": item_id,
                            "title": t,
                            "link": l,
                            "snippet": s,
                            "source": f"Web Radar ({topic})",
                        })
            except Exception as exc:
                logger.warning("Error en topic sweep '%s': %s", topic, exc)

    # 2. Sweep RSS/Atom Feeds
    if active_feeds:
        if fetch_fn is None:
            try:
                from web_engine import fetch_url
                fetch_fn = fetch_url
            except Exception as exc:
                logger.warning("Fetch engine no disponible para RSS: %s", exc)
                fetch_fn = lambda u: {"status": "error"}

        try:
            from web_extractor import extract_rss_atom_feed
        except Exception:
            extract_rss_atom_feed = lambda x: {"ok": False}

        for feed_url in active_feeds:
            try:
                fetch_res = fetch_fn(feed_url)
                if fetch_res.get("status") == "success" and fetch_res.get("content"):
                    parsed_feed = extract_rss_atom_feed(fetch_res["content"])
                    entries = parsed_feed.get("items", []) if isinstance(parsed_feed, dict) else (parsed_feed if isinstance(parsed_feed, list) else [])
                    for entry in entries:
                        total_scanned += 1
                        t = entry.get("title", "")
                        l = entry.get("link", "")
                        s = entry.get("description", entry.get("summary", ""))
                        if not t:
                            continue
                        item_id = compute_item_id(t, l)
                        if item_id not in seen_ids:
                            seen_ids.add(item_id)
                            new_items.append({
                                "id": item_id,
                                "title": t,
                                "link": l,
                                "snippet": s,
                                "source": f"RSS Feed",
                            })
            except Exception as exc:
                logger.warning("Error en feed sweep '%s': %s", feed_url, exc)

    # Save updated seen registry
    save_seen_registry(seen_ids, registry_path)

    # Format brief
    briefing_md = format_sentinel_briefing(new_items)
    telegram_dispatched = False

    # 3. Optional Telegram Notification
    if send_telegram and new_items:
        try:
            import telegram_service
            target_chat = chat_id or telegram_service.get_last_chat_id()
            if target_chat:
                t_res = telegram_service.send_telegram_message(str(target_chat), briefing_md)
                telegram_dispatched = t_res.get("status") == "success"
            else:
                logger.info("Telegram notification solicitada pero no hay chat_id registrado.")
        except Exception as exc:
            logger.warning("Fallo al enviar notificación de Centinela por Telegram: %s", exc)

    return {
        "status": "success" if new_items else "no_new_items",
        "timestamp": datetime.datetime.now().isoformat(),
        "total_scanned": total_scanned,
        "new_items_count": len(new_items),
        "new_items": new_items,
        "sent_to_telegram": telegram_dispatched,
        "executive_summary": briefing_md,
    }
