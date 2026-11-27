"""Vista «Luces»: semáforo o protoboard en el centro, editor del LED elegido y animaciones."""
from __future__ import annotations

import tkinter as tk

from duinovisor.dominio.placa import PINES
from duinovisor.dominio.secuencias import VEL_MAX, VEL_MIN
from duinovisor.ui import tema as T
from duinovisor.ui.constantes import ANCHO_LATERAL, MODOS, NOMBRE_LUZ, OPCIONES_RITMO, ORDEN_SEMAFORO, SECUENCIAS
from duinovisor.ui.widgets.base import entrada, etiqueta
from duinovisor.ui.widgets.botones import BotonPildora, Segmentado
from duinovisor.ui.widgets.contenedores import Aviso, Desplazable, Tarjeta
from duinovisor.ui.widgets.controles import Deslizador
from duinovisor.ui.widgets.luces import Chip, SemaforoVirtual
from duinovisor.ui.widgets.protoboard import FichaComponente, Protoboard


class LucesMixin:
    """Construye y mantiene al día la vista «Luces»."""

    def _construir_luces(self, padre):
        f = self.f
        vs = tk.Frame(padre, bg=T.FONDO)
        vs.columnconfigure(0, weight=1)
        vs.columnconfigure(1, minsize=self._px(ANCHO_LATERAL + 2 * Tarjeta.PAD + Desplazable.MARGEN))
        vs.rowconfigure(0, weight=1)
        self.vistas["semaforo"] = vs

        central = Tarjeta(vs, "Tus luces", f, llenar=True)
        central.grid(row=0, column=0, sticky="nsew", padx=(0, self._px(14)), pady=(0, self._px(14)))
        Segmentado(central.extra, self.v_modo_luces, [("semaforo", "Semáforo"), ("protoboard", "Protoboard")],
                   ancho=250, columnas=2, alto_fila=34, fuente=f, estilo="pista", tam=T.TAM_PEQ).pack()
        c = central.contenido
        c.columnconfigure(0, weight=1)
        c.rowconfigure(0, weight=1)

        self.area_luces = tk.Frame(c, bg=T.SUPERFICIE)
        self.area_luces.grid(row=0, column=0, sticky="nsew")
        self.area_luces.columnconfigure(0, weight=1)
        self.area_luces.rowconfigure(0, weight=1)
        self.f_semaforo = tk.Frame(self.area_luces, bg=T.SUPERFICIE)
        self.semaforo = SemaforoVirtual(self.f_semaforo, ancho=138, al_elegir=self.v_sel.set)
        self.semaforo.pack(expand=True)
        self.f_semaforo.bind("<Configure>", self._ajustar_semaforo)
        self.protoboard = Protoboard(self.area_luces, 600, 260, fuente=f, al_elegir=self.v_sel.set)
        self.ficha_proto = FichaComponente(self.area_luces, f)

        etiqueta(c, "", f, T.TAM_CUERPO, T.TEXTO, textvariable=self.v_sem, negrita=True).grid(
            row=1, column=0, pady=(self._px(8), 0))
        etiqueta(c, "", f, T.TAM_PEQ, T.TEXTO_3, textvariable=self.v_ayuda_luces).grid(row=2, column=0)
        fila_chips = tk.Frame(c, bg=T.SUPERFICIE)
        fila_chips.grid(row=3, column=0, pady=(self._px(12), 0))
        self.chips = {}
        for i, col in enumerate(ORDEN_SEMAFORO):
            ch = Chip(fila_chips, col, NOMBRE_LUZ[col], lambda col=col: self.v_sel.set(col), fuente=f)
            ch.grid(row=0, column=i, padx=self._px(5))
            self.chips[col] = ch

        desp = Desplazable(vs)
        desp.grid(row=0, column=1, sticky="nsew")
        lateral = desp.interior
        self.t_editor = Tarjeta(lateral, NOMBRE_LUZ[self.v_sel.get()], f)
        self.t_editor.pack(fill="x", pady=(0, self._px(14)))
        self.t_editor.titulo.configure(textvariable=self.v_titulo_editor)
        self.led_editor = None
        self.editor = tk.Frame(self.t_editor.contenido, bg=T.SUPERFICIE)
        self.editor.pack(fill="x")

        tseq = Tarjeta(lateral, "Animaciones", f, subtitulo="Todas las luces cambian solas siguiendo un patrón.")
        tseq.pack(fill="x", pady=(0, self._px(14)))
        a = tseq.contenido
        Segmentado(a, self.v_seq, SECUENCIAS, ancho=ANCHO_LATERAL, columnas=1, alto_fila=34, hueco=6,
                   fuente=f).pack(anchor="w")
        fila_vel = tk.Frame(a, bg=T.SUPERFICIE)
        fila_vel.pack(fill="x", pady=(self._px(12), 0))
        etiqueta(fila_vel, "Velocidad", f).pack(side="left")
        etiqueta(fila_vel, "", f, color=T.TEXTO, textvariable=self.v_vel_txt).pack(side="right")
        self.desl_vel = Deslizador(a, self.v_vel, VEL_MIN, VEL_MAX, ancho=ANCHO_LATERAL)
        self.desl_vel.pack(anchor="w")
        botones = tk.Frame(a, bg=T.SUPERFICIE)
        botones.pack(anchor="w", pady=(self._px(12), 0))
        self.b_seq = BotonPildora(botones, "Iniciar", self.alternar_secuencia, 130, 38, "relleno", f, T.SUPERFICIE)
        self.b_seq.pack(side="left")
        self.b_stop = BotonPildora(botones, "Detener", self.detener_secuencia, 110, 38, "fantasma", f, T.SUPERFICIE)
        self.b_stop.pack(side="left", padx=(self._px(8), 0))
        self._actualizar_botones_seq()

    def _ajustar_semaforo(self, e):
        """El semáforo crece hasta llenar el hueco disponible (con un tope para que no sea enorme)."""
        s = T.ESCALA
        alto = e.height / s * 0.94
        ancho = min(e.width / s * 0.8, alto * self.semaforo.BASE_W / self.semaforo.BASE_H, 210)
        self.semaforo.redimensionar(max(90, ancho))

    def _construir_editor(self):
        """Controles del LED elegido. Se rehace al elegir otro LED (los widgets se enlazan a sus variables)."""
        for w in self.editor.winfo_children():
            w.destroy()
        f, col = self.f, self.v_sel.get()
        led = self.paneles[col]
        self.led_editor = led
        ancho = ANCHO_LATERAL
        e = self.editor
        e.columnconfigure(0, weight=1)

        self.aviso_bloqueo = tk.Frame(e, bg=T.SUPERFICIE)
        self.aviso_txt = Aviso(self.aviso_bloqueo, "", f, ancho_texto=ancho - 30)
        self.aviso_txt.pack(fill="x")
        self.b_desbloquear = BotonPildora(self.aviso_bloqueo, "Detener animación", self._desbloquear, alto=34,
                                          estilo="suave", fuente=f)
        self.b_desbloquear.pack(anchor="w", pady=(self._px(10), 0))

        self.f_controles = tk.Frame(e, bg=T.SUPERFICIE)
        k = self.f_controles
        k.columnconfigure(0, weight=1)
        etiqueta(k, "¿Qué hace esta luz?", f, T.TAM_PEQ).grid(row=0, column=0, sticky="w")
        Segmentado(k, led.v_modo, MODOS, ancho=ancho, columnas=2, fuente=f).grid(
            row=1, column=0, sticky="w", pady=(self._px(6), 0))

        self.f_brillo = tk.Frame(k, bg=T.SUPERFICIE)
        fila = tk.Frame(self.f_brillo, bg=T.SUPERFICIE)
        fila.pack(fill="x")
        etiqueta(fila, "Brillo", f, T.TAM_PEQ).pack(side="left")
        etiqueta(fila, "", f, T.TAM_PEQ, T.TEXTO, textvariable=led.v_pct).pack(side="right")
        Deslizador(self.f_brillo, led.v_brillo, 0, 255, ancho=ancho).pack(anchor="w")

        self.f_ritmo = tk.Frame(k, bg=T.SUPERFICIE)
        etiqueta(self.f_ritmo, "Ritmo", f, T.TAM_PEQ).pack(anchor="w")
        Segmentado(self.f_ritmo, led.v_ritmo, OPCIONES_RITMO, ancho=ancho, columnas=3, fuente=f, tam=T.TAM_PEQ).pack(
            anchor="w", pady=(self._px(6), 0))

        self.f_tecnico = tk.Frame(k, bg=T.SUPERFICIE)
        t = self.f_tecnico
        tk.Frame(t, bg=T.BORDE, height=1).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, self._px(10)))
        etiqueta(t, "Datos técnicos", f, T.TAM_PEQ, T.TEXTO, negrita=True).grid(row=1, column=0, sticky="w")
        etiqueta(t, "Pin del Arduino", f, T.TAM_PEQ).grid(row=2, column=0, sticky="w", pady=2)
        etiqueta(t, f"{PINES[col]} (PWM)", f, T.TAM_PEQ, T.TEXTO).grid(row=2, column=1, sticky="e")
        etiqueta(t, "Valor PWM (0-255)", f, T.TAM_PEQ).grid(row=3, column=0, sticky="w", pady=2)
        etiqueta(t, "", f, T.TAM_PEQ, T.TEXTO, textvariable=led.v_brillo).grid(row=3, column=1, sticky="e")
        t.columnconfigure(0, weight=1)
        self.f_ms_blink = tk.Frame(t, bg=T.SUPERFICIE)
        self.f_ms_fade = tk.Frame(t, bg=T.SUPERFICIE)
        self.f_ms_blink.columnconfigure(0, weight=1)
        self.f_ms_fade.columnconfigure(0, weight=1)
        for fila_, (marco, texto, var) in enumerate((
                (self.f_ms_blink, "Encendida (ms)", led.v_on), (self.f_ms_blink, "Apagada (ms)", led.v_off),
                (self.f_ms_fade, "Ciclo completo (ms)", led.v_periodo))):
            etiqueta(marco, texto, f, T.TAM_PEQ).grid(row=fila_ % 2, column=0, sticky="w", pady=2)
            entrada(marco, var, 7, f).grid(row=fila_ % 2, column=1, sticky="e", pady=2)
        self.f_ms_blink.grid(row=4, column=0, columnspan=2, sticky="ew")
        self.f_ms_fade.grid(row=5, column=0, columnspan=2, sticky="ew")
        p = (self._px(14), 0)
        self.f_brillo.grid(row=2, column=0, sticky="ew", pady=p)
        self.f_ritmo.grid(row=3, column=0, sticky="ew", pady=p)
        self.f_tecnico.grid(row=4, column=0, sticky="ew", pady=(self._px(18), 0))
        self._bloqueo_editor = None
        self._actualizar_editor()

    def _actualizar_editor(self):
        if not self._construido or self.led_editor is None:
            return
        led = self.led_editor
        bloqueado = not led.habilitado
        if bloqueado != self._bloqueo_editor:
            self._bloqueo_editor = bloqueado
            if bloqueado:
                self.f_controles.grid_remove()
                self.aviso_bloqueo.grid(row=0, column=0, sticky="ew")
            else:
                self.aviso_bloqueo.grid_remove()
                self.f_controles.grid(row=0, column=0, sticky="ew")
        if bloqueado:
            if self.aplicado.seq is not None:
                self.aviso_txt.configurar("Hay una animación en marcha y las luces cambian solas. "
                                          "Detenla para poder elegir qué hace cada luz.")
                self.b_desbloquear.configurar(texto="Detener animación")
            else:
                self.aviso_txt.configurar("Las luces están funcionando como termómetro (lo activaste en Clima). "
                                          "Desactívalo allí para elegir qué hace cada luz.")
                self.b_desbloquear.configurar(texto="Ir a Clima")
            return
        modo = led.v_modo.get()
        (self.f_brillo.grid if modo != "OFF" else self.f_brillo.grid_remove)()
        (self.f_ritmo.grid if modo in ("BLINK", "FADE") else self.f_ritmo.grid_remove)()
        (self.f_tecnico.grid if self.v_detalles.get() else self.f_tecnico.grid_remove)()
        (self.f_ms_blink.grid if modo == "BLINK" else self.f_ms_blink.grid_remove)()
        (self.f_ms_fade.grid if modo == "FADE" else self.f_ms_fade.grid_remove)()

    def _desbloquear(self):
        if self.aplicado.seq is not None:
            self.detener_secuencia()
        else:
            self.v_vista.set("clima")

    def _al_elegir_led(self):
        col = self.v_sel.get()
        self.v_titulo_editor.set(NOMBRE_LUZ[col])
        if not self._construido:
            return
        self._construir_editor()
        self.semaforo.seleccionar(col)
        self.protoboard.seleccionar(col)
        self.protoboard.ver_componente(None)                 # la ficha pasa a ser la del LED elegido
        for c, ch in self.chips.items():
            ch.configurar(seleccionado=(c == col))

    def _mostrar_modo_luces(self):
        if not self._construido:
            return
        if self.v_modo_luces.get() == "protoboard":
            self.f_semaforo.grid_remove()
            self.protoboard.grid(row=0, column=0, sticky="nsew")
            self.ficha_proto.grid(row=1, column=0, sticky="ew", pady=(self._px(10), 0))
            self.v_ayuda_luces.set("Clic en una luz o en el sensor para ver su ficha · Rueda del ratón: acercar · "
                                   "Arrastra: moverte · Doble clic: ver todo")
        else:
            self.protoboard.grid_remove()
            self.ficha_proto.grid_remove()
            self.f_semaforo.grid(row=0, column=0, sticky="nsew")
            self.v_ayuda_luces.set("Haz clic en una luz para elegir qué hace.")

    def _actualizar_luces(self, bloqueado: bool):
        if not self._construido:
            return
        for c, ch in self.chips.items():
            ch.configurar(resumen="Automático" if bloqueado else self.paneles[c].resumen())
        self._actualizar_editor()
