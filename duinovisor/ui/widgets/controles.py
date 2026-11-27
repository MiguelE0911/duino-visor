"""Controles de valor: deslizador e interruptor."""
from __future__ import annotations

from duinovisor.ui import tema as T
from duinovisor.ui.widgets.base import Lienzo, rect_redondo


class Deslizador(Lienzo):
    """Deslizador entero con pista fina y asa redonda, ligado a una IntVar."""
    M = 11

    def __init__(self, master, variable, desde, hasta, ancho=180, fondo=None):
        super().__init__(master, ancho, 26, fondo)
        self.variable, self.desde, self.hasta = variable, desde, hasta
        self.configure(cursor="hand2")
        self.bind("<Button-1>", self._mover)
        self.bind("<B1-Motion>", self._mover)
        self._vigilar(variable, self._dibujar)
        self._dibujar()

    def _x(self, valor):
        f = (valor - self.desde) / (self.hasta - self.desde)
        return self.M + (self.ancho - 2 * self.M) * max(0.0, min(1.0, f))

    def _mover(self, e):
        if not self._habilitado:
            return
        x, _ = self._xy(e)
        f = max(0.0, min(1.0, (x - self.M) / (self.ancho - 2 * self.M)))
        v = round(self.desde + f * (self.hasta - self.desde))
        if v != self.variable.get():
            self.variable.set(v)

    def _pintar(self):
        y = self.alto / 2
        x = self._x(self.variable.get())
        color = T.ACENTO if self._habilitado else T.TEXTO_3
        self.create_line(self.M, y, self.ancho - self.M, y, fill=T.PISTA, width=self.g(5), capstyle="round")
        self.create_line(self.M, y, x, y, fill=color, width=self.g(5), capstyle="round")
        self.create_oval(x - 9, y - 9, x + 9, y + 9, fill=T.SUPERFICIE, outline=color, width=self.g(2.5))


class Interruptor(Lienzo):
    """Interruptor on/off ligado a una BooleanVar."""

    def __init__(self, master, variable, fondo=None):
        super().__init__(master, 44, 26, fondo)
        self.variable = variable
        self.configure(cursor="hand2")
        self.bind("<Button-1>", self._clic)
        self._vigilar(variable, self._dibujar)
        self._dibujar()

    def _clic(self, e):
        if self._habilitado:
            self.variable.set(not self.variable.get())

    def _pintar(self):
        on = bool(self.variable.get())
        pista = (T.ACENTO if on else T.PISTA) if self._habilitado else T.SUPERFICIE_2
        rect_redondo(self, 1, 2, 43, 24, 11, fill=pista, outline=pista)
        x = 32 if on else 12
        self.create_oval(x - 8, 13 - 8, x + 8, 13 + 8, fill="#ffffff", outline=T.mezclar(pista, "#000000", 0.08))
