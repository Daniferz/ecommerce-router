"""Pruebas de la API sin llamar a Gemini (el grafo se reemplaza o se usa 422)."""
from __future__ import annotations

import api.app as api_app
from fastapi.testclient import TestClient

client = TestClient(api_app.app)


def test_health():
    respuesta = client.get("/health")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["ok"] is True
    assert cuerpo["modelo"]


def test_chat_sin_texto_da_422():
    respuesta = client.post("/chat", json={"user_id": "u1"})
    assert respuesta.status_code == 422


def test_chat_sin_user_id_da_422():
    respuesta = client.post("/chat", json={"texto": "hola"})
    assert respuesta.status_code == 422


def test_chat_ok(monkeypatch):
    monkeypatch.setattr(
        api_app,
        "ejecutar",
        lambda grafo, texto, thread_id: {
            "nodos": ["router", "agente_preventa"],
            "estado": {
                "ruta": "preventa",
                "motivo": "Pregunta por un producto.",
                "respuesta": "Soy el agente de preventa.",
            },
        },
    )
    respuesta = client.post(
        "/chat", json={"user_id": "u1", "texto": "¿tienen la polera azul?"}
    )
    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "ruta": "preventa",
        "motivo": "Pregunta por un producto.",
        "respuesta": "Soy el agente de preventa.",
    }


def test_chat_error_del_modelo_da_502_sin_filtrar_detalle(monkeypatch, caplog):
    def falla(*args, **kwargs):
        raise RuntimeError("SECRETO-AIzaSy-123: stack trace interno")

    monkeypatch.setattr(api_app, "ejecutar", falla)
    respuesta = client.post("/chat", json={"user_id": "u1", "texto": "hola"})

    assert respuesta.status_code == 502
    assert respuesta.json()["detail"] == api_app.MENSAJE_502
    assert "SECRETO" not in respuesta.text
    assert "AIza" not in respuesta.text
    assert "Traceback" not in respuesta.text
    # El detalle sí queda en el log del servidor.
    assert "user_id=u1" in caplog.text


def test_telegram_responde_ok():
    respuesta = client.post("/telegram", json={"update_id": 1, "message": {}})
    assert respuesta.status_code == 200
    assert respuesta.json() == {"ok": True}


def test_telegram_fuera_del_swagger():
    openapi = client.get("/openapi.json").json()
    assert "/telegram" not in openapi["paths"]


def test_openapi_metadata_y_ejemplos():
    openapi = client.get("/openapi.json").json()

    assert openapi["info"]["title"] == "Ecommerce Router API"
    assert openapi["info"]["version"] == "1.0.0"
    tags = {tag["name"] for tag in openapi.get("tags", [])}
    assert {"salud", "chat", "telegram"} <= tags

    chat = openapi["paths"]["/chat"]["post"]
    for codigo in ("200", "422", "502"):
        assert codigo in chat["responses"], f"Falta documentar {codigo}"
        assert chat["responses"][codigo]["description"]

    ejemplo = openapi["components"]["schemas"]["ChatRequest"]["example"]
    assert ejemplo["user_id"] and ejemplo["texto"]
