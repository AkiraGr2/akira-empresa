"""
Executive Dossier PDF Generator (Improvement 8)
===============================================
Compiles deep research findings, fact triangulations, and security audits into
formal, executive-ready PDF dossiers (1-click compilation and optional Telegram delivery).

Features:
- Pure Python PDF-1.4 compilation ($0.00 COP / USD zero external dependency constraint).
- SHA-256 cryptographic verification fingerprint for executive auditing.
- Automated local persistence in data/dossiers/.
- Seamless 1-click dispatch to Director Jhon Grimm via Telegram documents.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Union

from pdf_service import create_executive_pdf

logger = logging.getLogger("akira.dossier")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOSSIERS_DIR = os.path.join(BASE_DIR, "data", "dossiers")


def _ensure_dossiers_dir(target_dir: str = DOSSIERS_DIR) -> None:
    """Ensures the destination directory exists."""
    if not os.path.exists(target_dir):
        try:
            os.makedirs(target_dir, exist_ok=True)
        except Exception as exc:
            logger.warning("No se pudo crear carpeta de dossiers: %s", exc)


def build_dossier_text(
    title: str,
    sections: Union[str, Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Constructs an executive text layout from a dict of sections or returns raw formatted string.
    """
    if isinstance(sections, str):
        return sections

    lines = [
        f"INFORME ESTRATÉGICO EJECUTIVO: {title.upper()}",
        "============================================================",
        f"FECHA DE EMISIÓN: {datetime.datetime.now().strftime('%d de %B de %Y - %H:%M:%S')}",
        "CERTIFICACIÓN: Directiva J.A.R.V.I.S. | Costo Operativo: $0.00 COP",
        "",
    ]

    for sec_title, sec_content in sections.items():
        clean_sec_title = str(sec_title).replace("_", " ").title()
        lines.append(f"## {clean_sec_title}")
        lines.append("------------------------------------------------------------")
        if isinstance(sec_content, list):
            for item in sec_content:
                if isinstance(item, dict):
                    item_str = " | ".join(f"{k}: {v}" for k, v in item.items() if v)
                    lines.append(f"• {item_str}")
                else:
                    lines.append(f"• {str(item)}")
        elif isinstance(sec_content, dict):
            for k, v in sec_content.items():
                lines.append(f"• {k}: {v}")
        else:
            lines.append(str(sec_content).strip())
        lines.append("")

    if metadata:
        lines.append("## METADATOS TÉCNICOS & TELEMETRÍA")
        lines.append("------------------------------------------------------------")
        for k, v in metadata.items():
            lines.append(f"• {k}: {v}")
        lines.append("")

    lines.append("============================================================")
    lines.append("FIN DEL DOSSIER EJECUTIVO - CONFIDENCIAL AKIRA COGNITIVE SUITE")
    return "\n".join(lines)


def compile_executive_dossier(
    title: str,
    content_or_sections: Union[str, Dict[str, Any]],
    recipient: str = "Director Jhon Grimm",
    author: str = "Akira Ultra Cognitive Suite",
    save_to_disk: bool = True,
    output_dir: Optional[str] = None,
    include_base64: bool = False,
) -> Dict[str, Any]:
    """
    Compiles an executive PDF dossier from textual or structured input.
    Generates SHA-256 fingerprint and saves to disk if requested.
    """
    formatted_text = build_dossier_text(title, content_or_sections)
    pdf_bytes = create_executive_pdf(title=title, content=formatted_text, recipient=recipient, author=author)
    
    sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    ts_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_title = re.sub(r"[^\w\-]", "_", title.strip())[:30]
    filename = f"Dossier_{clean_title}_{ts_str}.pdf"

    saved_path: Optional[str] = None
    if save_to_disk:
        target_dir = output_dir or DOSSIERS_DIR
        _ensure_dossiers_dir(target_dir)
        saved_path = os.path.join(target_dir, filename)
        try:
            with open(saved_path, "wb") as f:
                f.write(pdf_bytes)
        except Exception as exc:
            logger.warning("No se pudo guardar PDF en disco: %s", exc)
            saved_path = None

    response: Dict[str, Any] = {
        "status": "success",
        "title": title,
        "filename": filename,
        "file_path": saved_path,
        "size_bytes": len(pdf_bytes),
        "sha256": sha256,
        "timestamp": datetime.datetime.now().isoformat(),
        "recipient": recipient,
        "author": author,
    }

    if include_base64:
        response["pdf_base64"] = base64.b64encode(pdf_bytes).decode("ascii")

    return response


def dispatch_dossier_to_telegram(
    pdf_bytes: bytes,
    filename: str,
    caption: str = "",
    chat_id: Optional[str] = None,
    bot_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Dispatches a compiled PDF dossier directly to Telegram chat.
    Retrieves token and chat_id automatically from environment or stored configuration.
    """
    try:
        import telegram_service

        token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        if not token:
            cfg = telegram_service.load_telegram_config()
            token = cfg.get("bot_token")

        if not token:
            return {"ok": False, "error": "No se encontró token de Telegram configurado."}

        target_chat = chat_id or telegram_service.get_last_chat_id()
        if not target_chat:
            return {"ok": False, "error": "No hay chat_id registrado para enviar el documento."}

        doc_caption = caption or f"📑 Dossier Ejecutivo: {filename}\nDirectiva J.A.R.V.I.S. | $0.00 COP"
        res = telegram_service.send_telegram_document(
            bot_token=token,
            chat_id=str(target_chat),
            file_bytes=pdf_bytes,
            filename=filename,
            caption=doc_caption,
        )
        return res
    except Exception as exc:
        logger.warning("Fallo al enviar dossier por Telegram: %s", exc)
        return {"ok": False, "error": str(exc)}


def generate_and_dispatch_dossier(
    title: str,
    content_or_sections: Union[str, Dict[str, Any]],
    recipient: str = "Director Jhon Grimm",
    send_telegram: bool = False,
    chat_id: Optional[str] = None,
    include_base64: bool = False,
) -> Dict[str, Any]:
    """
    High-level 1-click pipeline: Compiles PDF and optionally sends it directly to Telegram.
    """
    compilation = compile_executive_dossier(
        title=title,
        content_or_sections=content_or_sections,
        recipient=recipient,
        include_base64=include_base64,
    )

    telegram_res = None
    if send_telegram and compilation.get("file_path"):
        try:
            with open(compilation["file_path"], "rb") as f:
                pdf_bytes = f.read()
            telegram_res = dispatch_dossier_to_telegram(
                pdf_bytes=pdf_bytes,
                filename=compilation["filename"],
                caption=f"📑 **Dossier Ejecutivo: {title}**\nGenerado para {recipient}.",
                chat_id=chat_id,
            )
        except Exception as exc:
            telegram_res = {"ok": False, "error": str(exc)}

    compilation["sent_to_telegram"] = bool(telegram_res and telegram_res.get("ok"))
    compilation["telegram_response"] = telegram_res
    return compilation
