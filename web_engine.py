"""
AKIRA LIVE WEB ENGINE v1.0
Zero-Cost ($0.00 COP/USD) Real-Time Web Search & Deep URL Content Extractor.
Connects Akira to live internet data without third-party paid API keys.
"""

import urllib.request
import urllib.parse
import re
import html
import datetime
import json
import logging

logger = logging.getLogger("akira.web_engine")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def search_duckduckgo_html(query: str, max_results: int = 5) -> list[dict]:
    """Realiza una búsqueda web en vivo usando DuckDuckGo HTML sin claves de API."""
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote_plus(query)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        logger.warning(f"DuckDuckGo search error: {e}")
        return []

    snippets = re.findall(r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', content, re.DOTALL)
    titles_links = re.findall(r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', content, re.DOTALL)

    results = []
    limit = min(len(titles_links), max(len(snippets), 1))
    
    for i in range(min(limit, max_results * 2)):
        link = titles_links[i][0]
        # Skip internal ad trackers if possible
        if "y.js?ad_domain" in link:
            continue
        if "uddg=" in link:
            m = re.search(r'uddg=([^&]+)', link)
            if m:
                link = urllib.parse.unquote(m.group(1))

        title = re.sub(r'<[^>]+>', '', titles_links[i][1]).strip()
        title = html.unescape(title)
        
        snip = ""
        if i < len(snippets):
            snip = re.sub(r'<[^>]+>', '', snippets[i]).strip()
            snip = html.unescape(snip)

        if title and link:
            results.append({
                "title": title,
                "link": link,
                "snippet": snip
            })
        if len(results) >= max_results:
            break

    return results

def search_wikipedia(query: str, max_results: int = 3) -> list[dict]:
    """Proveedor de respaldo en vivo vía API abierta de Wikipedia."""
    url = f"https://es.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote_plus(query)}&limit={max_results}&namespace=0&format=json"
    headers = {"User-Agent": "AkiraAssistant/2.0 (contact@akira.local)"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            results = []
            if len(data) >= 4:
                titles = data[1]
                snippets = data[2]
                links = data[3]
                for i in range(len(titles)):
                    results.append({
                        "title": titles[i],
                        "link": links[i],
                        "snippet": snippets[i] or f"Artículo enciclopédico sobre {titles[i]} en Wikipedia."
                    })
            return results
    except Exception as e:
        logger.warning(f"Wikipedia search error: {e}")
        return []

def search_web(query: str, max_results: int = 5) -> dict:
    """
    Punto de entrada unificado para búsqueda en tiempo real.
    Prueba primero DuckDuckGo HTML y si falla o no hay resultados, usa Wikipedia.
    """
    clean_query = query.strip()
    if not clean_query:
        return {
            "ok": False,
            "error": "Consulta de búsqueda vacía.",
            "results": [],
            "count": 0
        }

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    # Intento 1: DuckDuckGo HTML
    results = search_duckduckgo_html(clean_query, max_results=max_results)
    provider = "duckduckgo_live"

    # Intento 2: Respaldo Wikipedia
    if not results:
        results = search_wikipedia(clean_query, max_results=max_results)
        provider = "wikipedia_live"

    return {
        "ok": True,
        "query": clean_query,
        "provider": provider,
        "results": results,
        "count": len(results),
        "timestamp": now_iso
    }

def fetch_url(url: str, max_chars: int = 4000) -> dict:
    """
    Extrae y limpia el texto legible de cualquier página web externa en vivo.
    Remueve scripts, estilos, navegaciones y elementos no informativos.
    """
    clean_url = url.strip()
    if not clean_url.startswith(("http://", "https://")):
        return {
            "ok": False,
            "error": "URL inválida. Debe comenzar con http:// o https://",
            "url": clean_url
        }

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
    }
    req = urllib.request.Request(clean_url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=9) as resp:
            raw_html = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return {
            "ok": False,
            "error": f"No se pudo acceder a la URL: {str(e)}",
            "url": clean_url,
            "timestamp": now_iso
        }

    # Extraer título
    title_m = re.search(r'<title[^>]*>(.*?)</title>', raw_html, re.I | re.DOTALL)
    title = html.unescape(title_m.group(1)).strip() if title_m else "Sin título"

    # Limpiar elementos no legibles
    cleaned = re.sub(r'<(script|style|svg|nav|footer|header|noscript|aside)[^>]*>.*?</\1>', ' ', raw_html, flags=re.I | re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', cleaned)
    text = html.unescape(text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n\n', text).strip()

    truncated = text[:max_chars]
    if len(text) > max_chars:
        truncated += "\n\n[... Contenido truncado para optimización de contexto ...]"

    return {
        "ok": True,
        "url": clean_url,
        "title": title,
        "content": truncated,
        "char_count": len(text),
        "timestamp": now_iso
    }

def augment_prompt_with_web(query: str, max_results: int = 3) -> str:
    """Genera un bloque de contexto web enriquecido para inyectar en la conversación."""
    search_data = search_web(query, max_results=max_results)
    results = search_data.get("results", [])
    if not results:
        return ""

    context_lines = [
        "--- DATOS EN VIVO DE INTERNET (CONSULTA EN TIEMPO REAL) ---",
        f"Consulta: '{query}' | Fecha: {search_data.get('timestamp')}",
        ""
    ]
    for idx, r in enumerate(results, 1):
        context_lines.append(f"{idx}. {r['title']}")
        context_lines.append(f"   Fuente: {r['link']}")
        if r['snippet']:
            context_lines.append(f"   Resumen: {r['snippet']}")
        context_lines.append("")
    context_lines.append("--- FIN DATOS EN VIVO ---")
    return "\n".join(context_lines)
