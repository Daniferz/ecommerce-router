"""Comprueba que la configuración obligatoria exista y no tenga secretos reales."""
from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

CLAVES_ESPERADAS = [
    "GOOGLE_API_KEY",
    "MODELO=gemini-3.5-flash-lite",
    "DATABASE_URL=postgresql://",
    "TELEGRAM_TOKEN",
    "TELEGRAM_SECRET=cambiame",
    "PUBLIC_URL",
]


def test_env_example_trae_las_claves():
    contenido = (RAIZ / ".env.example").read_text(encoding="utf-8")
    for clave in CLAVES_ESPERADAS:
        assert clave in contenido, f"Falta {clave} en .env.example"


def test_gitignore_protecte_secretos():
    contenido = (RAIZ / ".gitignore").read_text(encoding="utf-8")
    for linea in (".env", ".venv", "__pycache__", ".langgraph_api"):
        assert linea in contenido, f"Falta {linea} en .gitignore"


def test_procfile_y_python_version():
    procfile = (RAIZ / "Procfile").read_text(encoding="utf-8")
    assert "web: uvicorn api.app:app --host 0.0.0.0 --port $PORT" in procfile
    assert (RAIZ / ".python-version").read_text(encoding="utf-8").strip() == "3.12"


def test_requirements_con_las_dependencias():
    contenido = (RAIZ / "requirements.txt").read_text(encoding="utf-8")
    for paquete in (
        "langgraph",
        "langgraph-checkpoint-postgres",
        "psycopg[binary,pool]",
        "langchain",
        "langchain-google-genai",
        "fastapi",
        "uvicorn",
        "httpx",
        "pydantic",
        "python-dotenv",
        "pytest",
    ):
        assert paquete in contenido, f"Falta {paquete} en requirements.txt"


def test_agents_md_existe():
    contenido = (RAIZ / "AGENTS.md").read_text(encoding="utf-8")
    for regla in ("src/{nombre_agente}", "--saltos", "--diagrama", "api/app.py", "Procfile"):
        assert regla in contenido, f"Falta la regla {regla} en AGENTS.md"
