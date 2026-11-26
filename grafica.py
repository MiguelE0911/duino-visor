"""Gráfica en vivo de temperatura y humedad sobre un Canvas de Tkinter."""
from __future__ import annotations

from collections import deque
from typing import Optional, Sequence

import tema as T

try:
    import tkinter as tk
    _Base = tk.Canvas
except ImportError:          # permite probar calcular_puntos sin Tkinter instalado
    tk = None
    _Base = object

MAX_LECTURAS = 60
T_MIN, T_MAX = 0.0, 50.0       # rango del DHT11 para temperatura
H_MIN, H_MAX = 0.0, 100.0


def calcular_puntos(valores: Sequence[Optional[float]], ancho: int, alto: int,
                    vmin: float, vmax: float, margen: tuple[int, int, int, int],
                    capacidad: int = MAX_LECTURAS) -> list[list[tuple[float, float]]]:
    """Convierte lecturas en segmentos de puntos (x, y) de pantalla.

    Los huecos (None, por ejemplo una lectura fallida) cortan la línea en segmentos.
    La lectura más reciente queda en el borde derecho.
    """
    izq, arriba, der, abajo = margen
    w = ancho - izq - der
    h = alto - arriba - abajo
    n = len(valores)
    segmentos: list[list[tuple[float, float]]] = []
    actual: list[tuple[float, float]] = []
    for i, v in enumerate(valores):
        if v is None:
            if actual:
                segmentos.append(actual)
                actual = []
            continue
        pos = capacidad - n + i                        # alineado a la derecha
        x = izq + w * pos / max(capacidad - 1, 1)
        frac = min(max((v - vmin) / (vmax - vmin), 0.0), 1.0)
        y = arriba + h * (1 - frac)
        actual.append((x, y))
    if actual:
        segmentos.append(actual)
    return segmentos


class Grafica(_Base):
    """Gráfica de área: temperatura en ámbar (con relleno) y humedad en crema."""
    MARGEN = (30, 10, 30, 10)

    def __init__(self, master, ancho: int = 420, alto: int = 170, fuente: str = "Helvetica"):
        super().__init__(master, width=ancho, height=alto, bg=T.TARJETA, highlightthickness=0, bd=0)
        self.ancho, self.alto, self._fuente = ancho, alto, fuente
        self.temperaturas: deque = deque(maxlen=MAX_LECTURAS)
        self.humedades: deque = deque(maxlen=MAX_LECTURAS)
        self.bind("<Configure>", self._al_redimensionar)
        self.dibujar()

    def agregar(self, temperatura: Optional[float], humedad: Optional[float]) -> None:
        self.temperaturas.append(temperatura)
        self.humedades.append(humedad)
        self.dibujar()

    def limpiar(self) -> None:
        self.temperaturas.clear()
        self.humedades.clear()
        self.dibujar()

    def _al_redimensionar(self, evento):
        self.ancho, self.alto = evento.width, evento.height
        self.dibujar()

    def dibujar(self) -> None:
        self.delete("all")
        izq, arriba, der, abajo = self.MARGEN
        x0, x1, y0, y1 = izq, self.ancho - der, arriba, self.alto - abajo
        for i in range(6):                                           # rejilla y escalas (50 °C / 100 %)
            y = y0 + (y1 - y0) * i / 5
            self.create_line(x0, y, x1, y, fill=T.BORDE)
            self.create_text(x0 - 6, y, text=f"{T_MAX - (T_MAX - T_MIN) * i / 5:.0f}", anchor="e",
                             fill=T.TEXTO_3, font=(self._fuente, 8))
            self.create_text(x1 + 6, y, text=f"{H_MAX - (H_MAX - H_MIN) * i / 5:.0f}", anchor="w",
                             fill=T.TEXTO_3, font=(self._fuente, 8))
        segmentos_t = calcular_puntos(list(self.temperaturas), self.ancho, self.alto, T_MIN, T_MAX, self.MARGEN)
        relleno = T.mezclar(T.TARJETA, T.AMBAR, 0.17)
        for seg in segmentos_t:                                      # área bajo la curva (franjas verticales)
            if len(seg) < 2:
                continue
            x = seg[0][0]
            while x <= seg[-1][0]:
                self.create_line(x, _interpolar(seg, x), x, y1, fill=relleno, width=3)
                x += 3
        for segmentos, color, ancho_linea in (
                (segmentos_t, T.AMBAR, 2.5),
                (calcular_puntos(list(self.humedades), self.ancho, self.alto, H_MIN, H_MAX, self.MARGEN),
                 T.mezclar(T.TEXTO, T.TARJETA, 0.15), 1.5)):
            for seg in segmentos:
                if len(seg) == 1:
                    x, y = seg[0]
                    self.create_oval(x - 2, y - 2, x + 2, y + 2, fill=color, outline=color)
                else:
                    self.create_line(*[c for p in seg for c in p], fill=color, width=ancho_linea,
                                     capstyle="round", joinstyle="round")


def _interpolar(segmento, x):
    """y de la poligonal `segmento` en la abscisa x."""
    for (xa, ya), (xb, yb) in zip(segmento, segmento[1:]):
        if xa <= x <= xb:
            return ya if xb == xa else ya + (yb - ya) * (x - xa) / (xb - xa)
    return segmento[-1][1]
