"""Autopruebas de Fase 4/5. Cada resultado: PASS, FAIL, PENDING o N/A. Nada se da por bueno sin comprobarlo.

- run_logic_tests: pruebas de comportamiento (validacion, idempotencia, versiones, privacidad, rollback).
- run_restart_probe: prueba REAL de reinicio. Un proceso escribe una sonda; otro proceso distinto la relee.
"""
from __future__ import annotations

import uuid

from .core import ConflictError, PersistenceError, ValidationError, new_id, validate_memory

PROBE_KEY = "selftest:restart-probe:v1"
PROBE_CONTENT = "AKIRA selftest restart probe v1: si puedes leer esto tras un reinicio, la persistencia funciona."


class _Abort(Exception):
    pass


def _res(name, ok, detail):
    return {"test": name, "status": "PASS" if ok else "FAIL", "detail": detail}


def _mem(marker, **over):
    base = {"content": f"selftest {marker}", "memory_type": "system", "importance": 1, "confidence": 1.0,
            "source": "selftest", "tags": ["selftest"], "privacy_level": "PRIVATE"}
    base.update(over)
    return base


def _guard(name, fn):
    try:
        return fn()
    except Exception as e:  # un fallo de la prueba es un FAIL, no un crash
        return _res(name, False, f"excepcion {type(e).__name__}: {str(e)[:120]}")


def run_logic_tests(service, fresh_service_factory=None):
    """fresh_service_factory: opcional, devuelve un servicio con conexiones nuevas ('reinicio suave')."""
    created_ids = []
    results = []

    def t_memory_persistence():
        name = "TEST_MEMORY_PERSISTENCE (reinicio suave)"
        r = service.save_memory(_mem(uuid.uuid4().hex), actor="selftest")
        rec = r["record"]
        created_ids.append(rec["id"])
        if r["outcome"] != "created" or not rec["id"].startswith("mem_"):
            return _res(name, False, "no se creo con ID valido")
        if not service.exists_memory(rec["id"]):
            return _res(name, False, "exists devolvio falso")
        if service.get_memory(rec["id"])["content"] != rec["content"]:
            return _res(name, False, "contenido distinto al releer")
        other = fresh_service_factory() if fresh_service_factory else service
        again = other.get_memory(rec["id"])
        ok = again is not None and again["content"] == rec["content"] and again["version"] == 1
        return _res(name, ok, "releido con servicio/conexiones nuevas" if fresh_service_factory
                    else "releido con el mismo servicio (no prueba reinicio)")

    def t_idempotent():
        name = "TEST_IDEMPOTENT_SYNC"
        key = f"selftest:idem:{uuid.uuid4().hex}"
        a = service.save_memory(_mem("idem"), actor="selftest", idempotency_key=key)
        b = service.save_memory(_mem("idem"), actor="selftest", idempotency_key=key)
        created_ids.append(a["record"]["id"])
        n = service.count_memory({"idempotency_key": key})
        ok = (a["outcome"] == "created" and b["outcome"] == "already_synced"
              and a["record"]["id"] == b["record"]["id"] and n == 1)
        return _res(name, ok, f"registros con la misma clave: {n}")

    def t_private():
        name = "TEST_PRIVATE_MEMORY"
        marker = f"priv-{uuid.uuid4().hex}"
        p = service.save_memory(_mem(marker, content=f"selftest {marker}", privacy_level="PRIVATE"), actor="selftest")
        s = service.save_memory(_mem(marker, content=f"selftest {marker}", privacy_level="SHAREABLE"), actor="selftest")
        created_ids.extend([p["record"]["id"], s["record"]["id"]])
        hive_ids = {r["id"] for r in service.search_memory({"text_contains": marker}, hive=True)}
        ok = p["record"]["id"] not in hive_ids and s["record"]["id"] in hive_ids
        return _res(name, ok, "PRIVATE fuera del Hive y SHAREABLE dentro (control positivo)")

    def t_versioning():
        name = "TEST_VERSIONING_CONFLICT"
        r = service.save_memory(_mem("ver"), actor="selftest")
        mid = r["record"]["id"]
        created_ids.append(mid)
        v2 = service.update_memory(mid, {"importance": 2}, expected_version=1, actor="selftest")
        try:
            service.update_memory(mid, {"importance": 3}, expected_version=1, actor="selftest")
            return _res(name, False, "la segunda actualizacion con version vieja NO dio conflicto")
        except ConflictError:
            pass
        final = service.get_memory(mid)
        return _res(name, v2["version"] == 2 and final["version"] == 2 and final["importance"] == 2,
                    "version 1->2 y conflicto detectado")

    def t_archive():
        name = "TEST_ARCHIVE_SOFT_DELETE"
        marker = f"arch-{uuid.uuid4().hex}"
        r = service.save_memory(_mem(marker), actor="selftest")
        mid = r["record"]["id"]
        created_ids.append(mid)
        a = service.archive_memory(mid, actor="selftest")
        hidden = mid not in {x["id"] for x in service.search_memory({"text_contains": marker})}
        return _res(name, a["status"] == "archived" and hidden and service.exists_memory(mid),
                    "archivada, oculta en busqueda normal y aun recuperable")

    def t_validation():
        name = "TEST_VALIDATION_REJECTS"
        before = service.count_memory({"status__in": ["active", "archived", "deleted"]})
        bad = [
            _mem("x", content="   "),
            _mem("x", privacy_level="PUBLIC"),
            _mem("x", importance=99),
            dict(_mem("x"), id="mem_forzado"),
        ]
        rejected = 0
        for b in bad:
            try:
                service.save_memory(b, actor="selftest")
            except ValidationError:
                rejected += 1
        after = service.count_memory({"status__in": ["active", "archived", "deleted"]})
        return _res(name, rejected == len(bad) and before == after, f"rechazados {rejected}/{len(bad)}, sin escrituras")

    def t_rollback():
        name = "TEST_TRANSACTION_ROLLBACK"
        rec = dict(validate_memory(_mem("rb")), id=new_id("mem"), status="active", schema_version="memory.v1")
        try:
            with service.repo.transaction() as tx:
                tx.create("memories", rec)
                raise _Abort()
        except _Abort:
            pass
        return _res(name, not service.exists_memory(rec["id"]), "el registro no existe tras el rollback")

    for name, fn in (("TEST_MEMORY_PERSISTENCE (reinicio suave)", t_memory_persistence),
                     ("TEST_IDEMPOTENT_SYNC", t_idempotent), ("TEST_PRIVATE_MEMORY", t_private),
                     ("TEST_VERSIONING_CONFLICT", t_versioning), ("TEST_ARCHIVE_SOFT_DELETE", t_archive),
                     ("TEST_VALIDATION_REJECTS", t_validation), ("TEST_TRANSACTION_ROLLBACK", t_rollback)):
        results.append(_guard(name, fn))

    results.append({"test": "TEST_RELATION_INTEGRITY", "status": "N/A",
                    "detail": "Aun no existen tablas de Experience/Learning/Knowledge (Etapas E-F)."})

    for mid in created_ids:  # dejar limpio el estado activo
        try:
            cur = service.get_memory(mid)
            if cur and cur["status"] == "active":
                service.archive_memory(mid, actor="selftest")
        except PersistenceError:
            pass
    return results


