"""Indicadores del clima: medidor circular de temperatura y barras de humedad."""
from __future__ import annotations

from duinovisor.ui import tema as T
from duinovisor.ui.widgets.base import Lienzo


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
