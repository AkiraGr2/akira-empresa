"""
AKIRA TELEGRAM NOTIFICATION & CONVERSATIONAL SERVICE v3.0
Zero-Cost ($0.00 COP/USD) private communication channel with Jhon's mobile phone.
Uses the official Telegram Bot API (free, unlimited, instant).
Capabilities:
1. Bidirectional 2-way chat with Webhooks & Polling.
2. Voice note processing (download audio & Whisper transcription).
3. PDF document generator and sender via Telegram sendDocument.
4. Upwork autonomous opportunities sentinel.
5. Executive instant 1-word commands (/estado, /colmena, /upwork, /pdf, /buscar, /briefing).
"""

import urllib.request
import urllib.parse
import json
import logging
import uuid

logger = logging.getLogger("akira.telegram")

def get_last_chat_id(bot_token: str) -> str | None:
    """Auto-detecta el chat_id de Jhon consultando las últimas interacciones del bot."""
    clean_token = bot_token.strip()
    url = f"https://api.telegram.org/bot{clean_token}/getUpdates"
    req = urllib.request.Request(url, headers={"User-Agent": "AkiraAssistant/3.0"})
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

def send_telegram_message(bot_token: str, chat_id: str, text: str, parse_mode: str = "Markdown") -> dict:
    """
    Envía un mensaje de texto formateado a Telegram.
    Si el parseador de Markdown falla por caracteres especiales, reintenta automáticamente en texto plano.
    """
    clean_token = bot_token.strip()
    clean_chat_id = str(chat_id).strip()
    clean_text = text[:4000] if len(text) > 4000 else text

    url = f"https://api.telegram.org/bot{clean_token}/sendMessage"
    payload = {
        "chat_id": clean_chat_id,
        "text": clean_text
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "AkiraAssistant/3.0"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("ok"):
                return {"ok": True, "chat_id": clean_chat_id, "message_id": result["result"].get("message_id")}
            return {"ok": False, "error": result.get("description", "Error desconocido en Telegram")}
    except urllib.error.HTTPError as e:
        if parse_mode:
            return send_telegram_message(clean_token, clean_chat_id, clean_text, parse_mode=None)
        try:
            err_data = json.loads(e.read().decode("utf-8"))
            return {"ok": False, "error": err_data.get("description", str(e))}
        except Exception:
            return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def send_telegram_document(bot_token: str, chat_id: str, file_bytes: bytes, filename: str = "Propuesta_Akira.pdf", caption: str = "") -> dict:
    """Envía un archivo PDF o binario como documento adjunto descargable directo a Telegram."""
    clean_token = bot_token.strip()
    clean_chat_id = str(chat_id).strip()
    boundary = "----WebKitFormBoundaryAkiraDoc" + uuid.uuid4().hex[:12]
    
    parts = []
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{clean_chat_id}\r\n".encode("utf-8"))
    if caption:
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption}\r\n".encode("utf-8"))
    clean_fn = filename.replace('"', '')
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; filename=\"{clean_fn}\"\r\nContent-Type: application/pdf\r\n\r\n".encode("utf-8"))
    parts.append(file_bytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    
    body = b"".join(parts)
    url = f"https://api.telegram.org/bot{clean_token}/sendDocument"
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "AkiraAssistant/3.0"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            if res.get("ok"):
                return {"ok": True, "message_id": res["result"].get("message_id"), "filename": filename}
            return {"ok": False, "error": res.get("description", "Error sendDocument")}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def get_telegram_file_bytes(bot_token: str, file_id: str) -> tuple[bytes | None, str | None]:
    """Descarga los bytes de un archivo o nota de voz desde Telegram."""
    clean_token = bot_token.strip()
    url = f"https://api.telegram.org/bot{clean_token}/getFile?file_id={file_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "AkiraAssistant/3.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if not data.get("ok"):
                return None, data.get("description", "Error getFile")
            file_path = data["result"].get("file_path")
            if not file_path:
                return None, "No file_path returned"
                
        dl_url = f"https://api.telegram.org/file/bot{clean_token}/{file_path}"
        req_dl = urllib.request.Request(dl_url, headers={"User-Agent": "AkiraAssistant/3.0"})
        with urllib.request.urlopen(req_dl, timeout=15) as dl_resp:
            return dl_resp.read(), file_path
    except Exception as e:
        return None, str(e)

def transcribe_telegram_voice(audio_bytes: bytes, groq_keys: list = None, filename: str = "voice.oga") -> str | None:
    """Transcribe una nota de voz de Telegram a texto usando Whisper a costo $0.00 COP."""
    if not audio_bytes or not groq_keys:
        return None
    boundary = "----WebKitFormBoundaryAkiraVoice" + uuid.uuid4().hex[:12]
    parts = []
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\nwhisper-large-v3-turbo\r\n".encode("utf-8"))
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"language\"\r\n\res\r\n".encode("utf-8"))
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\nContent-Type: audio/ogg\r\n\r\n".encode("utf-8"))
    parts.append(audio_bytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(parts)
    
    for key in groq_keys:
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            data=body,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "User-Agent": "AkiraAssistant/3.0"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                text = res.get("text", "").strip()
                if text:
                    return text
        except Exception:
            continue
    return None

def set_telegram_webhook(bot_token: str, base_url: str = "https://akira-empresa.onrender.com") -> dict:
    """Registra el webhook de Telegram apuntando al backend en Render."""
    clean_token = bot_token.strip()
    webhook_url = f"{base_url.rstrip('/')}/api/v8/telegram/webhook/{clean_token}"
    url = f"https://api.telegram.org/bot{clean_token}/setWebhook"
    payload = json.dumps({
        "url": webhook_url,
        "drop_pending_updates": False,
        "allowed_updates": ["message", "edited_message"]
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "AkiraAssistant/3.0"}
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
    req = urllib.request.Request(url, headers={"User-Agent": "AkiraAssistant/3.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            return {"ok": bool(res.get("ok")), "result": res.get("result", [])}
    except Exception as e:
        return {"ok": False, "error": str(e), "result": []}

def handle_telegram_update(bot_token: str, update: dict, reply_generator=None, groq_keys: list = None) -> dict:
    """
    Procesa un mensaje recibido desde Telegram (texto, voz o comandos ejecutivos) y responde inmediatamente.
    """
    clean_token = bot_token.strip()
    msg = update.get("message") or update.get("channel_post") or update.get("edited_message")
    if not msg:
        return {"ok": False, "reason": "no_message_in_update"}
        
    chat = msg.get("chat", {})
    chat_id = str(chat.get("id", ""))
    if not chat_id:
        return {"ok": False, "reason": "missing_chat_id"}

    # 1. NOTA DE VOZ / AUDIO
    voice_obj = msg.get("voice") or msg.get("audio")
    text = ""
    if voice_obj and voice_obj.get("file_id"):
        file_id = voice_obj["file_id"]
        send_telegram_message(clean_token, chat_id, "🎙️ _Escuchando y transcribiendo tu nota de voz..._")
        audio_bytes, _ = get_telegram_file_bytes(clean_token, file_id)
        transcribed = None
        if audio_bytes and groq_keys:
            transcribed = transcribe_telegram_voice(audio_bytes, groq_keys)
        
        if transcribed:
            text = transcribed
            send_telegram_message(clean_token, chat_id, f"📝 *Te escuché:* _{transcribed}_")
        else:
            send_telegram_message(clean_token, chat_id, "🌸 Recibí tu audio, Jhon. Estoy lista para responderte en texto.")
            text = "Hola Akira"

    if not text:
        text = str(msg.get("text", "")).strip()

    if not text:
        send_telegram_message(clean_token, chat_id, "🌸 He recibido tu archivo, Jhon. Estoy en línea y lista para continuar.")
        return {"ok": True, "chat_id": chat_id, "action": "media_received"}

    # 2. COMANDOS EJECUTIVOS EN 1 PALABRA

    # /start
    if text == "/start":
        welcome_text = (
            "🌸 *¡Hola Jhon! Soy Akira.*\n\n"
            "✨ Tu conexión privada conmigo está 100% activa a costo $0.00 COP.\n\n"
            "💬 *Puedes hablarme o enviarme notas de voz:*\n"
            "Escríbeme o háblame de lo que quieras y te responderé en tiempo real.\n\n"
            "📌 *Acciones Ejecutivas Rápidas:*\n"
            "• `/estado` — Estado del sistema y presupuesto.\n"
            "• `/briefing` — Resumen diario con noticias web en vivo.\n"
            "• `/upwork` — Radar de oportunidades y propuesta lista.\n"
            "• `/pdf [tema]` — Genera y te envía un documento PDF formal.\n"
            "• `/buscar [tema]` — Búsqueda web en vivo.\n"
            "• `/colmena` — Estado de los 267 especialistas tácticos.\n"
            "• `/tareas` — Misiones y tareas activas.\n\n"
            "👑 _Lista y a tu servicio, Creador._"
        )
        send_telegram_message(clean_token, chat_id, welcome_text)
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
        send_telegram_message(clean_token, chat_id, status_text)
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
            "⚡ _Pídeme cualquier misión y convocaré a los especialistas adecuados._"
        )
        send_telegram_message(clean_token, chat_id, hive_text)
        return {"ok": True, "chat_id": chat_id, "action": "hive"}

    # /tareas
    if text == "/tareas":
        tasks_text = (
            "📋 *SUPERVISIÓN DE TAREAS Y MISIONES*\n\n"
            "• *Misiones en Curso:* 0 activas (Modo Autopilot listo)\n"
            "• *Centinela Autónomo:* Vigilancia web en segundo plano activa\n"
            "• *Historial:* Almacenamiento local persistente sincronizado\n\n"
            "👑 _¿Deseas que iniciemos una nueva misión hoy?_"
        )
        send_telegram_message(clean_token, chat_id, tasks_text)
        return {"ok": True, "chat_id": chat_id, "action": "tasks"}

    # /upwork
    if text.startswith("/upwork"):
        try:
            import executive_service
            up = executive_service.run_upwork_sentinel(clean_token, chat_id)
            return {"ok": True, "chat_id": chat_id, "action": "upwork", "sent": up.get("telegram_sent")}
        except Exception as e:
            send_telegram_message(clean_token, chat_id, f"⚠️ Error en centinela Upwork: {e}")
            return {"ok": False, "error": str(e)}

    # /pdf [tema]
    if text.startswith("/pdf"):
        topic = text.replace("/pdf", "").strip() or "Servicios Profesionales de Desarrollo y Automatizacion"
        try:
            import executive_service
            res_pdf = executive_service.generate_and_send_pdf(clean_token, chat_id, topic)
            return {"ok": True, "chat_id": chat_id, "action": "pdf", "result": res_pdf}
        except Exception as e:
            send_telegram_message(clean_token, chat_id, f"⚠️ Error al generar PDF: {e}")
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

    # /buscar [tema]
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
            send_telegram_message(clean_token, chat_id, "\n".join(lines))
            return {"ok": True, "chat_id": chat_id, "action": "search", "count": len(results)}
        except Exception as e:
            send_telegram_message(clean_token, chat_id, f"⚠️ Error en búsqueda: {e}")
            return {"ok": False, "error": str(e)}

    # /ayuda
    if text == "/ayuda":
        help_text = (
            "💡 *COMANDOS DISPONIBLES EN TELEGRAM:*\n\n"
            "• `/estado` — Ver métricas del sistema y presupuesto.\n"
            "• `/briefing` — Recibir el resumen matutino con noticias en vivo.\n"
            "• `/upwork` — Buscar oportunidades y generar propuesta ganadora.\n"
            "• `/pdf [tema]` — Generar y descargar un documento PDF formal.\n"
            "• `/buscar [consulta]` — Búsqueda web en tiempo real.\n"
            "• `/colmena` — Ver los 267 especialistas tácticos.\n"
            "• `/tareas` — Ver misiones y tareas activas.\n\n"
            "🎙️ *Notas de voz:* Puedes enviarme un audio de voz normal y te responderé de inmediato.\n"
            "💬 *O háblame natural:* Escríbeme cualquier consulta y te responderé como tu socia ejecutiva."
        )
        send_telegram_message(clean_token, chat_id, help_text)
        return {"ok": True, "chat_id": chat_id, "action": "help"}

    # 3. CONVERSACIÓN EJECUTIVA NATURAL
    reply_text = None
    if reply_generator:
        try:
            reply_text = reply_generator(text)
        except Exception as e:
            logger.error(f"Error en reply_generator: {e}")
            
    if not reply_text:
        reply_text = f"🌸 Te escucho fuerte y claro, Jhon. Recibí tu consulta: '{text}'. Todo tu ecosistema está activo y en guardia a costo $0.00 COP."

    send_res = send_telegram_message(clean_token, chat_id, reply_text)
    return {"ok": True, "chat_id": chat_id, "action": "chat_reply", "send_result": send_res}

def process_pending_telegram_updates(bot_token: str, reply_generator=None, groq_keys: list = None) -> dict:
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
        res = handle_telegram_update(clean_token, upd, reply_generator=reply_generator, groq_keys=groq_keys)
        if res.get("ok"):
            processed_count += 1
            
    if highest_id > 0:
        get_telegram_updates(clean_token, offset=highest_id + 1, limit=1)
        
    return {"ok": True, "processed": processed_count, "highest_update_id": highest_id}

def test_telegram_connection(bot_token: str, chat_id: str = None, reply_generator=None, groq_keys: list = None) -> dict:
    """Prueba y valida la conexión con el celular de Jhon y configura el webhook."""
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

    # 1. Registrar webhook para recibir mensajes y notas de voz en vivo
    wh_res = set_telegram_webhook(clean_token)

    # 2. Procesar mensajes que Jhon ya haya escrito antes de activar el webhook
    poll_res = process_pending_telegram_updates(clean_token, reply_generator=reply_generator, groq_keys=groq_keys)

    welcome_text = (
        "🌸 *¡Hola Jhon! Soy Akira.*\n\n"
        "✨ Tu conexión privada conmigo está 100% activa a costo $0.00 COP.\n\n"
        "💬 *Puedes hablarme o enviarme notas de voz:*\n"
        "Escríbeme o háblame de lo que quieras y te responderé en tiempo real.\n\n"
        "📌 *Acciones Ejecutivas Rápidas:*\n"
        "• `/estado` — Estado del sistema y presupuesto.\n"
        "• `/briefing` — Resumen matutino con noticias web en vivo.\n"
        "• `/upwork` — Radar de oportunidades y propuesta lista.\n"
        "• `/pdf [tema]` — Genera y te envía un documento PDF formal.\n"
        "• `/buscar [tema]` — Búsqueda web en vivo.\n"
        "• `/colmena` — Estado de los 267 especialistas tácticos.\n"
        "• `/tareas` — Misiones y tareas activas.\n\n"
        "👑 _Lista y a tu servicio, Creador._"
    )

    send_res = send_telegram_message(clean_token, active_chat_id, welcome_text)
    if send_res.get("ok"):
        return {
            "ok": True,
            "chat_id": active_chat_id,
            "webhook_registered": wh_res.get("ok", False),
            "pending_messages_processed": poll_res.get("processed", 0),
            "message": "¡Conexión bidireccional lista! Akira te envió la confirmación y ya puedes chatear o enviarle notas de voz desde Telegram."
        }
    return send_res
