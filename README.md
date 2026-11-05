# Ecommerce Router API

Chat de un ecommerce con un agente **router** (LangGraph + Gemini) que clasifica
cada mensaje en una de tres rutas y lo deriva al agente correspondiente.

| Ruta | Cuándo |
|---|---|
| `preventa` | Intención de compra, productos, precios, tallas, stock, promociones, pagos |
| `postventa` | Quejas, reclamos, pedidos existentes, devoluciones, cambios, garantía |
| `generica` | Saludos sin pedido y temas ajenos a la tienda |

Por ahora los tres agentes destino son cascarones (respuestas fijas): lo
importante es que el router enrute bien. La conversación se guarda en memoria
por `user_id` (thread_id).

## Estructura

```
main.py                 CLI para ejecutar agentes
api/app.py              API FastAPI + Swagger
src/router/             agente router (graph.py, prompts.py, tools.py)
src/asistente/          agente de ejemplo
scripts/                utilidades y pruebas manuales
tests/                  pytest + casos_router.json (15 casos)
bruno/                  colección de requests
Procfile, .python-version, requirements.txt   despliegue en Heroku
```

## Requisitos

- Python 3.12
- Una `GOOGLE_API_KEY` de Google AI Studio

## Instalación

```bash
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

En Linux/macOS: `python3.12 -m venv .venv`, `source .venv/bin/activate` y
`cp .env.example .env`.

Edita `.env` y pega tu `GOOGLE_API_KEY`. El archivo `.env` está en `.gitignore`:
**nunca** se sube al repositorio.

## Correr el router en local

```bash
python main.py router "¿tienen la polera azul en talla M?"
python main.py router "mi pedido 4521 llegó roto" --saltos
python main.py router --diagrama
```

- `--saltos` imprime `router → agente_postventa` y el motivo de la decisión.
- `--diagrama` imprime el Mermaid del grafo sin llamar al modelo.
- `--hilo <id>` cambia el thread_id de la memoria (por defecto `cli`).

## Levantar la API

```bash
uvicorn api.app:app --reload --port 8000
```

- Swagger: http://localhost:8000/docs (botón **Try it out**)
- OpenAPI: http://localhost:8000/openapi.json
- Salud: http://localhost:8000/health

### Probar `/chat` con curl

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "usuario-123", "texto": "¿tienen la polera azul en talla M?"}'
```

En Windows usa Git Bash para ese comando o PowerShell:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/chat `
  -ContentType "application/json" `
  -Body '{"user_id": "usuario-123", "texto": "¿tienen la polera azul en talla M?"}'
```

Respuesta:

```json
{
  "ruta": "preventa",
  "motivo": "El cliente pregunta por un producto antes de comprar.",
  "respuesta": "Soy el agente de preventa. Recibí: ..."
}
```

## Correr las pruebas

```bash
pytest                     # suite completa
pytest tests/test_api.py -q  # solo la API (no llama a Gemini)
python scripts/test_router.py  # tabla de los 15 casos contra el router real
```

`tests/test_router.py` exige **al menos 13/15** aciertos (el modelo no es
determinista). Si Gemini no está disponible (sin clave, sin cuota), esos tests
se omiten con el motivo en el resumen.

## Conectar Telegram

1. En Telegram, habla con **@BotFather** → `/newbot` → copia el token en
   `TELEGRAM_TOKEN` (`.env`).
2. Elige un secreto para el webhook (letras, números, `_` y `-`) y ponlo en
   `TELEGRAM_SECRET`.
3. Telegram exige una URL **https pública**: en local no funciona. Despliega
   primero en Heroku (siguiente sección) y usa esa URL como `PUBLIC_URL`.
4. Registra el webhook:

```bash
curl -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"${PUBLIC_URL}/telegram\", \"secret_token\": \"${TELEGRAM_SECRET}\"}"
```

5. Verifica que quedó registrado:

```bash
curl "https://api.telegram.org/bot${TELEGRAM_TOKEN}/getWebhookInfo"
```

Nota: por ahora `POST /telegram` solo responde `{"ok": true}`; el procesamiento
del mensaje se completa en la parte 5. El secreto se envía en el header
`X-Telegram-Bot-Api-Secret-Token` para que la API lo valide.

## Desplegar en Heroku

El `Procfile` ya trae `web: uvicorn api.app:app --host 0.0.0.0 --port $PORT` y
`.python-version` fija Python 3.12.

```bash
heroku login
heroku create                      # anota la URL que imprime
heroku config:set GOOGLE_API_KEY=tu_clave
heroku config:set MODELO=gemini-3.5-flash-lite
heroku config:set TELEGRAM_TOKEN=tu_token
heroku config:set TELEGRAM_SECRET=tu_secreto
heroku config:set PUBLIC_URL=https://tu-app.herokuapp.com
git push heroku main
heroku open
heroku logs --tail                 # para ver errores
```

Nunca subas `.env` ni pegues claves en el código: en Heroku van con
`heroku config:set`.

## Bruno

Abre la carpeta `bruno/` con Bruno y elige el entorno **Local** o **Heroku**.
Cambia `baseUrl` en `bruno/environments/Heroku.bru` por tu URL real.
