"""Pregunta directo al agente de redes (A2A) e imprime su respuesta completa.

Uso:
    python scripts/ver_redes.py "qué se dice de Samsung"
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.router.a2a_redes import MENSAJE_SIN_REDES, preguntar_redes  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    pregunta = " ".join(sys.argv[1:] if argv is None else argv).strip()
    if not pregunta:
        print('Uso: python scripts/ver_redes.py "pregunta"')
        return 1

    try:
        respuesta = asyncio.run(preguntar_redes(pregunta, "script-ver-redes"))
    except Exception as error:  # noqa: BLE001 - la terminal muestra el motivo
        print(f"{MENSAJE_SIN_REDES}: {error}")
        return 1

    if not respuesta:
        print("El agente de redes no devolvió texto.")
        return 0

    print(respuesta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
