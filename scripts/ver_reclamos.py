"""Lista los reclamos de postventa guardados.

Uso:
    python scripts/ver_reclamos.py
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.router.reclamos import asegurar_tabla, listar_reclamos  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _fecha(valor) -> str:
    if not valor:
        return "(sin fecha)"
    if isinstance(valor, datetime):
        return valor.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    return str(valor)


def main() -> int:
    if not asegurar_tabla():
        print("Aviso: sin base de datos; se muestra la memoria de este proceso.")

    filas = listar_reclamos()
    if not filas:
        print("No hay reclamos guardados.")
        return 0

    print(f"{'Ticket':<28} {'Pedido':<12} {'Motivo':<24} Creado")
    print("-" * 92)
    for fila in filas:
        print(
            f"{str(fila.get('ticket', '')):<28} "
            f"{str(fila.get('numero_pedido', '')):<12} "
            f"{str(fila.get('motivo', ''))[:24]:<24} "
            f"{_fecha(fila.get('creado_en'))}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
