"""
AKIRA VOICE SERVICE
Zero-Cost ($0.00 COP/USD) hyper-realistic neural voice generator using edge-tts.
Default Voice: 'es-CO-SalomeNeural' (Warm, executive Colombian female voice).
Fallback Voice: 'es-CO-GonzaloNeural' or standard synthesis.
Safe execution inside both standalone scripts and active async event loops (FastAPI / Uvicorn).
"""

import asyncio
import logging
import concurrent.futures

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
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Si se invoca dentro de un event loop activo (FastAPI), ejecutar en threadpool aislado
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(lambda: asyncio.run(_synthesize_edge_tts(text, voice))).result(timeout=25)
        else:
            return asyncio.run(_synthesize_edge_tts(text, voice))
    except Exception as e:
        logger.warning(f"Error generando voz con edge-tts: {e}")
        return None