def run_restart_probe(service, boot_id):
    """Sonda de reinicio real. Primera vez: la escribe. Tras reiniciar el servicio: la relee y compara."""
    found = service.search_memory({"idempotency_key": PROBE_KEY, "status__in": ["active", "archived", "deleted"]},
                                  limit=1)
    if not found:
        r = service.save_memory(
            {"content": PROBE_CONTENT, "memory_type": "system", "importance": 1, "confidence": 1.0,
             "source": "selftest", "source_reference": boot_id, "privacy_level": "PRIVATE",
             "tags": ["selftest", "restart-probe"]},
            actor="selftest", idempotency_key=PROBE_KEY)
        service.record_audit("selftest", "selftest.restart_probe.written", "memories", r["record"]["id"],
                             "success", {"boot_id": boot_id})
        return {"test": "TEST_RESTART_PROBE", "status": "PENDING",
                "detail": "Sonda escrita. Reinicia el servicio en Render y revisa /api/v8/persistence/status."}
    rec = found[0]
    same_content = rec["content"] == PROBE_CONTENT
    other_process = rec.get("source_reference") != boot_id
    if same_content and not other_process:
        return {"test": "TEST_RESTART_PROBE", "status": "PENDING",
                "detail": "La sonda existe pero la escribio este mismo proceso. Falta reiniciar."}
    ok = same_content and other_process
    service.record_audit("selftest", "selftest.restart_probe.verified", "memories", rec["id"],
                         "success" if ok else "failure",
                         {"written_by_boot": rec.get("source_reference"), "verified_by_boot": boot_id,
                          "same_content": same_content})
    return _res("TEST_RESTART_PROBE", ok,
                "sonda escrita por otro proceso y releida intacta" if ok else "el contenido de la sonda cambio")


def summarize(results):
    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return counts
