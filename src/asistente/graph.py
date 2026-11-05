"""Grafo del agente `asistente`: solo nodos y aristas.

Aquí NO van prompts ni reglas: esos textos viven en prompts.py.
"""
from __future__ import annotations

from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from src.asistente import prompts
from src.asistente.tools import pulir_texto
from src.base import crear_modelo, texto_de


class Estado(TypedDict):
    mensaje: str  # entrada
    respuesta: str  # salida


def responder(state: Estado) -> dict:
    """Nodo 1: redacta la respuesta con el LLM."""
    salida = crear_modelo().invoke(
        [
            SystemMessage(content=prompts.PROMPT_RESPONDER),
            HumanMessage(content=state["mensaje"]),
        ]
    )
    return {"respuesta": texto_de(salida)}


def pulir(state: Estado) -> dict:
    """Nodo 2: mejora la respuesta y normaliza el texto."""
    salida = crear_modelo().invoke(
        [
            SystemMessage(content=prompts.PROMPT_PULIR),
            HumanMessage(content=state["respuesta"]),
        ]
    )
    return {"respuesta": pulir_texto(texto_de(salida))}


def construir_grafo():
    grafo = StateGraph(Estado)
    grafo.add_node("responder", responder)
    grafo.add_node("pulir", pulir)
    grafo.add_edge(START, "responder")
    grafo.add_edge("responder", "pulir")
    grafo.add_edge("pulir", END)
    return grafo.compile()


# Grafo compilado: es lo que importan main.py y la API.
app = construir_grafo()
