"""Arranque aislado del Persistence Service. Corre en un hilo: NUNCA bloquea ni tumba el chat.

Estados: starting -> ok | not_configured | error. El detalle del error va a los logs de Render,
al endpoint solo sale el tipo de excepcion (sin host, usuario ni claves).
"""
from __future__ import annotations

import os
import threading
import time
import uuid
from datetime import datetime, timezone

from .selftest import run_logic_tests, run_restart_probe, summarize
from .service import PersistenceService

STATE = {
    "state": "starting",
    "boot_id": uuid.uuid4().hex,
    "started_at": datetime.now(timezone.utc).isoformat(),
    "configured": False,
    "connected": False,
    "migrations_applied_now": [],
    "error_type": None,
    "selftest_this_boot": None,
    "service": None,
}


def _default_backend():
    """Crea pool, migra y devuelve un repositorio Postgres. Lanza excepcion si no hay DATABASE_URL."""
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        return None
    from .postgres import PostgresRepository, make_pool, migrate  # import perezoso: psycopg solo se necesita aqui
    pool = make_pool(url)
    try:
        pool.open(wait=True, timeout=45)
        STATE["migrations_applied_now"] = migrate(pool)
        repo = PostgresRepository(pool)
        repo.ping()
    except Exception:
        try:
            pool.close()  # no dejar pools abiertos si el intento falla
        except Exception:
            pass
        raise
    return repo, (lambda: PostgresRepository(make_pool_open(url)))


_EXTRA_POOLS = []


def make_pool_open(url):
    """Pool nuevo para el 'reinicio suave' del selftest. Se cierra al terminar las pruebas."""
    from .postgres import make_pool
    pool = make_pool(url)
    pool.open(wait=True, timeout=45)
    _EXTRA_POOLS.append(pool)
    return pool


def _close_extra_pools():
    while _EXTRA_POOLS:
        try:
            _EXTRA_POOLS.pop().close()
        except Exception:
            pass


def boot(backend_factory=None, attempts=3, wait_seconds=(5, 10), sleep=time.sleep):
    backend_factory = backend_factory or _default_backend
    STATE["configured"] = bool(os.getenv("DATABASE_URL", "").strip()) or backend_factory is not _default_backend
    if not STATE["configured"]:
        STATE["state"] = "not_configured"
        return
    last = None
    for i in range(attempts):
        try:
            backend = backend_factory()
            if backend is None:
                STATE["state"] = "not_configured"
                return
            repo, fresh_repo_factory = backend
            service = PersistenceService(repo)
            service.health()
            STATE.update(service=service, connected=True, state="ok", error_type=None)
            break
        except Exception as e:  # Neon puede estar despertando: se reintenta
            last = e
            STATE.update(state="starting" if i < attempts - 1 else "error", error_type=type(e).__name__)
            print(f"[persistence] intento {i + 1}/{attempts} fallo: {type(e).__name__}: {str(e)[:200]}", flush=True)
            if i < attempts - 1:
                sleep(wait_seconds[min(i, len(wait_seconds) - 1)])
    else:
        return
    if os.getenv("AKIRA_PERSISTENCE_SELFTEST", "").strip() == "1":
        try:
            fresh = (lambda: PersistenceService(fresh_repo_factory()))
            results = run_logic_tests(service, fresh_service_factory=fresh)
            results.append(run_restart_probe(service, STATE["boot_id"]))
            summary = summarize(results)
            failed = summary.get("FAIL", 0) > 0
            service.record_audit("selftest", "selftest.logic", "persistence", None,
                                 "failure" if failed else "success",
                                 {"boot_id": STATE["boot_id"], "summary": summary,
                                  "results": [{"test": r["test"], "status": r["status"]} for r in results]})
            STATE["selftest_this_boot"] = {"summary": summary, "results": results}
            print(f"[persistence] selftest: {summary}", flush=True)
            _close_extra_pools()
        except Exception as e:
            STATE["selftest_this_boot"] = {"summary": {"FAIL": 1}, "error_type": type(e).__name__}
            print(f"[persistence] selftest fallo: {type(e).__name__}: {str(e)[:200]}", flush=True)


def start_background():
    threading.Thread(target=boot, daemon=True, name="akira-persistence-boot").start()


def get_status():
    snap = {k: STATE[k] for k in ("state", "boot_id", "started_at", "configured", "connected",
                                  "migrations_applied_now", "error_type", "selftest_this_boot")}
    service = STATE.get("service")
    if service is not None:
        try:
            snap["backend"] = service.health()
            snap["memories_active"] = service.count_memory()
            snap["selftest_history"] = [
                {"ts": a["ts"], "action": a["action"], "status": a["status"], "detail": a["detail"]}
                for a in service.recent_audit(actor="selftest", limit=10)]
        except Exception as e:
            snap["status_error_type"] = type(e).__name__
    return snap
