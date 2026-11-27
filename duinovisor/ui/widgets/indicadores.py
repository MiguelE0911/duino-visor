"""Indicadores del clima.

Dos vistas: medidor circular de temperatura y barras de humedad, o termómetro tradicional y una gota que se
llena. Las cuentas de la gota (`contorno_gota`, `recortar_bajo`) no necesitan Tkinter y se prueban solas.
"""
from __future__ import annotations

import math

from duinovisor.ui import tema as T
from duinovisor.ui.widgets.base import Lienzo
from duinovisor.ui.widgets.grafica import COLOR_HUMEDAD

ESCALA_TERMOMETRO = (0, 50)          # °C: el rango del DHT11
COLOR_TERMOMETRO = "#e5533d"         # el rojo de un termómetro de toda la vida


def contorno_gota(cx: float, cy: float, r: float, n: int = 48) -> list[tuple[float, float]]:
    """Puntos de una gota: un círculo de radio r centrado en (cx, cy) y una punta a 2r por encima.

    Las rectas desde la punta tocan el círculo a 60° de la vertical, así el contorno no tiene picos raros.
    """
    puntos = [(cx, cy - 2 * r)]
    for k in range(n + 1):
        a = math.radians(60 + 240 * k / n)            # de 60° a 300°, pasando por abajo
        puntos.append((cx + r * math.sin(a), cy - r * math.cos(a)))
    return puntos


def recortar_bajo(puntos: list[tuple[float, float]], nivel: float) -> list[tuple[float, float]]:
    """La parte del polígono que queda por debajo de `nivel` (y >= nivel en la pantalla).

    Es Sutherland-Hodgman con un único borde horizontal: el Canvas de Tk no sabe recortar.
    """
    if not puntos:
        return []
    salida = []
    for i, actual in enumerate(puntos):
        previo = puntos[i - 1]
        dentro_a, dentro_p = actual[1] >= nivel, previo[1] >= nivel
        if dentro_a != dentro_p:
            t = (nivel - previo[1]) / (actual[1] - previo[1])
            salida.append((previo[0] + t * (actual[0] - previo[0]), nivel))
        if dentro_a:
            salida.append(actual)
    return salida


class Medidor(Lienzo):
    """Medidor circular de 270 grados con el valor en el centro."""

    def __init__(self, master, ancho=170, alto=150, fuente="Helvetica", fondo=None):
        super().__init__(master, ancho, alto, fondo)
        self._fuente = fuente
        self._estado = (0.0, "--", "°C")
        self._dibujar()

    def poner(self, fraccion, texto, unidad="°C"):
        self._estado = (max(0.0, min(1.0, fraccion)), texto, unidad)
        self._dibujar()

    def _pintar(self):
        f, texto, unidad = self._estado
        cx, cy = self.ancho / 2, self.alto / 2 + 4
        r = min(self.ancho, self.alto) / 2 - 14
        self.create_arc(cx - r, cy - r, cx + r, cy + r, start=225, extent=-270, style="arc", outline=T.PISTA,
                        width=self.g(11))
        if f > 0:
            self.create_arc(cx - r, cy - r, cx + r, cy + r, start=225, extent=-270 * f, style="arc",
                            outline=T.ACENTO, width=self.g(11))
        self.create_text(cx, cy - 4, text=texto, fill=T.TEXTO, font=(self._fuente, 24, "bold"))
        self.create_text(cx, cy + 22, text=unidad, fill=T.TEXTO_2, font=(self._fuente, T.TAM_PEQ))


