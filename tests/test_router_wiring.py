"""Pruebas del cableado del agente `router` sin llamar a Gemini (modelo falso)."""
from __future__ import annotations

import pytest

import src.router.graph as router_graph
from src.base import ejecutar


class ModeloRouterFalso:
    """Imita a with_structured_output(Decision) con reglas simples."""

    def with_structured_output(self, esquema):
        self.esquema = esquema
        return self

    def invoke(self, mensajes):
        texto = mensajes[-1].content.lower()
        if any(p in texto for p in ("pedido", "devolver", "roto", "reclamo")):
            return router_graph.Decision(
                ruta="postventa", motivo="Habla de un pedido existente."
            )
        if any(p in texto for p in ("polera", "talla", "precio", "cuesta", "stock")):
            return router_graph.Decision(
                ruta="preventa", motivo="Pregunta por un producto antes de comprar."
            )
        return router_graph.Decision(
            ruta="generica", motivo="No tiene que ver con la tienda."
        )


@pytest.fixture
def grafo(monkeypatch):
    monkeypatch.setattr(
        router_graph, "crear_modelo", lambda *args, **kwargs: ModeloRouterFalso()
    )
    return router_graph.app


@pytest.mark.parametrize(
    ("mensaje", "ruta", "nodo"),
    [
        ("¿tienen la polera azul en talla M?", "preventa", "agente_preventa"),
        ("mi pedido 4521 llegó roto", "postventa", "agente_postventa"),
        ("hola", "generica", "respuesta_generica"),
        ("¿cuánto cuesta el envío a Valparaíso?", "preventa", "agente_preventa"),
        ("quiero devolver unas zapatillas", "postventa", "agente_postventa"),
        ("¿qué hora es en Tokio?", "generica", "respuesta_generica"),
    ],
)
def test_enruta_y_responde(grafo, mensaje, ruta, nodo):
    resultado = ejecutar(grafo, mensaje, thread_id="test-router")
    assert resultado["estado"]["ruta"] == ruta
    assert resultado["estado"]["motivo"]
    assert resultado["nodos"] == ["router", nodo]
    assert mensaje in resultado["respuesta"] or nodo == "respuesta_generica"


def test_memoria_por_thread_id(grafo):
    ejecutar(grafo, "hola", thread_id="memoria-1")
    resultado = ejecutar(grafo, "mi pedido 4521 llegó roto", thread_id="memoria-1")
    # 2 turnos → 4 mensajes (humano + asistente por turno)
    assert len(resultado["estado"]["messages"]) == 4
