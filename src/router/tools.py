"""Herramientas del agente `router`.

Preventa consulta el catálogo real; postventa consulta pedidos y políticas y
registra reclamos. El nodo genérico usa `contexto_tienda` como contexto.
"""
from __future__ import annotations

import asyncio
import json
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from src.router import a2a_redes
from src.router.catalogo import MENSAJE_SIN_BASE, consultar
from src.router.reclamos import guardar_reclamo

DATA = Path(__file__).resolve().parents[2] / "data"
TIENDA = DATA / "tienda.md"
PEDIDOS = DATA / "pedidos.json"
POLITICAS = DATA / "politicas.md"

# Etiqueta que muestra --saltos para la llamada A2A.
ETIQUETAS_HERRAMIENTAS = {
    "consultar_redes": "consultar_redes (A2A)",
}


@lru_cache(maxsize=1)
def contexto_tienda() -> str:
    """Contenido de data/tienda.md, como contexto del nodo genérico."""
    return TIENDA.read_text(encoding="utf-8").strip()


def _json(filas: list[dict]) -> str:
    """Serializa las filas para que el modelo las lea sin perder datos."""
    return json.dumps(filas, ensure_ascii=False, default=str)


def _hilo(config: RunnableConfig | None) -> str:
    """thread_id de la conversación, si la config del grafo lo trae."""
    if not config:
        return ""
    return str((config.get("configurable") or {}).get("thread_id") or "")


# --------------------------------------------------------------------------- #
# Preventa: catálogo
# --------------------------------------------------------------------------- #
@tool
def buscar_productos(
    consulta: str,
    categoria: str = "",
    marca: str = "",
    precio_max: int | None = None,
) -> str:
    """Busca productos del catálogo por palabras del nombre.

    Devuelve hasta 5 productos, primero los de mejor rating, con sku_id,
    nombre, marca, precio_internet, descuento_pct y rating.

    Args:
        consulta: palabras que deben aparecer en el nombre (ej. "televisor 55").
        categoria: "Smartphones" o "Televisores"; vacío para todas.
        marca: marca a buscar en la columna marca o dentro del nombre.
        precio_max: precio máximo en pesos chilenos.
    """
    condiciones = ["precio_internet IS NOT NULL"]
    parametros: list[Any] = []

    for palabra in consulta.split():
        condiciones.append("POSITION(LOWER(%s) IN LOWER(nombre)) > 0")
        parametros.append(palabra)

    if categoria.strip():
        condiciones.append("LOWER(categoria) = LOWER(%s)")
        parametros.append(categoria.strip())

    if marca.strip():
        condiciones.append(
            "(POSITION(LOWER(%s) IN LOWER(COALESCE(marca, ''))) > 0 "
            "OR POSITION(LOWER(%s) IN LOWER(nombre)) > 0)"
        )
        parametros.extend([marca.strip(), marca.strip()])

    if precio_max is not None:
        condiciones.append("precio_internet <= %s")
        parametros.append(int(precio_max))

    sql = (
        "SELECT sku_id, nombre, marca, precio_internet, descuento_pct, rating "
        "FROM catalogo.productos_unicos "
        f"WHERE {' AND '.join(condiciones)} "
        "ORDER BY rating DESC NULLS LAST, precio_internet ASC NULLS LAST, "
        "nombre ASC "
        "LIMIT 5"
    )

    try:
        filas = consultar(sql, parametros)
        return _json(filas) if filas else "Sin resultados."
    except Exception:  # noqa: BLE001 - la base no debe tumbar el agente
        return MENSAJE_SIN_BASE


@tool
def ver_producto(sku_id: str) -> str:
    """Devuelve todo el detalle de un producto, incluido su link.

    Úsala antes de recomendar un producto para poder entregar el link.

    Args:
        sku_id: identificador del producto (el que devuelve buscar_productos).
    """
    sql = (
        "SELECT sku_id, nombre, marca, categoria, subcategoria, "
        "precio_normal, precio_internet, descuento_pct, rating, "
        "tienda_oficial, link, imagen "
        "FROM catalogo.productos_unicos "
        "WHERE sku_id = %s "
        "LIMIT 1"
    )
    try:
        filas = consultar(sql, [sku_id])
        if not filas:
            return "No encontré un producto con ese SKU."
        return _json(filas)
    except Exception:  # noqa: BLE001 - la base no debe tumbar el agente
        return MENSAJE_SIN_BASE


@tool
def mejores_ofertas(categoria: str = "", limite: int = 5) -> str:
    """Lista los productos con mayor descuento_pct del catálogo.

    Args:
        categoria: "Smartphones" o "Televisores"; vacío para todas.
        limite: cuántos productos devolver (1 a 10; por defecto 5).
    """
    tope = max(1, min(int(limite), 10))
    condiciones = ["descuento_pct IS NOT NULL"]
    parametros: list[Any] = []

    if categoria.strip():
        condiciones.append("LOWER(categoria) = LOWER(%s)")
        parametros.append(categoria.strip())

    sql = (
        "SELECT sku_id, nombre, marca, precio_internet, descuento_pct, rating "
        "FROM catalogo.productos_unicos "
        f"WHERE {' AND '.join(condiciones)} "
        "ORDER BY descuento_pct DESC NULLS LAST, rating DESC NULLS LAST "
        "LIMIT %s"
    )
    parametros.append(tope)

    try:
        filas = consultar(sql, parametros)
        return _json(filas) if filas else "Sin resultados."
    except Exception:  # noqa: BLE001 - la base no debe tumbar el agente
        return MENSAJE_SIN_BASE


