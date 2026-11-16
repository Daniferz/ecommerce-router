"""Reclamos de postventa: Postgres si hay base; si no, memoria del proceso.

La tabla se crea sola (`CREATE TABLE IF NOT EXISTS`) y se llama a
`asegurar_tabla()` al arrancar la API y la CLI. Si no hay DATABASE_URL o la
base falla, los reclamos quedan en memoria y se avisa en el log.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from src.router.db import conexion, url_base

logger = logging.getLogger("ecommerce.reclamos")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(_handler)

_TABLA = """\
CREATE TABLE IF NOT EXISTS reclamos (
    ticket TEXT PRIMARY KEY,
    numero_pedido TEXT NOT NULL,
    motivo TEXT NOT NULL,
    detalle TEXT NOT NULL,
    thread_id TEXT NOT NULL DEFAULT '',
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""

_RECLAMOS_RAM: list[dict[str, Any]] = []
_TABLA_LISTA = False
_AVISO_MEMORIA = False


def _avisar_memoria(motivo: str) -> None:
    """Registra una sola vez que los reclamos no van a Postgres."""
    global _AVISO_MEMORIA
    if not _AVISO_MEMORIA:
        logger.warning(
            "%s Los reclamos se guardan en memoria y se pierden al reiniciar.",
            motivo,
        )
        _AVISO_MEMORIA = True


def asegurar_tabla() -> bool:
    """Crea la tabla de reclamos si hay base.

    Devuelve True si los reclamos se están guardando en Postgres.
    """
    global _TABLA_LISTA
    if _TABLA_LISTA:
        return True
    if not url_base():
        _avisar_memoria("DATABASE_URL no está definida.")
        return False
    try:
        with conexion() as conn:
            with conn.cursor() as cursor:
                cursor.execute(_TABLA)
        _TABLA_LISTA = True
        logger.info("Tabla de reclamos lista en Postgres.")
        return True
    except Exception as error:  # noqa: BLE001 - la API no debe caerse por esto
        _avisar_memoria(
            f"No se pudo preparar la tabla de reclamos "
            f"({type(error).__name__}: {error})."
        )
        return False


def guardar_reclamo(
    numero_pedido: str,
    motivo: str,
    detalle: str,
    thread_id: str = "",
) -> str:
    """Guarda un reclamo y devuelve su número de ticket."""
    ticket = f"REC-{datetime.now():%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"
    fila = {
        "ticket": ticket,
        "numero_pedido": numero_pedido,
        "motivo": motivo,
        "detalle": detalle,
        "thread_id": thread_id,
        "creado_en": datetime.now(timezone.utc).isoformat(),
    }

    if asegurar_tabla():
        try:
            with conexion() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO reclamos "
                        "(ticket, numero_pedido, motivo, detalle, thread_id) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (ticket, numero_pedido, motivo, detalle, thread_id),
                    )
            return ticket
        except Exception as error:  # noqa: BLE001 - fallback a memoria
            _avisar_memoria(
                f"No se pudo guardar el reclamo en Postgres "
                f"({type(error).__name__}: {error})."
            )

    _RECLAMOS_RAM.append(fila)
    return ticket


def listar_reclamos() -> list[dict]:
    """Devuelve los reclamos, del más nuevo al más viejo."""
    if asegurar_tabla():
        try:
            with conexion() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT ticket, numero_pedido, motivo, detalle, "
                        "thread_id, creado_en "
                        "FROM reclamos "
                        "ORDER BY creado_en DESC"
                    )
                    return cursor.fetchall()
        except Exception as error:  # noqa: BLE001 - fallback a memoria
            _avisar_memoria(
                f"No se pudieron leer los reclamos de Postgres "
                f"({type(error).__name__}: {error})."
            )
    return list(_RECLAMOS_RAM)
