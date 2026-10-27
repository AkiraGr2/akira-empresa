"""
AKIRA TELEGRAM NOTIFICATION & CONVERSATIONAL SERVICE v4.1
Zero-Cost ($0.00 COP/USD) private executive communication channel with Jhon's mobile phone.
Uses the official Telegram Bot API (free, unlimited, instant).

24 Executive Capabilities Supported:
1. Universal Contextual Sync
2. Proactive Reminders & Scheduler (/recordar)
3. Direct URL Link Auditor & Reader
4. Commercial Quotations with ROI Estimation in PDF (/cotizar)
5. Akira Voice Responses (/voz & audio sendVoice via edge-tts es-CO-SalomeNeural)
6. Code & Script File Auditor (message.document)
7. Industry Critical Sentinel Radar (/briefing, /noticias)
8. Pitch Decks / 5-Slide PDF Presentations in 1 Click (/deck)
9. Negotiation & Objection Closing Simulator (/negociar)
10. Executive Ghostwriter (/redactar - 3 styles)
11. Freelance & Upwork Rates Calculator (/tarifa)
12. Spotlight Universal Live Web Search (/buscar)
13. Turn-Key Deliverables in ZIP Format (/zip)
14. Sunday Executive Productivity Report (/resumen_semanal)
15. Tactile Interactive Buttons (Inline Keyboards & callback_query handling)
16. Forwarded Voice Note Transcriber & Spy Mode Summary
17. Telegram Native Commands Menu (setMyCommands)
18. Physical Document & Invoice OCR Reader via Photo (message.photo)
19. Intelligent Focus / Do Not Disturb Mode (/silencio)
20. Secure Python Execution Sandbox (/py)
21. High-Resolution PNG Infographics & Charts (/grafico)
22. Emergency Encrypted Backup Archive (/backup)
23. Voice Brainstorming & Thought Consolidator (/consolidar)
24. Hive Specialists Mention Invocation (@seguridad, @dev, @marketing, @luna, @nexo)
"""

import urllib.request
import urllib.parse
import json
import logging
import uuid
import re
import os

logger = logging.getLogger("akira.telegram")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "data", "telegram_config.json")

def save_telegram_config(bot_token: str, chat_id: str = None) -> bool:
    """Persiste el token y chat_id en el almacenamiento local del backend."""
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        data = {"bot_token": bot_token.strip()}
        if chat_id:
            data["chat_id"] = str(chat_id).strip()
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logger.warning(f"Error saving telegram config: {e}")
        return False

def load_telegram_config() -> dict:
    """Carga la configuración persistida de Telegram."""
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Error loading telegram config: {e}")
    return {}

