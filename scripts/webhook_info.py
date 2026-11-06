"""Consulta getWebhookInfo y avisa si el webhook quedó mal o hay errores.

Uso (desde la raíz):
    python scripts/webhook_info.py

Requiere en .env: TELEGRAM_TOKEN (y opcionalmente PUBLIC_URL para comparar).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
load_dotenv(RAIZ / ".env")


def main() -> int:
    token = (os.getenv("TELEGRAM_TOKEN") or "").strip()
    public_url = (os.getenv("PUBLIC_URL") or "").rstrip("/")

    if not token:
        print("Falta TELEGRAM_TOKEN en .env", file=sys.stderr)
        return 1

    try:
        respuesta = httpx.get(
            f"https://api.telegram.org/bot{token}/getWebhookInfo", timeout=30
        )
    except httpx.HTTPError as error:
        print(f"Error de red: {type(error).__name__}", file=sys.stderr)
        return 1

    try:
        datos = respuesta.json()
    except ValueError:
        print(respuesta.status_code, respuesta.text)
        return 1

    print(json.dumps(datos, indent=2, ensure_ascii=False))

    info = datos.get("result") or {}
    esperado = f"{public_url}/telegram" if public_url else None
    problemas = []

    url_actual = info.get("url") or ""
    if not url_actual:
        problemas.append(
            "No hay webhook registrado: corre python scripts/set_webhook.py."
        )
    elif esperado and url_actual != esperado:
        problemas.append(
            f'El webhook apunta a "{url_actual}" y debería ser "{esperado}".'
        )
    if info.get("last_error_message"):
        fecha = info.get("last_error_date")
        problemas.append(
            f'Último error ({fecha}): {info["last_error_message"]}'
        )
    pendientes = info.get("pending_update_count") or 0
    if pendientes:
        problemas.append(f"Hay {pendientes} update(s) pendientes de entregar.")

    print()
    if problemas:
        print("Revisar:")
        for problema in problemas:
            print(f"  - {problema}")
        return 1

    print("Webhook OK: sin errores pendientes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
