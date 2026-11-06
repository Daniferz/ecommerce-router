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


SECRETO = "secreto-de-prueba"
CABECERA = "X-Telegram-Bot-Api-Secret-Token"


def _update(texto: str = "hola", chat_id: int = 123) -> dict:
    return {"update_id": 1, "message": {"text": texto, "chat": {"id": chat_id}}}


def test_telegram_sin_secreto(monkeypatch):
    monkeypatch.setenv("TELEGRAM_SECRET", SECRETO)
    respuesta = client.post("/telegram", json=_update())
    assert respuesta.status_code == 403


def test_telegram_secreto_incorrecto(monkeypatch):
    monkeypatch.setenv("TELEGRAM_SECRET", SECRETO)
    respuesta = client.post(
        "/telegram", json=_update(), headers={CABECERA: "otro-secreto"}
    )
    assert respuesta.status_code == 403


def test_telegram_ignora_updates_sin_texto(monkeypatch):
    monkeypatch.setenv("TELEGRAM_SECRET", SECRETO)
    llamadas = []
    monkeypatch.setattr(api_app, "ejecutar", lambda *args: llamadas.append(args))

    respuesta = client.post(
        "/telegram",
        json={"update_id": 1, "message": {"chat": {"id": 123}}},
        headers={CABECERA: SECRETO},
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {"ok": True, "ignorado": True}
    assert llamadas == []


def test_telegram_ejecuta_y_responde(monkeypatch):
    monkeypatch.setenv("TELEGRAM_SECRET", SECRETO)
    llamadas = []
    enviados = []

    def ejecutar_falso(grafo, mensaje, thread_id):
        llamadas.append((mensaje, thread_id))
        return {
            "estado": {
                "ruta": "preventa",
                "motivo": "Pregunta por un producto.",
                "respuesta": "Soy el agente de preventa.",
            }
        }

    async def enviar_falso(chat_id, texto):
        enviados.append((chat_id, texto))

    monkeypatch.setattr(api_app, "ejecutar", ejecutar_falso)
    monkeypatch.setattr(api_app, "enviar_telegram", enviar_falso)

    respuesta = client.post(
        "/telegram",
        json=_update("¿tienen la polera azul?", chat_id=987),
        headers={CABECERA: SECRETO},
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {"ok": True}
    assert llamadas == [("¿tienen la polera azul?", "987")]
    assert enviados == [(987, "Soy el agente de preventa.")]


def test_telegram_200_aunque_falle_el_modelo(monkeypatch):
    monkeypatch.setenv("TELEGRAM_SECRET", SECRETO)

    def falla(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(api_app, "ejecutar", falla)

    respuesta = client.post(
        "/telegram", json=_update(), headers={CABECERA: SECRETO}
    )

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
