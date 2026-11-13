"""Inspecciona la memoria persistente del agente `router`.

Uso:
    python scripts/ver_memoria.py            # lista los hilos guardados
    python scripts/ver_memoria.py prueba1    # mensajes de esa conversación

Necesita DATABASE_URL en .env. Si la memoria está en RAM no hay historial
persistente que mostrar (cada proceso tiene su propia memoria).
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402

from src.base import (  # noqa: E402
    abrir_memoria,
    cargar_agente,
    cerrar_memoria,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

QUIEN = {HumanMessage: "Cliente", AIMessage: "Agente"}


def _fecha(ts: str) -> str:
    """Convierte el timestamp ISO del checkpoint a fecha local legible."""
    if not ts:
        return "(sin fecha)"
    try:
        momento = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return momento.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return ts


def listar_hilos(saver) -> None:
    """Imprime una fila por thread_id con su total de checkpoints y fecha."""
    resumen: dict[str, dict] = {}
    for tupla in saver.list(None):
        hilo = tupla.config["configurable"]["thread_id"]
        datos = resumen.setdefault(hilo, {"total": 0, "ultimo": ""})
        datos["total"] += 1
        ts = tupla.checkpoint.get("ts", "")
        if ts > datos["ultimo"]:
            datos["ultimo"] = ts

    if not resumen:
        print("No hay hilos guardados todavía.")
        return

    print(f"{'Hilo':<32} {'Checkpoints':>12}  Último")
    print("-" * 72)
    for hilo, datos in sorted(
        resumen.items(), key=lambda par: par[1]["ultimo"], reverse=True
    ):
        print(f"{hilo:<32} {datos['total']:>12}  {_fecha(datos['ultimo'])}")


def ver_hilo(grafo, hilo: str) -> int:
    """Imprime los mensajes del hilo en orden (del más viejo al más nuevo)."""
    config = {"configurable": {"thread_id": hilo}}
    estado = grafo.get_state(config)
    mensajes = (estado.values or {}).get("messages", []) if estado else []
    if not mensajes:
        print(f'El hilo "{hilo}" no tiene mensajes guardados.')
        return 1

    print(f'Conversación "{hilo}" ({len(mensajes)} mensajes):')
    for mensaje in mensajes:
        quien = QUIEN.get(type(mensaje), mensaje.type)
        print(f"{quien}: {mensaje.content}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argumentos = list(sys.argv[1:] if argv is None else argv)
    memoria = abrir_memoria()

    if memoria.tipo != "postgres":
        print("Memoria en RAM: no hay historial persistente que mostrar.")
        print(f"Motivo: {memoria.motivo or 'DATABASE_URL no definida'}.")
        return 0

    try:
        if argumentos:
            grafo = cargar_agente("router", checkpointer=memoria.checkpointer)
            return ver_hilo(grafo, argumentos[0])
        listar_hilos(memoria.checkpointer)
        return 0
    finally:
        cerrar_memoria()


if __name__ == "__main__":
    raise SystemExit(main())
