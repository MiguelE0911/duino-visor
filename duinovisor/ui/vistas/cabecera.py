"""Cabecera: nombre, estado de la conexión, pestañas, «Aplicar» y menú."""
from __future__ import annotations

import tkinter as tk

from duinovisor.ui import tema as T
from duinovisor.ui.widgets.base import etiqueta
from duinovisor.ui.widgets.botones import BotonIcono, BotonPildora, Segmentado


class CabeceraMixin:
    """Construye la cabecera de la ventana."""

    def _construir_cabecera(self):
        f = self.f
        cab = tk.Frame(self, bg=T.FONDO)
        cab.grid(row=0, column=0, sticky="ew", padx=self._px(24), pady=(self._px(18), self._px(14)))
        cab.columnconfigure(1, weight=1)

        izq = tk.Frame(cab, bg=T.FONDO)
        izq.grid(row=0, column=0, sticky="w")
        etiqueta(izq, "DuinoVisor", f, T.TAM_TITULO, T.TEXTO, T.FONDO, negrita=True).pack(anchor="w")
        fila = tk.Frame(izq, bg=T.FONDO)
        fila.pack(anchor="w")
        d = self._px(10)
        self.punto = tk.Canvas(fila, width=d, height=d, bg=T.FONDO, highlightthickness=0, bd=0)
        self.punto.pack(side="left", padx=(0, self._px(6)))
        self.punto.create_oval(1, 1, d - 1, d - 1, fill=T.TEXTO_3, outline="", tags="punto")
        etiqueta(fila, "", f, T.TAM_PEQ, T.TEXTO_2, T.FONDO, textvariable=self.v_estado).pack(side="left")
        self.b_reintentar = BotonPildora(fila, "Reintentar", self.reintentar, alto=26, estilo="texto", fuente=f,
                                         fondo=T.FONDO, tam=T.TAM_PEQ)

        self.tabs = Segmentado(cab, self.v_vista, [("semaforo", "Luces"), ("clima", "Clima")], ancho=240,
                               columnas=2, alto_fila=40, fuente=f, fondo=T.FONDO, estilo="pista")
        self.tabs.grid(row=0, column=1)

        der = tk.Frame(cab, bg=T.FONDO)
        der.grid(row=0, column=2, sticky="e")
        etiqueta(der, "", f, T.TAM_PEQ, T.ACENTO, T.FONDO, textvariable=self.v_pendiente).pack(
            side="left", padx=(0, self._px(10)))
        self.b_detalles = BotonPildora(der, "Mostrar detalles", lambda: self.v_detalles.set(not self.v_detalles.get()),
                                       ancho=150, alto=40, estilo="fantasma", fuente=f, fondo=T.FONDO)
        self.b_detalles.pack(side="left", padx=(0, self._px(8)))
        self.b_aplicar = BotonPildora(der, "Aplicar cambios", self.aplicar, ancho=160, alto=40, estilo="relleno",
                                      fuente=f, fondo=T.FONDO)
        self.b_aplicar.pack(side="left", padx=(0, self._px(12)))
        self.b_tema = BotonIcono(der, "luna" if T.tema_actual == "claro" else "sol", self.alternar_tema, 40, T.FONDO)
        self.b_tema.pack(side="left", padx=(0, self._px(6)))
        self.b_menu = BotonIcono(der, "menu", self._abrir_menu, 40, T.FONDO)
        self.b_menu.pack(side="left")

        self.menu = tk.Menu(self, tearoff=0, bg=T.SUPERFICIE, fg=T.TEXTO, activebackground=T.ACENTO_SUAVE,
                            activeforeground=T.TEXTO, bd=0, relief="flat", font=(f, T.TAM_CUERPO))
        self.menu.add_command(label="Guardar escena…", command=self.guardar_escena)
        self.menu.add_command(label="Cargar escena…", command=self.cargar_escena)
        self.menu.add_separator()
        self.menu.add_command(label="Exportar lecturas (CSV)…", command=self.exportar_csv)
        self.menu.add_separator()
        self.menu.add_command(label="Ajustes…", command=self.abrir_ajustes)

    def _abrir_menu(self):
        try:
            x = self.b_menu.winfo_rootx() + self.b_menu.winfo_width() - self._px(200)
            y = self.b_menu.winfo_rooty() + self.b_menu.winfo_height() + self._px(4)
            self.menu.tk_popup(x, y)
        finally:
            try:
                self.menu.grab_release()
            except Exception:
                pass
