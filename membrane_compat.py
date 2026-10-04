"""AKIRA V8-B3a - Compatibility Layer: contadores REALES para la Membrana.

Reemplaza los numeros fijos (51/31/82) por conteos leidos del Persistence Service.
Reglas (Fase 4 s27-28, Contrato s3 y s20):
  - Nunca inventa cifras: si la persistencia no esta lista, dice available=False.
  - Nunca bloquea una peticion: la consulta a la base corre en un hilo aparte y la
    peticion recibe el ultimo valor conocido (stale-while-revalidate).
  - Solo cuenta memorias de origenes REALES (REAL_SOURCES); los registros del selftest
    y de la sonda de reinicio no cuentan como memoria de Akira.
  - "shared" usa el filtro del Hive del servicio: PRIVATE y SENSITIVE nunca se cuentan ahi.
  - Nunca lanza excepciones hacia el llamador.
"""
import threading
import time

REAL_SOURCES = ("akira_chat", "browser_sync", "owner_note")
TTL_OK_SECONDS = 30
TTL_ERROR_SECONDS = 10


def default_service_getter():
    """Devuelve el PersistenceService listo, o None (no cargado, arrancando o con error)."""
    try:
        from persistence import runtime
        return runtime.STATE.get("service")
    except Exception:
        return None


class MembraneCounts:
    def __init__(self, service_getter=default_service_getter, clock=time.time, spawn=None):
        self._get_service = service_getter
        self._clock = clock
        self._spawn = spawn or self._spawn_thread
        self._lock = threading.Lock()
        self._refreshing = False
        self._value = None          # ultimo resultado (ok o error)
        self._value_at = 0.0

    @staticmethod
    def _spawn_thread(fn):
        threading.Thread(target=fn, daemon=True, name="akira-membrane-count").start()

    # ---------------------------------------------------------------- consulta real
    def _query(self):
        service = self._get_service()
        if service is None:
            return {"ok": False, "reason": "persistence_not_ready"}
        try:
            flt = {"source__in": list(REAL_SOURCES)}
            total = int(service.count_memory(dict(flt)))
            shared = int(service.count_memory(dict(flt), hive=True))
            return {"ok": True, "total": total, "shared": shared}
        except Exception as e:
            return {"ok": False, "reason": "query_failed", "error_type": type(e).__name__}

    def _refresh(self):
        try:
            result = self._query()
            with self._lock:
                self._value, self._value_at = result, self._clock()
        finally:
            with self._lock:
                self._refreshing = False

    def _maybe_refresh(self):
        with self._lock:
            ttl = TTL_OK_SECONDS if (self._value or {}).get("ok") else TTL_ERROR_SECONDS
            stale = self._value is None or (self._clock() - self._value_at) >= ttl
            if not stale or self._refreshing:
                return
            self._refreshing = True
        try:
            self._spawn(self._refresh)
        except Exception:
            with self._lock:
                self._refreshing = False

    # ---------------------------------------------------------------- API publica
    def snapshot(self):
        """Forma compatible con el count() antiguo, pero con datos reales. No bloquea."""
        try:
            self._maybe_refresh()
            with self._lock:
                v = self._value
                age = None if v is None else round(self._clock() - self._value_at, 1)
            if v is not None and v.get("ok"):
                shared, total = v["shared"], v["total"]
                return {"available": True, "source": "persistence", "age_seconds": age,
                        "shared": shared, "knowledge": 0, "total": total,
                        "membrana": {"shared": shared, "knowledge": 0, "vectors": 0, "hive": shared},
                        "identity": "Akira"}
            reason = "warming_up" if v is None else v.get("reason", "unknown")
            out = {"available": False, "source": "persistence", "reason": reason, "age_seconds": age,
                   "shared": 0, "knowledge": 0, "total": 0,
                   "membrana": {"shared": 0, "knowledge": 0, "vectors": 0, "hive": 0},
                   "identity": "Akira"}
            if v is not None and v.get("error_type"):
                out["error_type"] = v["error_type"]
            return out
        except Exception as e:
            return {"available": False, "source": "persistence", "reason": "internal_error",
                    "error_type": type(e).__name__, "shared": 0, "knowledge": 0, "total": 0,
                    "membrana": {"shared": 0, "knowledge": 0, "vectors": 0, "hive": 0},
                    "identity": "Akira"}
