"""Grafo del agente `router`: enruta el chat de un ecommerce.

Solo nodos y aristas. Los textos viven en prompts.py.
"""
from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from src.base import crear_modelo, texto_de
from src.router import prompts
from src.router.tools import contexto_tienda


class Decision(BaseModel):
    ruta: Literal["preventa", "postventa", "generica"] = Field(
        description="A qué agente va el mensaje."
    )
    motivo: str = Field(description="Una frase: por qué esa ruta.")


class Estado(TypedDict):
    mensaje: str  # entrada
    ruta: str  # la llena el router
    motivo: str  # lo llena el router
    respuesta: str  # salida
    messages: Annotated[list[AnyMessage], add_messages]  # memoria por thread_id


def router(state: Estado) -> dict:
    """Nodo router: decide la ruta con salida estructurada."""
    # temperature=0: clasificación estable para las pruebas.
    clasificador = crear_modelo(temperatura=0).with_structured_output(Decision)
    decision = clasificador.invoke(
        [
            SystemMessage(content=prompts.PROMPT_ROUTER),
            *state.get("messages", []),
            HumanMessage(content=state["mensaje"]),
        ]
    )
    return {
        "ruta": decision.ruta,
        "motivo": decision.motivo,
        "messages": [HumanMessage(content=state["mensaje"])],
    }


def agente_preventa(state: Estado) -> dict:
    """Cascarón de preventa (por ahora respuesta fija)."""
    respuesta = prompts.PROMPT_PREVENTA.format(mensaje=state["mensaje"])
    return {"respuesta": respuesta, "messages": [AIMessage(content=respuesta)]}


def agente_postventa(state: Estado) -> dict:
    """Cascarón de postventa (por ahora respuesta fija)."""
    respuesta = prompts.PROMPT_POSTVENTA.format(mensaje=state["mensaje"])
    return {"respuesta": respuesta, "messages": [AIMessage(content=respuesta)]}


def respuesta_generica(state: Estado) -> dict:
    """Nodo genérico: conversa con el modelo y el contexto de la tienda.

    Recibe todo el historial (`messages`) para saludar por su nombre y mantener
    el hilo. Si el modelo falla, devuelve la frase fija en vez de propagar el
    error.
    """
    try:
        mensajes = [
            SystemMessage(
                content=prompts.PROMPT_GENERICA.format(ficha=contexto_tienda())
            ),
            *state.get("messages", []),
        ]
        respuesta = texto_de(crear_modelo().invoke(mensajes))
    except Exception:  # noqa: BLE001 - si el modelo falla, no se rompe el grafo
        respuesta = ""

    if not respuesta:
        respuesta = prompts.RESPUESTA_GENERICA_FIJA

    return {"respuesta": respuesta, "messages": [AIMessage(content=respuesta)]}


def elegir_agente(state: Estado) -> str:
    """Arista condicional: devuelve la ruta decidida por el router."""
    return state["ruta"]


def construir_grafo(checkpointer=None):
    grafo = StateGraph(Estado)
    grafo.add_node("router", router)
    grafo.add_node("agente_preventa", agente_preventa)
    grafo.add_node("agente_postventa", agente_postventa)
    grafo.add_node("respuesta_generica", respuesta_generica)

    grafo.add_edge(START, "router")
    grafo.add_conditional_edges(
        "router",
        elegir_agente,
        {
            "preventa": "agente_preventa",
            "postventa": "agente_postventa",
            "generica": "respuesta_generica",
        },
    )
    grafo.add_edge("agente_preventa", END)
    grafo.add_edge("agente_postventa", END)
    grafo.add_edge("respuesta_generica", END)

    # Memoria por thread_id (configurable.thread_id al invocar). La API y la
    # CLI pasan PostgresSaver cuando hay DATABASE_URL; sin él, RAM.
    return grafo.compile(checkpointer=checkpointer or MemorySaver())


app = construir_grafo()
