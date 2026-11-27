"""Panel «Detalles técnicos»: registro de comunicación (el puerto está en Configuración)."""
from __future__ import annotations

import tkinter as tk

from duinovisor.ui import tema as T
from duinovisor.ui.widgets.base import etiqueta
from duinovisor.ui.widgets.contenedores import Tarjeta


class DetallesMixin:
    """Construye el panel de detalles y escribe el registro."""

    def _construir_detalles(self):
        f = self.f
        self.t_detalles = Tarjeta(self, "Detalles técnicos", f)
        c = self.t_detalles.contenido
        c.columnconfigure(0, weight=1)
        reg = tk.Frame(c, bg=T.SUPERFICIE)
        reg.grid(row=0, column=0, sticky="nsew")
        cab = tk.Frame(reg, bg=T.SUPERFICIE)
        cab.pack(fill="x")
        etiqueta(cab, "Registro de comunicación", f, T.TAM_PEQ).pack(side="left")
        etiqueta(cab, "  ·  9600 baudios · sketch control_leds.ino", f, T.TAM_MINI, T.TEXTO_3).pack(side="left")
        etiqueta(cab, "→ enviado   ", f, T.TAM_MINI, T.ACENTO).pack(side="right")
        etiqueta(cab, "← recibido   ", f, T.TAM_MINI, T.EXITO).pack(side="right")
        marco = tk.Frame(reg, bg=T.SUPERFICIE_2)
        marco.pack(fill="both", expand=True, pady=(self._px(4), 0))
        self.txt = tk.Text(marco, height=6, state="disabled", wrap="word", bg=T.SUPERFICIE_2, fg=T.TEXTO_2,
                           relief="flat", bd=0, highlightthickness=0, font=(self.f_mono, T.TAM_PEQ),
                           padx=self._px(10), pady=self._px(6))
        self.txt.pack(fill="both", expand=True)
        self.txt.tag_configure("tx", foreground=T.ACENTO)
        self.txt.tag_configure("rx", foreground=T.EXITO)
        self.txt.tag_configure("err", foreground=T.ERROR)
        self.txt.tag_configure("info", foreground=T.TEXTO_2)

    def _mostrar_detalles(self):
        if not self._construido:
            return
        si = bool(self.v_detalles.get())
        self.b_detalles.configurar(texto="Ocultar detalles" if si else "Mostrar detalles")
        if si:
            self.t_detalles.grid(row=3, column=0, sticky="ew", padx=self._px(24), pady=(0, self._px(18)))
        else:
            self.t_detalles.grid_remove()
        self._mostrar_detalles_config(si)
        self._actualizar_editor()

    def log(self, texto: str, etiqueta_: str = "info"):
        self._lineas_log.append((texto, etiqueta_))
        self._escribir_log([(texto, etiqueta_)])

    def _escribir_log(self, lineas):
        if not hasattr(self, "txt"):
            return
        self.txt.configure(state="normal")
        for texto, etq in lineas:
            self.txt.insert("end", texto + "\n", etq)
        if int(self.txt.index("end-1c").split(".")[0]) > 500:
            self.txt.delete("1.0", "50.0")
        self.txt.see("end")
        self.txt.configure(state="disabled")

    def _repintar_log(self):
        self._escribir_log(list(self._lineas_log))
