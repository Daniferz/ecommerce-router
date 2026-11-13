"""Pruebas de la memoria: RAM sin DATABASE_URL y fallback si Postgres falla."""
from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver

from src import base


def _limpiar() -> None:
    base.cerrar_memoria()


def test_sin_database_url_usa_ram(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    _limpiar()
    try:
        memoria = base.abrir_memoria()
        assert memoria.tipo == "ram"
        assert isinstance(memoria.checkpointer, MemorySaver)
        assert "DATABASE_URL" in memoria.motivo
    finally:
        _limpiar()


def test_postgres_caido_usa_ram_sin_tumbar_la_app(monkeypatch):
    # Puerto 1: conexión rechazada al instante, sin esperar al timeout real.
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://usuario:clave@127.0.0.1:1/base"
    )
    monkeypatch.setenv("DATABASE_TIMEOUT", "2")
    _limpiar()
    try:
        memoria = base.abrir_memoria()
        assert memoria.tipo == "ram"
        assert isinstance(memoria.checkpointer, MemorySaver)
        assert "Postgres no disponible" in memoria.motivo
    finally:
        _limpiar()
