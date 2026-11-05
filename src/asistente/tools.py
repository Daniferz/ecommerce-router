"""Herramientas (@tool) y utilidades del agente `asistente`."""
from __future__ import annotations

from langchain_core.tools import tool


@tool
def contar_palabras(texto: str) -> int:
    """Cuenta las palabras de un texto."""
    return len(texto.split())


def pulir_texto(texto: str) -> str:
    """Normaliza espacios y quita saltos de línea sobrantes."""
    return " ".join(texto.split())
