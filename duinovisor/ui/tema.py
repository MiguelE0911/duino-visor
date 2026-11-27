"""Paletas (clara y oscura), colores de acento y tipografía de DuinoVisor.

Los widgets leen los colores de este módulo (T.FONDO, T.ACENTO, ...) cuando se crean, así que para
cambiar de tema basta con llamar a `aplicar()` y volver a construir la ventana.
"""
from __future__ import annotations

# ---------------------------------------------------------------- paletas
PALETAS = {
    "claro": {
        "FONDO": "#f4f5f7",         # fondo de la ventana
        "SUPERFICIE": "#ffffff",    # tarjetas
        "SUPERFICIE_2": "#f1f3f6",  # campos, botones secundarios, hover
        "BORDE": "#e1e4e9",
        "PISTA": "#e3e6eb",         # pistas de deslizadores, medidor y barras
        "TEXTO": "#1c2026",
        "TEXTO_2": "#4f5864",
        "TEXTO_3": "#8a929c",
        "EXITO": "#1a7f45",
        "ERROR": "#c2362b",
        "ALARMA": "#c2362b",
        "SOBRE_ACENTO": "#ffffff",
    },
    "oscuro": {
        "FONDO": "#141415",
        "SUPERFICIE": "#232325",
        "SUPERFICIE_2": "#2b2b2e",
        "BORDE": "#34343a",
        "PISTA": "#3a3a3e",
        "TEXTO": "#ece6da",
        "TEXTO_2": "#a39c8e",
        "TEXTO_3": "#6f6a60",
        "EXITO": "#a3c48a",
        "ERROR": "#e07a5f",
        "ALARMA": "#b8452f",
        "SOBRE_ACENTO": "#141415",
    },
}

# nombre -> (rótulo, color en tema claro, color en tema oscuro). Los del claro tienen contraste
# suficiente con texto blanco; los del oscuro, con texto casi negro.
ACENTOS = {
    "azul": ("Azul", "#2563eb", "#60a5fa"),
    "verde": ("Verde azulado", "#0f766e", "#2dd4bf"),
    "violeta": ("Violeta", "#7c3aed", "#a78bfa"),
    "ambar": ("Ámbar", "#b45309", "#e9a24b"),
    "rosa": ("Rosa", "#db2777", "#f472b6"),
}
TEMA_POR_DEFECTO, ACENTO_POR_DEFECTO = "claro", "azul"

LED_BASE = {"R": "#e5533d", "G": "#4fbf5f", "Y": "#f2c14e"}

# Escala de la pantalla (1.0 = 96 ppp). La fija la App al arrancar; los lienzos la usan para
# dibujar al tamaño correcto en pantallas con escalado (125 %, 150 %...).
ESCALA = 1.0

# Tamaños de letra (puntos)
TAM_TITULO, TAM_SECCION, TAM_CUERPO, TAM_PEQ, TAM_MINI = 20, 13, 11, 10, 9

FUENTES_PREFERIDAS = ("Segoe UI Variable Text", "Segoe UI", "SF Pro Display", "Helvetica Neue", "Ubuntu",
                      "Cantarell", "DejaVu Sans", "Helvetica", "Arial")
FUENTES_MONO = ("Cascadia Mono", "Consolas", "SF Mono", "Menlo", "DejaVu Sans Mono", "Ubuntu Mono",
                "Courier New")

tema_actual, acento_actual = TEMA_POR_DEFECTO, ACENTO_POR_DEFECTO


def hex_a_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def mezclar(a: str, b: str, f: float) -> str:
    """Color entre `a` (f = 0) y `b` (f = 1)."""
    f = max(0.0, min(1.0, f))
    ra, rb = hex_a_rgb(a), hex_a_rgb(b)
    return "#{:02x}{:02x}{:02x}".format(*(round(x + (y - x) * f) for x, y in zip(ra, rb)))


def aplicar(tema: str = TEMA_POR_DEFECTO, acento: str = ACENTO_POR_DEFECTO) -> None:
    """Fija los colores del módulo. Valores desconocidos caen en los de por defecto."""
    global tema_actual, acento_actual, ACENTO, ACENTO_HOVER, ACENTO_SUAVE, OSCURO
    tema = tema if tema in PALETAS else TEMA_POR_DEFECTO
    acento = acento if acento in ACENTOS else ACENTO_POR_DEFECTO
    tema_actual, acento_actual = tema, acento
    globals().update(PALETAS[tema])
    OSCURO = tema == "oscuro"
    ACENTO = ACENTOS[acento][2 if OSCURO else 1]
    ACENTO_HOVER = mezclar(ACENTO, "#ffffff" if OSCURO else "#000000", 0.15)
    ACENTO_SUAVE = mezclar(SUPERFICIE, ACENTO, 0.16 if OSCURO else 0.10)  # noqa: F821 (lo define update)


aplicar()


# ---------------------------------------------------------------- tipografía
def _primera(preferidas, disponibles, defecto: str) -> str:
    existentes = {f.lower() for f in disponibles}
    for nombre in preferidas:
        if nombre.lower() in existentes:
            return nombre
    return defecto


def elegir_fuente(disponibles) -> str:
    """Primera fuente preferida que exista; si ninguna, la genérica de Tk."""
    return _primera(FUENTES_PREFERIDAS, disponibles, "Helvetica")


def _familias(raiz):
    from tkinter import font as tkfont
    return tkfont.families(raiz)


def fuente(raiz=None) -> str:
    try:
        return elegir_fuente(_familias(raiz))
    except Exception:
        return "Helvetica"


def fuente_mono(raiz=None) -> str:
    try:
        return _primera(FUENTES_MONO, _familias(raiz), "TkFixedFont")
    except Exception:
        return "TkFixedFont"
