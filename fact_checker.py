"""
AKIRA FACT-CHECKER & MULTI-SOURCE TRIANGULATOR v1.0
Zero-Cost ($0.00 COP/USD) Anti-Hallucination & Cross-Verification Gate.

Prevents false consensus and hallucinations by validating technical claims
and assertions across multiple independent web domains before consolidation.
"""

import urllib.parse
import re
from typing import Dict, Any, List

import web_engine

def _extract_domain(url: str) -> str:
    """Extrae el dominio base para asegurar fuentes independientes."""
    try:
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return url

def _extract_keywords(text: str) -> set:
    """Extrae tokens significativos descartando palabras vacías comunes."""
    stopwords = {
        "de", "la", "el", "en", "y", "a", "los", "se", "del", "las", "un", "por", "con", "no", "una",
        "su", "para", "es", "al", "lo", "como", "mas", "más", "pero", "sus", "le", "ya", "o", "fue",
        "este", "ha", "si", "sí", "porque", "esta", "son", "entre", "cuando", "muy", "sin", "sobre",
        "the", "and", "is", "in", "to", "of", "a", "with", "for", "as", "on", "that", "it", "at", "by"
    }
    words = re.findall(r"\b[a-záéíóúñA-Z0-9_\-\.]{3,}\b", text.lower())
    return {w for w in words if w not in stopwords}

def triangulate_claim(claim: str, max_sources: int = 3, sources=None) -> Dict[str, Any]:
    """
    Triangula una afirmación o concepto técnico cruzando evidencias de múltiples
    dominios web independientes. Retorna veredicto, puntaje de consenso y fuentes.
    """
    clean_claim = claim.strip()
    if not clean_claim:
        return {"ok": False, "error": "Afirmación vacía para verificar"}

    claim_keywords = _extract_keywords(clean_claim)
    if not claim_keywords:
        return {"ok": False, "error": "La afirmación no contiene palabras clave suficientes"}

    # 1. Búsqueda en vivo de evidencia
    max_sources = max(1, min(int(max_sources), 10))
    if sources is not None:
        if not isinstance(sources, list) or any(not isinstance(s, (str, dict)) for s in sources):
            return {"ok": False, "error": "sources debe ser una lista de URLs o referencias"}
        raw_results = [{"link": s} if isinstance(s, str) else
                       {**s, "link": s.get("link") or s.get("url") or ""} for s in sources[:10]]
        if any(not str(s['link']).startswith(('https://', 'http://')) for s in raw_results):
            return {"ok": False, "error": "sources requiere URLs HTTP o HTTPS"}
    else:
        search_data = web_engine.search_web(clean_claim, max_results=max_sources * 2)
        raw_results = search_data.get("results", [])

    if not raw_results:
        return {
            "ok": True,
            "claim": clean_claim,
            "verified": False,
            "consensus_score": 0.0,
            "verdict": "EVIDENCIA_NO_ENCONTRADA",
            "sources_count": 0,
            "sources": [],
            "consensus_summary": "No se encontraron fuentes web públicas que mencionen este término.",
            "discrepancies": []
        }

    # 2. Filtrar fuentes por dominios únicos independientes
    seen_domains = set()
    independent_sources: List[Dict[str, Any]] = []

    for r in raw_results:
        link = r.get("link", "")
        domain = _extract_domain(link)
        if domain and domain not in seen_domains:
            seen_domains.add(domain)
            independent_sources.append(r)
        if len(independent_sources) >= max_sources:
            break

    # 3. Analizar concordancia semántica por fuente
    supporting_sources = []
    discrepancies = []

    # Raíces de advertencia y contradicción (desmentido, obsoleto/a, deprecado/a, incompatible)
    contradiction_stems = [
        "desmentid", "fals", "deprecad", "obsolet", "incompatibl",
        "no soporta", "no es compatible", "deprecated", "unsupported", "vulnerable"
    ]

    for src in independent_sources:
        title = src.get("title", "")
        snip = src.get("snippet", "")
        combined_text = f"{title} {snip}".lower()
        src_keywords = _extract_keywords(combined_text)

        overlap = claim_keywords.intersection(src_keywords)
        overlap_ratio = len(overlap) / max(1, len(claim_keywords))

        has_contradiction = any(stem in combined_text for stem in contradiction_stems)

        if has_contradiction:
            discrepancies.append(f"Advertencia en {src.get('link')}: '{snip[:120]}...'")

        if overlap_ratio >= 0.30 and not has_contradiction:
            supporting_sources.append({
                "domain": _extract_domain(src.get("link", "")),
                "title": title,
                "link": src.get("link"),
                "overlap_ratio": round(overlap_ratio, 2)
            })

    total_sources = max(1, len(independent_sources))
    consensus_score = len(supporting_sources) / total_sources

    if discrepancies:
        consensus_score = max(0.0, consensus_score - 0.25)

    is_verified = consensus_score >= 0.50 and len(supporting_sources) >= 1

    if is_verified:
        verdict = "VERIFICADO"
        summary = f"Afirmación respaldada por {len(supporting_sources)} fuentes independientes con alta coherencia."
    elif discrepancies:
        verdict = "CONTRADICTORIO_O_ADVERTENCIA"
        summary = "Se detectaron posibles discrepancias, advertencias de compatibilidad o desmentidos en las fuentes."
    else:
        verdict = "EVIDENCIA_DIVERGENTE"
        summary = "Las fuentes encontradas no aportan evidencia concluyente para corroborar la afirmación."

    return {
        "ok": True,
        "claim": clean_claim,
        "verified": is_verified,
        "consensus_score": round(consensus_score, 2),
        "verdict": verdict,
        "sources_count": len(independent_sources),
        "sources": independent_sources,
        "supporting_sources": supporting_sources,
        "consensus_summary": summary,
        "discrepancies": discrepancies
    }
