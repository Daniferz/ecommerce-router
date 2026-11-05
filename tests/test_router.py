"""Prueba de calidad del router con los 15 casos de tests/casos_router.json.

El modelo no es determinista: se exigen al menos 13/15 aciertos, no 15.
Si Gemini no está disponible (sin clave o sin créditos) se omiten las pruebas.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from src.base import cargar_agente, ejecutar

CASOS = json.loads((Path(__file__).parent / "casos_router.json").read_text(encoding="utf-8"))
UMBRAL = 13
IDS = [f"{i:02d}-{caso['mensaje'][:32]}" for i, caso in enumerate(CASOS, start=1)]


def _ejecutar(grafo, mensaje: str, thread_id: str):
    try:
        return ejecutar(grafo, mensaje, thread_id=thread_id)
    except Exception as error:
        texto = str(error)
        if "RESOURCE_EXHAUSTED" in texto or "402" in texto or "API key" in texto:
            pytest.skip(f"Gemini no disponible: {texto[:180]}")
        raise


@pytest.fixture(scope="module")
def resultados() -> list[dict]:
    if not os.getenv("GOOGLE_API_KEY"):
        pytest.skip("Falta GOOGLE_API_KEY para probar el router real.")

    grafo = cargar_agente("router")
    salida = []
    for numero, caso in enumerate(CASOS, start=1):
        resultado = _ejecutar(grafo, caso["mensaje"], f"pytest-{numero}")
        obtenido = resultado["estado"].get("ruta")
        salida.append(
            {
                "mensaje": caso["mensaje"],
                "esperado": caso["esperado"],
                "obtenido": obtenido,
                "motivo": resultado["estado"].get("motivo", ""),
                "nodos": resultado["nodos"],
                "ok": obtenido == caso["esperado"],
            }
        )
    return salida


@pytest.mark.parametrize("indice", range(len(CASOS)), ids=IDS)
def test_caso(resultados, indice):
    """Cada caso debe producir una ruta válida y pasar por su nodo."""
    fila = resultados[indice]
    assert fila["obtenido"] in {"preventa", "postventa", "generica"}
    assert fila["nodos"][0] == "router"
    assert fila["motivo"]


def test_minimo_13_de_15(resultados):
    aciertos = sum(fila["ok"] for fila in resultados)
    fallados = [
        f'{fila["mensaje"]} (esperado {fila["esperado"]}, obtenido {fila["obtenido"]})'
        for fila in resultados
        if not fila["ok"]
    ]
    assert aciertos >= UMBRAL, (
        f"Solo {aciertos}/{len(resultados)} aciertos (mínimo {UMBRAL}).\n"
        "Fallados:\n  - " + "\n  - ".join(fallados)
    )
