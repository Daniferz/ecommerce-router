"""API FastAPI del proyecto.

Se levanta con:  uvicorn api.app:app --reload --port 8000
Documentación:   http://localhost:8000/docs
"""
from __future__ import annotations

import logging
import os
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from src.base import MODELO_POR_DEFECTO, cargar_agente, ejecutar

logger = logging.getLogger("ecommerce.router")

RUTAS = ("preventa", "postventa", "generica")
MENSAJE_502 = "El router no pudo procesar el mensaje. Intenta nuevamente en unos segundos."

# El grafo se compila UNA sola vez, al importar la app.
# El modelo se crea recién dentro del nodo, así que esto no llama a Gemini.
GRAFO = cargar_agente("router")


# --------------------------------------------------------------------------- #
# Modelos (con descripción y ejemplo para que /docs venga listo)
# --------------------------------------------------------------------------- #
class HealthResponse(BaseModel):
    ok: bool = Field(
        description="true si el servicio está operativo.",
        examples=[True],
    )
    modelo: str = Field(
        description="Modelo configurado en la variable MODELO.",
        examples=["gemini-3.5-flash-lite"],
    )


class ChatRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "usuario-123",
                "texto": "¿tienen la polera azul en talla M?",
            }
        }
    )

    user_id: str = Field(
        min_length=1,
        description="Identificador del usuario. Se usa como thread_id de la conversación.",
        examples=["usuario-123"],
    )
    texto: str = Field(
        min_length=1,
        description="Mensaje del cliente que el router debe clasificar.",
        examples=["¿tienen la polera azul en talla M?"],
    )


class ErrorDetalle(BaseModel):
    loc: list[str | int] = Field(
        description="Ubicación del campo con error (por ejemplo, ['body', 'texto']).",
        examples=[["body", "texto"]],
    )
    msg: str = Field(
        description="Descripción del error de validación.",
        examples=["Field required"],
    )
    type: str = Field(
        description="Tipo de error de Pydantic.",
        examples=["missing"],
    )


class ErrorValidacion(BaseModel):
    detail: list[ErrorDetalle] = Field(
        description="Lista de errores de validación del body."
    )


class ChatResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ruta": "preventa",
                "motivo": "El cliente pregunta por un producto antes de comprar.",
                "respuesta": "Soy el agente de preventa. Recibí: ...",
            }
        }
    )

    ruta: Literal["preventa", "postventa", "generica"] = Field(
        description="Ruta elegida por el router: preventa, postventa o generica.",
        examples=["preventa"],
    )
    motivo: str = Field(
        description="Una frase del router explicando por qué eligió esa ruta.",
        examples=["El cliente pregunta por un producto antes de comprar."],
    )
    respuesta: str = Field(
        description="Respuesta del agente destino.",
        examples=["Soy el agente de preventa. Recibí: ..."],
    )


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #
app = FastAPI(
    title="Ecommerce Router API",
    version="1.0.0",
    description=(
        "API del chat de un ecommerce. El endpoint `/chat` recibe el mensaje de "
        "un cliente y lo envía a una de tres rutas:\n\n"
        "- **preventa**: intención de compra, productos, precios, tallas, stock, "
        "promociones o formas de pago antes de comprar.\n"
        "- **postventa**: quejas, reclamos, seguimiento de pedidos existentes, "
        "devoluciones, cambios, garantía o producto dañado.\n"
        "- **generica**: saludos sin pedido y temas ajenos a la tienda.\n\n"
        "La conversación se guarda en memoria por `user_id` (thread_id)."
    ),
    openapi_tags=[
        {
            "name": "salud",
            "description": "Estado del servicio y modelo en uso.",
        },
        {
            "name": "chat",
            "description": (
                "Mensajes de clientes. El router decide la ruta y el agente "
                "destino responde."
            ),
        },
        {
            "name": "telegram",
            "description": "Webhook de Telegram (se completa en la parte 5).",
        },
    ],
)


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["salud"],
    summary="Estado del servicio",
    description="Devuelve `ok` y el modelo configurado. No llama a Gemini.",
)
def health() -> HealthResponse:
    return HealthResponse(
        ok=True,
        modelo=os.getenv("MODELO") or MODELO_POR_DEFECTO,
    )


@app.post(
    "/chat",
    response_model=ChatResponse,
    tags=["chat"],
    summary="Enruta un mensaje de cliente",
    description=(
        "Ejecuta el grafo `router` con `thread_id = user_id` y devuelve la ruta "
        "elegida, el motivo y la respuesta del agente destino."
    ),
    responses={
        200: {"description": "El router eligió una ruta y el agente respondió."},
        422: {
            "model": ErrorValidacion,
            "description": (
                "Body inválido: falta `user_id` o `texto`, o tienen un tipo "
                "de dato incorrecto."
            ),
        },
        502: {
            "description": (
                "El modelo (Gemini) falló o no está disponible. El detalle "
                "queda en el log del servidor, no en la respuesta."
            )
        },
    },
)
def chat(entrada: ChatRequest) -> ChatResponse:
    try:
        resultado = ejecutar(GRAFO, entrada.texto, thread_id=entrada.user_id)
    except Exception:
        # El detalle (incluida la causa) queda solo en el log del servidor.
        logger.exception("Fallo el router para user_id=%s", entrada.user_id)
        raise HTTPException(status_code=502, detail=MENSAJE_502)

    estado = resultado["estado"]
    ruta = estado.get("ruta")
    if ruta not in RUTAS:
        logger.error(
            "Ruta inválida devuelta por el router: %r (user_id=%s)",
            ruta,
            entrada.user_id,
        )
        raise HTTPException(status_code=502, detail=MENSAJE_502)

    return ChatResponse(
        ruta=ruta,
        motivo=estado.get("motivo") or "",
        respuesta=estado.get("respuesta") or "",
    )


@app.post(
    "/telegram",
    tags=["telegram"],
    include_in_schema=False,
    summary="Webhook de Telegram (pendiente)",
)
async def telegram() -> dict:
    """Recibe cualquier JSON y responde ok. Se completa en la parte 5."""
    return {"ok": True}
