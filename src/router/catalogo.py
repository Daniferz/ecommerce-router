"""Acceso de solo lectura al catálogo de la tienda en Postgres.

Usa la misma DATABASE_URL que el checkpointer. Cada consulta abre una conexión
y la cierra al terminar.
"""
from __future__ import annotations

from typing import Any, Sequence

from src.router.db import conexion, url_base

MENSAJE_SIN_BASE = "catálogo no disponible"


def _solo_select(sql: str) -> bool:
    """True si el SQL es un único SELECT (sin otros statements)."""
    limpio = sql.strip()
    if not limpio.upper().startswith("SELECT"):
        return False
    return ";" not in limpio.rstrip(";")


def consultar(sql: str, parametros: Sequence[Any] = ()) -> list[dict]:
    """Ejecuta un SELECT parametrizado y devuelve las filas como diccionarios.

    El SQL lo escribe siempre el código (nunca el usuario ni el modelo) y los
    valores viajan como parámetros. Solo se permiten consultas SELECT.
    """
    if not _solo_select(sql):
        raise ValueError("Solo se permiten consultas SELECT.")
    if not url_base():
        raise RuntimeError("DATABASE_URL no está definida.")

    with conexion() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, parametros)
            return cursor.fetchall()
