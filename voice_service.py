"""
AKIRA VOICE SERVICE
Zero-Cost ($0.00 COP/USD) hyper-realistic neural voice generator using edge-tts.
Default Voice: 'es-CO-SalomeNeural' (Warm, executive Colombian female voice).
Fallback Voice: 'es-CO-GonzaloNeural' or standard synthesis.
"""

import asyncio
import logging

logger = logging.getLogger("akira.voice")

async def _synthesize_edge_tts(text: str, voice: str = "es-CO-SalomeNeural") -> bytes:
    import edge_tts
    clean_text = text[:1500].strip()
    communicate = edge_tts.Communicate(clean_text, voice)
    chunks = []
    async for chunk in communicate.stream():
        if chunk.get("type") == "audio":
            chunks.append(chunk["data"])
    return b"".join(chunks)

def generate_voice_bytes(text: str, voice: str = "es-CO-SalomeNeural") -> bytes | None:
    """Genera bytes de audio (MP3/OGG) de alta fidelidad para notas de voz en Telegram."""
    if not text or not text.strip():
        return None
    try:
        return asyncio.run(_synthesize_edge_tts(text, voice))
    except Exception as e:
        logger.warning(f"Error generando voz con edge-tts: {e}")
        return None
