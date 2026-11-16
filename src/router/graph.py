"""Grafo del agente `router`: enruta el chat de un ecommerce.

Solo nodos y aristas. Los textos viven en prompts.py.
"""
from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from src.base import crear_modelo, texto_de
from src.router import prompts
from src.router.tools import (
    ETIQUETAS_HERRAMIENTAS,
    buscar_productos,
    consultar_redes,
    contexto_tienda,
    crear_reclamo,
    estado_pedido,
    mejores_ofertas,
    politica,
    ver_producto,
)


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
    herramientas: list[str]  # herramientas usadas por el agente en este turno


def router(state: Estado) -> dict:
    """Nodo router: decide la ruta con salida estructurada.

    Mira los últimos 4 mensajes y la ruta anterior para que una respuesta corta
    ("sí", "Samsung", "hasta 300 mil") siga en la conversación que venía.
    """
    # temperature=0: clasificación estable para las pruebas.
    clasificador = crear_modelo(temperatura=0).with_structured_output(Decision)
    historial = list(state.get("messages", []))[-4:]
    decision = clasificador.invoke(
        [
            SystemMessage(
                content=prompts.PROMPT_ROUTER.format(
                    ruta_anterior=state.get("ruta") or "(ninguna)"
                )
            ),
            *historial,
            HumanMessage(content=state["mensaje"]),
        ]
    )
    return {
        "ruta": decision.ruta,
        "motivo": decision.motivo,
        "messages": [HumanMessage(content=state["mensaje"])],
        "herramientas": [],
    }


def _herramientas_usadas(mensajes: list[AnyMessage]) -> list[str]:
    """Nombres de las herramientas que llamó el agente, en orden y sin repetir."""
    nombres: list[str] = []
    for mensaje in mensajes:
        if not isinstance(mensaje, AIMessage):
            continue
        for llamada in mensaje.tool_calls or []:
            nombre = llamada.get("name")
            if not nombre:
                continue
            etiqueta = ETIQUETAS_HERRAMIENTAS.get(nombre, nombre)
            if etiqueta not in nombres:
                nombres.append(etiqueta)
    return nombres


def _config_actual() -> dict:
    """Config mínima del grafo actual, con el thread_id para las herramientas."""
    try:
        from langgraph.config import get_config

        config = get_config() or {}
        thread_id = (config.get("configurable") or {}).get("thread_id")
        if thread_id:
            return {"configurable": {"thread_id": thread_id}}
    except Exception:  # noqa: BLE001 - fuera de un grafo no hay config
        pass
    return {}


def _correr_agente(
    historial: list[AnyMessage],
    herramientas: list,
    system_prompt: str,
) -> tuple[str, list[AnyMessage], list[str]]:
    """Ejecuta un agente ReAct y devuelve respuesta, mensajes nuevos y tools."""
    try:
        agente = create_agent(
            crear_modelo(),
            tools=herramientas,
            system_prompt=system_prompt,
        )
        salida = agente.invoke(
            {"messages": historial},
            config=_config_actual(),
        )
        nuevos = list(salida.get("messages", []))[len(historial):]

        respuesta = ""
        for mensaje in reversed(nuevos):
            if isinstance(mensaje, AIMessage) and not mensaje.tool_calls:
                respuesta = texto_de(mensaje)
                if respuesta:
                    break
        return respuesta, nuevos, _herramientas_usadas(nuevos)
    except Exception:  # noqa: BLE001 - el agente no debe tumbar la API
        return "", [], []


def agente_preventa(state: Estado) -> dict:
    """Agente ReAct de preventa: consulta el catálogo con herramientas."""
    respuesta, nuevos, herramientas = _correr_agente(
        list(state.get("messages", [])),
        [buscar_productos, ver_producto, mejores_ofertas, consultar_redes],
        prompts.PROMPT_PREVENTA,
    )

    if not respuesta:
        respuesta = prompts.RESPUESTA_PREVENTA_FIJA.format(
            mensaje=state["mensaje"]
        )
        nuevos = [AIMessage(content=respuesta)]
        herramientas = []

    return {
        "respuesta": respuesta,
        "messages": nuevos,
        "herramientas": herramientas,
    }


def agente_postventa(state: Estado) -> dict:
    """Agente ReAct de postventa: pedidos, políticas y reclamos."""
    respuesta, nuevos, herramientas = _correr_agente(
        list(state.get("messages", [])),
        [estado_pedido, politica, crear_reclamo],
        prompts.PROMPT_POSTVENTA,
    )

    if not respuesta:
        respuesta = prompts.RESPUESTA_POSTVENTA_FIJA.format(
            mensaje=state["mensaje"]
        )
        nuevos = [AIMessage(content=respuesta)]
        herramientas = []

    return {
        "respuesta": respuesta,
        "messages": nuevos,
        "herramientas": herramientas,
    }


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
