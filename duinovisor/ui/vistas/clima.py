"""Vista «Clima»: temperatura, humedad, avisos, semáforo térmico y gráfica."""
from __future__ import annotations

import tkinter as tk

from duinovisor.ui import tema as T
from duinovisor.ui.widgets.base import entrada, etiqueta
from duinovisor.ui.widgets.contenedores import Desplazable, Tarjeta
from duinovisor.ui.widgets.controles import Interruptor
from duinovisor.ui.widgets.grafica import COLOR_HUMEDAD, Grafica
from duinovisor.ui.widgets.indicadores import Barras, Medidor


class ClimaMixin:
    """Construye y pinta la vista «Clima» y la franja de alarma."""

    def _construir_clima(self, padre):
        f = self.f
        vc = tk.Frame(padre, bg=T.FONDO)
        vc.columnconfigure(0, weight=4, uniform="vc")
        vc.columnconfigure(1, weight=5, uniform="vc")
        vc.rowconfigure(0, weight=1)
        self.vistas["clima"] = vc
        desp = Desplazable(vc)
        desp.grid(row=0, column=0, sticky="nsew", padx=(0, self._px(2)))
        izq = desp.interior
        sep = self._px(14)

        fila = tk.Frame(izq, bg=T.FONDO)
        fila.pack(fill="x", pady=(0, sep))
        fila.columnconfigure((0, 1), weight=1, uniform="s")
        ttemp = Tarjeta(fila, "Temperatura", f)
        ttemp.grid(row=0, column=0, sticky="nsew", padx=(0, self._px(7)))
        self.medidor = Medidor(ttemp.contenido, fuente=f)
        self.medidor.pack()
        etiqueta(ttemp.contenido, "", f, T.TAM_PEQ, T.TEXTO_2, textvariable=self.v_zona).pack()
        thum = Tarjeta(fila, "Humedad", f)
        thum.grid(row=0, column=1, sticky="nsew", padx=(self._px(7), 0))
        etiqueta(thum.extra, "", f, T.TAM_SECCION, T.TEXTO, textvariable=self.v_hum, negrita=True).pack()
        self.barras = Barras(thum.contenido)
        self.barras.pack()
        etiqueta(thum.contenido, "Últimas lecturas", f, T.TAM_PEQ, T.TEXTO_3).pack()

        tav = Tarjeta(izq, "Avisos", f, subtitulo="Suena y aparece una franja roja si se pasa de estos valores.")
        tav.pack(fill="x", pady=(0, sep))
        self._fila_interruptor(tav.contenido, 0, "Avisarme", self.v_alarmas)
        self._fila_numero(tav.contenido, 1, "Temperatura máxima", self.v_amax_t, "°C")
        self._fila_numero(tav.contenido, 2, "Humedad máxima", self.v_amax_h, "%")

        tter = Tarjeta(izq, "Semáforo según la temperatura", f,
                       subtitulo="Las luces indican si hace fresco (verde), templado (amarillo) o calor (rojo).")
        tter.pack(fill="x", pady=(0, sep))
        self._fila_interruptor(tter.contenido, 0, "Usar las luces como termómetro", self.v_termo)
        self._fila_numero(tter.contenido, 1, "Verde por debajo de", self.v_tmin, "°C")
        self._fila_numero(tter.contenido, 2, "Rojo desde", self.v_tmax, "°C")
        etiqueta(tter.contenido, "Pulsa «Aplicar cambios» para enviarlo al Arduino.", f, T.TAM_PEQ, T.TEXTO_3).grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(self._px(6), 0))

        thist = Tarjeta(vc, "Últimos minutos", f, llenar=True)
        thist.grid(row=0, column=1, sticky="nsew", padx=(self._px(7), 0), pady=(0, sep))
        etiqueta(thist.extra, "● temperatura (°C)  ", f, T.TAM_PEQ, T.ACENTO).pack(side="left")
        etiqueta(thist.extra, "● humedad (%)", f, T.TAM_PEQ, COLOR_HUMEDAD).pack(side="left")
        self.grafica = Grafica(thist.contenido, 420, 300, f, self._datos_t, self._datos_h)
        self.grafica.pack(fill="both", expand=True)

    def _fila_interruptor(self, padre, fila, texto, variable):
        padre.columnconfigure(0, weight=1)
        etiqueta(padre, texto, self.f, color=T.TEXTO).grid(row=fila, column=0, sticky="w", pady=self._px(4))
        Interruptor(padre, variable).grid(row=fila, column=1, columnspan=2, sticky="e", pady=self._px(4))

    def _fila_numero(self, padre, fila, texto, variable, unidad, ancho=5):
        padre.columnconfigure(0, weight=1)
        etiqueta(padre, texto, self.f).grid(row=fila, column=0, sticky="w", pady=self._px(4))
        entrada(padre, variable, ancho, self.f).grid(row=fila, column=1, sticky="e", padx=(self._px(8), 0),
                                                     ipady=self._px(2))
        etiqueta(padre, unidad, self.f, T.TAM_PEQ, T.TEXTO_3, width=3, anchor="w").grid(
            row=fila, column=2, sticky="w", padx=(self._px(6), 0))

    def _pintar_clima(self):
        """Medidor y barras con la última lectura (también tras reconstruir la ventana)."""
        if not self._construido:
            return
        if self._ultima is None:
            self.medidor.poner(0, "--")
        else:
            self.medidor.poner(self._ultima[0] / 50, f"{self._ultima[0]:.1f}")
        self.barras.poner([h for h in list(self._datos_h)[-6:]], 100)

    def _actualizar_banner(self):
        if not hasattr(self, "banner"):
            return
        motivos = [a.motivo for a in (self.alarma_t, self.alarma_h) if a.activa]
        if motivos:
            self.banner.configure(text="⚠  Aviso: " + " · ".join(motivos))
            self.banner.grid(row=2, column=0, sticky="ew", padx=self._px(24), pady=(0, self._px(14)))
        else:
            self.banner.grid_remove()
