"""Verifica que la API esté arriba.

Uso (con la API corriendo):  python scripts/ping_api.py
"""
from __future__ import annotations

import sys

import httpx


def main() -> int:
    url = "http://127.0.0.1:8000/"
    try:
        respuesta = httpx.get(url, timeout=5)
    except httpx.HTTPError as error:
        print(f"No se pudo conectar a {url}: {error}", file=sys.stderr)
        print("Levántala con: uvicorn api.app:app --reload --port 8000", file=sys.stderr)
        return 1
    print(respuesta.status_code, respuesta.json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
