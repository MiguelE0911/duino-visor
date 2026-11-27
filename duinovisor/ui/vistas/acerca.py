"""Ventana «Acerca de»: qué es DuinoVisor, quién lo hizo y para qué asignatura."""
from __future__ import annotations

import tkinter as tk

from duinovisor import __version__
from duinovisor.ui import tema as T
from duinovisor.ui.widgets.base import etiqueta
from duinovisor.ui.widgets.botones import BotonPildora

DESCRIPCION = ("Controla y observa una placa Arduino de forma sencilla: enciende, apaga y anima sus luces, "
               "y mira la temperatura y la humedad en vivo, sin escribir código.")
AUTORES = "Yohana Franceschi y Miguel Aparicio"
ASIGNATURA = "Organización y Arquitectura de Computadoras"
PLACA = "Arduino 101 (Intel Curie), conectado por USB"


class AcercaMixin:
    """Abre (una sola vez) la ventana «Acerca de»."""

    def abrir_acerca(self):
        if self._ventana_acerca is not None:
            try:
                self._ventana_acerca.lift()
                return
            except tk.TclError:
                self._ventana_acerca = None
        f = self.f
        v = tk.Toplevel(self)
        self._ventana_acerca = v
        v.title("Acerca de DuinoVisor")
        v.configure(bg=T.SUPERFICIE)
        v.resizable(False, False)
        v.transient(self)
        v.protocol("WM_DELETE_WINDOW", self._cerrar_acerca)
        c = tk.Frame(v, bg=T.SUPERFICIE, padx=self._px(28), pady=self._px(24))
        c.pack(fill="both", expand=True)
        etiqueta(c, "DuinoVisor", f, T.TAM_TITULO, T.TEXTO, negrita=True).pack(anchor="w")
        etiqueta(c, f"Versión {__version__}", f, T.TAM_PEQ, T.TEXTO_3).pack(anchor="w")
        etiqueta(c, DESCRIPCION, f, T.TAM_CUERPO, T.TEXTO_2, justify="left", anchor="w",
                 wraplength=self._px(380)).pack(anchor="w", pady=(self._px(14), 0))
        datos = tk.Frame(c, bg=T.SUPERFICIE)
        datos.pack(anchor="w", fill="x", pady=(self._px(16), 0))
        datos.columnconfigure(1, weight=1)
        for i, (titulo, valor) in enumerate((("Creado por", AUTORES), ("Asignatura", ASIGNATURA),
                                             ("Placa", PLACA))):
            etiqueta(datos, titulo, f, T.TAM_PEQ, T.TEXTO_3).grid(row=i, column=0, sticky="nw",
                                                                  padx=(0, self._px(14)), pady=self._px(3))
            etiqueta(datos, valor, f, T.TAM_CUERPO, T.TEXTO, justify="left", anchor="w",
                     wraplength=self._px(290)).grid(row=i, column=1, sticky="w", pady=self._px(3))
        BotonPildora(c, "Listo", self._cerrar_acerca, 100, 38, "relleno", f).pack(anchor="e", pady=(self._px(22), 0))

    def _cerrar_acerca(self):
        if self._ventana_acerca is not None:
            try:
                self._ventana_acerca.destroy()
            except tk.TclError:
                pass
        self._ventana_acerca = None
