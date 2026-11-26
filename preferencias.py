"""Preferencias de la ventana (tema y color de acento) guardadas en un .json del usuario."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

POR_DEFECTO = {"tema": "claro", "acento": "azul"}


def ruta() -> Path:
    """%APPDATA%/DuinoVisor en Windows; ~/.config/duinovisor en el resto. DUINOVISOR_AJUSTES la cambia."""
    propia = os.environ.get("DUINOVISOR_AJUSTES")
    if propia:
        return Path(propia)
    if sys.platform == "win32" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "DuinoVisor" / "ajustes.json"
    return Path.home() / ".config" / "duinovisor" / "ajustes.json"


def cargar() -> dict:
    """Siempre devuelve un dict completo: si el archivo falta o está roto, valen los valores por defecto."""
    datos = dict(POR_DEFECTO)
    try:
        leido = json.loads(ruta().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return datos
    if isinstance(leido, dict):
        datos.update({k: v for k, v in leido.items() if k in POR_DEFECTO and isinstance(v, str)})
    return datos


def guardar(datos: dict) -> bool:
    """Guarda sin lanzar excepciones (no poder guardar las preferencias no debe romper la app)."""
    try:
        r = ruta()
        r.parent.mkdir(parents=True, exist_ok=True)
        r.write_text(json.dumps({k: datos.get(k, v) for k, v in POR_DEFECTO.items()}, indent=2), encoding="utf-8")
        return True
    except OSError:
        return False
