"""API FastAPI del proyecto.

Se levanta con:  uvicorn api.app:app --reload --port 8000
Documentación:   http://localhost:8000/docs
"""
from __future__ import annotations

import hmac
import logging
import os
from typing import Literal

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from src.base import MODELO_POR_DEFECTO, cargar_agente, ejecutar

logger = logging.getLogger("ecommerce.router")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(_handler)
# httpx loguea las URLs en INFO: incluiría el token del bot. Nunca.
logging.getLogger("httpx").setLevel(logging.WARNING)

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


@app.get("/", include_in_schema=False)
def raiz() -> RedirectResponse:
    """La raíz lleva al Swagger."""
    return RedirectResponse(url="/docs")


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


async def enviar_telegram(chat_id: int, texto: str) -> None:
    """Envía un mensaje al chat usando la API HTTP de Telegram (solo httpx).

    Nunca se loguea la URL: contiene el token del bot.
    """
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("Falta TELEGRAM_TOKEN: no se puede responder en Telegram.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=30) as cliente:
            respuesta = await cliente.post(url, json={"chat_id": chat_id, "text": texto})
    except httpx.HTTPError as error:
        logger.error("Error de red al enviar a Telegram: %s", type(error).__name__)
        return

    if respuesta.status_code >= 400:
        logger.error(
            "Telegram rechazó sendMessage: %s %s",
            respuesta.status_code,
            respuesta.text[:300],
        )


@app.post(
    "/telegram",
    tags=["telegram"],
    include_in_schema=False,
    summary="Webhook de Telegram",
)
async def telegram(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(
        default=None, alias="X-Telegram-Bot-Api-Secret-Token"
    ),
) -> dict:
    """Recibe updates de Telegram, los enruta y responde por sendMessage."""
    esperado = os.getenv("TELEGRAM_SECRET", "")
    recibido = x_telegram_bot_api_secret_token or ""
    if not esperado or not hmac.compare_digest(
        recibido.encode(), esperado.encode()
    ):
        raise HTTPException(status_code=403, detail="Secreto de webhook inválido")

    try:
        update = await request.json()
    except Exception:
        return {"ok": True, "ignorado": True}

    if not isinstance(update, dict):
        return {"ok": True, "ignorado": True}

    mensaje = update.get("message") or {}
    texto = (mensaje.get("text") or "").strip()
    chat_id = (mensaje.get("chat") or {}).get("id")

    # Updates sin texto (fotos, stickers, etc.) se ignoran.
    if not texto or chat_id is None:
        return {"ok": True, "ignorado": True}

    try:
        resultado = await run_in_threadpool(
            ejecutar, GRAFO, texto, str(chat_id)
        )
        estado = resultado["estado"]
        respuesta = estado.get("respuesta") or ""
        logger.info(
            "Telegram chat_id=%s ruta=%s motivo=%s",
            chat_id,
            estado.get("ruta"),
            estado.get("motivo"),
        )
        if respuesta:
            await enviar_telegram(chat_id, respuesta)
    except Exception:
        # A Telegram se le responde 200 igual, para que no reintente en bucle.
        logger.exception("Fallo procesando el update de Telegram (chat_id=%s)", chat_id)

    return {"ok": True}
