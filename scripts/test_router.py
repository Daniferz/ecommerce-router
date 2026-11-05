"""Corre los 15 casos de tests/casos_router.json contra el router real.

Uso (desde la raíz):
    python scripts/test_router.py
"""
from __future__ import annotations

import json
import os
import sys
import warnings
from pathlib import Path

# gemini-3.5-flash-lite ignora temperature y avisa en cada llamada.
warnings.filterwarnings("ignore", message=".*fixed sampling defaults.*")

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.base import cargar_agente, ejecutar  # noqa: E402

CASOS = RAIZ / "tests" / "casos_router.json"
UMBRAL = 13
ANCHO_MENSAJE = 46
ANCHO_MOTIVO = 58


def recortar(texto: str, ancho: int) -> str:
    texto = " ".join(texto.split())
    return texto if len(texto) <= ancho else texto[: ancho - 1] + "…"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if not os.getenv("GOOGLE_API_KEY"):
        print("Falta GOOGLE_API_KEY en .env.", file=sys.stderr)
        return 1

    casos = json.loads(CASOS.read_text(encoding="utf-8"))
    grafo = cargar_agente("router")

    filas = []
    for numero, caso in enumerate(casos, start=1):
        try:
            resultado = ejecutar(
                grafo, caso["mensaje"], thread_id=f"caso-{numero}"
            )
        except Exception as error:
            print(f"Error en el caso {numero}: {error}", file=sys.stderr)
            return 1

        obtenido = resultado["estado"].get("ruta", "?")
        filas.append(
            {
                "numero": numero,
                "mensaje": caso["mensaje"],
                "esperado": caso["esperado"],
                "obtenido": obtenido,
                "ok": obtenido == caso["esperado"],
                "motivo": resultado["estado"].get("motivo", ""),
            }
        )

    print(
        f"{'#':>2}  {'MENSAJE':<{ANCHO_MENSAJE}}  {'ESPERADO':<10}  "
        f"{'OBTENIDO':<10}  {'OK':<2}  MOTIVO"
    )
    print("-" * (ANCHO_MENSAJE + ANCHO_MOTIVO + 34))
    for fila in filas:
        print(
            f"{fila['numero']:>2}  {recortar(fila['mensaje'], ANCHO_MENSAJE):<{ANCHO_MENSAJE}}  "
            f"{fila['esperado']:<10}  {fila['obtenido']:<10}  "
            f"{'✔' if fila['ok'] else '✘':<2}  {recortar(fila['motivo'], ANCHO_MOTIVO)}"
        )

    aciertos = sum(fila["ok"] for fila in filas)
    total = len(filas)
    porcentaje = 100 * aciertos / total if total else 0
    print()
    print(f"Aciertos: {aciertos}/{total} ({porcentaje:.1f}%)")

    fallados = [fila for fila in filas if not fila["ok"]]
    if fallados:
        print("Fallados:")
        for fila in fallados:
            print(
                f'  - "{fila["mensaje"]}" → esperado {fila["esperado"]}, '
                f'obtenido {fila["obtenido"]} ({fila["motivo"]})'
            )

    if aciertos < UMBRAL:
        print(f"\nPor debajo del umbral ({aciertos} < {UMBRAL}).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
