"""Endpoint de solo lectura del estado de persistencia. Sin datos de memorias ni secretos.
(No se exponen lectura/escritura de memorias por HTTP hasta que exista autenticacion real.)"""
from fastapi import APIRouter

from .runtime import get_status

router = APIRouter(prefix="/api/v8/persistence", tags=["persistence-v8"])


@router.get("/status")
def persistence_status():  # def (no async): la consulta a la base corre en el pool de hilos y no bloquea el chat
    return get_status()
