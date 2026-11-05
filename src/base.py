"""Compartido por todos los agentes: .env, modelo, carga y ejecución de grafos."""
from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# Carga .env aunque se ejecute desde otro directorio.
load_dotenv(RAIZ / ".env")

MODELO_POR_DEFECTO = "gemini-3.5-flash-lite"
NODOS_OCULTOS = ("__start__", "__end__")


@lru_cache(maxsize=None)
def crear_modelo(temperatura: float = 0.2) -> ChatGoogleGenerativeAI:
    """Modelo Gemini (se crea al invocar, no al importar).

    Se cachea por temperatura: el router usa 0 para ser estable.
    """
    kwargs: dict = {
        "model": os.getenv("MODELO") or MODELO_POR_DEFECTO,
        "temperature": temperatura,
    }
    clave = os.getenv("GOOGLE_API_KEY")
    if clave:
        kwargs["api_key"] = clave
    return ChatGoogleGenerativeAI(**kwargs)


def texto_de(respuesta) -> str:
    """Extrae texto plano de la respuesta del modelo (str o bloques)."""
    contenido = getattr(respuesta, "content", respuesta)
    if isinstance(contenido, str):
        return contenido.strip()
    if isinstance(contenido, list):
        partes = [
            bloque.get("text", "")
            for bloque in contenido
            if isinstance(bloque, dict)
        ]
        return "".join(partes).strip()
    return str(contenido).strip()


def agentes_disponibles() -> list[str]:
    """Carpetas de src/ que tienen graph.py (los agentes)."""
    src = RAIZ / "src"
    if not src.is_dir():
        return []
    return sorted(
        carpeta.name
        for carpeta in src.iterdir()
        if carpeta.is_dir()
        and not carpeta.name.startswith((".", "_"))
        and (carpeta / "graph.py").is_file()
    )


def cargar_agente(nombre: str):
    """Importa src.{nombre}.graph y devuelve el grafo compilado (`app`)."""
    import importlib

    disponibles = agentes_disponibles()
    if nombre not in disponibles:
        raise ValueError(
            f'Agente "{nombre}" no existe. Disponibles: {", ".join(disponibles) or "(ninguno)"}'
        )
    modulo = importlib.import_module(f"src.{nombre}.graph")
    grafo = getattr(modulo, "app", None)
    if grafo is None:
        raise ValueError(f"src/{nombre}/graph.py no exporta `app` (grafo compilado).")
    return grafo


def ejecutar(grafo, mensaje: str, thread_id: str = "cli") -> dict:
    """Ejecuta el grafo y devuelve nodos, respuesta y estado final.

    thread_id identifica la conversación para los grafos con memoria
    (checkpointer MemorySaver).
    """
    nodos: list[str] = []
    estado: dict = {}
    config = {"configurable": {"thread_id": thread_id}}
    for modo, chunk in grafo.stream(
        {"mensaje": mensaje}, config=config, stream_mode=["values", "updates"]
    ):
        if modo == "values":
            estado = chunk
        else:
            nodos.extend(nodo for nodo in chunk if nodo not in NODOS_OCULTOS)
    return {
        "nodos": nodos,
        "respuesta": (estado or {}).get("respuesta", ""),
        "estado": estado or {},
    }
