"""
AKIRA TELEGRAM NOTIFICATION & CONVERSATIONAL SERVICE v2.0
Zero-Cost ($0.00 COP/USD) private communication channel with Jhon's mobile phone.
Uses the official Telegram Bot API (free, unlimited, instant).
Supports both instant Webhooks and Polling for bidirectional 2-way chat.
"""

import urllib.request
import urllib.parse
import json
import logging

logger = logging.getLogger("akira.telegram")

def get_last_chat_id(bot_token: str) -> str | None:
    """
    Auto-detecta el chat_id de Jhon consultando las últimas interacciones del bot.
    Permite que Jhon simplemente le dé '/start' a su bot sin tener que buscar IDs numéricos.
    """
    clean_token = bot_token.strip()
    url = f"https://api.telegram.org/bot{clean_token}/getUpdates"
    req = urllib.request.Request(url, headers={"User-Agent": "AkiraAssistant/2.0"})
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
            "User-Agent": "AkiraAssistant/2.0"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("ok"):
                return {"ok": True, "chat_id": clean_chat_id, "message_id": result["result"].get("message_id")}
            return {"ok": False, "error": result.get("description", "Error desconocido en Telegram")}
    except urllib.error.HTTPError as e:
        # Fallback a texto plano si falla el parse_mode
        if parse_mode:
            return send_telegram_message(clean_token, clean_chat_id, clean_text, parse_mode=None)
        try:
            err_data = json.loads(e.read().decode("utf-8"))
            return {"ok": False, "error": err_data.get("description", str(e))}
        except Exception:
            return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def set_telegram_webhook(bot_token: str, base_url: str = "https://akira-empresa.onrender.com") -> dict:
    """
    Registra el webhook de Telegram apuntando al backend en Render.
    Permite que cuando Jhon le escriba al bot, Telegram notifique inmediatamente a Akira.
    """
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
        headers={"Content-Type": "application/json", "User-Agent": "AkiraAssistant/2.0"}
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
    req = urllib.request.Request(url, headers={"User-Agent": "AkiraAssistant/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            return {"ok": bool(res.get("ok")), "result": res.get("result", [])}
    except Exception as e:
        return {"ok": False, "error": str(e), "result": []}

def handle_telegram_update(bot_token: str, update: dict, reply_generator=None) -> dict:
    """
    Procesa un mensaje recibido desde Telegram y responde inmediatamente.
    Soporta /start, /briefing, /sentinel y conversación ejecutiva natural.
    """
    clean_token = bot_token.strip()
    msg = update.get("message") or update.get("channel_post") or update.get("edited_message")
    if not msg:
        return {"ok": False, "reason": "no_message_in_update"}
        
    chat = msg.get("chat", {})
    chat_id = str(chat.get("id", ""))
    if not chat_id:
        return {"ok": False, "reason": "missing_chat_id"}
        
    text = str(msg.get("text", "")).strip()
    if not text:
        send_telegram_message(clean_token, chat_id, "🌸 He recibido tu archivo multimedia, Jhon. Estoy en línea y lista para continuar.")
        return {"ok": True, "chat_id": chat_id, "action": "media_received"}

    # Comando /start
    if text == "/start":
        welcome_text = (
            "🌸 *¡Hola Jhon! Soy Akira.*\n\n"
            "✨ Tu conexión privada conmigo está 100% activa a costo $0.00 COP.\n\n"
            "💬 *Ya puedes hablarme directamente por aquí:*\n"
            "Escríbeme lo que quieras (preguntas, ideas, proyectos o consultas) y te responderé en tiempo real.\n\n"
            "📌 *Comandos directos:*\n"
            "• `/briefing` — Para recibir tu resumen ejecutivo matutino.\n"
            "• `/sentinel` — Para ver oportunidades frescas del mercado.\n\n"
            "👑 _Lista y a tu servicio, Creador._"
        )
        send_telegram_message(clean_token, chat_id, welcome_text)
        return {"ok": True, "chat_id": chat_id, "action": "start"}

    # Comando /briefing
    if text.startswith("/briefing"):
        try:
            import executive_service
            bf = executive_service.generate_executive_briefing(clean_token, chat_id, send_telegram=True)
            return {"ok": True, "chat_id": chat_id, "action": "briefing", "sent": bf.get("telegram_sent")}
        except Exception as e:
            send_telegram_message(clean_token, chat_id, f"⚠️ Error al generar briefing: {e}")
            return {"ok": False, "error": str(e)}

    # Comando /sentinel o /oportunidades
    if text.startswith("/sentinel") or text.startswith("/oportunidades"):
        try:
            import executive_service
            st = executive_service.run_opportunity_sentinel(telegram_token=clean_token, chat_id=chat_id)
            return {"ok": True, "chat_id": chat_id, "action": "sentinel", "sent": st.get("telegram_sent")}
        except Exception as e:
            send_telegram_message(clean_token, chat_id, f"⚠️ Error al ejecutar centinela: {e}")
            return {"ok": False, "error": str(e)}

    # Conversación ejecutiva natural
    reply_text = None
    if reply_generator:
        try:
            reply_text = reply_generator(text)
        except Exception as e:
            logger.error(f"Error en reply_generator: {e}")
            
    if not reply_text:
        reply_text = f"🌸 Te escucho fuerte y claro, Jhon. Recibí tu consulta: '{text}'. Todo tu sistema está activo y a tu disposición."

    send_res = send_telegram_message(clean_token, chat_id, reply_text)
    return {"ok": True, "chat_id": chat_id, "action": "chat_reply", "send_result": send_res}

def process_pending_telegram_updates(bot_token: str, reply_generator=None) -> dict:
    """
    Descarga y responde a todos los mensajes pendientes en getUpdates.
    Marca el offset para que Telegram sepa que fueron atendidos.
    """
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
        res = handle_telegram_update(clean_token, upd, reply_generator=reply_generator)
        if res.get("ok"):
            processed_count += 1
            
    # Marcar los updates como leídos avanzando el offset
    if highest_id > 0:
        get_telegram_updates(clean_token, offset=highest_id + 1, limit=1)
        
    return {"ok": True, "processed": processed_count, "highest_update_id": highest_id}

def test_telegram_connection(bot_token: str, chat_id: str = None, reply_generator=None) -> dict:
    """
    Prueba y valida la conexión con el celular de Jhon.
    Auto-detecta chat_id, registra el Webhook para recibir mensajes,
    y procesa de inmediato cualquier mensaje que Jhon ya haya enviado.
    """
    if not bot_token or not bot_token.strip():
        return {"ok": False, "error": "Por favor ingresa el Token de tu Bot de Telegram."}

    clean_token = bot_token.strip()
    active_chat_id = chat_id.strip() if chat_id else None

    # Auto-detección si no se suministró chat_id
    if not active_chat_id:
        active_chat_id = get_last_chat_id(clean_token)

    if not active_chat_id:
        return {
            "ok": False,
            "error": "El bot no ha recibido ningún mensaje aún. Por favor abre tu nuevo bot en Telegram y presiona el botón 'Iniciar' (/start), luego vuelve a probar.",
            "requires_start": True
        }

    # 1. Registrar webhook para recibir mensajes en vivo
    wh_res = set_telegram_webhook(clean_token)

    # 2. Procesar cualquier mensaje que Jhon ya haya escrito antes de activar el webhook
    poll_res = process_pending_telegram_updates(clean_token, reply_generator=reply_generator)

    welcome_text = (
        "🌸 *¡Hola Jhon! Soy Akira.*\n\n"
        "✨ Tu conexión privada con mi sistema está activa y funcionando con éxito a costo $0.00 COP.\n\n"
        "💬 *Ya puedes hablarme directamente por aquí:*\n"
        "Escríbeme lo que quieras (preguntas, ideas, proyectos o consultas) y te responderé en tiempo real.\n\n"
        "📌 *Comandos directos:*\n"
        "• `/briefing` — Para recibir tu resumen ejecutivo matutino.\n"
        "• `/sentinel` — Para ver oportunidades frescas del mercado.\n\n"
        "👑 _Lista y a tu servicio, Creador._"
    )

    send_res = send_telegram_message(clean_token, active_chat_id, welcome_text)
    if send_res.get("ok"):
        return {
            "ok": True,
            "chat_id": active_chat_id,
            "webhook_registered": wh_res.get("ok", False),
            "pending_messages_processed": poll_res.get("processed", 0),
            "message": "¡Conexión bidireccional lista! Akira te envió un mensaje de bienvenida y ya puedes chatear con ella desde Telegram."
        }
    return send_res
