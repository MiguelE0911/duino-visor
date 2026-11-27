"""Ventana «Ajustes» y cambio de tema o color de acento (reconstruye la ventana)."""
from __future__ import annotations

import tkinter as tk

from duinovisor.almacenamiento import preferencias
from duinovisor.ui import tema as T
from duinovisor.ui.widgets.base import etiqueta
from duinovisor.ui.widgets.botones import BotonPildora, MuestraColor, Segmentado


class AjustesMixin:
    """Ajustes de apariencia."""

    def abrir_ajustes(self):
        if self._ventana_ajustes is not None:
            try:
                self._ventana_ajustes.lift()
                return
            except tk.TclError:
                self._ventana_ajustes = None
        f = self.f
        v = tk.Toplevel(self)
        self._ventana_ajustes = v
        v.title("Ajustes")
        v.configure(bg=T.SUPERFICIE)
        v.resizable(False, False)
        v.transient(self)
        v.protocol("WM_DELETE_WINDOW", self._cerrar_ajustes)
        c = tk.Frame(v, bg=T.SUPERFICIE, padx=self._px(28), pady=self._px(24))
        c.pack(fill="both", expand=True)
        etiqueta(c, "Ajustes", f, T.TAM_SECCION + 2, T.TEXTO, negrita=True).pack(anchor="w")
        etiqueta(c, "Apariencia", f, T.TAM_PEQ).pack(anchor="w", pady=(self._px(18), self._px(6)))
        Segmentado(c, self.v_tema, [("claro", "Claro"), ("oscuro", "Oscuro")], ancho=260, columnas=2, alto_fila=38,
                   fuente=f, estilo="pista").pack(anchor="w")
        etiqueta(c, "Color de acento", f, T.TAM_PEQ).pack(anchor="w", pady=(self._px(18), self._px(6)))
        fila = tk.Frame(c, bg=T.SUPERFICIE)
        fila.pack(anchor="w")
        for i, (clave, (nombre, claro, oscuro)) in enumerate(T.ACENTOS.items()):
            celda = tk.Frame(fila, bg=T.SUPERFICIE)
            celda.grid(row=0, column=i, padx=(0, self._px(10)))
            MuestraColor(celda, oscuro if T.OSCURO else claro, lambda k=clave: self.v_acento.set(k),
                         seleccionado=(clave == T.acento_actual)).pack()
            etiqueta(celda, nombre, f, T.TAM_MINI, T.TEXTO_2 if clave != T.acento_actual else T.TEXTO).pack()
        BotonPildora(c, "Listo", self._cerrar_ajustes, 100, 38, "relleno", f).pack(anchor="e", pady=(self._px(22), 0))

    def _cerrar_ajustes(self):
        if self._ventana_ajustes is not None:
            try:
                self._ventana_ajustes.destroy()
            except tk.TclError:
                pass
        self._ventana_ajustes = None

    def alternar_tema(self):
        self.v_tema.set("oscuro" if T.tema_actual == "claro" else "claro")

    def _cambio_apariencia(self):
        tema, acento = self.v_tema.get(), self.v_acento.get()
        if (tema, acento) == (T.tema_actual, T.acento_actual):
            return
        T.aplicar(tema, acento)
        self.prefs.update(tema=T.tema_actual, acento=T.acento_actual)
        preferencias.guardar(self.prefs)
        self._reconstruir()

    def _reconstruir(self):
        """Vuelve a crear todos los widgets con los colores actuales. El estado (variables, espejo, lo
        aplicado, lecturas y envíos en curso) no se toca."""
        ajustes = self._ventana_ajustes is not None
        self._ventana_ajustes = None
        self._construido = False
        for w in self.winfo_children():
            w.destroy()
        self._estilo()
        self._construir()
        self.al_cambiar()
        if ajustes:
            self.abrir_ajustes()
