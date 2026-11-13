"""Compartido por todos los agentes: .env, modelo, carga y ejecución de grafos."""
from __future__ import annotations

import logging
import os
import sys
import warnings
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# Carga .env aunque se ejecute desde otro directorio.
load_dotenv(RAIZ / ".env")

MODELO_POR_DEFECTO = "gemini-3.5-flash-lite"
NODOS_OCULTOS = ("__start__", "__end__")

logger = logging.getLogger("ecommerce.memoria")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(_handler)

TipoMemoria = Literal["ram", "postgres"]


@dataclass
class Memoria:
    """Checkpointer en uso y por qué se eligió."""

    checkpointer: object
    tipo: TipoMemoria
    motivo: str = ""


_memoria: Memoria | None = None
_pool = None


def abrir_memoria() -> Memoria:
    """Abre la memoria de conversaciones una sola vez.

    Con DATABASE_URL usa Postgres (pool de 1 a 2 conexiones, tablas creadas con
    setup()). Si la variable falta o Postgres no responde, cae a MemorySaver
    (RAM) y deja el motivo en el log: la API nunca se queda caída por esto.
    """
    global _memoria, _pool
    if _memoria is not None:
        return _memoria

    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        _memoria = Memoria(
            checkpointer=MemorySaver(),
            tipo="ram",
            motivo="DATABASE_URL no está definida",
        )
        logger.info("Memoria en RAM (MemorySaver): DATABASE_URL no está definida.")
        return _memoria

    pool = None
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg_pool import ConnectionPool

        timeout = float(os.getenv("DATABASE_TIMEOUT", "10"))
        pool = ConnectionPool(
            conninfo=url,
            min_size=1,
            max_size=2,
            open=False,
            timeout=timeout,
            check=ConnectionPool.check_connection,
            kwargs={"autocommit": True, "prepare_threshold": 0},
        )
        pool.open(wait=True, timeout=timeout)
        saver = PostgresSaver(pool)
        saver.setup()

        _pool = pool
        _memoria = Memoria(checkpointer=saver, tipo="postgres")
        logger.info("Memoria en Postgres (pool de 1 a 2 conexiones).")
        return _memoria
    except Exception as error:  # noqa: BLE001 - cualquier fallo cae a RAM
        if pool is not None:
            try:
                pool.close()
            except Exception:  # noqa: BLE001 - cerrando tras el fallo
                pass
        motivo = f"Postgres no disponible ({type(error).__name__}: {error})"
        logger.warning("%s. Se usa RAM (MemorySaver).", motivo)
        _memoria = Memoria(checkpointer=MemorySaver(), tipo="ram", motivo=motivo)
        return _memoria


def memoria_actual() -> Memoria:
    """Devuelve la memoria abierta (la abre si hace falta)."""
    return _memoria if _memoria is not None else abrir_memoria()


def cerrar_memoria() -> None:
    """Cierra el pool de Postgres (si se abrió) y olvida el checkpointer."""
    global _memoria, _pool
    if _pool is not None:
        _pool.close()
        _pool = None
    _memoria = None


# gemini-3.5-flash-lite usa sampling fijo e ignora `temperature`; el aviso es
# informativo y solo ensucia los logs en cada llamada.
warnings.filterwarnings("ignore", message=".*fixed sampling defaults.*")


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


def cargar_agente(nombre: str, checkpointer=None):
    """Importa src.{nombre}.graph y devuelve el grafo compilado.

    Si se pasa un checkpointer, recompila el grafo con él (Postgres o RAM).
    Sin checkpointer devuelve el `app` del módulo tal cual.
    """
    import importlib

    disponibles = agentes_disponibles()
    if nombre not in disponibles:
        raise ValueError(
            f'Agente "{nombre}" no existe. Disponibles: {", ".join(disponibles) or "(ninguno)"}'
        )
    modulo = importlib.import_module(f"src.{nombre}.graph")
    if checkpointer is not None:
        constructor = getattr(modulo, "construir_grafo", None)
        if constructor is not None:
            return constructor(checkpointer)
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
