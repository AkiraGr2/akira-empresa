"""
AKIRA STRUCTURED WEB EXTRACTOR v1.0
Zero-Cost ($0.00 COP/USD) Multiformat Extractor for HTML Tables, JSON-LD Schemas & RSS/Atom Feeds.
Extracts structured machine-readable knowledge directly from web markup.
"""

import re
import html
import json
import xml.etree.ElementTree as ET
from typing import Dict, Any, List

def extract_tables_from_html(html_str: str) -> List[Dict[str, Any]]:
    """
    Detecta y extrae todas las tablas HTML presentes en el texto y las convierte
    en tablas Markdown legibles y listas de registros estructurados.
    """
    if not html_str or "<table" not in html_str.lower():
        return []

    tables_found = []
    table_pattern = re.compile(r"<table[^>]*>(.*?)</table>", re.DOTALL | re.IGNORECASE)
    row_pattern = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
    cell_pattern = re.compile(r"<(th|td)[^>]*>(.*?)</\1>", re.DOTALL | re.IGNORECASE)

    for t_idx, t_match in enumerate(table_pattern.finditer(html_str), 1):
        table_html = t_match.group(1)
        rows_data = []
        headers = []

        for r_match in row_pattern.finditer(table_html):
            row_html = r_match.group(1)
            cells = []
            is_header_row = "<th" in row_html.lower()

            for c_match in cell_pattern.finditer(row_html):
                cell_text = re.sub(r"<[^>]+>", "", c_match.group(2)).strip()
                cell_text = html.unescape(cell_text)
                cell_text = re.sub(r"\s+", " ", cell_text)
                cells.append(cell_text)

            if cells:
                if is_header_row and not headers:
                    headers = cells
                else:
                    rows_data.append(cells)

        if not headers and rows_data:
            headers = [f"Columna_{i+1}" for i in range(len(rows_data[0]))]

        # Construir representación Markdown
        md_lines = []
        if headers:
            md_lines.append("| " + " | ".join(headers) + " |")
            md_lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in rows_data[:50]:  # Acotar a 50 filas máx
            # Rellenar columnas faltantes si la fila es más corta
            padded = row + [""] * max(0, len(headers) - len(row))
            md_lines.append("| " + " | ".join(padded[:len(headers)]) + " |")

        tables_found.append({
            "table_index": t_idx,
            "headers": headers,
            "rows_count": len(rows_data),
            "rows": rows_data[:30],
            "markdown": "\n".join(md_lines)
        })

    return tables_found

def extract_json_ld_schemas(html_str: str) -> List[Dict[str, Any]]:
    """
    Extrae esquemas JSON-LD embebidos (<script type="application/ld+json">)
    tales como TechArticle, Product, Organization, FAQPage, etc.
    """
    if not html_str or "ld+json" not in html_str.lower():
        return []

    pattern = re.compile(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.DOTALL | re.IGNORECASE)
    schemas = []

    for match in pattern.finditer(html_str):
        raw_json = match.group(1).strip()
        try:
            parsed = json.loads(raw_json)
            if isinstance(parsed, list):
                schemas.extend(parsed)
            elif isinstance(parsed, dict):
                schemas.append(parsed)
        except Exception:
            continue

    return schemas

def extract_rss_atom_feed(xml_str: str, max_items: int = 10) -> Dict[str, Any]:
    """
    Parsea feeds de noticias y actualizaciones en formato RSS 2.0 o Atom.
    """
    clean_xml = xml_str.strip()
    if not clean_xml:
        return {"ok": False, "error": "Contenido XML vacío"}

    items = []
    feed_title = "Feed Desconocido"

    try:
        # Remover declaraciones xml o tags que puedan confundir al parser
        root = ET.fromstring(clean_xml)
        
        # Caso RSS: <rss><channel><item>
        channel = root.find("channel")
        if channel is not None:
            t_elem = channel.find("title")
            if t_elem is not None and t_elem.text:
                feed_title = t_elem.text.strip()
            for it in channel.findall("item")[:max_items]:
                item_dict = {
                    "title": (it.findtext("title") or "Sin título").strip(),
                    "link": (it.findtext("link") or "").strip(),
                    "description": re.sub(r"<[^>]+>", "", it.findtext("description") or "").strip()[:400],
                    "pub_date": (it.findtext("pubDate") or "").strip()
                }
                items.append(item_dict)
            return {"ok": True, "type": "rss_2.0", "feed_title": feed_title, "items_count": len(items), "items": items}

        # Caso Atom: <feed xmlns="..."><entry>
        # Ignorar namespaces para parseo resiliente
        for elem in root.iter():
            if elem.tag.endswith("title") and feed_title == "Feed Desconocido" and elem.text:
                feed_title = elem.text.strip()
            if elem.tag.endswith("entry") and len(items) < max_items:
                title = ""
                link = ""
                summary = ""
                updated = ""
                for child in elem:
                    if child.tag.endswith("title"):
                        title = (child.text or "").strip()
                    elif child.tag.endswith("link"):
                        link = child.attrib.get("href", "").strip() or (child.text or "").strip()
                    elif child.tag.endswith("summary") or child.tag.endswith("content"):
                        summary = re.sub(r"<[^>]+>", "", child.text or "").strip()[:400]
                    elif child.tag.endswith("updated") or child.tag.endswith("published"):
                        updated = (child.text or "").strip()
                if title:
                    items.append({"title": title, "link": link, "description": summary, "pub_date": updated})

        if items:
            return {"ok": True, "type": "atom", "feed_title": feed_title, "items_count": len(items), "items": items}
    except Exception as e:
        return {"ok": False, "error": f"Error parseando feed: {str(e)}"}

    return {"ok": False, "error": "No se detectó estructura válida de RSS o Atom"}

def extract_structured_web(content: str) -> Dict[str, Any]:
    """
    Punto de entrada unificado que extrae tablas, esquemas JSON-LD y feeds de cualquier contenido web.
    """
    tables = extract_tables_from_html(content)
    schemas = extract_json_ld_schemas(content)
    feed_res = extract_rss_atom_feed(content) if ("<rss" in content.lower() or "<feed" in content.lower()) else {"ok": False}

    return {
        "ok": True,
        "tables_count": len(tables),
        "tables": tables,
        "schemas_count": len(schemas),
        "schemas": schemas,
        "feed": feed_res if feed_res.get("ok") else None
    }

# Alias for backwards compatibility
extract_rss_or_atom = extract_rss_atom_feed