class Barras(Lienzo):
    """Barras verticales con extremos redondeados (las últimas lecturas)."""

    def __init__(self, master, n=6, ancho=170, alto=120, fondo=None):
        super().__init__(master, ancho, alto, fondo)
        self.n = n
        self._valores, self._maximo = [None] * n, 100.0
        self._dibujar()

    def poner(self, valores, maximo=100.0):
        v = list(valores)[-self.n:]
        self._valores = [None] * (self.n - len(v)) + v
        self._maximo = float(maximo)
        self._dibujar()

    def _pintar(self):
        grosor = 16
        paso = (self.ancho - 20) / self.n
        base, tope = self.alto - 6 - grosor / 2, 6 + grosor / 2
        for i, v in enumerate(self._valores):
            x = 10 + paso * (i + 0.5)
            self.create_line(x, base, x, tope, fill=T.PISTA, width=self.g(grosor), capstyle="round")
            if v is not None:
                frac = max(0.0, min(1.0, v / self._maximo))
                color = T.ACENTO if i == self.n - 1 else T.mezclar(T.SUPERFICIE, T.ACENTO, 0.55)
                self.create_line(x, base, x, base - (base - tope) * frac, fill=color, width=self.g(grosor),
                                 capstyle="round")


class Termometro(Lienzo):
    """Termómetro de tubo con bulbo, escala de 0 a 50 °C y el valor a la derecha."""

    def __init__(self, master, ancho=170, alto=170, fuente="Helvetica", fondo=None):
        super().__init__(master, ancho, alto, fondo)
        self._fuente = fuente
        self._t = None
        self._dibujar()

    def poner(self, temperatura):
        self._t = temperatura
        self._dibujar()

    def _pintar(self):
        lo, hi = ESCALA_TERMOMETRO
        x, arriba, abajo = 52, 14, 118                 # el tubo
        rb = 17                                         # radio del bulbo
        yb = abajo + rb - 2
        self.create_line(x, arriba, x, abajo, fill=T.PISTA, width=self.g(18), capstyle="round")
        self.create_oval(x - rb, yb - rb, x + rb, yb + rb, fill=T.PISTA, outline="")
        for v in range(lo, hi + 1, 10):
            y = abajo - (v - lo) / (hi - lo) * (abajo - arriba)
            self.create_line(x + 13, y, x + 19, y, fill=T.TEXTO_3, width=self.g(1))
            self.create_text(x + 23, y, text=str(v), anchor="w", fill=T.TEXTO_3, font=(self._fuente, T.TAM_MINI))
        if self._t is not None:
            frac = max(0.0, min(1.0, (self._t - lo) / (hi - lo)))
            y = abajo - frac * (abajo - arriba)
            self.create_line(x, abajo, x, y, fill=COLOR_TERMOMETRO, width=self.g(9), capstyle="round")
            self.create_oval(x - rb + 5, yb - rb + 5, x + rb - 5, yb + rb - 5, fill=COLOR_TERMOMETRO, outline="")
        texto = "--" if self._t is None else f"{self._t:.1f}"
        self.create_text(128, 66, text=texto, fill=T.TEXTO, font=(self._fuente, 20, "bold"))
        self.create_text(128, 92, text="°C", fill=T.TEXTO_2, font=(self._fuente, T.TAM_PEQ))


class Gota(Lienzo):
    """Gota de agua que se llena desde abajo según la humedad (0-100 %), con el valor dentro."""

    def __init__(self, master, ancho=170, alto=170, fuente="Helvetica", fondo=None):
        super().__init__(master, ancho, alto, fondo)
        self._fuente = fuente
        self._h = None
        self._dibujar()

    def poner(self, humedad):
        self._h = humedad
        self._dibujar()

    def _pintar(self):
        r = 46
        cx, cy = self.ancho / 2, self.alto - 12 - r
        contorno = contorno_gota(cx, cy, r)
        plano = [c for p in contorno for c in p]
        self.create_polygon(plano, fill=T.SUPERFICIE_2, outline="")
        if self._h is not None:
            frac = max(0.0, min(1.0, self._h / 100))
            arriba, abajo = cy - 2 * r, cy + r
            agua = recortar_bajo(contorno, abajo - frac * (abajo - arriba))
            if len(agua) >= 3:
                self.create_polygon([c for p in agua for c in p], fill=T.mezclar(T.SUPERFICIE, COLOR_HUMEDAD, 0.8),
                                    outline="")
        self.create_polygon(plano, fill="", outline=COLOR_HUMEDAD, width=self.g(2.5))
        texto = "--" if self._h is None else f"{self._h:.0f} %"
        self.create_text(cx, cy + 4, text=texto, fill=T.TEXTO, font=(self._fuente, 18, "bold"))
