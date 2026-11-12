# AGENTS.md — Reglas del proyecto

Proyecto Python 3.12 con agentes (LangGraph + Gemini), API FastAPI y despliegue en Heroku.

## Estructura

```
.
├── main.py              # CLI: ejecuta los agentes
├── api/app.py           # FastAPI
├── src/
│   ├── base.py          # compartido: .env, modelo, carga y ejecución de grafos
│   └── {nombre_agente}/ # un agente por carpeta
│       ├── graph.py     # nodos y aristas del grafo
│       ├── prompts.py   # TODOS los prompts
│       └── tools.py     # herramientas (@tool) y utilidades
├── scripts/             # scripts sueltos
├── tests/               # pruebas pytest
├── Procfile             # Heroku
├── .python-version      # 3.12
└── requirements.txt     # siempre actualizado
```

## Reglas

1. **Agentes en `src/{nombre_agente}/`** con `graph.py`, `prompts.py` y `tools.py`.
   - Cada nodo tiene **su propio prompt en `prompts.py`**.
   - **Nada de reglas ni textos dentro de `graph.py`**: solo la definición de nodos
     y aristas. En `graph.py` se exporta `app` (el grafo compilado).
   - El estado de cada grafo es un `TypedDict` con `mensaje` (entrada) y
     `respuesta` (salida).

2. **Se ejecutan desde la raíz**:
   ```bash
   python main.py {nombre_agente} "mensaje"
   ```
   - Flag `--saltos`: imprime los nodos por los que pasó el grafo.
   - Flag `--diagrama`: imprime el Mermaid del grafo **sin ejecutarlo**.

3. **La API va en `api/app.py`** (FastAPI) y se levanta con:
   ```bash
   uvicorn api.app:app --reload --port 8000
   ```

4. **Scripts sueltos en `scripts/`** y **pruebas en `tests/`** (pytest):
   ```bash
   pytest
   ```

5. **Heroku**: `Procfile` con
   `web: uvicorn api.app:app --host 0.0.0.0 --port $PORT`,
   `.python-version` con `3.12`, y `requirements.txt` siempre actualizado
   (regenerarlo cuando se agregue o cambie una dependencia).

6. **`.gitignore`** debe mantener siempre: `.env`, `.venv`, `__pycache__` y
   `.langgraph_api`. **Nunca valores reales en el código**: todo secreto vive en
   `.env` (copia `.env.example`), nunca en el repositorio.

## Variables de entorno (`.env.example`)

| Variable | Qué es |
|---|---|
| `GOOGLE_API_KEY` | Clave de Google AI Studio |
| `MODELO` | `gemini-3.5-flash-lite` |
| `API_KEY` | Clave que protege `POST /chat` (cabecera `X-API-Key`) |
| `TELEGRAM_TOKEN` | Lo da @BotFather; vacío hasta el paso 5 |
| `TELEGRAM_SECRET` | Secreto que Telegram envía en cada webhook para verificarlo |
| `PUBLIC_URL` | URL https pública; vacío hasta Heroku |

## Cómo agregar un agente

1. Crear `src/mi_agente/{__init__.py, graph.py, prompts.py, tools.py}`.
2. Escribir los prompts en `prompts.py`.
3. Definir nodos y aristas en `graph.py` y exportar `app = construir_grafo()`.
4. Probar: `python main.py mi_agente --diagrama` y luego `python main.py mi_agente "hola" --saltos`.

## Endpoints de la API

- `GET /` — salud, modelo y agentes disponibles.
- `POST /chat` — `{"agente": "...", "mensaje": "..."}` → respuesta + nodos.
- `POST /webhook/telegram` — recibe los updates de Telegram; verifica el header
  `X-Telegram-Bot-Api-Secret-Token` contra `TELEGRAM_SECRET` (401 si no coincide).
