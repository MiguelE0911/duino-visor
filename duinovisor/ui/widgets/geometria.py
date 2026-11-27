"""Cuentas de dibujo sin Tkinter: curvas de los cables, degradados, encaje y zoom de la protoboard.

Todo trabaja con tuplas de números, así que se prueba en cualquier equipo (tests/ui/test_geometria.py).
"""
from __future__ import annotations

import math

Punto = tuple[float, float]


# ---------------------------------------------------------------- curvas
def curva_suave(puntos: list[Punto], pasos: int = 10) -> list[Punto]:
    """Polilínea que sigue la misma curva que Tk dibuja con `smooth=True` (splines cuadráticos).

    Con los puntos de control P0..Pn, cada tramo va del punto medio de (Pi, Pi+1) al de (Pi+1, Pi+2) con Pi+1
    de control; el primero empieza en P0 y el último acaba en Pn. Así la línea dibujada y la animación de la
    corriente que la recorre coinciden.
    """
    if len(puntos) < 3:
        return list(puntos)
    medio = [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in zip(puntos, puntos[1:])]
    salida = [puntos[0]]
    ultimo = len(puntos) - 3
    for i in range(ultimo + 1):
        inicio = puntos[0] if i == 0 else medio[i]
        control = puntos[i + 1]
        fin = puntos[-1] if i == ultimo else medio[i + 1]
        for k in range(1, pasos + 1):
            t = k / pasos
            u = 1 - t
            salida.append((u * u * inicio[0] + 2 * u * t * control[0] + t * t * fin[0],
                           u * u * inicio[1] + 2 * u * t * control[1] + t * t * fin[1]))
    return salida


def longitud(polilinea: list[Punto]) -> float:
    return sum(math.dist(a, b) for a, b in zip(polilinea, polilinea[1:]))


def punto_en(polilinea: list[Punto], fraccion: float) -> Punto:
    """El punto a esa fracción (0-1) del largo de la polilínea."""
    if not polilinea:
        return (0.0, 0.0)
    objetivo = max(0.0, min(1.0, fraccion)) * longitud(polilinea)
    for a, b in zip(polilinea, polilinea[1:]):
        tramo = math.dist(a, b)
        if objetivo <= tramo and tramo > 0:
            t = objetivo / tramo
            return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        objetivo -= tramo
    return polilinea[-1]


# ---------------------------------------------------------------- degradados
def bandas(y0: float, y1: float, n: int) -> list[tuple[float, float, float]]:
    """Franjas horizontales (ya, yb, f) que cubren de y0 a y1 sin huecos; f va de 0 (arriba) a 1 (abajo)."""
    n = max(1, n)
    alto = (y1 - y0) / n
    return [(y0 + i * alto, y0 + (i + 1) * alto, i / (n - 1) if n > 1 else 0.0) for i in range(n)]


# ---------------------------------------------------------------- encaje y zoom
# `escena` es el tamaño del montaje en unidades virtuales; `vista`, el rectángulo útil del lienzo en píxeles
# (x0, y0, x1, y1): el lienzo entero menos lo que tapan la ficha y los márgenes.
def encaje(vista, escena) -> float:
    """Zoom con el que todo el montaje cabe en la vista."""
    return min((vista[2] - vista[0]) / escena[0], (vista[3] - vista[1]) / escena[1])


def origen_centrado(vista, z: float, escena) -> Punto:
    """Dónde cae la esquina (0, 0) del montaje para que quede centrado en la vista con zoom z."""
    return (vista[0] + (vista[2] - vista[0] - escena[0] * z) / 2,
            vista[1] + (vista[3] - vista[1] - escena[1] * z) / 2)


def zoom_en_punto(px: float, py: float, z0: float, z1: float, origen) -> Punto:
    """Nuevo origen al pasar de z0 a z1 sin mover el punto del montaje que está bajo (px, py)."""
    ox, oy = origen
    return px - (px - ox) * z1 / z0, py - (py - oy) * z1 / z0


def limitar_origen(origen, vista, z: float, escena) -> Punto:
    """Si el montaje cabe en un eje, queda centrado; si no, no se puede alejar tanto que se vea un hueco."""
    res = []
    for o, tam, a, b in ((origen[0], escena[0] * z, vista[0], vista[2]), (origen[1], escena[1] * z, vista[1], vista[3])):
        res.append(a + (b - a - tam) / 2 if tam <= b - a else min(a, max(b - tam, o)))
    return res[0], res[1]


def suavizar(t: float) -> float:
    """Curva «ease-out» (0 -> 0, 1 -> 1) para las animaciones."""
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3
