"""Herramientas y utilidades del agente `router`.

El router no usa herramientas: solo clasifica. Aquí vive la lectura del
contexto de la tienda que necesita el nodo genérico.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

TIENDA = Path(__file__).resolve().parents[2] / "data" / "tienda.md"


@lru_cache(maxsize=1)
def contexto_tienda() -> str:
    """Contenido de data/tienda.md, como contexto del nodo genérico."""
    return TIENDA.read_text(encoding="utf-8").strip()
