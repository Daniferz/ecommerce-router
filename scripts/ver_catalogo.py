"""Mira el catálogo de la tienda desde la terminal.

Uso:
    python scripts/ver_catalogo.py "televisor"   # hasta 10 productos
    python scripts/ver_catalogo.py               # productos por categoría
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.router.catalogo import MENSAJE_SIN_BASE, consultar  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _precio(valor) -> str:
    """Formatea pesos chilenos con punto de miles."""
    if valor is None:
        return "sin precio"
    return f"${int(valor):,}".replace(",", ".")


def _rating(valor) -> str:
    if valor is None:
        return "sin rating"
    return f"{valor}/5"


def main(argv: list[str] | None = None) -> int:
    argumentos = list(sys.argv[1:] if argv is None else argv)
    texto = " ".join(argumentos).strip()

    try:
        if not texto:
            filas = consultar(
                "SELECT categoria, COUNT(*) AS total "
                "FROM catalogo.productos_unicos "
                "GROUP BY categoria "
                "ORDER BY categoria"
            )
            if not filas:
                print("El catálogo está vacío.")
                return 0
            print("Productos por categoría:")
            for fila in filas:
                print(f"- {fila['categoria']}: {fila['total']}")
            return 0

        filas = consultar(
            "SELECT sku_id, nombre, precio_internet, rating "
            "FROM catalogo.productos_unicos "
            "WHERE nombre ILIKE %s "
            "ORDER BY rating DESC NULLS LAST, nombre ASC "
            "LIMIT 10",
            [f"%{texto}%"],
        )
    except Exception as error:  # noqa: BLE001 - la base puede no estar disponible
        print(f"{MENSAJE_SIN_BASE}: {error}")
        return 1

    if not filas:
        print(f'No hay productos cuyo nombre contenga "{texto}".')
        return 0

    for fila in filas:
        print(
            f"{fila['sku_id']}  {fila['nombre']}  "
            f"{_precio(fila.get('precio_internet'))}  {_rating(fila.get('rating'))}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
