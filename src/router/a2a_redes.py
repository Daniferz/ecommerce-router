"""Cliente A2A del agente de redes sociales del curso.

Habla con el servicio de inteligencia de mercado por A2A (JSON-RPC) usando
INTEL_URL e INTEL_TOKEN, que viven en .env. La ficha pública del agente está
en {INTEL_URL}/.well-known/agent-card.json.
"""
from __future__ import annotations

import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

from a2a.client import ClientConfig, create_client
from a2a.helpers.proto_helpers import get_stream_response_text, new_text_message
from a2a.types import Role, SendMessageRequest

RAIZ = Path(__file__).resolve().parents[2]
load_dotenv(RAIZ / ".env")

TIEMPO_ESPERA = 60.0
MENSAJE_SIN_REDES = "el agente de redes no está disponible"


def _config() -> tuple[str, str]:
    """URL y token del agente de redes; falla claro si falta alguno."""
    url = (os.getenv("INTEL_URL") or "").strip().rstrip("/")
    token = (os.getenv("INTEL_TOKEN") or "").strip()
    if not url or not token:
        raise RuntimeError("Faltan INTEL_URL o INTEL_TOKEN en .env.")
    return url, token


async def preguntar_redes(texto: str, hilo: str = "") -> str:
    """Pregunta al agente de redes y devuelve el texto completo de su respuesta.

    El hilo viaja como context_id para que el agente remoto mantenga el
    contexto de la conversación. Propaga los errores: quien llama decide qué
    hacer (la herramienta los convierte en un aviso y el chat sigue).
    """
    url, token = _config()

    async with httpx.AsyncClient(
        headers={"Authorization": f"Bearer {token}"},
        timeout=TIEMPO_ESPERA,
    ) as http:
        cliente = await create_client(
            url,
            client_config=ClientConfig(httpx_client=http, streaming=False),
        )
        try:
            peticion = SendMessageRequest(
                message=new_text_message(
                    texto,
                    role=Role.ROLE_USER,
                    context_id=hilo or None,
                )
            )
            partes: list[str] = []
            async for respuesta in cliente.send_message(peticion):
                trozo = get_stream_response_text(respuesta)
                if trozo:
                    partes.append(trozo)
            return "\n".join(partes).strip()
        finally:
            await cliente.close()