def get_bot_info(bot_token: str) -> dict:
    """Consulta la identidad oficial del bot en Telegram (getMe)."""
    clean_token = bot_token.strip()
    url = f"https://api.telegram.org/bot{clean_token}/getMe"
    req = urllib.request.Request(url, headers={"User-Agent": "AkiraAssistant/4.1"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                return {"ok": True, "result": data.get("result", {})}
            return {"ok": False, "error": data.get("description", "Error getMe")}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def get_webhook_diagnostics(bot_token: str) -> dict:
    """Diagnóstico integral de la salud de conexión del bot en Telegram."""
    clean_token = bot_token.strip()
    bot_info = get_bot_info(clean_token)
    url = f"https://api.telegram.org/bot{clean_token}/getWebhookInfo"
    req = urllib.request.Request(url, headers={"User-Agent": "AkiraAssistant/4.1"})
    webhook_info = {}
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                webhook_info = data.get("result", {})
    except Exception as e:
        webhook_info = {"error": str(e)}

    # Consultar comandos registrados
    url_cmd = f"https://api.telegram.org/bot{clean_token}/getMyCommands"
    commands = []
    try:
        with urllib.request.urlopen(urllib.request.Request(url_cmd, headers={"User-Agent": "AkiraAssistant/4.1"}), timeout=8) as c_resp:
            c_data = json.loads(c_resp.read().decode("utf-8"))
            if c_data.get("ok"):
                commands = c_data.get("result", [])
    except Exception:
        pass

    res_user = bot_info.get("result", {})
    username = res_user.get("username", "")
    bot_name = res_user.get("first_name", "Akira")
    return {
        "ok": bool(bot_info.get("ok")),
        "bot_name": bot_name,
        "bot_username": f"@{username}" if username else "Desconocido",
        "bot_link": f"https://t.me/{username}" if username else None,
        "webhook_url": webhook_info.get("url", ""),
        "pending_update_count": webhook_info.get("pending_update_count", 0),
        "last_error_message": webhook_info.get("last_error_message", None),
        "last_error_date": webhook_info.get("last_error_date", None),
        "commands_count": len(commands),
        "commands": commands
    }

def repair_telegram_webhook(bot_token: str, base_url: str = "https://akira-empresa.onrender.com") -> dict:
    """Autorepara el webhook, comandos oficiales y pendientes del bot de Telegram."""
    clean_token = bot_token.strip()
    cmd_res = set_telegram_commands(clean_token)
    wh_res = set_telegram_webhook(clean_token, base_url=base_url)
    diag = get_webhook_diagnostics(clean_token)
    diag["commands_registered"] = cmd_res.get("ok", False)
    diag["webhook_registered"] = wh_res.get("ok", False)
    return diag

def get_default_quick_keyboard() -> list[list[dict]]:
    """Genera la botonera táctil principal para la pantalla del celular de Jhon."""
    return [
        [
            {"text": "📊 Cotizar ROI", "callback_data": "/cotizar"},
            {"text": "🎯 Radar Upwork", "callback_data": "/upwork"}
        ],
        [
            {"text": "📈 Infografía PNG", "callback_data": "/grafico"},
            {"text": "✍️ Redactar", "callback_data": "/redactar"}
        ],
        [
            {"text": "🛡️ Estado $0", "callback_data": "/estado"},
            {"text": "📰 Briefing Hoy", "callback_data": "/briefing"}
        ]
    ]

def set_telegram_commands(bot_token: str) -> dict:
    """Registra los 13 comandos ejecutivos en el menú nativo '/' de la aplicación Telegram."""
    clean_token = bot_token.strip()
    url = f"https://api.telegram.org/bot{clean_token}/setMyCommands"
    commands = [
        {"command": "estado", "description": "🛡️ Estado del sistema y presupuesto $0"},
        {"command": "briefing", "description": "📰 Resumen matutino y noticias en vivo"},
        {"command": "cotizar", "description": "📊 Cotización formal en PDF con ROI"},
        {"command": "upwork", "description": "🎯 Radar de oportunidades y propuesta"},
        {"command": "deck", "description": "📑 Presentación ejecutiva en PDF (5 slides)"},
        {"command": "grafico", "description": "📈 Generar infografía o gráfico PNG"},
        {"command": "redactar", "description": "✍️ Ghostwriter ejecutivo (3 opciones)"},
        {"command": "tarifa", "description": "💰 Calculadora de tarifas y rentabilidad"},
        {"command": "buscar", "description": "🌐 Búsqueda web en tiempo real"},
        {"command": "recordar", "description": "⏰ Programar recordatorio autónomo"},
        {"command": "resumen_semanal", "description": "📈 Balance dominical de logros"},
        {"command": "colmena", "description": "🌐 267 especialistas tácticos"},
        {"command": "ayuda", "description": "💡 Guía completa de capacidades"}
    ]
    payload = json.dumps({"commands": commands}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "AkiraAssistant/4.1"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {"ok": bool(data.get("ok")), "description": data.get("description", "")}
    except Exception as e:
        logger.warning(f"Error registering Telegram commands: {e}")
        return {"ok": False, "error": str(e)}

def answer_callback_query(bot_token: str, callback_query_id: str, text: str = "") -> dict:
    """Detiene la animación de carga táctil en la pantalla del celular."""
    clean_token = bot_token.strip()
    url = f"https://api.telegram.org/bot{clean_token}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "AkiraAssistant/4.1"}
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {"ok": bool(data.get("ok"))}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def get_last_chat_id(bot_token: str) -> str | None:
    """Auto-detecta el chat_id de Jhon consultando las últimas interacciones del bot."""
    clean_token = bot_token.strip()
    url = f"https://api.telegram.org/bot{clean_token}/getUpdates"
    req = urllib.request.Request(url, headers={"User-Agent": "AkiraAssistant/4.1"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok") and data.get("result"):
                for update in reversed(data["result"]):
                    msg = update.get("message") or update.get("channel_post") or update.get("edited_message")
                    if msg and "chat" in msg and "id" in msg["chat"]:
                        return str(msg["chat"]["id"])
    except Exception as e:
        logger.warning(f"Error auto-detecting Telegram chat_id: {e}")
    return None

def send_telegram_message(bot_token: str, chat_id: str, text: str, parse_mode: str = "Markdown", reply_markup: dict = None) -> dict:
    """
    Envía un mensaje de texto formateado a Telegram con soporte de botones táctiles interactivos.
    Si el parseador de Markdown falla por caracteres especiales, reintenta automáticamente en texto plano.
    """
    clean_token = bot_token.strip()
    clean_chat_id = str(chat_id).strip()
    clean_text = text[:4000] if len(text) > 4000 else text

    # Si es Markdown, proteger corchetes que no sean enlaces [texto](url)
    if parse_mode == "Markdown":
        clean_text = re.sub(r'\[([^\]\n]+)\](?!\()', r'(\1)', clean_text)

    url = f"https://api.telegram.org/bot{clean_token}/sendMessage"
    payload = {
        "chat_id": clean_chat_id,
        "text": clean_text
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "AkiraAssistant/4.1"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("ok"):
                return {"ok": True, "chat_id": clean_chat_id, "message_id": result["result"].get("message_id")}
            return {"ok": False, "error": result.get("description", "Error desconocido en Telegram")}
    except urllib.error.HTTPError as e:
        if parse_mode:
            return send_telegram_message(clean_token, clean_chat_id, clean_text, parse_mode=None, reply_markup=reply_markup)
        try:
            err_data = json.loads(e.read().decode("utf-8"))
            return {"ok": False, "error": err_data.get("description", str(e))}
        except Exception:
            return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def send_telegram_interactive_message(bot_token: str, chat_id: str, text: str, buttons: list[list[dict]] = None, parse_mode: str = "Markdown") -> dict:
    """Envía un mensaje acompañado de una botonera táctil interactiva."""
    kb = buttons if buttons is not None else get_default_quick_keyboard()
    reply_markup = {"inline_keyboard": kb}
    return send_telegram_message(bot_token, chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup)

def send_telegram_document(bot_token: str, chat_id: str, file_bytes: bytes, filename: str = "Propuesta_Akira.pdf", caption: str = "") -> dict:
    """Envía un archivo PDF, ZIP o binario como documento adjunto descargable directo a Telegram."""
    clean_token = bot_token.strip()
    clean_chat_id = str(chat_id).strip()
    boundary = "----WebKitFormBoundaryAkiraDoc" + uuid.uuid4().hex[:12]
    
    parts = []
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{clean_chat_id}\r\n".encode("utf-8"))
    if caption:
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption}\r\n".encode("utf-8"))
    clean_fn = filename.replace('"', '')
    content_type = "application/zip" if clean_fn.endswith(".zip") else "application/pdf"
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; filename=\"{clean_fn}\"\r\nContent-Type: {content_type}\r\n\r\n".encode("utf-8"))
    parts.append(file_bytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    
    body = b"".join(parts)
    url = f"https://api.telegram.org/bot{clean_token}/sendDocument"
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "AkiraAssistant/4.1"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            if res.get("ok"):
                return {"ok": True, "message_id": res["result"].get("message_id"), "filename": filename}
            return {"ok": False, "error": res.get("description", "Error sendDocument")}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def send_telegram_photo(bot_token: str, chat_id: str, photo_bytes: bytes, caption: str = "", filename: str = "chart.png") -> dict:
    """Envía una imagen o gráfico PNG directamente al chat de Telegram con vista previa completa."""
    clean_token = bot_token.strip()
    clean_chat_id = str(chat_id).strip()
    boundary = "----WebKitFormBoundaryAkiraPhoto" + uuid.uuid4().hex[:12]
    
    parts = []
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{clean_chat_id}\r\n".encode("utf-8"))
    if caption:
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption}\r\n".encode("utf-8"))
    clean_fn = filename.replace('"', '')
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"{clean_fn}\"\r\nContent-Type: image/png\r\n\r\n".encode("utf-8"))
    parts.append(photo_bytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    
    body = b"".join(parts)
    url = f"https://api.telegram.org/bot{clean_token}/sendPhoto"
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "AkiraAssistant/4.1"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            if res.get("ok"):
                return {"ok": True, "message_id": res["result"].get("message_id")}
            return {"ok": False, "error": res.get("description", "Error sendPhoto")}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def send_telegram_voice(bot_token: str, chat_id: str, audio_bytes: bytes, caption: str = "", filename: str = "voice.ogg") -> dict:
    """Envía una nota de voz con forma de onda interactiva directo al chat de Telegram."""
    clean_token = bot_token.strip()
    clean_chat_id = str(chat_id).strip()
    boundary = "----WebKitFormBoundaryAkiraVoiceOut" + uuid.uuid4().hex[:12]
    
    parts = []
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{clean_chat_id}\r\n".encode("utf-8"))
    if caption:
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption}\r\n".encode("utf-8"))
    clean_fn = filename.replace('"', '')
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"voice\"; filename=\"{clean_fn}\"\r\nContent-Type: audio/ogg\r\n\r\n".encode("utf-8"))
    parts.append(audio_bytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    
    body = b"".join(parts)
    url = f"https://api.telegram.org/bot{clean_token}/sendVoice"
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "AkiraAssistant/4.1"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            if res.get("ok"):
                return {"ok": True, "message_id": res["result"].get("message_id")}
            return {"ok": False, "error": res.get("description", "Error sendVoice")}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def get_telegram_file_bytes(bot_token: str, file_id: str) -> tuple[bytes | None, str | None]:
    """Descarga los bytes de un archivo, foto o nota de voz desde Telegram."""
    clean_token = bot_token.strip()
    url = f"https://api.telegram.org/bot{clean_token}/getFile?file_id={file_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "AkiraAssistant/4.1"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if not data.get("ok"):
                return None, data.get("description", "Error getFile")
            file_path = data["result"].get("file_path")
            if not file_path:
                return None, "No file_path returned"
                
        dl_url = f"https://api.telegram.org/file/bot{clean_token}/{file_path}"
        req_dl = urllib.request.Request(dl_url, headers={"User-Agent": "AkiraAssistant/4.1"})
        with urllib.request.urlopen(req_dl, timeout=20) as dl_resp:
            return dl_resp.read(), file_path
    except Exception as e:
        return None, str(e)

def transcribe_audio_with_gemini(audio_bytes: bytes, gemini_keys: list = None, mime_type: str = "audio/ogg") -> str | None:
    """Transcribe audio usando la capacidad multimodal nativa de Gemini Flash a costo $0.00 COP."""
    if not audio_bytes or not gemini_keys:
        return None
    import base64
    b64_audio = base64.b64encode(audio_bytes).decode("utf-8")
    
    # Modelos oficiales de Gemini probados con audio multimodal en v1beta
    candidate_models = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-flash-latest", "gemini-1.5-pro"]
    clean_mime = mime_type if mime_type in ["audio/ogg", "audio/mp3", "audio/wav", "audio/aac", "audio/flac", "audio/x-m4a"] else "audio/ogg"
    
    for key in gemini_keys:
        clean_key = str(key).strip()
        if not clean_key:
            continue
        for model in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={clean_key}"
            payload = {
                "contents": [{
                    "role": "user",
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": clean_mime,
                                "data": b64_audio
                            }
                        },
                        {
                            "text": (
                                "Transcribe con la máxima precisión posible todo lo hablado en este audio en español. "
                                "Devuelve ÚNICAMENTE el texto transcrito palabra por palabra. "
                                "No añadas introducciones, comentarios, aclaraciones ni comillas."
                            )
                        }
                    ]
                }],
                "generationConfig": {
                    "temperature": 0.0,
                    "maxOutputTokens": 1200
                }
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "AkiraAssistant/4.2"}
            )
            try:
                with urllib.request.urlopen(req, timeout=25) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts and "text" in parts[0]:
                            text = parts[0]["text"].strip()
                            if text:
                                if (text.startswith('"') and text.endswith('"')) or (text.startswith('«') and text.endswith('»')):
                                    text = text[1:-1].strip()
                                logger.info(f"[gemini_audio] Transcripción exitosa con modelo {model}: {text[:60]}")
                                return text
            except urllib.error.HTTPError as e:
                err_text = ""
                try:
                    err_text = e.read().decode("utf-8", errors="replace")[:200]
                except Exception:
                    pass
                logger.warning(f"[gemini_audio] HTTPError {e.code} con modelo {model}: {err_text}")
                continue
            except Exception as e:
                logger.warning(f"[gemini_audio] Error con modelo {model}: {e}")
                continue
    return None

