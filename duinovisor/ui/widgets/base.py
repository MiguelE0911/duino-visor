"""Piezas comunes de los widgets: lienzo escalado, rectángulos redondeados, etiquetas y entradas.

Los colores se leen de `tema` al crear cada widget: tras `tema.aplicar()` hay que volver a crearlos.
Los lienzos dibujan en unidades lógicas (96 ppp) y luego se escalan con `tema.ESCALA`.
"""
from __future__ import annotations

import tkinter as tk

from duinovisor.ui import tema as T


def rect_redondo(c, x0, y0, x1, y1, r, **kw):
    r = max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1,
           x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
    return c.create_polygon(pts, smooth=True, **kw)


def entrada(master, variable, ancho=7, fuente="Helvetica", fondo=None):
    return tk.Entry(master, textvariable=variable, width=ancho, bg=T.SUPERFICIE_2, fg=T.TEXTO,
                    insertbackground=T.ACENTO, relief="flat", highlightthickness=1,
                    highlightbackground=T.BORDE, highlightcolor=T.ACENTO, font=(fuente, T.TAM_CUERPO),
                    justify="center", disabledbackground=fondo or T.SUPERFICIE, disabledforeground=T.TEXTO_3)


def etiqueta(master, texto="", fuente="Helvetica", tam=None, color=None, fondo=None, negrita=False, **kw):
    tam = tam or T.TAM_CUERPO
    return tk.Label(master, text=texto, bg=fondo or T.SUPERFICIE, fg=color or T.TEXTO_2,
                    font=(fuente, tam, "bold") if negrita else (fuente, tam), **kw)


def medir(texto: str, fuente: str, tam: int, negrita=False) -> float:
    """Ancho del texto en unidades lógicas (aproximado si no hay pantalla)."""
    try:
        from tkinter import font as tkfont
        px = tkfont.Font(family=fuente, size=tam, weight="bold" if negrita else "normal").measure(texto)
        return px / T.ESCALA
    except Exception:
        return len(texto) * tam * 0.62


class Lienzo(tk.Canvas):
    """Base: tamaño lógico, escala de pantalla, habilitar/deshabilitar y traces que se limpian solos."""

    def __init__(self, master, ancho, alto, fondo=None, zoom=1.0):
        self.S = T.ESCALA
        self.zoom = zoom
        self.fondo = fondo or T.SUPERFICIE
        super().__init__(master, width=round(ancho * self.S), height=round(alto * self.S), bg=self.fondo,
                         highlightthickness=0, bd=0)
        self.ancho, self.alto = ancho / zoom, alto / zoom          # coordenadas de dibujo
        self._habilitado = True
        self._traces = []
        self.bind("<Destroy>", self._al_destruir, add="+")

    def _vigilar(self, variable, funcion):
        tid = variable.trace_add("write", lambda *_: funcion())
        self._traces.append((variable, tid))

    def _al_destruir(self, e=None):
        if e is not None and e.widget is not self:
            return
        for variable, tid in self._traces:
            try:
                variable.trace_remove("write", tid)
            except Exception:
                pass
        self._traces = []

    def _xy(self, e):
        f = self.S * self.zoom
        return e.x / f, e.y / f

    def g(self, w):
        """Grosor de línea escalado."""
        return max(1, round(w * self.S * self.zoom))

    def habilitar(self, si: bool) -> None:
        self._habilitado = bool(si)
        self._dibujar()

    def _dibujar(self) -> None:
        try:
            self.delete("all")
        except tk.TclError:
            return
        self._pintar()
        f = self.S * self.zoom
        if f != 1:
            self.scale("all", 0, 0, f, f)

    def _pintar(self) -> None:            # lo redefine cada widget
        pass
