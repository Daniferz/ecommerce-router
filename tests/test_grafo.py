"""Prueba el recorrido del grafo (--saltos / /chat) sin llamar a Gemini."""
from __future__ import annotations

from types import SimpleNamespace

import src.asistente.graph as grafo_asistente
from src.base import ejecutar


class ModeloFalso:
    """Simula al modelo: devuelve un texto con espacios de sobra."""

    def invoke(self, mensajes):
        return SimpleNamespace(content="  respuesta   simulada \n ")


def test_ejecutar_devuelve_nodos_y_respuesta(monkeypatch):
    monkeypatch.setattr(grafo_asistente, "crear_modelo", lambda: ModeloFalso())

    resultado = ejecutar(grafo_asistente.app, "hola")

    assert resultado["nodos"] == ["responder", "pulir"]
    assert resultado["respuesta"] == "respuesta simulada"


def test_ejecutar_sin_estado_de_respuesta(monkeypatch):
    monkeypatch.setattr(grafo_asistente, "crear_modelo", lambda: ModeloFalso())
    resultado = ejecutar(grafo_asistente.app, "hola")
    assert isinstance(resultado["nodos"], list)
