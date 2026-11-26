"""Paleta oscura con acento ámbar y tipografía de DuinoVisor."""
from __future__ import annotations

FONDO = "#141415"        # fondo de la ventana
BARRA = "#19191a"        # barra lateral
TARJETA = "#232325"      # tarjetas
TARJETA_2 = "#2b2b2e"    # campos y botones secundarios
BORDE = "#34343a"
PISTA = "#3a3a3e"        # pistas de deslizadores, medidor y barras

AMBAR = "#e9a24b"
AMBAR_CLARO = "#f4c47f"
SOBRE_AMBAR = "#1b1b1c"  # texto sobre fondo ámbar

TEXTO = "#ece6da"
TEXTO_2 = "#a39c8e"
TEXTO_3 = "#6f6a60"

VERDE = "#a3c48a"
ROJO = "#e07a5f"
ROJO_ALARMA = "#b8452f"

LED_BASE = {"R": "#e5533d", "G": "#6fcf6f", "Y": "#f2c14e"}

FUENTES_PREFERIDAS = ("Segoe UI", "SF Pro Display", "Helvetica Neue", "Ubuntu", "Cantarell",
                      "DejaVu Sans", "Helvetica", "Arial")


def hex_a_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def mezclar(a: str, b: str, f: float) -> str:
    """Color entre `a` (f = 0) y `b` (f = 1)."""
    f = max(0.0, min(1.0, f))
    ra, rb = hex_a_rgb(a), hex_a_rgb(b)
    return "#{:02x}{:02x}{:02x}".format(*(round(x + (y - x) * f) for x, y in zip(ra, rb)))


def elegir_fuente(disponibles) -> str:
    """Primera fuente preferida que exista; si ninguna, la genérica de Tk."""
    existentes = {f.lower() for f in disponibles}
    for nombre in FUENTES_PREFERIDAS:
        if nombre.lower() in existentes:
            return nombre
    return "Helvetica"


def fuente(raiz=None) -> str:
    try:
        from tkinter import font as tkfont
        return elegir_fuente(tkfont.families(raiz))
    except Exception:
        return "Helvetica"
