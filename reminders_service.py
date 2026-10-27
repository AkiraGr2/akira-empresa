"""
AKIRA AUTONOMOUS REMINDERS & SILENT MODE SERVICE
Zero-Cost ($0.00 COP/USD) scheduler for proactive alerts and focus periods.
Uses Python threading and memory/SQLite persistence.
"""

import time
import re
import threading
import logging

logger = logging.getLogger("akira.reminders")

# Estructura en memoria: list of {"id": str, "chat_id": str, "bot_token": str, "due_at": float, "text": str}
_ACTIVE_REMINDERS = []
_SILENT_UNTIL = {}  # chat_id -> timestamp
_LOCK = threading.Lock()
_WORKER_STARTED = False

def parse_time_duration(time_str: str) -> int:
    """
    Parsea cadenas como '30s', '15m', '2h', '1d' o '10' (por defecto minutos).
    Retorna los segundos correspondientes.
    """
    clean = time_str.strip().lower()
    match = re.match(r"^(\d+)\s*([smhd]?)$", clean)
    if not match:
        return 0
    val = int(match.group(1))
    unit = match.group(2)
    if unit == "s":
        return val
    elif unit == "m" or unit == "":
        return val * 60
    elif unit == "h":
        return val * 3600
    elif unit == "d":
        return val * 86400
    return 0

def add_reminder(bot_token: str, chat_id: str, duration_str: str, text: str) -> dict:
    """Registra un recordatorio autónomo que se disparará tras el tiempo indicado."""
    seconds = parse_time_duration(duration_str)
    if seconds <= 0:
        return {"ok": False, "error": "Formato de tiempo no válido. Usa ej: '15m', '2h', '30s'."}
    
    due_at = time.time() + seconds
    rem_id = f"rem_{int(due_at)}_{len(_ACTIVE_REMINDERS)}"
    
    with _LOCK:
        _ACTIVE_REMINDERS.append({
            "id": rem_id,
            "bot_token": bot_token,
            "chat_id": str(chat_id),
            "due_at": due_at,
            "text": text.strip()
        })
    
    _ensure_worker_started()
    return {
        "ok": True,
        "reminder_id": rem_id,
        "seconds": seconds,
        "due_at": due_at,
        "text": text.strip()
    }

def set_silent_mode(chat_id: str, duration_str: str = "2h") -> dict:
    """Activa el modo silencio / foco para un chat."""
    seconds = parse_time_duration(duration_str)
    if seconds <= 0:
        seconds = 7200  # 2 horas por defecto
    silent_until = time.time() + seconds
    with _LOCK:
        _SILENT_UNTIL[str(chat_id)] = silent_until
    return {"ok": True, "chat_id": str(chat_id), "silent_until": silent_until, "seconds": seconds}

def is_in_silent_mode(chat_id: str) -> bool:
    """Verifica si el usuario se encuentra actualmente en modo silencio."""
    with _LOCK:
        silent_until = _SILENT_UNTIL.get(str(chat_id), 0)
        return time.time() < silent_until

def disable_silent_mode(chat_id: str) -> dict:
    """Desactiva manualmente el modo silencio."""
    with _LOCK:
        if str(chat_id) in _SILENT_UNTIL:
            del _SILENT_UNTIL[str(chat_id)]
    return {"ok": True, "chat_id": str(chat_id), "silent": False}

def _worker_loop():
    """Bucle autónomo centinela que revisa y dispara recordatorios pendientes."""
    while True:
        try:
            now = time.time()
            to_fire = []
            with _LOCK:
                remaining = []
                for r in _ACTIVE_REMINDERS:
                    if r["due_at"] <= now:
                        to_fire.append(r)
                    else:
                        remaining.append(r)
                _ACTIVE_REMINDERS.clear()
                _ACTIVE_REMINDERS.extend(remaining)

            for r in to_fire:
                chat_id = r["chat_id"]
                token = r["bot_token"]
                msg_text = (
                    f"⏰ *RECORDATORIO AUTÓNOMO DE AKIRA*\n\n"
                    f"Jhon, me pediste recordarte:\n"
                    f"📌 *{r['text']}*\n\n"
                    f"👑 _Lista para continuar a tu orden, Creador._"
                )
                try:
                    import telegram_service
                    telegram_service.send_telegram_message(token, chat_id, msg_text)
                except Exception as e:
                    logger.warning(f"Error despachando recordatorio {r['id']}: {e}")
        except Exception as e:
            logger.error(f"Error en bucle de recordatorios: {e}")
        time.sleep(2)

def _ensure_worker_started():
    global _WORKER_STARTED
    with _LOCK:
        if not _WORKER_STARTED:
            t = threading.Thread(target=_worker_loop, daemon=True, name="AkiraRemindersWorker")
            t.start()
            _WORKER_STARTED = True


def get_pending_tasks(chat_id: str) -> list:
    """Retorna las tareas/recordatorios pendientes para el chat."""
    now = time.time()
    with _LOCK:
        return [
            dict(r) for r in _ACTIVE_REMINDERS
            if str(r.get("chat_id")) == str(chat_id) and r.get("due_at", 0) > now
        ]

def complete_task(reminder_id: str) -> bool:
    """Marca y remueve una tarea/recordatorio completado."""
    with _LOCK:
        for i, r in enumerate(_ACTIVE_REMINDERS):
            if r.get("id") == reminder_id:
                _ACTIVE_REMINDERS.pop(i)
                return True
    return False
