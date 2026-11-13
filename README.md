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

Edita `.env` y pega tu `GOOGLE_API_KEY`. Genera también una `API_KEY` para
proteger `/chat` (ver [Clave de la API](#clave-de-la-api)). El archivo `.env`
está en `.gitignore`: **nunca** se sube al repositorio.

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

## Clave de la API

`POST /chat` está protegido con una clave para que nadie pueda usar tu agente
(y gastar tu cuota de Gemini) solo con conocer la URL. Se envía en la cabecera
`X-API-Key` y se compara con la variable de entorno `API_KEY`; si falta o no
coincide, la API responde **401**. `/health` y `/telegram` siguen abiertos
(Telegram usa su propio secreto).

### Generar una clave

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### En local

Ponla en `.env` (nunca se sube al repo):

```
API_KEY=la-clave-que-generaste
```

Reinicia uvicorn para que lea la variable.

### En Heroku

```bash
heroku config:set API_KEY=la-clave-que-generaste
```

O en el dashboard: **Settings → Config Vars → Reveal Config Vars → Add**.
Debe ser la **misma** clave que uses desde el cliente.

### Usarla desde Swagger

En `/docs`, pulsa **Authorize**, pega la clave y luego **Try it out** en
`POST /chat`. El candado indica que el endpoint está protegido.

### Probar `/chat` con curl

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"user_id": "usuario-123", "texto": "¿tienen la polera azul en talla M?"}'
```

En Windows usa Git Bash para ese comando o PowerShell:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/chat `
  -Headers @{"X-API-Key"=$env:API_KEY} `
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

Sin la cabecera (o con una clave distinta) la respuesta es:

```json
{"detail": "Falta o es incorrecta la cabecera X-API-Key."}
```

## Memoria de las conversaciones

El agente guarda el historial por `thread_id` (en `/chat` es el `user_id`). Si
defines `DATABASE_URL`, usa Postgres (`PostgresSaver`) y las conversaciones
sobreviven a los reinicios de Heroku. Sin la variable, o si Postgres no responde
al arrancar, cae a memoria RAM (`MemorySaver`) y deja el motivo en el log.

En local, agrega a `.env`:

```
DATABASE_URL=postgresql://usuario:clave@host:5432/base
```

En Heroku:

```bash
heroku config:set DATABASE_URL=postgresql://...
```

`GET /health` indica `"memoria": "postgres"` o `"memoria": "ram"`.

Para elegir el hilo desde la terminal:

```bash
python main.py router "hola" --hilo cliente-123
```

Para inspeccionar la memoria:

```bash
python scripts/ver_memoria.py               # hilos, checkpoints y último uso
python scripts/ver_memoria.py cliente-123   # mensajes de ese hilo
```

El pool usa mínimo 1 y máximo 2 conexiones, y las tablas se crean solas con
`setup()` al arrancar.

## Correr las pruebas

```bash
pytest                     # suite completa
pytest tests/test_api.py -q  # solo la API (no llama a Gemini)
python scripts/test_router.py  # tabla de los 15 casos contra el router real
```

`tests/test_router.py` exige **al menos 13/15** aciertos (el modelo no es
determinista). Si Gemini no está disponible (sin clave, sin cuota), esos tests
se omiten con el motivo en el resumen.

## Telegram

El bot se crea a mano con **@BotFather** y la API habla con Telegram solo con
`httpx` (sin librerías de bot). Pasos, en orden:

### 1. Crear el bot y configurar Heroku

En Telegram: **@BotFather** → `/newbot` → copia el token. Elige también un
secreto para el webhook: **solo** letras, números, `_` y `-` (si usas un
generador de contraseñas con símbolos como `*%^/<>`, Telegram devuelve
`400 Bad Request: secret token contains illegal characters`).

```bash
heroku config:set TELEGRAM_TOKEN=123456:ABC-tu-token
heroku config:set TELEGRAM_SECRET=tu-secreto
```

### 2. Commit y push a GitHub y a Heroku

```bash
git add .
git commit -m "telegram"
git push origin main
git push heroku main
```

### 3. Registrar el webhook

En tu `.env` local pon la URL de Heroku (sin barra final):

```
PUBLIC_URL=https://tu-app.herokuapp.com
```

```bash
python scripts/set_webhook.py    # setWebhook con PUBLIC_URL + /telegram
python scripts/webhook_info.py   # getWebhookInfo: URL y errores pendientes
```

### 4. Probar con los 6 mensajes

Escríbelos al bot y mira la ruta en los logs:

```bash
heroku logs --tail
```

| Mensaje | Ruta esperada |
|---|---|
| ¿tienen la polera azul en talla M? | preventa |
| mi pedido 4521 llegó roto | postventa |
| hola | generica |
| ¿cuánto cuesta el envío a Valparaíso? | preventa |
| quiero devolver unas zapatillas | postventa |
| ¿qué hora es en Tokio? | generica |

Cada mensaje deja en el log:
`Telegram chat_id=... ruta=... motivo=...`

### 5. Si no responde, revisa

- El webhook apunta a `https://<tu-app>.herokuapp.com/telegram` (https y
  terminado en `/telegram`): `python scripts/webhook_info.py`.
- `TELEGRAM_SECRET` es **idéntico** en `heroku config` y en el `setWebhook`
  (si no, la API responde 403).
- `TELEGRAM_TOKEN` es el del bot correcto (`getWebhookInfo` debe dar `ok`).
- `heroku logs --tail`: ahí aparecen los 403, los 502 del modelo y los errores
  de `sendMessage`.

### Probar en local antes de desplegar (opcional)

```bash
cloudflared tunnel --url http://localhost:8000
```

Usa la URL https que imprime como `PUBLIC_URL` en `.env`, corre
`python scripts/set_webhook.py` y escríbele al bot. Esa URL cambia cada vez que
reinicias el túnel: si cambia, vuelve a registrar el webhook.

## Desplegar en Heroku

El `Procfile` ya trae `web: uvicorn api.app:app --host 0.0.0.0 --port $PORT` y
`.python-version` fija Python 3.12.

```bash
heroku login
heroku create                      # anota la URL que imprime
heroku config:set GOOGLE_API_KEY=tu_clave
heroku config:set MODELO=gemini-3.5-flash-lite
heroku config:set API_KEY=tu_clave_de_api
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
