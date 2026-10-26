"""
AKIRA TELEGRAM NOTIFICATION SERVICE v1.0
Zero-Cost ($0.00 COP/USD) private communication channel with Jhon's mobile phone.
Uses the official Telegram Bot API (free, unlimited, instant).
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
                # Buscar el último mensaje recibido
                for update in reversed(data["result"]):
                    msg = update.get("message") or update.get("channel_post") or update.get("edited_message")
                    if msg and "chat" in msg and "id" in msg["chat"]:
                        return str(msg["chat"]["id"])
    except Exception as e:
        logger.warning(f"Error auto-detecting Telegram chat_id: {e}")
    return None

def send_telegram_message(bot_token: str, chat_id: str, text: str) -> dict:
    """Envía un mensaje de texto formateado a Telegram."""
    clean_token = bot_token.strip()
    clean_chat_id = str(chat_id).strip()
    
    url = f"https://api.telegram.org/bot{clean_token}/sendMessage"
    payload = {
        "chat_id": clean_chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
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
        try:
            err_data = json.loads(e.read().decode("utf-8"))
            return {"ok": False, "error": err_data.get("description", str(e))}
        except Exception:
            return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def test_telegram_connection(bot_token: str, chat_id: str = None) -> dict:
    """
    Prueba y valida la conexión con el celular de Jhon.
    Si no se provee chat_id, lo auto-detecta automáticamente.
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

    welcome_text = (
        "🌸 *¡Hola Jhon! Soy Akira.*\n\n"
        "✨ Tu conexión privada con mi sistema está activa y funcionando con éxito a costo $0.00 COP.\n\n"
        "A partir de ahora podré reportarte aquí:\n"
        "• Resúmenes ejecutivos y novedades importantes.\n"
        "• Alertas de tareas o misiones completadas.\n"
        "• Notificaciones clave sin que tengas que estar frente al computador.\n\n"
        "👑 _Lista y a tu servicio, Creador._"
    )

    send_res = send_telegram_message(clean_token, active_chat_id, welcome_text)
    if send_res.get("ok"):
        return {
            "ok": True,
            "chat_id": active_chat_id,
            "message": "¡Mensaje enviado con éxito a tu Telegram! Revisa tu celular."
        }
    return send_res