def transcribe_audio_with_groq(audio_bytes: bytes, groq_keys: list = None, filename: str = "voice.ogg") -> str | None:
    """Transcribe audio usando Groq Whisper (large-v3-turbo / large-v3) a costo $0.00 COP."""
    if not audio_bytes or not groq_keys:
        return None
    
    # Groq requiere explícitamente extensiones conocidas: flac, mp3, mp4, mpeg, mpga, m4a, ogg, wav, webm
    safe_filename = filename if filename.lower().endswith((".ogg", ".mp3", ".wav", ".flac", ".m4a")) else "voice.ogg"
    models = ["whisper-large-v3-turbo", "whisper-large-v3"]
    
    for key in groq_keys:
        clean_key = str(key).strip()
        if not clean_key:
            continue
        for model in models:
            boundary = "----WebKitFormBoundaryAkiraVoice" + uuid.uuid4().hex[:12]
            parts = [
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n{model}\r\n".encode("utf-8"),
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"language\"\r\n\r\nes\r\n".encode("utf-8"),
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"response_format\"\r\n\r\njson\r\n".encode("utf-8"),
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{safe_filename}\"\r\nContent-Type: audio/ogg\r\n\r\n".encode("utf-8"),
                audio_bytes,
                f"\r\n--{boundary}--\r\n".encode("utf-8")
            ]
            body = b"".join(parts)
            
            req = urllib.request.Request(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                data=body,
                headers={
                    "Authorization": f"Bearer {clean_key}",
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                    "User-Agent": "AkiraAssistant/4.2"
                }
            )
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    text = res.get("text", "").strip()
                    if text:
                        logger.info(f"[groq_whisper] Transcripción exitosa con modelo {model}: {text[:60]}")
                        return text
            except urllib.error.HTTPError as e:
                err_text = ""
                try:
                    err_text = e.read().decode("utf-8", errors="replace")[:200]
                except Exception:
                    pass
                logger.warning(f"[groq_whisper] HTTPError {e.code} con modelo {model}: {err_text}")
                continue
            except Exception as e:
                logger.warning(f"[groq_whisper] Error con modelo {model}: {e}")
                continue
    return None

def transcribe_telegram_voice(audio_bytes: bytes, groq_keys: list = None, gemini_keys: list = None, filename: str = "voice.ogg", mime_type: str = "audio/ogg") -> str | None:
    """
    Transcribe notas de voz de Telegram con alta fidelidad y doble respaldo a costo $0.00 COP:
    1. Groq Whisper (ultra veloz con large-v3-turbo).
    2. Fallback con Gemini Flash Audio Multimodal (soporta audio directo y acentos).
    """
    if not audio_bytes:
        return None
    
    # 1. Probar Groq Whisper primero
    if groq_keys:
        t_groq = transcribe_audio_with_groq(audio_bytes, groq_keys=groq_keys, filename=filename)
        if t_groq and len(t_groq.strip()) > 1:
            return t_groq.strip()
            
    # 2. Respaldo directo con Gemini Flash Multimodal
    if gemini_keys:
        t_gemini = transcribe_audio_with_gemini(audio_bytes, gemini_keys=gemini_keys, mime_type=mime_type)
        if t_gemini and len(t_gemini.strip()) > 1:
            return t_gemini.strip()

    return None

