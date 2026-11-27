"""Pestaña «Configuración»: conexión con el Arduino, sensor y apariencia, cada ajuste con su explicación.

También el cambio de tema o de color de acento, que reconstruye la ventana entera.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from duinovisor.almacenamiento import preferencias
from duinovisor.ui import tema as T
from duinovisor.ui.constantes import PERIODOS_SENSOR
from duinovisor.ui.widgets.base import entrada, etiqueta
from duinovisor.ui.widgets.botones import BotonIcono, BotonPildora, MuestraColor, Segmentado
from duinovisor.ui.widgets.contenedores import Desplazable, Tarjeta
from duinovisor.ui.widgets.controles import Interruptor

ANCHO_DESCRIPCION = 400          # ancho (lógico) del texto explicativo de cada ajuste


class ConfiguracionMixin:
    """Construye la pestaña de configuración y guarda las preferencias."""

    # ------------------------------------------------------------------ variables
    def _crear_variables_config(self):
        self.v_auto = tk.BooleanVar(value=bool(self.prefs["auto_conectar"]))
        self.v_dht_preset = tk.StringVar(value="")
        self.v_auto.trace_add("write", lambda *_: self._guardar_pref("auto_conectar", bool(self.v_auto.get())))
        # «Leer el sensor cada»: el selector y los ms exactos se mantienen sincronizados
        self.v_dht.trace_add("write", lambda *_: self._sincronizar_preset())
        self.v_dht_preset.trace_add("write", lambda *_: self._elegir_preset())
        self._sincronizar_preset()

    def _sincronizar_preset(self):
        ms = self.v_dht.get().strip()
        valor = ms if ms in dict(PERIODOS_SENSOR) else ""
        if self.v_dht_preset.get() != valor:
            self.v_dht_preset.set(valor)

    def _elegir_preset(self):
        valor = self.v_dht_preset.get()
        if valor and valor != self.v_dht.get().strip():
            self.v_dht.set(valor)

    def _guardar_pref(self, clave, valor):
        if self.prefs.get(clave) != valor:
            self.prefs[clave] = valor
            preferencias.guardar(self.prefs)

    # ------------------------------------------------------------------ pestaña
    def _construir_config(self, padre):
        f = self.f
        vc = tk.Frame(padre, bg=T.FONDO)
        vc.columnconfigure(0, weight=1)
        vc.rowconfigure(0, weight=1)
        self.vistas["config"] = vc
        desp = Desplazable(vc)
        desp.grid(row=0, column=0, sticky="nsew")
        cols = tk.Frame(desp.interior, bg=T.FONDO)
        cols.pack(fill="x")
        cols.columnconfigure((0, 1), weight=1, uniform="cfg")
        izq = tk.Frame(cols, bg=T.FONDO)
        izq.grid(row=0, column=0, sticky="new", padx=(0, self._px(7)))
        der = tk.Frame(cols, bg=T.FONDO)
        der.grid(row=0, column=1, sticky="new", padx=(self._px(7), 0))
        sep = self._px(14)

        # --- conexión
        tcon = Tarjeta(izq, "Conexión con el Arduino", f,
                       subtitulo="Cómo encuentra el programa tu placa conectada por USB.")
        tcon.pack(fill="x", pady=(0, sep))
        c = tcon.contenido
        self._fila_ajuste(c, 0, "Buscar el Arduino al abrir",
                          "Al abrir el programa prueba cada puerto USB hasta encontrar la placa y se conecta solo. "
                          "Apágalo si prefieres elegir el puerto tú.",
                          lambda p: Interruptor(p, self.v_auto))

        def puerto(p):
            marco = tk.Frame(p, bg=T.SUPERFICIE)
            self.cb_puerto = ttk.Combobox(marco, textvariable=self.v_puerto, width=12, style="Duino.TCombobox",
                                          font=(f, T.TAM_CUERPO))
            self.cb_puerto.pack(side="left")
            self.b_refrescar = BotonIcono(marco, "refrescar", self.actualizar_puertos, 34)
            self.b_refrescar.pack(side="left", padx=(self._px(6), 0))
            return marco
        self._fila_ajuste(c, 1, "Puerto",
                          "La «puerta» USB por la que habla con el Arduino (en Windows, COM3, COM5...). "
                          "Solo hace falta elegirlo si no lo encuentra solo.", puerto)
        botones = tk.Frame(c, bg=T.SUPERFICIE)
        botones.grid(row=2, column=0, columnspan=2, sticky="w", pady=(self._px(10), 0))
        self.b_power = BotonPildora(botones, "Conectar", self.alternar_conexion, 130, 36, "relleno", f)
        self.b_power.pack(side="left")
        BotonPildora(botones, "Buscar de nuevo", self.buscar_placa, 150, 36, "fantasma", f).pack(
            side="left", padx=(self._px(8), 0))

        # --- sensor
        tsen = Tarjeta(izq, "Sensor de clima", f, subtitulo="El DHT11 mide la temperatura y la humedad.")
        tsen.pack(fill="x", pady=(0, sep))
        s = tsen.contenido
        self._fila_ajuste(s, 0, "Leer el sensor cada",
                          "Cada cuánto tiempo mide. Más seguido da una gráfica más detallada; el DHT11 no "
                          "mejora por debajo de 1 segundo. Pulsa «Aplicar cambios» para enviarlo.",
                          None)
        Segmentado(s, self.v_dht_preset, PERIODOS_SENSOR, ancho=ANCHO_DESCRIPCION, columnas=6, alto_fila=32,
                   hueco=6, fuente=f, tam=T.TAM_PEQ).grid(row=1, column=0, columnspan=2, sticky="w",
                                                          pady=(self._px(8), 0))
        self.f_dht_exacto = tk.Frame(s, bg=T.SUPERFICIE)
        self.f_dht_exacto.columnconfigure(0, weight=1)
        etiqueta(self.f_dht_exacto, "Valor exacto (ms, de 1000 a 3600000)", f, T.TAM_PEQ).grid(
            row=0, column=0, sticky="w")
        entrada(self.f_dht_exacto, self.v_dht, 8, f).grid(row=0, column=1, sticky="e", ipady=self._px(2))

        # --- apariencia
        tap = Tarjeta(der, "Apariencia", f, subtitulo="Cómo se ve la ventana. Se recuerda al volver a abrir.")
        tap.pack(fill="x", pady=(0, sep))
        a = tap.contenido
        self._fila_ajuste(a, 0, "Tema", "Claro para habitaciones con luz; oscuro cansa menos la vista de noche. "
                          "El botón de la luna o el sol de arriba también lo cambia.",
                          lambda p: Segmentado(p, self.v_tema, [("claro", "Claro"), ("oscuro", "Oscuro")], ancho=170,
                                               columnas=2, alto_fila=34, fuente=f, estilo="pista", tam=T.TAM_PEQ))
        self._fila_ajuste(a, 1, "Color de acento", "El color de los botones, las pestañas elegidas y la gráfica.",
                          None)
        fila = tk.Frame(a, bg=T.SUPERFICIE)
        fila.grid(row=2, column=0, columnspan=2, sticky="w", pady=(self._px(8), 0))
        for i, (clave, (nombre, claro, oscuro)) in enumerate(T.ACENTOS.items()):
            celda = tk.Frame(fila, bg=T.SUPERFICIE)
            celda.grid(row=0, column=i, padx=(0, self._px(10)))
            MuestraColor(celda, oscuro if T.OSCURO else claro, lambda k=clave: self.v_acento.set(k),
                         seleccionado=(clave == T.acento_actual)).pack()
            etiqueta(celda, nombre, f, T.TAM_MINI, T.TEXTO_2 if clave != T.acento_actual else T.TEXTO).pack()

        # --- acerca de
        tac = Tarjeta(der, "Acerca de", f, subtitulo="Quién hizo DuinoVisor y para qué.")
        tac.pack(fill="x", pady=(0, sep))
        BotonPildora(tac.contenido, "Acerca de DuinoVisor", self.abrir_acerca, 190, 36, "suave", f).pack(anchor="w")

    def _fila_ajuste(self, padre, fila, titulo, descripcion, control=None):
        """Un ajuste: título y explicación a la izquierda y, si hay, su control a la derecha."""
        padre.columnconfigure(0, weight=1)
        textos = tk.Frame(padre, bg=T.SUPERFICIE)
        textos.grid(row=fila, column=0, sticky="nw", pady=(self._px(10) if fila else 0, 0))
        etiqueta(textos, titulo, self.f, color=T.TEXTO, negrita=True).pack(anchor="w")
        texto = etiqueta(textos, descripcion, self.f, T.TAM_PEQ, T.TEXTO_2, justify="left", anchor="w",
                         wraplength=self._px(ANCHO_DESCRIPCION))
        texto.pack(anchor="w")
        controles = padre.__dict__.setdefault("_controles_ajuste", [])     # comparten la columna de la derecha
        if control is not None:
            widget = control(padre)
            widget.grid(row=fila, column=1, sticky="ne", padx=(self._px(12), 0), pady=(self._px(10) if fila else 0, 0))
            controles.append(widget)

        def ajustar(e):
            """La explicación ocupa el ancho que dejan libre los controles (sin cortarse ni dejar un hueco)."""
            ocupado = max((w.winfo_reqwidth() for w in controles), default=0)
            libre = e.width - (ocupado + self._px(24) if controles else 0)
            texto.configure(wraplength=max(self._px(160), libre))
        padre.bind("<Configure>", ajustar, add="+")

    def _mostrar_detalles_config(self, si: bool):
        if si:
            self.f_dht_exacto.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(self._px(10), 0))
        else:
            self.f_dht_exacto.grid_remove()

    # ------------------------------------------------------------------ apariencia
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
        aplicado, lecturas, envíos en curso y la pestaña abierta) no se toca."""
        acerca = self._ventana_acerca is not None
        self._ventana_acerca = None
        self._construido = False
        for w in self.winfo_children():
            w.destroy()
        self._estilo()
        self._construir()
        self.al_cambiar()
        if acerca:
            self.abrir_acerca()
