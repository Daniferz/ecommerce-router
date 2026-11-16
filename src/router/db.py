"""Conexión corta a Postgres: la misma DATABASE_URL del checkpointer.

Cada consulta abre una conexión y la cierra al salir, para no consumir el cupo
de conexiones de la base.
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from psycopg import Connection, connect
from psycopg.rows import DictRow, dict_row

RAIZ = Path(__file__).resolve().parents[2]
load_dotenv(RAIZ / ".env")


def url_base() -> str:
    """DATABASE_URL sin espacios; cadena vacía si no está definida."""
    return (os.getenv("DATABASE_URL") or "").strip()


@contextmanager
def conexion() -> Iterator[Connection[DictRow]]:
    """Abre una conexión y la cierra al terminar el bloque."""
    url = url_base()
    if not url:
        raise RuntimeError("DATABASE_URL no está definida.")

    timeout = int(os.getenv("DB_TIMEOUT", "5"))
    with connect(
        url,
        row_factory=dict_row,
        connect_timeout=timeout,
        application_name="ecommerce-router",
    ) as conn:
        yield conn
