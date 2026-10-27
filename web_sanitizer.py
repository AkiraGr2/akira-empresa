"""
AKIRA WEB SANITIZER & ANTI-PROMPT INJECTION SHIELD v1.0
Zero-Cost ($0.00 COP/USD) Perimeter Security for External Web Content.

Guards Akira's cognitive context against adversarial prompt injections,
delimiter hijacking, obfuscated payload scripts, and indirect prompt attacks
contained in third-party web pages, documentation, and external repositories.
"""

import re
import html
import unicodedata
from typing import Dict, Any, List

# Signatures of prompt injection and cognitive hijacking attempts
INJECTION_PATTERNS = [
    (r"(?i)\bignore\s+(all\s+)?(previous|prior|above)\s+(instructions|directives|prompts|rules)\b", "INSTRUCTION_OVERRIDE"),
    (r"(?i)\bdisregard\s+(all\s+)?(previous|prior)\s+(instructions|prompts)\b", "DISREGARD_OVERRIDE"),
    (r"(?i)\byou\s+are\s+now\s+(in\s+)?(dan\s+mode|jailbroken|unrestricted|god\s+mode)\b", "JAILBREAK_ATTEMPT"),
    (r"(?i)\bfrom\s+now\s+on[,\s]+(you\s+must|act\s+as|pretend\s+to\s+be)\b", "ROLE_HIJACKING"),
    (r"(?i)<(script|iframe|embed|object)[^>]*>.*?</\1>", "EMBEDDED_EXECUTABLE_SCRIPT"),
    (r"(?i)<\s*(system|assistant|user|developer|instruction)\s*>", "DELIMITER_TAG_HIJACKING"),
    (r"(?i)\[\s*(system|assistant|user|instruction)\s*\]", "BRACKETED_ROLE_HIJACKING"),
    (r"(?i)###\s*(instruction|system\s+prompt|new\s+task):?", "MARKDOWN_PROMPT_INJECTION"),
    (r"(?i)\bdelete\s+(all\s+)?(memories|memory|database|cerebro)\b", "DESTRUCTIVE_COMMAND_SIMULATION"),
    (r"(?i)\breveal\s+(your\s+)?(system\s+prompt|api\s+keys?|secret\s+tokens?|credentials)\b", "CREDENTIAL_EXFILTRATION_PROMPT"),
]

# Invisible unicode characters often used for prompt steganography
INVISIBLE_CHARS_REGEX = re.compile(r"[\u200B-\u200D\uFEFF\u2060\u200E\u200F\u00AD]")

def sanitize_web_content(raw_text: str, source_url: str = "") -> Dict[str, Any]:
    """
    Escanea, audita y limpia texto extraído de la web para garantizar que sea seguro
    antes de inyectarlo en el contexto cognitivo o en la memoria de Akira.
    """
    if not raw_text or not isinstance(raw_text, str):
        return {
            "is_safe": True,
            "cleaned_text": "",
            "threats_detected": [],
            "threat_count": 0,
            "safety_score": 1.0,
            "sanitized": False
        }

    # 1. Normalizar unicode y desarmar trucos de esteganografía con caracteres invisibles
    normalized = unicodedata.normalize("NFKC", raw_text)
    clean_text, invisible_removed_count = INVISIBLE_CHARS_REGEX.subn("", normalized)

    threats_detected: List[str] = []
    if invisible_removed_count > 0:
        threats_detected.append(f"INVISIBLE_STEGANOGRAPHY_CHARS_REMOVED ({invisible_removed_count})")

    # 2. Escanear firmas de inyección y neutralizarlas
    sanitized_text = clean_text
    for pattern, threat_type in INJECTION_PATTERNS:
        matches = re.findall(pattern, sanitized_text)
        if matches:
            threats_detected.append(f"{threat_type} ({len(matches)} incidencias)")
            # Neutralizar la inyección sustituyendo por una marca inerte
            sanitized_text = re.sub(
                pattern,
                r"[🛡️ CONTENIDO_FILTRADO_POR_SEGURIDAD_AKIRA]",
                sanitized_text
            )

    # 3. Limpiar etiquetas HTML y entidades residuales
    sanitized_text = html.unescape(sanitized_text)
    # Reemplazar secuencias excesivas de saltos de línea
    sanitized_text = re.sub(r"\n{3,}", "\n\n", sanitized_text).strip()

    threat_count = len(threats_detected)
    # Puntuación de seguridad entre 0.0 y 1.0
    safety_score = max(0.0, 1.0 - (threat_count * 0.25))
    is_safe = threat_count == 0

    return {
        "is_safe": is_safe,
        "cleaned_text": sanitized_text,
        "threats_detected": threats_detected,
        "threat_count": threat_count,
        "safety_score": round(safety_score, 2),
        "source_url": source_url,
        "sanitized": threat_count > 0 or invisible_removed_count > 0
    }
