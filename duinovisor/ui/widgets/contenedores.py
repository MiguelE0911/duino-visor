"""Contenedores: tarjeta con título, panel desplazable y aviso con franja de color."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from duinovisor.ui import tema as T
from duinovisor.ui.widgets.base import rect_redondo


class Tarjeta(tk.Canvas):
    """Panel de esquinas redondas con título. El contenido va en `.contenido`.

    Con `llenar=True` el contenido ocupa todo el alto que el layout le dé a la tarjeta; si no, la tarjeta
    toma el alto de su contenido.
    """
    PAD = 18

    def __init__(self, master, titulo="", fuente="Helvetica", radio=14, color=None, fondo=None, llenar=False,
                 subtitulo=""):
        color, fondo = color or T.SUPERFICIE, fondo or T.FONDO
        super().__init__(master, bg=fondo, highlightthickness=0, bd=0, height=60, width=120)
        self.S = T.ESCALA
        self._pad = round(self.PAD * self.S)
        self._radio, self._color, self._llenar = radio * self.S, color, llenar
        self.cuerpo = tk.Frame(self, bg=color)
        self._ventana = self.create_window(self._pad, self._pad, anchor="nw", window=self.cuerpo)
        cabecera = tk.Frame(self.cuerpo, bg=color)
        self.titulo = tk.Label(cabecera, text=titulo, bg=color, fg=T.TEXTO, font=(fuente, T.TAM_SECCION, "bold"),
                               anchor="w")
        self.titulo.pack(side="left")
        self.extra = tk.Frame(cabecera, bg=color)
        self.extra.pack(side="right")
        if titulo or subtitulo:
            cabecera.pack(fill="x")
        if subtitulo:
            tk.Label(self.cuerpo, text=subtitulo, bg=color, fg=T.TEXTO_2, font=(fuente, T.TAM_PEQ), anchor="w",
                     justify="left").pack(fill="x")
        self.contenido = tk.Frame(self.cuerpo, bg=color)
        self.contenido.pack(fill="both", expand=True, pady=(round(12 * self.S) if titulo else 0, 0))
        self.bind("<Configure>", self._al_cambiar_tamano)
        if not llenar:
            self.cuerpo.bind("<Configure>", self._al_cambiar_cuerpo)

    def _al_cambiar_tamano(self, e):
        self.delete("fondo")
        rect_redondo(self, 1, 1, e.width - 1, e.height - 1, self._radio, fill=self._color,
                     outline=T.BORDE, tags="fondo")
        self.tag_lower("fondo")
        kw = {"width": max(10, e.width - 2 * self._pad)}
        if self._llenar:
            kw["height"] = max(10, e.height - 2 * self._pad)
        self.itemconfigure(self._ventana, **kw)

    def _al_cambiar_cuerpo(self, e):
        self.configure(height=e.height + 2 * self._pad)


class Desplazable(tk.Frame):
    """Columna con desplazamiento vertical: la barra solo aparece si el contenido no cabe.

    El contenido va en `.interior`. A la derecha queda siempre un margen (`MARGEN`) donde se dibuja la barra.
    La rueda del ratón desplaza la columna que está bajo el puntero.
    """
    MARGEN = 12
    _instancias: list = []
    _instalado = False

    def __init__(self, master, fondo=None):
        fondo = fondo or T.FONDO
        super().__init__(master, bg=fondo)
        self._margen = round(self.MARGEN * T.ESCALA)
        self.lienzo = tk.Canvas(self, bg=fondo, highlightthickness=0, bd=0, width=10, height=10)
        self.lienzo.pack(fill="both", expand=True)
        self.barra = ttk.Scrollbar(self, orient="vertical", command=self.lienzo.yview, style="Duino.Vertical.TScrollbar")
        self.lienzo.configure(yscrollcommand=self.barra.set)
        self.interior = tk.Frame(self.lienzo, bg=fondo)
        self._ventana = self.lienzo.create_window(0, 0, anchor="nw", window=self.interior)
        self._visible = False
        self.interior.bind("<Configure>", self._ajustar)
        self.lienzo.bind("<Configure>", self._ajustar)
        Desplazable._instancias.append(self)
        self.bind("<Destroy>", lambda e: e.widget is self and self in Desplazable._instancias
                  and Desplazable._instancias.remove(self), add="+")
        if not Desplazable._instalado:
            try:
                self.bind_all("<MouseWheel>", Desplazable._rueda, add="+")
                Desplazable._instalado = True
            except Exception:
                pass

    def _ajustar(self, e=None):
        try:
            ancho, alto = self.lienzo.winfo_width(), self.lienzo.winfo_height()
            req = self.interior.winfo_reqheight()
            self.lienzo.itemconfigure(self._ventana, width=max(10, ancho - self._margen))
            self.lienzo.configure(scrollregion=(0, 0, ancho, req))
            sobra = req > alto + 1
            if sobra and not self._visible:
                self.barra.place(relx=1, rely=0, relheight=1, anchor="ne", width=self._margen)
            elif not sobra and self._visible:
                self.barra.place_forget()
                self.lienzo.yview_moveto(0)
            self._visible = sobra
        except (tk.TclError, TypeError):
            pass

    @staticmethod
    def _rueda(e):
        destino = str(e.widget)
        for d in Desplazable._instancias:
            if d._visible and destino.startswith(str(d)):
                d.lienzo.yview_scroll(int(-e.delta / 120) or (-1 if e.delta > 0 else 1), "units")
                return


class Aviso(tk.Frame):
    """Caja informativa con una barra de color a la izquierda (texto en lenguaje llano)."""

    def __init__(self, master, texto="", fuente="Helvetica", fondo=None, color=None, ancho_texto=280):
        color = color or T.ACENTO
        relleno = T.mezclar(fondo or T.SUPERFICIE, color, 0.10)
        super().__init__(master, bg=relleno)
        tk.Frame(self, bg=color, width=round(4 * T.ESCALA)).pack(side="left", fill="y")
        self.etiqueta = tk.Label(self, text=texto, bg=relleno, fg=T.TEXTO, font=(fuente, T.TAM_PEQ), justify="left",
                                 anchor="w", wraplength=round(ancho_texto * T.ESCALA), padx=12, pady=10)
        self.etiqueta.pack(side="left", fill="both", expand=True)

    def configurar(self, texto):
        self.etiqueta.configure(text=texto)