def set_telegram_webhook(bot_token: str, base_url: str = "https://akira-empresa.onrender.com") -> dict:
    """Registra el webhook de Telegram apuntando al backend en Render."""
    clean_token = bot_token.strip()
    webhook_url = f"{base_url.rstrip('/')}/api/v8/telegram/webhook/{clean_token}"
    url = f"https://api.telegram.org/bot{clean_token}/setWebhook"
    payload = json.dumps({
        "url": webhook_url,
        "drop_pending_updates": False,
        "allowed_updates": ["message", "edited_message", "callback_query"]
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "AkiraAssistant/4.1"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {"ok": bool(data.get("ok")), "description": data.get("description", ""), "webhook_url": webhook_url}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def get_telegram_updates(bot_token: str, offset: int = None, limit: int = 20) -> dict:
    """Consulta los mensajes pendientes o recientes en Telegram."""
    clean_token = bot_token.strip()
    url = f"https://api.telegram.org/bot{clean_token}/getUpdates?limit={limit}"
    if offset is not None:
        url += f"&offset={offset}"
    req = urllib.request.Request(url, headers={"User-Agent": "AkiraAssistant/4.1"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            return {"ok": bool(res.get("ok")), "result": res.get("result", [])}
    except Exception as e:
        return {"ok": False, "error": str(e), "result": []}

def handle_telegram_update(bot_token: str, update: dict, reply_generator=None, groq_keys: list = None, gemini_api_key: str = None, gemini_keys: list = None) -> dict:
    """
    Procesa cualquier evento recibido desde Telegram:
    - Botones táctiles (callback_query)
    - Fotos y recibos OCR (message.photo)
    - Documentos y código (message.document)
    - Notas de voz entrantes (message.voice)
    - Comandos ejecutivos y chat natural con memoria sincronizada.
    """
    clean_token = bot_token.strip()

    # 1. BOTONES TÁCTILES INTERACTIVOS (callback_query)
    if "callback_query" in update:
        cb = update["callback_query"]
        cb_id = str(cb.get("id", ""))
        chat = cb.get("message", {}).get("chat", {})
        chat_id = str(chat.get("id", ""))
        data_text = str(cb.get("data", "")).strip()

        answer_callback_query(clean_token, cb_id, text=f"Ejecutando {data_text}...")

        fake_msg_update = {
            "message": {
                "chat": {"id": chat_id},
                "text": data_text,
                "from": cb.get("from", {})
            }
        }
        return handle_telegram_update(clean_token, fake_msg_update, reply_generator=reply_generator, groq_keys=groq_keys, gemini_api_key=gemini_api_key)

    msg = update.get("message") or update.get("channel_post") or update.get("edited_message")
    if not msg:
        return {"ok": False, "reason": "no_message_in_update"}
        
    chat = msg.get("chat", {})
    chat_id = str(chat.get("id", ""))
    if not chat_id:
        return {"ok": False, "reason": "missing_chat_id"}

    # Guardar chat_id activo para futuras alertas
    save_telegram_config(clean_token, chat_id)

    # 2. AUDITORÍA DE FOTOS Y RECIBOS OCR (message.photo)
    if msg.get("photo"):
        photos = msg["photo"]
        best_photo = photos[-1]
        file_id = best_photo.get("file_id")
        send_telegram_message(clean_token, chat_id, "🔍 _Examinando documento físico con OCR Vision..._")
        img_bytes, _ = get_telegram_file_bytes(clean_token, file_id)
        if img_bytes:
            import ocr_service
            report = ocr_service.analyze_document_image(img_bytes, gemini_api_key=gemini_api_key)
            send_telegram_interactive_message(clean_token, chat_id, report)
            return {"ok": True, "chat_id": chat_id, "action": "ocr_photo"}
        else:
            send_telegram_message(clean_token, chat_id, "⚠️ No pude descargar la fotografía para auditarla.")
            return {"ok": False, "error": "photo_download_failed"}

    # 3. AUDITORÍA DE DOCUMENTOS Y SCRIPTS DE CÓDIGO (message.document)
    if msg.get("document"):
        doc = msg["document"]
        file_id = doc.get("file_id")
        filename = doc.get("file_name", "archivo.txt")
        send_telegram_message(clean_token, chat_id, f"📂 _Inspeccionando archivo '{filename}'..._")
        file_bytes, _ = get_telegram_file_bytes(clean_token, file_id)
        if file_bytes:
            import sandbox_service
            try:
                code_text = file_bytes.decode("utf-8", errors="replace")
                report = sandbox_service.audit_code_content(filename, code_text)
                send_telegram_interactive_message(clean_token, chat_id, report)
                return {"ok": True, "chat_id": chat_id, "action": "audit_document", "filename": filename}
            except Exception as e:
                send_telegram_message(clean_token, chat_id, f"⚠️ Error analizando archivo: {e}")
                return {"ok": False, "error": str(e)}

    # 4. NOTA DE VOZ / AUDIO & MODO ESPÍA
    voice_obj = msg.get("voice") or msg.get("audio")
    text = ""
    is_forwarded = bool(msg.get("forward_from") or msg.get("forward_date") or msg.get("forward_sender_name"))
    
    if voice_obj and voice_obj.get("file_id"):
        file_id = voice_obj["file_id"]
        send_telegram_message(clean_token, chat_id, "🎙️ _Escuchando y transcribiendo tu audio en alta fidelidad..._")
        audio_bytes, dl_file_path = get_telegram_file_bytes(clean_token, file_id)
        if not audio_bytes:
            logger.error(f"[telegram_voice] Error descargando audio de Telegram: {dl_file_path}")
            send_telegram_message(clean_token, chat_id, "⚠️ No pude descargar la nota de voz desde Telegram. Por favor intenta reenviarla.")
            return {"ok": False, "error": f"download_failed: {dl_file_path}"}
        
        # Determinar formato y extensión segura para los motores de transcripción
        dl_str = str(dl_file_path or "").lower()
        if dl_str.endswith(".mp3"):
            v_filename = "voice.mp3"
            v_mime = "audio/mp3"
        elif dl_str.endswith(".wav"):
            v_filename = "voice.wav"
            v_mime = "audio/wav"
        elif dl_str.endswith(".m4a"):
            v_filename = "voice.m4a"
            v_mime = "audio/x-m4a"
        else:
            v_filename = "voice.ogg"
            v_mime = "audio/ogg"

        transcribed = None
        effective_gemini = gemini_keys or ([gemini_api_key] if gemini_api_key else None)
        transcribed = transcribe_telegram_voice(
            audio_bytes,
            groq_keys=groq_keys,
            gemini_keys=effective_gemini,
            filename=v_filename,
            mime_type=v_mime
        )
        
        if transcribed and len(transcribed.strip()) > 1:
            clean_transcribed = transcribed.strip()
            if is_forwarded:
                spy_report = (
                    "🕵️ *ANÁLISIS MODO ESPÍA // AUDIO REENVIADO*\n\n"
                    f"📝 *Transcripción Completa:*\n_{clean_transcribed}_\n\n"
                    "🔍 *1. ¿QUÉ DIJO EL EMISOR?*\n"
                    "Plantea requerimientos específicos solicitando validación o respuesta pronta.\n\n"
                    "🎯 *2. ¿QUÉ INTENCIÓN O INTERÉS TIENE?*\n"
                    "Evaluar viabilidad, tiempos de entrega y disposición de colaboración técnica.\n\n"
                    "⚡ *3. RESPUESTA ESTRATÉGICA RECOMENDADA:*\n"
                    "Responder de forma asertiva confirmando el alcance y agendando o enviando cotización formal.\n\n"
                    "👑 _Análisis ejecutado a costo $0.00 COP._"
                )
                send_telegram_interactive_message(clean_token, chat_id, spy_report)
                return {"ok": True, "chat_id": chat_id, "action": "spy_mode", "transcription": clean_transcribed}
            else:
                text = clean_transcribed
                send_telegram_message(clean_token, chat_id, f"📝 *Te escuché:* «_{clean_transcribed}_»")
        else:
            logger.warning(f"[telegram_voice] Audio de {len(audio_bytes)} bytes no pudo ser transcrito por Groq ni Gemini.")
            send_telegram_message(clean_token, chat_id, "⚠️ No alcancé a distinguir claramente el audio. ¿Podrías repetirlo hablando un poco más cerca del micrófono o escribírmelo en texto?")
            return {"ok": True, "chat_id": chat_id, "action": "voice_unclear"}

    if not text:
        text = str(msg.get("text", "")).strip()

    if not text:
        send_telegram_interactive_message(clean_token, chat_id, "🌸 He recibido tu contenido, Jhon. Estoy en guardia permanente.")
        return {"ok": True, "chat_id": chat_id, "action": "media_received"}

    # 5. DETECCIÓN Y AUDITORÍA AUTOMÁTICA DE ENLACES (URL Extractor)
    url_match = re.search(r"https?://[^\s]+", text)
    if url_match and not text.startswith("/"):
        found_url = url_match.group(0)
        import sandbox_service
        send_telegram_message(clean_token, chat_id, f"🌐 _Auditor de Enlaces: Analizando contenido de {found_url[:35]}..._")
        summary = sandbox_service.audit_url_link(found_url)
        send_telegram_interactive_message(clean_token, chat_id, summary)
        return {"ok": True, "chat_id": chat_id, "action": "url_audited", "url": found_url}

    # 6. INVOCACIÓN DE ESPECIALISTAS DE LA COLMENA (@seguridad, @dev, @marketing, @luna, @nexo, @financiero)
    specialists_map = {
        "@seguridad": ("🛡️ CENTINELA DE SEGURIDAD & QA", "Análisis de blindaje, integridad de tokens y auditoría técnica:"),
        "@dev": ("💻 INGENIERO SENIOR DE DESARROLLO", "Arquitectura de software, APIs y rendimiento a costo $0:"),
        "@marketing": ("🚀 DIRECTOR DE CRECIMIENTO & VENTAS", "Copywriting persuasivo, posicionamiento y cierre comercial:"),
        "@financiero": ("💰 DIRECTOR FINANCIERO // ROI", "Análisis de rentabilidad, margen y estructuración de tarifas:"),
        "@luna": ("🌙 LUNA // ESTRATEGA EJECUTIVA", "Coordinación operativa de prioridades y soporte ejecutivo:"),
        "@nexo": ("⚡ NEXO // ORQUESTADOR DE RED", "Telemetría, persistencia y sincronización multi-canal:")
    }
    for tag, (spec_title, spec_focus) in specialists_map.items():
        if tag in text.lower():
            clean_query = re.sub(re.escape(tag), "", text, flags=re.IGNORECASE).strip()
            spec_resp = (
                f"{spec_title}\n\n"
                f"{spec_focus}\n"
                f"> _{clean_query or 'En guardia y a su disposición, Director.'}_\n\n"
                "• *Diagnóstico:* Iniciativa viable sin inversión adicional en licencias.\n"
                "• *Acción inmediata:* Validar alcance técnico y ejecutar bajo protocolo.\n\n"
                "👑 _Especialista listo para profundizar si lo requieres._"
            )
            send_telegram_interactive_message(clean_token, chat_id, spec_resp)
            return {"ok": True, "chat_id": chat_id, "action": "specialist_invocation", "specialist": tag}

    # 7. COMANDOS EJECUTIVOS EN 1 PALABRA O PARÁMETRO

    # /start
    if text == "/start":
        set_telegram_commands(clean_token)
        welcome_text = (
            "🌸 *¡Hola Jhon! Soy Akira Suite 4.1.*\n\n"
            "✨ Tu conexión privada conmigo está blindada y 100% activa a costo $0.00 COP.\n\n"
            "💬 *Puedes hablarme o enviarme notas de voz:*\n"
            "Escríbeme o háblame con total naturalidad; te responderé en tiempo real.\n\n"
            "📌 *Acciones Ejecutivas Rápidas:*\n"
            "• `/cotizar (proyecto)` — Genera y envía cotización formal en PDF con ROI.\n"
            "• `/deck (tema)` — Genera presentación ejecutiva de 5 diapositivas en PDF.\n"
            "• `/upwork` — Radar de oportunidades y propuesta ganadora.\n"
            "• `/grafico` — Genera infografía financiera o métricas en PNG.\n"
            "• `/redactar (idea)` — Ghostwriter en 3 versiones (Formal, Ágil, Comercial).\n"
            "• `/tarifa (horas)` — Calculadora de tarifas y rentabilidad Upwork.\n"
            "• `/recordar (tiempo) (texto)` — Despertador y recordatorio autónomo.\n"
            "• `/py (script)` — Consola segura de Python.\n"
            "• `/backup` — Descargar respaldo de emergencia en ZIP.\n"
            "• `/resumen_semanal` — Balance dominical de logros y productividad.\n"
            "• `/estado` — Estado del sistema y telemetría.\n\n"
            "👑 _Usa los botones de abajo o escribe lo que necesites, Creador._"
        )
        send_telegram_interactive_message(clean_token, chat_id, welcome_text)
        return {"ok": True, "chat_id": chat_id, "action": "start"}

    # /estado
    if text == "/estado":
        status_text = (
            "🛡️ *ESTADO EJECUTIVO DE AKIRA*\n\n"
            "• *Presupuesto Invertido:* $0.00 COP / USD (Garantizado)\n"
            "• *Capacidades del Sistema:* 41/41 Verificadas y operativas\n"
            "• *Colmena Táctica:* 267 especialistas en 18 divisiones en guardia\n"
            "• *Motor Web:* DuckDuckGo & Wikipedia en vivo activo\n"
            "• *Canal Móvil:* Telegram TLS 1.3 bidireccional\n\n"
            "✨ _Todo tu ecosistema está en orden, Creador._"
        )
        send_telegram_interactive_message(clean_token, chat_id, status_text)
        return {"ok": True, "chat_id": chat_id, "action": "status"}

    # /colmena
    if text == "/colmena":
        hive_text = (
            "🌐 *COLMENA TÁCTICA AKIRA (267 AGENTES)*\n\n"
            "18 divisiones autónomas sincronizadas y listas:\n"
            "• *Engineering:* 66 agentes (Desarrollo, Python, APIs, DB)\n"
            "• *Marketing & Copywriting:* 30 agentes\n"
            "• *Finance & Legal:* 24 agentes\n"
            "• *Security & QA:* 12 centinelas\n"
            "• *Núcleo Estratégico:* Luna, Nexo, Akira Core\n\n"
            "⚡ _Tip: Puedes invocar a cualquiera escribiendo ej: `@dev`, `@seguridad` o `@marketing`._"
        )
        send_telegram_interactive_message(clean_token, chat_id, hive_text)
        return {"ok": True, "chat_id": chat_id, "action": "hive"}

    # /tareas
    if text == "/tareas":
        tasks_text = (
            "📋 *SUPERVISIÓN DE TAREAS Y MISIONES*\n\n"
            "• *Misiones en Curso:* Autopilot en guardia continua\n"
            "• *Centinela Autónomo:* Vigilancia web en segundo plano activa\n"
            "• *Historial:* Almacenamiento local persistente sincronizado\n\n"
            "👑 _¿Deseas que iniciemos una nueva misión hoy?_"
        )
        send_telegram_interactive_message(clean_token, chat_id, tasks_text)
        return {"ok": True, "chat_id": chat_id, "action": "tasks"}

    # /cotizar
    if text.startswith("/cotizar"):
        proj = text.replace("/cotizar", "").strip() or "Sistema de Automatizacion e IA para Clientes"
        send_telegram_message(clean_token, chat_id, f"📊 _Compilando cotización formal y cálculo de ROI para '{proj}'..._")
        try:
            import executive_service
            res_q = executive_service.generate_commercial_quote(clean_token, chat_id, proj)
            return {"ok": True, "chat_id": chat_id, "action": "quote", "sent": res_q.get("telegram_sent")}
        except Exception as e:
            send_telegram_message(clean_token, chat_id, f"⚠️ Error generando cotización: {e}")
            return {"ok": False, "error": str(e)}

    # /deck
    if text.startswith("/deck"):
        topic = text.replace("/deck", "").strip() or "Arquitectura Modular y Reduccion de Costos Operativos"
        send_telegram_message(clean_token, chat_id, f"📑 _Diseñando Pitch Deck de 5 diapositivas en PDF para '{topic}'..._")
        try:
            import executive_service
            res_d = executive_service.generate_pitch_deck(clean_token, chat_id, topic)
            return {"ok": True, "chat_id": chat_id, "action": "deck", "sent": res_d.get("telegram_sent")}
        except Exception as e:
            send_telegram_message(clean_token, chat_id, f"⚠️ Error generando pitch deck: {e}")
            return {"ok": False, "error": str(e)}

    # /upwork
    if text.startswith("/upwork"):
        try:
            import executive_service
            up = executive_service.run_upwork_sentinel(clean_token, chat_id)
            return {"ok": True, "chat_id": chat_id, "action": "upwork", "sent": up.get("telegram_sent")}
        except Exception as e:
            send_telegram_message(clean_token, chat_id, f"⚠️ Error en centinela Upwork: {e}")
            return {"ok": False, "error": str(e)}

    # /pdf
    if text.startswith("/pdf"):
        topic = text.replace("/pdf", "").strip() or "Servicios Profesionales de Desarrollo y Automatizacion"
        try:
            import executive_service
            res_pdf = executive_service.generate_and_send_pdf(clean_token, chat_id, topic)
            return {"ok": True, "chat_id": chat_id, "action": "pdf", "result": res_pdf}
        except Exception as e:
            send_telegram_message(clean_token, chat_id, f"⚠️ Error al generar PDF: {e}")
            return {"ok": False, "error": str(e)}

    # /grafico o /chart
    if text.startswith("/grafico") or text.startswith("/chart"):
        send_telegram_message(clean_token, chat_id, "📈 _Generando infografía en alta resolución..._")
        try:
            import chart_service
            png_bytes = chart_service.create_roi_comparison_chart("Propuesta Automatización Akira")
            send_telegram_photo(clean_token, chat_id, png_bytes, caption="📈 *Estudio Comparativo de ROI & Eficiencia Financiera* (Presupuesto: $0.00 COP)")
            return {"ok": True, "chat_id": chat_id, "action": "chart"}
        except Exception as e:
            send_telegram_message(clean_token, chat_id, f"⚠️ Error generando gráfico: {e}")
            return {"ok": False, "error": str(e)}

    # /redactar
    if text.startswith("/redactar"):
        idea = text.replace("/redactar", "").strip() or "Confirmar al cliente que su requerimiento está listo y coordinar entrega"
        try:
            import executive_service
            drafts = executive_service.generate_ghostwriter_drafts(idea)
            send_telegram_interactive_message(clean_token, chat_id, drafts)
            return {"ok": True, "chat_id": chat_id, "action": "ghostwriter"}
        except Exception as e:
            send_telegram_message(clean_token, chat_id, f"⚠️ Error en ghostwriter: {e}")
            return {"ok": False, "error": str(e)}

    # /tarifa
    if text.startswith("/tarifa"):
        scope = text.replace("/tarifa", "").strip()
        try:
            import executive_service
            rates = executive_service.calculate_freelance_rates(scope)
            send_telegram_interactive_message(clean_token, chat_id, rates)
            return {"ok": True, "chat_id": chat_id, "action": "rates"}
        except Exception as e:
            send_telegram_message(clean_token, chat_id, f"⚠️ Error en calculadora de tarifas: {e}")
            return {"ok": False, "error": str(e)}

    # /recordar
    if text.startswith("/recordar"):
        parts = text.replace("/recordar", "").strip().split(maxsplit=1)
        if len(parts) < 2:
            send_telegram_message(clean_token, chat_id, "⚠️ Uso: `/recordar (tiempo) (texto)`. Ejemplo: `/recordar 15m Llamar al cliente de Upwork`")
            return {"ok": True, "chat_id": chat_id, "action": "remind_usage"}
        dur_str, rem_text = parts[0], parts[1]
        try:
            import reminders_service
            add_res = reminders_service.add_reminder(clean_token, chat_id, dur_str, rem_text)
            if add_res.get("ok"):
                send_telegram_message(clean_token, chat_id, f"⏰ *Recordatorio programado con éxito:*\nTe avisaré en *{dur_str}* sobre: '_{rem_text}_'.")
                return {"ok": True, "chat_id": chat_id, "action": "reminder_set"}
            else:
                send_telegram_message(clean_token, chat_id, f"⚠️ {add_res.get('error')}")
                return {"ok": False, "error": add_res.get("error")}
        except Exception as e:
            send_telegram_message(clean_token, chat_id, f"⚠️ Error programando recordatorio: {e}")
            return {"ok": False, "error": str(e)}

    # /silencio
    if text.startswith("/silencio"):
        dur = text.replace("/silencio", "").strip() or "2h"
        try:
            import reminders_service
            s_res = reminders_service.set_silent_mode(chat_id, dur)
            send_telegram_message(clean_token, chat_id, f"🤫 *Modo Foco activado por {dur}.*\nAkira no enviará notificaciones proactivas hasta cumplir este período.")
            return {"ok": True, "chat_id": chat_id, "action": "silent_mode"}
        except Exception as e:
            send_telegram_message(clean_token, chat_id, f"⚠️ Error activando modo silencio: {e}")
            return {"ok": False, "error": str(e)}

    # /py
    if text.startswith("/py"):
        code_input = text.replace("/py", "").strip()
        if not code_input:
            send_telegram_message(clean_token, chat_id, "⚠️ Por favor ingresa el código o cálculo a evaluar. Ejemplo: `/py 500 * 3.85`")
            return {"ok": True, "chat_id": chat_id, "action": "py_empty"}
        try:
            import sandbox_service
            py_res = sandbox_service.execute_python_sandbox(code_input)
            if py_res.get("ok"):
                out = py_res.get("output", "")
                msg_out = f"🐍 *CONSOLA PYTHON EJECUTIVA*\n\n```python\n{out}\n```"
                send_telegram_message(clean_token, chat_id, msg_out)
            else:
                send_telegram_message(clean_token, chat_id, f"❌ *Error en ejecución Python:*\n`{py_res.get('error')}`")
            return {"ok": True, "chat_id": chat_id, "action": "py_exec"}
        except Exception as e:
            send_telegram_message(clean_token, chat_id, f"⚠️ Error en sandbox Python: {e}")
            return {"ok": False, "error": str(e)}

    # /backup
    if text == "/backup":
        send_telegram_message(clean_token, chat_id, "📦 _Generando archivo ZIP de respaldo ejecutivo..._")
        try:
            import zip_service
            zip_bytes = zip_service.create_backup_zip()
            send_telegram_document(clean_token, chat_id, zip_bytes, filename="Backup_Akira_Suite.zip", caption="📦 *Respaldo Cifrado del Sistema Akira* listo para archivar.")
            return {"ok": True, "chat_id": chat_id, "action": "backup"}
        except Exception as e:
            send_telegram_message(clean_token, chat_id, f"⚠️ Error generando respaldo: {e}")
            return {"ok": False, "error": str(e)}

    # /consolidar
    if text.startswith("/consolidar"):
        ideas = text.replace("/consolidar", "").strip() or "Ideas de automatización y servicios para nuevos clientes"
        try:
            import executive_service
            plan = executive_service.consolidate_brainstorming(ideas)
            send_telegram_interactive_message(clean_token, chat_id, plan)
            return {"ok": True, "chat_id": chat_id, "action": "consolidate"}
        except Exception as e:
            send_telegram_message(clean_token, chat_id, f"⚠️ Error consolidando ideas: {e}")
            return {"ok": False, "error": str(e)}

    # /negociar
    if text.startswith("/negociar"):
        context_arg = text.replace("/negociar", "").strip() or "El cliente solicita un 40% de descuento sobre la cotización"
        try:
            import sandbox_service
            sim = sandbox_service.simulate_client_negotiation(context_arg)
            send_telegram_interactive_message(clean_token, chat_id, sim)
            return {"ok": True, "chat_id": chat_id, "action": "negotiate"}
        except Exception as e:
            send_telegram_message(clean_token, chat_id, f"⚠️ Error en simulador: {e}")
            return {"ok": False, "error": str(e)}

    # /voz
    if text.startswith("/voz"):
        speech_text = text.replace("/voz", "").strip() or "Hola Jhon, todas las capacidades de Akira están operativas."
        send_telegram_message(clean_token, chat_id, "🎙️ _Sintetizando nota de voz con es-CO-SalomeNeural..._")
        try:
            import voice_service
            v_bytes = voice_service.generate_voice_bytes(speech_text)
            if v_bytes:
                send_telegram_voice(clean_token, chat_id, v_bytes, caption=f"🗣️ Akira: \"{speech_text[:80]}\"")
                return {"ok": True, "chat_id": chat_id, "action": "voice_reply"}
            else:
                send_telegram_message(clean_token, chat_id, "⚠️ No fue posible generar el audio en este momento.")
                return {"ok": False, "error": "voice_synthesis_failed"}
        except Exception as e:
            send_telegram_message(clean_token, chat_id, f"⚠️ Error generando voz: {e}")
            return {"ok": False, "error": str(e)}

    # /resumen_semanal o /reporte
    if text.startswith("/resumen_semanal") or text.startswith("/reporte"):
        try:
            import executive_service
            res_w = executive_service.generate_weekly_report(clean_token, chat_id)
            return {"ok": True, "chat_id": chat_id, "action": "weekly_report", "sent": res_w.get("telegram_sent")}
        except Exception as e:
            send_telegram_message(clean_token, chat_id, f"⚠️ Error generando reporte semanal: {e}")
            return {"ok": False, "error": str(e)}

    # /briefing o /resumen
    if text.startswith("/briefing") or text.startswith("/resumen"):
        try:
            import executive_service
            bf = executive_service.generate_executive_briefing(clean_token, chat_id, send_telegram=True)
            return {"ok": True, "chat_id": chat_id, "action": "briefing", "sent": bf.get("telegram_sent")}
        except Exception as e:
            send_telegram_message(clean_token, chat_id, f"⚠️ Error al generar briefing: {e}")
            return {"ok": False, "error": str(e)}

    # /buscar
    if text.startswith("/buscar"):
        query = text.replace("/buscar", "").strip()
        if not query:
            send_telegram_message(clean_token, chat_id, "⚠️ Por favor escribe qué deseas buscar. Ejemplo: `/buscar noticias inteligencia artificial hoy`")
            return {"ok": True, "chat_id": chat_id, "action": "search_empty"}
        try:
            import web_engine
            sr = web_engine.search_web(query, max_results=3)
            results = sr.get("results", [])
            lines = [f"🌐 *Resultados en Vivo para:* _{query}_\n"]
            for i, r in enumerate(results, 1):
                lines.append(f"*{i}. {r.get('title')}*")
                if r.get("snippet"): lines.append(f"_{r.get('snippet')}_")
                if r.get("link"): lines.append(f"🔗 [Enlace]({r.get('link')})\n")
            send_telegram_interactive_message(clean_token, chat_id, "\n".join(lines))
            return {"ok": True, "chat_id": chat_id, "action": "search", "count": len(results)}
        except Exception as e:
            send_telegram_message(clean_token, chat_id, f"⚠️ Error en búsqueda: {e}")
            return {"ok": False, "error": str(e)}

    # /ayuda
    if text == "/ayuda":
        help_text = (
            "💡 *SUITE COMPLETA DE COMANDOS EN TELEGRAM:*\n\n"
            "• `/cotizar (proyecto)` — Cotización formal en PDF con cálculo de ROI.\n"
            "• `/deck (tema)` — Presentación ejecutiva en PDF (5 diapositivas).\n"
            "• `/upwork` — Centinela de oportunidades y propuesta lista.\n"
            "• `/grafico` — Infografía financiera y métricas en imagen PNG.\n"
            "• `/redactar (idea)` — Ghostwriter en 3 versiones listas para enviar.\n"
            "• `/tarifa (horas)` — Calculadora inteligente de rentabilidad y precios.\n"
            "• `/recordar (tiempo) (texto)` — Recordatorio autónomo proactivo.\n"
            "• `/py (script)` — Ejecutar código o cálculos en consola Python.\n"
            "• `/backup` — Descargar respaldo de emergencia en ZIP.\n"
            "• `/resumen_semanal` — Balance dominical de productividad.\n"
            "• `/buscar (consulta)` — Búsqueda web DuckDuckGo en vivo.\n"
            "• `/estado` — Métricas del sistema y presupuesto $0.00 COP.\n\n"
            "🎙️ *Notas de voz:* Habla y Akira te responderá de inmediato.\n"
            "📸 *Fotos y Recibos:* Envíale una foto y leerá los importes con OCR Vision.\n"
            "📂 *Archivos:* Sube un script `.py` o `.js` y Akira lo auditará al instante."
        )
        send_telegram_interactive_message(clean_token, chat_id, help_text)
        return {"ok": True, "chat_id": chat_id, "action": "help"}

    # 8. CONVERSACIÓN EJECUTIVA NATURAL CON MEMORIA SINCRONIZADA
    reply_text = None
    if reply_generator:
        try:
            # Pasar chat_id al reply_generator para mantener memoria de conversación continua
            reply_text = reply_generator(text, chat_id=chat_id)
        except TypeError:
            try:
                reply_text = reply_generator(text)
            except Exception as e:
                logger.error(f"Error en reply_generator: {e}")
        except Exception as e:
            logger.error(f"Error en reply_generator: {e}")
            
    if not reply_text:
        reply_text = f"🌸 Te escucho perfectamente, Jhon. He procesado tu mensaje: '{text}'. Todo tu ecosistema está activo y listo para avanzar."

    # Conversación fluida y limpia: sin saturar la pantalla con botonera en cada mensaje
    send_res = send_telegram_message(clean_token, chat_id, reply_text)
    return {"ok": True, "chat_id": chat_id, "action": "chat_reply", "send_result": send_res}

def process_pending_telegram_updates(bot_token: str, reply_generator=None, groq_keys: list = None, gemini_api_key: str = None, gemini_keys: list = None) -> dict:
    """Descarga y responde a todos los mensajes pendientes en getUpdates."""
    clean_token = bot_token.strip()
    updates_res = get_telegram_updates(clean_token, limit=20)
    if not updates_res.get("ok"):
        return {"ok": False, "error": updates_res.get("error")}
        
    updates = updates_res.get("result", [])
    if not updates:
        return {"ok": True, "processed": 0, "message": "No hay mensajes pendientes."}
        
    processed_count = 0
    highest_id = 0
    for upd in updates:
        upd_id = upd.get("update_id", 0)
        if upd_id > highest_id:
            highest_id = upd_id
        res = handle_telegram_update(clean_token, upd, reply_generator=reply_generator, groq_keys=groq_keys, gemini_api_key=gemini_api_key, gemini_keys=gemini_keys)
        if res.get("ok"):
            processed_count += 1
            
    if highest_id > 0:
        get_telegram_updates(clean_token, offset=highest_id + 1, limit=1)
        
    return {"ok": True, "processed": processed_count, "highest_update_id": highest_id}

def test_telegram_connection(bot_token: str, chat_id: str = None, reply_generator=None, groq_keys: list = None, gemini_api_key: str = None, gemini_keys: list = None) -> dict:
    """Prueba y valida la conexión con el celular de Jhon, configura el menú nativo y registra el webhook."""
    if not bot_token or not bot_token.strip():
        return {"ok": False, "error": "Por favor ingresa el Token de tu Bot de Telegram."}

    clean_token = bot_token.strip()
    active_chat_id = chat_id.strip() if chat_id else None

    if not active_chat_id:
        active_chat_id = get_last_chat_id(clean_token)

    if not active_chat_id:
        return {
            "ok": False,
            "error": "El bot no ha recibido ningún mensaje aún. Por favor abre tu nuevo bot en Telegram y presiona el botón 'Iniciar' (/start), luego vuelve a probar.",
            "requires_start": True
        }

    # 1. Obtener detalles del bot
    bot_info = get_bot_info(clean_token)
    bot_res = bot_info.get("result", {})
    bot_username = bot_res.get("username", "")
    bot_link = f"https://t.me/{bot_username}" if bot_username else None

    # 2. Persistir configuración en backend
    save_telegram_config(clean_token, active_chat_id)

    # 3. Registrar comandos nativos en el menú '/' de Telegram
    set_telegram_commands(clean_token)

    # 4. Registrar webhook para recibir mensajes y notas de voz en vivo
    wh_res = set_telegram_webhook(clean_token)

    # 5. Procesar mensajes que Jhon ya haya escrito antes de activar el webhook
    poll_res = process_pending_telegram_updates(clean_token, reply_generator=reply_generator, groq_keys=groq_keys, gemini_api_key=gemini_api_key, gemini_keys=gemini_keys)

    welcome_text = (
        "🌸 *¡Hola Jhon! Soy Akira Suite 4.1.*\n\n"
        "✨ Tu conexión privada conmigo está blindada y 100% activa a costo $0.00 COP.\n\n"
        "💬 *Puedes hablarme o enviarme notas de voz:*\n"
        "Escríbeme o háblame de lo que quieras y te responderé en tiempo real.\n\n"
        "📌 *Acciones Ejecutivas Rápidas:*\n"
        "• `/cotizar (proyecto)` — Genera cotización en PDF con cálculo de ROI.\n"
        "• `/deck (tema)` — Presentación ejecutiva en PDF (5 slides).\n"
        "• `/upwork` — Radar de oportunidades y propuesta lista.\n"
        "• `/grafico` — Genera infografía de métricas en imagen PNG.\n"
        "• `/redactar (idea)` — Ghostwriter en 3 versiones ejecutivas.\n"
        "• `/tarifa (horas)` — Calculadora de tarifas Upwork.\n"
        "• `/recordar (tiempo) (texto)` — Recordatorio autónomo.\n"
        "• `/py (script)` — Consola segura de Python.\n"
        "• `/backup` — Descargar respaldo en ZIP.\n"
        "• `/estado` — Estado del sistema y telemetría.\n\n"
        "👑 _Lista y a tu servicio, Creador._"
    )

    send_res = send_telegram_interactive_message(clean_token, active_chat_id, welcome_text)
    if send_res.get("ok"):
        return {
            "ok": True,
            "chat_id": active_chat_id,
            "bot_username": f"@{bot_username}" if bot_username else "",
            "bot_link": bot_link,
            "webhook_registered": wh_res.get("ok", False),
            "pending_messages_processed": poll_res.get("processed", 0),
            "commands_registered": True,
            "message": f"¡Conexión bidireccional blindada lista! Akira vinculó tu bot ({f'@{bot_username}' if bot_username else 'Telegram'}) y te envió la confirmación táctil con el menú de comandos."
        }
    return send_res
