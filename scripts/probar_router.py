"""Corre los 6 mensajes de prueba del router y muestra ruta, nodos y motivo.

Uso (desde la raíz, con GOOGLE_API_KEY en .env):
    python scripts/probar_router.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.base import cargar_agente, ejecutar  # noqa: E402

MENSAJES = [
    "¿tienen la polera azul en talla M?",
    "mi pedido 4521 llegó roto",
    "hola",
    "¿cuánto cuesta el envío a Valparaíso?",
    "quiero devolver unas zapatillas",
    "¿qué hora es en Tokio?",
]


def main() -> int:
    if not os.getenv("GOOGLE_API_KEY"):
        print("Falta GOOGLE_API_KEY en .env. Pégala y vuelve a correr.", file=sys.stderr)
        return 1

    grafo = cargar_agente("router")
    for numero, mensaje in enumerate(MENSAJES, start=1):
        resultado = ejecutar(grafo, mensaje, thread_id=f"prueba-{numero}")
        print(f'{numero}. "{mensaje}"')
        print(f"   ruta:   {resultado['estado'].get('ruta')}")
        print(f"   nodos:  {' → '.join(resultado['nodos'])}")
        print(f"   motivo: {resultado['estado'].get('motivo')}")
        print(f"   resp.:  {resultado['respuesta']}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
