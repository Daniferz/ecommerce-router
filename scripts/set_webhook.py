"""Registra el webhook del bot en Telegram.

Uso (desde la raíz):
    python scripts/set_webhook.py

Requiere en .env: TELEGRAM_TOKEN, TELEGRAM_SECRET y PUBLIC_URL (https).
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
    secret = (os.getenv("TELEGRAM_SECRET") or "").strip()
    public_url = (os.getenv("PUBLIC_URL") or "").rstrip("/")

    faltan = [
        nombre
        for nombre, valor in (
            ("TELEGRAM_TOKEN", token),
            ("TELEGRAM_SECRET", secret),
            ("PUBLIC_URL", public_url),
        )
        if not valor
    ]
    if faltan:
        print(f"Faltan en .env: {', '.join(faltan)}", file=sys.stderr)
        return 1

    url = f"{public_url}/telegram"
    print(f"setWebhook -> {url}")

    try:
        respuesta = httpx.post(
            f"https://api.telegram.org/bot{token}/setWebhook",
            json={"url": url, "secret_token": secret},
            timeout=30,
        )
    except httpx.HTTPError as error:
        print(f"Error de red: {type(error).__name__}", file=sys.stderr)
        return 1

    try:
        datos = respuesta.json()
    except ValueError:
        print(respuesta.status_code, respuesta.text)
        return 1

    print(respuesta.status_code)
    print(json.dumps(datos, indent=2, ensure_ascii=False))
    return 0 if datos.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
