"""Punto de entrada: ejecuta los agentes desde la raíz del proyecto.

Uso:
    python main.py {nombre_agente} "mensaje"
    python main.py {nombre_agente} "mensaje" --saltos   # nodos recorridos
    python main.py {nombre_agente} --diagrama           # Mermaid sin ejecutar
"""
from __future__ import annotations

import argparse
import os
import sys

from src.base import (
    abrir_memoria,
    agentes_disponibles,
    cargar_agente,
    cerrar_memoria,
    ejecutar,
)

# En Windows la consola puede ser cp1252 y romper al imprimir "→" o acentos.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ejecuta un agente del proyecto.")
    parser.add_argument("agente", help="nombre de la carpeta en src/")
    parser.add_argument("mensaje", nargs="?", default="", help="mensaje de entrada")
    parser.add_argument(
        "--saltos",
        action="store_true",
        help="imprime los nodos por los que pasó el grafo",
    )
    parser.add_argument(
        "--diagrama",
        action="store_true",
        help="imprime el Mermaid del grafo sin ejecutarlo",
    )
    parser.add_argument(
        "--hilo",
        default="cli",
        help="thread_id de la conversación (memoria); por defecto 'cli'",
    )
    args = parser.parse_args(argv)

    try:
        grafo = cargar_agente(args.agente)
    except ValueError as error:
        print(f"Disponibles: {', '.join(agentes_disponibles())}", file=sys.stderr)
        sys.exit(str(error))

    if args.diagrama:
        print(grafo.get_graph().draw_mermaid())
        return 0

    if not args.mensaje:
        sys.exit(f'Falta el mensaje: python main.py {args.agente} "hola"')

    if not os.getenv("GOOGLE_API_KEY"):
        sys.exit(
            "Falta GOOGLE_API_KEY en .env (copia .env.example a .env y pega tu clave)."
        )

    memoria = abrir_memoria()
    try:
        grafo = cargar_agente(args.agente, checkpointer=memoria.checkpointer)
        resultado = ejecutar(grafo, args.mensaje, args.hilo)
    except Exception as error:  # API caída, sin créditos, etc.
        sys.exit(f"Error al ejecutar el agente: {error}")
    finally:
        cerrar_memoria()

    if args.saltos:
        print("Nodos recorridos: " + (" → ".join(resultado["nodos"]) or "(ninguno)"))
        motivo = resultado["estado"].get("motivo")
        if motivo:
            print(f"Motivo: {motivo}")

    print(resultado["respuesta"] or "(sin respuesta)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
