"""Pruebas de la CLI: main.py."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "main.py", *args],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )


def test_diagrama_imprime_mermaid_sin_ejecutar():
    resultado = _cli("asistente", "--diagrama")
    assert resultado.returncode == 0, resultado.stderr
    assert "graph TD" in resultado.stdout
    assert "responder" in resultado.stdout
    assert "pulir" in resultado.stdout


def test_agente_inexistente():
    resultado = _cli("no_existe", "hola")
    assert resultado.returncode != 0
    assert "asistente" in (resultado.stderr + resultado.stdout)


def test_sin_mensaje():
    resultado = _cli("asistente")
    assert resultado.returncode != 0
    assert "mensaje" in (resultado.stderr + resultado.stdout)