# --------------------------------------------------------------------------- #
# Preventa: redes sociales y noticias (A2A)
# --------------------------------------------------------------------------- #
def _preguntar_sync(texto: str, hilo: str) -> str:
    """Corre la corrutina A2A desde el nodo síncrono del grafo."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(a2a_redes.preguntar_redes(texto, hilo))

    # Ya hay un loop en este hilo: la llamada va a un hilo propio.
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(
            asyncio.run, a2a_redes.preguntar_redes(texto, hilo)
        ).result()


@tool
def consultar_redes(tema: str, config: RunnableConfig) -> str:
    """Consulta qué se comenta en redes y noticias sobre una marca o producto.

    Úsala solo cuando el cliente pregunte por opiniones, comentarios, noticias
    o tendencias de una marca o un producto; tarda unos 15 segundos.

    Args:
        tema: marca o producto a consultar (ej. "Samsung", "iPhone 16").
    """
    tema = tema.strip()
    if not tema:
        return a2a_redes.MENSAJE_SIN_REDES

    try:
        respuesta = _preguntar_sync(tema, _hilo(config))
    except Exception:  # noqa: BLE001 - A2A no debe tumbar el chat
        return a2a_redes.MENSAJE_SIN_REDES

    respuesta = respuesta.strip()
    if not respuesta:
        return a2a_redes.MENSAJE_SIN_REDES
    return respuesta[:1500]


# --------------------------------------------------------------------------- #
# Postventa: pedidos, políticas y reclamos
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _pedidos() -> list[dict]:
    """Pedidos inventados de data/pedidos.json."""
    return json.loads(PEDIDOS.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _secciones_politicas() -> list[tuple[str, str]]:
    """Secciones de data/politicas.md como (título, cuerpo)."""
    titulo = ""
    cuerpo: list[str] = []
    secciones: list[tuple[str, str]] = []

    for linea in POLITICAS.read_text(encoding="utf-8").splitlines():
        if linea.startswith("## "):
            if titulo:
                secciones.append((titulo, "\n".join(cuerpo).strip()))
            titulo = linea[3:].strip()
            cuerpo = []
        elif titulo:
            cuerpo.append(linea)

    if titulo:
        secciones.append((titulo, "\n".join(cuerpo).strip()))
    return secciones


def _normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar temas de políticas."""
    descompuesto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(
        caracter for caracter in descompuesto if not unicodedata.combining(caracter)
    ).strip()


@tool
def estado_pedido(numero: str) -> str:
    """Devuelve el detalle de un pedido por su número, o "no existe".

    Args:
        numero: número del pedido (ej. PED-1001).
    """
    buscado = numero.strip().lower()
    for pedido in _pedidos():
        if str(pedido.get("numero", "")).strip().lower() == buscado:
            return json.dumps(pedido, ensure_ascii=False, default=str)
    return "no existe"


@tool
def politica(tema: str) -> str:
    """Devuelve la sección de políticas de la tienda sobre un tema.

    Temas: devoluciones, cambios o garantía.

    Args:
        tema: tema consultado (ej. "devoluciones", "cambios", "garantía").
    """
    clave = _normalizar(tema)
    secciones = _secciones_politicas()

    if not clave:
        return "\n\n".join(f"## {titulo}\n{cuerpo}" for titulo, cuerpo in secciones)

    sinonimos = {
        "devoluciones": ("devolucion", "devoluciones", "devolver"),
        "cambios": ("cambio", "cambios", "cambiar"),
        "garantia": ("garantia", "garantias"),
    }

    for titulo, cuerpo in secciones:
        nombre = _normalizar(titulo)
        if clave in nombre or nombre in clave:
            return f"## {titulo}\n{cuerpo}"
        if any(palabra in clave for palabra in sinonimos.get(nombre, ())):
            return f"## {titulo}\n{cuerpo}"

    disponibles = ", ".join(titulo for titulo, _ in secciones)
    return f"No hay una política para ese tema. Temas disponibles: {disponibles}."


@tool
def crear_reclamo(
    numero_pedido: str,
    motivo: str,
    detalle: str,
    config: RunnableConfig,
) -> str:
    """Registra un reclamo de postventa y devuelve el número de ticket.

    Úsala solo después de confirmar el motivo con el cliente.

    Args:
        numero_pedido: número del pedido (ej. PED-1001).
        motivo: motivo breve del reclamo.
        detalle: lo que contó el cliente, con el contexto necesario.
    """
    thread_id = _hilo(config)
    ticket = guardar_reclamo(
        numero_pedido.strip(),
        motivo.strip(),
        detalle.strip(),
        thread_id,
    )
    return f"Ticket {ticket} creado para el pedido {numero_pedido.strip()}."
