"""Ventana de DuinoVisor (Tkinter).

Dos vistas: «Luces» (el semáforo, o la protoboard, en el centro; al hacer clic en una luz se edita en el
panel de la derecha) y «Clima» (temperatura, humedad, gráfica, avisos y semáforo térmico). Lo técnico
(puerto, registro, milisegundos, PWM) queda detrás de «Mostrar detalles».

El semáforo, la protoboard y los chips espejan lo que hace el Arduino: se calculan con el mismo modelo que el
sketch, a partir de lo que la placa confirmó con OK.

Las variables de Tk (la configuración) viven en la App y no en los widgets: así la ventana se puede
reconstruir entera al cambiar de tema o de color sin perder nada.
"""
from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from collections import deque
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
from typing import Optional

import escenas
import preferencias
import protocol as P
import tema as T
from alarmas import Alarma
from arduino_link import Enlace, PySerialNoDisponible, autodetectar, listar_puertos
from exportar import escribir_csv
from grafica import MAX_LECTURAS, Grafica
from simulador import ArduinoSimulado
from vista_placa import PINES, Protoboard
from widgets import (Aviso, Barras, BotonIcono, BotonPildora, Chip, Desplazable, Deslizador, Interruptor, Medidor,
                     MuestraColor, SemaforoVirtual, Segmentado, Tarjeta, entrada, etiqueta)

SIN_RESPUESTA_MS = 1500
POLL_MS = 50
MAX_LECTURAS_CSV = 100_000
MODOS = [("OFF", "Apagada"), ("ON", "Encendida"), ("BLINK", "Parpadea"), ("FADE", "Respira")]
SECUENCIAS = [(n, P.NOMBRES_SEQ[n]) for n in P.SECUENCIAS]
NOMBRE_LUZ = {"R": "Luz roja", "G": "Luz verde", "Y": "Luz amarilla"}
ORDEN_SEMAFORO = ("R", "Y", "G")
# Ritmos sencillos: Parpadea usa el mismo tiempo encendida y apagada; Respira, el periodo completo.
RITMOS = {"BLINK": {"lento": 1000, "normal": 500, "rapido": 200},
          "FADE": {"lento": 4000, "normal": 2000, "rapido": 1000}}
OPCIONES_RITMO = [("lento", "Lento"), ("normal", "Normal"), ("rapido", "Rápido")]
ZONAS = ["hace fresco (verde)", "templado (amarillo)", "hace calor (rojo)"]
ANCHO_LATERAL = 340


def apagados() -> dict:
    return {c: (P.LedConfig(color=c, modo="OFF"), 0.0) for c in P.COLORES}


class LedUI:
    """Lo que la ventana tiene configurado para un LED (sin widgets).

    Mantiene `v_ritmo` (Lento/Normal/Rápido) sincronizado con los milisegundos exactos: elegir un ritmo
    escribe los ms y, si los ms no coinciden con ningún ritmo, no queda ninguno marcado.
    """

    def __init__(self, color: str, al_cambiar):
        self.color, self.al_cambiar = color, al_cambiar
        self.v_modo = tk.StringVar(value="OFF")
        self.v_brillo = tk.IntVar(value=255)
        self.v_on, self.v_off, self.v_periodo = (tk.StringVar(value=v) for v in ("500", "500", "2000"))
        self.v_ritmo = tk.StringVar(value="normal")
        self.v_pct = tk.StringVar(value="100 %")
        self.habilitado = True
        self._ocupado = False
        for v in (self.v_modo, self.v_brillo, self.v_on, self.v_off, self.v_periodo):
            v.trace_add("write", self._cambio)
        self.v_ritmo.trace_add("write", self._elegir_ritmo)

    def _cambio(self, *_):
        if self._ocupado:
            return
        self.v_pct.set(f"{round(int(self.v_brillo.get()) * 100 / 255)} %")
        self._sincronizar_ritmo()
        self.al_cambiar()

    def ritmo_actual(self) -> str:
        modo = self.v_modo.get()
        if modo == "BLINK":
            on, off = self.v_on.get().strip(), self.v_off.get().strip()
            for nombre, ms in RITMOS["BLINK"].items():
                if on == off == str(ms):
                    return nombre
        elif modo == "FADE":
            for nombre, ms in RITMOS["FADE"].items():
                if self.v_periodo.get().strip() == str(ms):
                    return nombre
        return ""

    def _sincronizar_ritmo(self):
        r = self.ritmo_actual()
        if self.v_ritmo.get() != r:
            self._ocupado = True
            try:
                self.v_ritmo.set(r)
            finally:
                self._ocupado = False

    def _elegir_ritmo(self, *_):
        if self._ocupado:
            return
        ms = RITMOS.get(self.v_modo.get(), {}).get(self.v_ritmo.get())
        if ms is None:
            return
        self._ocupado = True
        try:
            if self.v_modo.get() == "BLINK":
                self.v_on.set(str(ms))
                self.v_off.set(str(ms))
            else:
                self.v_periodo.set(str(ms))
        finally:
            self._ocupado = False
        self._cambio()

    def resumen(self) -> str:
        modo = self.v_modo.get()
        if modo == "OFF":
            return "Apagada"
        if modo == "ON":
            return f"Encendida · {self.v_pct.get()}"
        ritmo = dict(OPCIONES_RITMO).get(self.ritmo_actual(), "a medida").lower()
        return f"{'Parpadea' if modo == 'BLINK' else 'Respira'} · {ritmo}"

    def habilitar(self, si: bool):
        self.habilitado = bool(si)

    def _entero(self, var: tk.StringVar, nombre: str) -> int:
        try:
            return int(var.get().strip())
        except ValueError:
            raise ValueError(f"LED {P.NOMBRES_COLOR[self.color]}: «{nombre}» debe ser un número entero")

    def obtener(self) -> P.LedConfig:
        modo = self.v_modo.get()
        on = self._entero(self.v_on, "encendido") if modo == "BLINK" else 500
        off = self._entero(self.v_off, "apagado") if modo == "BLINK" else 500
        per = self._entero(self.v_periodo, "periodo") if modo == "FADE" else 2000
        cfg = P.LedConfig(self.color, modo, int(self.v_brillo.get()), on, off, per)
        problemas = P.errores(cfg)
        if problemas:
            raise ValueError(f"LED {P.NOMBRES_COLOR[self.color]}: " + "; ".join(problemas))
        return cfg

    def cargar(self, cfg: P.LedConfig):
        self.v_modo.set(cfg.modo)
        self.v_brillo.set(cfg.brillo)
        self.v_on.set(str(cfg.on_ms))
        self.v_off.set(str(cfg.off_ms))
        self.v_periodo.set(str(cfg.periodo_ms))


# Se mantiene el nombre antiguo por compatibilidad con código de la rama de funcionalidades.
PanelLed = LedUI


class App(tk.Tk):
    def __init__(self, demo: bool = False):
        super().__init__()
        T.ESCALA = self._escala()
        self.prefs = preferencias.cargar()
        T.aplicar(self.prefs["tema"], self.prefs["acento"])
        self.title("DuinoVisor" + (" — modo demostración" if demo else ""))
        ancho, alto = self.winfo_screenwidth(), self.winfo_screenheight()
        s = T.ESCALA
        self.geometry(f"{min(round(1260 * s), ancho - 40)}x{min(round(820 * s), alto - 90)}")
        self.minsize(round(1000 * s), round(660 * s))
        self.demo = demo
        self.f = T.fuente(self)
        self.f_mono = T.fuente_mono(self)
        self.enlace = Enlace()
        self.sim: Optional[ArduinoSimulado] = None
        self.aplicado = P.Aplicado()
        self.pendientes: list[P.Paso] = []
        self.paso_actual: Optional[P.Paso] = None
        self._intentos = 0
        self._id_timeout = None
        self.cola_ui: "queue.Queue[tuple]" = queue.Queue()
        self._t0 = time.monotonic()
        self.secuencia = P.SecuenciaLocal()          # espejo de la secuencia que corre en el Arduino
        self.vista = apagados()                      # espejo de los LEDs: color -> (config, instante)
        self.zona = -1                               # zona del semáforo térmico (espejo)
        self.lecturas: list = []                     # para exportar a CSV
        self.alarma_t = Alarma("Temperatura", " °C", maximo=35)
        self.alarma_h = Alarma("Humedad", " %", maximo=80)
        self._texto_sem = None
        self._lineas_log: deque = deque(maxlen=500)   # el registro sobrevive a reconstruir la ventana
        self._datos_t: deque = deque(maxlen=MAX_LECTURAS)
        self._datos_h: deque = deque(maxlen=MAX_LECTURAS)
        self._ultima = None                          # (temperatura, humedad) o None
        self._estado_tipo = "off"
        self._construido = False
        self._ventana_ajustes = None
        self._bloqueo_editor = None

        self._crear_variables()
        self._estilo()
        self._construir()
        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        self.bind_all("<Control-Return>", lambda e: self.aplicar())
        self.al_cambiar()
        self.after(POLL_MS, self._ciclo)
        if demo:
            self.conectar_demo()
        else:
            self.buscar_placa()

    def ahora_ms(self) -> float:
        return (time.monotonic() - self._t0) * 1000

    def _escala(self) -> float:
        try:
            s = float(self.winfo_fpixels("1i")) / 96
            return s if 0.5 <= s <= 4 else 1.0
        except Exception:
            return 1.0

    # ------------------------------------------------------------------ estado (variables)
    def _crear_variables(self):
        self.paneles = {c: LedUI(c, self.al_cambiar) for c in P.COLORES}
        self.v_sel = tk.StringVar(value="R")                       # LED que se edita
        self.v_vista = tk.StringVar(value="semaforo")              # pestaña: semaforo (Luces) o clima
        self.v_modo_luces = tk.StringVar(value="semaforo")         # semaforo o protoboard
        self.v_detalles = tk.BooleanVar(value=False)
        self.v_tema = tk.StringVar(value=T.tema_actual)
        self.v_acento = tk.StringVar(value=T.acento_actual)
        self.v_estado = tk.StringVar(value="Sin conexión")
        self.v_pendiente = tk.StringVar(value="")
        self.v_puerto = tk.StringVar()
        self.v_sem = tk.StringVar(value="Sin conexión")
        self.v_titulo_editor = tk.StringVar(value=NOMBRE_LUZ["R"])
        self.v_bloqueo = tk.StringVar(value="")
        # secuencias
        self.v_seq = tk.StringVar(value="VIAL")
        self.v_vel = tk.IntVar(value=100)
        self.v_vel_txt = tk.StringVar(value="100 %")
        # clima
        self.v_temp = tk.StringVar(value="-- °C")
        self.v_hum = tk.StringVar(value="-- %")
        self.v_zona = tk.StringVar(value="")
        self.v_dht = tk.StringVar(value="2000")
        self.v_termo = tk.BooleanVar(value=False)
        self.v_tmin, self.v_tmax = tk.StringVar(value="22"), tk.StringVar(value="28")
        self.v_alarmas = tk.BooleanVar(value=False)
        self.v_amax_t, self.v_amax_h = tk.StringVar(value="35"), tk.StringVar(value="80")

        self.v_sel.trace_add("write", lambda *_: self._al_elegir_led())
        self.v_vista.trace_add("write", lambda *_: self.mostrar_vista(self.v_vista.get()))
        self.v_modo_luces.trace_add("write", lambda *_: self._mostrar_modo_luces())
        self.v_detalles.trace_add("write", lambda *_: self._mostrar_detalles())
        for v in (self.v_tema, self.v_acento):
            v.trace_add("write", lambda *_: self._cambio_apariencia())
        for v in (self.v_seq, self.v_vel):
            v.trace_add("write", lambda *_: self._cambio_seq())
        for v in (self.v_dht, self.v_termo, self.v_tmin, self.v_tmax):
            v.trace_add("write", lambda *_: self.al_cambiar())

    # ------------------------------------------------------------------ interfaz
    def _estilo(self):
        try:
            est = ttk.Style(self)
            est.theme_use("clam")
            est.configure("Duino.TCombobox", fieldbackground=T.SUPERFICIE_2, background=T.SUPERFICIE_2,
                          foreground=T.TEXTO, arrowcolor=T.TEXTO_2, bordercolor=T.BORDE,
                          lightcolor=T.SUPERFICIE_2, darkcolor=T.SUPERFICIE_2, selectbackground=T.SUPERFICIE_2,
                          selectforeground=T.TEXTO, padding=4)
            est.map("Duino.TCombobox",
                    fieldbackground=[("readonly", T.SUPERFICIE_2)],
                    foreground=[("readonly", T.TEXTO)],
                    background=[("active", T.PISTA), ("readonly", T.SUPERFICIE_2)],
                    arrowcolor=[("active", T.ACENTO)],
                    bordercolor=[("focus", T.ACENTO)],
                    selectbackground=[("readonly", T.SUPERFICIE_2), ("focus", T.SUPERFICIE_2)],
                    selectforeground=[("readonly", T.TEXTO), ("focus", T.TEXTO)])
            est.configure("Duino.Vertical.TScrollbar", troughcolor=T.FONDO, background=T.PISTA, bordercolor=T.FONDO,
                          lightcolor=T.PISTA, darkcolor=T.PISTA, arrowcolor=T.TEXTO_3, arrowsize=self._px(10))
            est.map("Duino.Vertical.TScrollbar", background=[("active", T.TEXTO_3)])
            self.option_add("*TCombobox*Listbox.background", T.SUPERFICIE)
            self.option_add("*TCombobox*Listbox.foreground", T.TEXTO)
            self.option_add("*TCombobox*Listbox.selectBackground", T.ACENTO)
            self.option_add("*TCombobox*Listbox.selectForeground", T.SOBRE_ACENTO)
            self.option_add("*TCombobox*Listbox.font", (self.f, T.TAM_CUERPO))
        except tk.TclError:
            pass

    def _px(self, n: float) -> int:
        return round(n * T.ESCALA)

    def _construir(self):
        self.configure(bg=T.FONDO)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self._construir_cabecera()

        cuerpo = tk.Frame(self, bg=T.FONDO)
        cuerpo.grid(row=1, column=0, sticky="nsew", padx=self._px(24))
        cuerpo.columnconfigure(0, weight=1)
        cuerpo.rowconfigure(0, weight=1)
        self.banner = tk.Label(self, text="", bg=T.ALARMA, fg="#ffffff", font=(self.f, T.TAM_CUERPO, "bold"),
                               anchor="w", padx=self._px(16), pady=self._px(8))
        self.vistas = {}
        self._construir_luces(cuerpo)
        self._construir_clima(cuerpo)
        self._construir_detalles()

        self._construido = True
        self.mostrar_vista(self.v_vista.get())
        self._mostrar_modo_luces()
        self._mostrar_detalles()
        self._al_elegir_led()
        self._repintar_log()
        self._pintar_clima()
        self._actualizar_banner()
        self._poner_estado(self.v_estado.get(), self._estado_tipo)
        self.actualizar_puertos(silencioso=True)
        self._texto_sem = None

    # --- cabecera
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

    # --- vista Luces
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

        etiqueta(c, "", f, T.TAM_CUERPO, T.TEXTO, textvariable=self.v_sem, negrita=True).grid(
            row=1, column=0, pady=(self._px(8), 0))
        etiqueta(c, "Haz clic en una luz para elegir qué hace.", f, T.TAM_PEQ, T.TEXTO_3).grid(row=2, column=0)
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

        tseq = Tarjeta(lateral, "Animaciones", f, subtitulo="Las tres luces cambian solas siguiendo un patrón.")
        tseq.pack(fill="x", pady=(0, self._px(14)))
        a = tseq.contenido
        Segmentado(a, self.v_seq, SECUENCIAS, ancho=ANCHO_LATERAL, columnas=1, alto_fila=34, hueco=6,
                   fuente=f).pack(anchor="w")
        fila_vel = tk.Frame(a, bg=T.SUPERFICIE)
        fila_vel.pack(fill="x", pady=(self._px(12), 0))
        etiqueta(fila_vel, "Velocidad", f).pack(side="left")
        etiqueta(fila_vel, "", f, color=T.TEXTO, textvariable=self.v_vel_txt).pack(side="right")
        self.desl_vel = Deslizador(a, self.v_vel, P.VEL_MIN, P.VEL_MAX, ancho=ANCHO_LATERAL)
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
        ancho = min(e.width / s * 0.8, alto * SemaforoVirtual.BASE_W / SemaforoVirtual.BASE_H, 210)
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
        for c, ch in self.chips.items():
            ch.configurar(seleccionado=(c == col))

    def _mostrar_modo_luces(self):
        if not self._construido:
            return
        if self.v_modo_luces.get() == "protoboard":
            self.f_semaforo.grid_remove()
            self.protoboard.grid(row=0, column=0, sticky="nsew")
        else:
            self.protoboard.grid_remove()
            self.f_semaforo.grid(row=0, column=0, sticky="nsew")

    # --- vista Clima
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

        self.t_sensor = Tarjeta(izq, "Sensor (detalles)", f)
        self._fila_numero(self.t_sensor.contenido, 0, "Leer el sensor cada", self.v_dht, "ms", ancho=7)

        thist = Tarjeta(vc, "Últimos minutos", f, llenar=True)
        thist.grid(row=0, column=1, sticky="nsew", padx=(self._px(7), 0), pady=(0, sep))
        etiqueta(thist.extra, "● temperatura (°C)  ", f, T.TAM_PEQ, T.ACENTO).pack(side="left")
        from grafica import COLOR_HUMEDAD
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

    # --- panel de detalles (conexión y registro)
    def _construir_detalles(self):
        f = self.f
        self.t_detalles = Tarjeta(self, "Detalles técnicos", f)
        c = self.t_detalles.contenido
        c.columnconfigure(1, weight=1)
        con = tk.Frame(c, bg=T.SUPERFICIE)
        con.grid(row=0, column=0, sticky="nw", padx=(0, self._px(24)))
        etiqueta(con, "Puerto serie", f, T.TAM_PEQ).grid(row=0, column=0, columnspan=3, sticky="w")
        self.cb_puerto = ttk.Combobox(con, textvariable=self.v_puerto, width=16, style="Duino.TCombobox",
                                      font=(f, T.TAM_CUERPO))
        self.cb_puerto.grid(row=1, column=0, sticky="w", pady=(self._px(4), 0))
        self.b_refrescar = BotonIcono(con, "refrescar", self.actualizar_puertos, 34)
        self.b_refrescar.grid(row=1, column=1, padx=(self._px(6), 0), pady=(self._px(4), 0))
        self.b_power = BotonPildora(con, "Conectar", self.alternar_conexion, 120, 34, "fantasma", f)
        self.b_power.grid(row=2, column=0, columnspan=2, sticky="w", pady=(self._px(8), 0))
        etiqueta(con, "Placa: 9600 baudios · sketch control_leds.ino", f, T.TAM_MINI, T.TEXTO_3).grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(self._px(8), 0))

        reg = tk.Frame(c, bg=T.SUPERFICIE)
        reg.grid(row=0, column=1, sticky="nsew")
        cab = tk.Frame(reg, bg=T.SUPERFICIE)
        cab.pack(fill="x")
        etiqueta(cab, "Registro de comunicación", f, T.TAM_PEQ).pack(side="left")
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
            self.t_sensor.pack(fill="x", pady=(0, self._px(14)))
        else:
            self.t_detalles.grid_remove()
            self.t_sensor.pack_forget()
        self._actualizar_editor()

    def mostrar_vista(self, nombre: str):
        """Cambia entre Luces (semaforo) y Clima. No toca nada de lo aplicado en el Arduino."""
        if self.v_vista.get() != nombre:
            self.v_vista.set(nombre)
            return
        for n, v in self.vistas.items():
            if n == nombre:
                v.grid(row=0, column=0, sticky="nsew")
            else:
                v.grid_remove()
        self.vista_actual = nombre

    # --- ajustes y tema
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

    # --- registro
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

    # ------------------------------------------------------------------ estado de la ventana
    def _leds_ui(self) -> dict:
        return {c: p.obtener() for c, p in self.paneles.items()}

    def leer_ui(self):
        """(leds, dht_ms, termo) de la ventana. Lanza ValueError con un mensaje claro."""
        try:
            dht = int(self.v_dht.get().strip())
        except ValueError:
            raise ValueError("«Leer el sensor cada (ms)» debe ser un número entero")
        termo = None
        if self.v_termo.get():
            try:
                termo = (int(self.v_tmin.get().strip()), int(self.v_tmax.get().strip()))
            except ValueError:
                raise ValueError("Las temperaturas del semáforo deben ser números enteros")
        return (self._leds_ui() if termo is None else {}), dht, termo

    def al_cambiar(self, *_):
        bloqueado = self.v_termo.get() or self.aplicado.seq is not None
        for p in self.paneles.values():
            p.habilitar(not bloqueado)
        self._actualizar_botones_seq()
        self._actualizar_luces(bloqueado)
        pendiente = False
        if not self.enlace.conectado:
            self.v_pendiente.set("")
        else:
            try:
                pasos = P.plan(*self.leer_ui(), self.aplicado)
                pendiente = bool(pasos)
                self.v_pendiente.set("Tienes cambios sin aplicar" if pasos else "")
            except ValueError:
                pendiente = True
                self.v_pendiente.set("Revisa los valores: hay alguno incorrecto")
        if hasattr(self, "b_aplicar"):
            self.b_aplicar.configurar(estilo="relleno" if pendiente or not self.enlace.conectado else "suave")

    def _actualizar_luces(self, bloqueado: bool):
        if not self._construido:
            return
        for c, ch in self.chips.items():
            ch.configurar(resumen="Automático" if bloqueado else self.paneles[c].resumen())
        self._actualizar_editor()

    # ------------------------------------------------------------------ conexión
    def _poner_estado(self, texto: str, tipo: str):
        """tipo: ok, buscando, error u off. Pinta el punto y muestra «Reintentar» cuando hace falta."""
        self._estado_tipo = tipo
        self.v_estado.set(texto)
        if not self._construido:
            return
        color = {"ok": T.EXITO, "buscando": T.ACENTO, "error": T.ERROR}.get(tipo, T.TEXTO_3)
        self.punto.itemconfigure("punto", fill=color)
        if tipo in ("error", "off"):
            self.b_reintentar.pack(side="left", padx=(self._px(6), 0))
        else:
            self.b_reintentar.pack_forget()
        self.b_power.configurar(texto="Desconectar" if self.enlace.conectado else "Conectar")

    def reintentar(self):
        if self.demo:
            self.conectar_demo()
        else:
            self.buscar_placa()

    def actualizar_puertos(self, silencioso: bool = False):
        try:
            nombres = [p.device for p in listar_puertos()]
        except PySerialNoDisponible as e:
            nombres = []
            if not silencioso:
                messagebox.showerror("Falta pyserial", str(e))
        if self.demo:
            nombres = ["SIMULADOR"] + nombres
        self.cb_puerto["values"] = nombres

    def buscar_placa(self):
        self._poner_estado("Buscando tu Arduino…", "buscando")

        def trabajo():
            try:
                puerto = autodetectar(progreso=lambda p: self.cola_ui.put(("progreso", p)))
                self.cola_ui.put(("detectado", puerto))
            except PySerialNoDisponible as e:
                self.cola_ui.put(("fallo", str(e)))
            except Exception as e:
                self.cola_ui.put(("fallo", f"Error al buscar la placa: {e}"))
        threading.Thread(target=trabajo, daemon=True).start()

    def alternar_conexion(self):
        if self.enlace.conectado:
            self.desconectar()
        else:
            self.conectar()

    def conectar(self):
        puerto = self.v_puerto.get().strip()
        if not puerto:
            messagebox.showinfo("Puerto", "Elige un puerto de la lista o pulsa el botón de actualizar.")
            return
        if self.demo and puerto == "SIMULADOR":
            self.conectar_demo()
            return
        self._poner_estado("Conectando…", "buscando")

        def trabajo():
            try:
                self.enlace.conectar(puerto)
                self.cola_ui.put(("conectado", puerto))
            except PySerialNoDisponible as e:
                self.cola_ui.put(("fallo", str(e)))
            except Exception as e:
                self.cola_ui.put(("fallo", f"No se pudo abrir {puerto}: {e}"))
        threading.Thread(target=trabajo, daemon=True).start()

    def conectar_demo(self):
        self.sim = ArduinoSimulado()
        self.enlace.usar(self.sim)
        self.v_puerto.set("SIMULADOR")
        self._al_conectar("SIMULADOR")

    def _reiniciar_espejo(self):
        self.aplicado = P.Aplicado()               # no se sabe qué tiene la placa: se reenvía todo
        self.pendientes, self.paso_actual = [], None
        self.secuencia.detener()
        self.vista = apagados()
        self.zona = -1
        self.alarma_t.reiniciar()
        self.alarma_h.reiniciar()
        self._actualizar_banner()

    def _al_conectar(self, puerto: str):
        self._reiniciar_espejo()
        if puerto == "SIMULADOR":
            self._poner_estado("Modo demostración: Arduino simulado", "ok")
        else:
            self._poner_estado(f"Arduino conectado ({puerto})", "ok")
        self.log(f"Conectado a {puerto}. Configura los LEDs y pulsa Aplicar.", "info")
        self.al_cambiar()

    def desconectar(self, motivo: str = "", avisar_arduino: bool = True):
        self._cancelar_timeout()
        if avisar_arduino:
            self._detener_arduino()
        self.enlace.cerrar()
        self.sim = None
        self._reiniciar_espejo()
        self._poner_estado(motivo or "Sin conexión", "error" if motivo else "off")
        self.v_pendiente.set("")
        self.al_cambiar()

    def _detener_arduino(self):
        """Si la app para o se cierra, la secuencia del Arduino también se detiene."""
        if self.enlace.conectado and self.aplicado.seq is not None:
            try:
                self.enlace.enviar("SEQ OFF")
            except Exception:
                pass

    # ------------------------------------------------------------------ envío con confirmación
    def _enviar_pasos(self, pasos: list) -> bool:
        if not self.enlace.conectado:
            messagebox.showwarning("Sin conexión", "Conecta el Arduino primero.")
            return False
        if self.paso_actual is not None or self.pendientes:
            self.log("Ya hay un envío en curso.", "info")
            return False
        self.pendientes = list(pasos)
        self._enviar_siguiente()
        return True

    def aplicar(self):
        if not self.enlace.conectado:
            messagebox.showwarning("Sin conexión", "Conecta el Arduino primero.")
            return
        if self.paso_actual is not None or self.pendientes:
            self.log("Ya hay un envío en curso.", "info")
            return
        try:
            pasos = P.plan(*self.leer_ui(), self.aplicado)
        except ValueError as e:
            messagebox.showwarning("Valores inválidos", f"No se envió nada.\n\n{e}")
            return
        if not pasos:
            self.log("Nada que enviar: ya está aplicado.", "info")
            return
        self._enviar_pasos(pasos)

    def _enviar_siguiente(self, reintento: bool = False):
        if not reintento:
            if not self.pendientes:
                self.paso_actual = None
                self.log("Aplicado.", "info")
                self.al_cambiar()
                return
            self.paso_actual = self.pendientes.pop(0)
            self._intentos = 0
        paso = self.paso_actual
        try:
            self.enlace.enviar(paso.texto)
        except Exception as e:
            self._abortar(f"No se pudo enviar «{paso.texto}»: {e}")
            return
        self.log("→ " + paso.texto, "tx")
        self._id_timeout = self.after(SIN_RESPUESTA_MS, self._sin_respuesta, paso)

    def _sin_respuesta(self, paso):
        if self.paso_actual is not paso:
            return
        if self._intentos < 1:
            self._intentos += 1
            self.log(f"Sin respuesta a «{paso.texto}», reintentando…", "err")
            self._enviar_siguiente(reintento=True)
        else:
            self._abortar(f"El Arduino no respondió a «{paso.texto}». Se detuvo el envío. "
                          "Comprueba que la placa tenga cargado control_leds.ino.")

    def _cancelar_timeout(self):
        if self._id_timeout is not None:
            self.after_cancel(self._id_timeout)
            self._id_timeout = None

    def _abortar(self, mensaje: str):
        self._cancelar_timeout()
        self.pendientes, self.paso_actual = [], None
        self.log(mensaje, "err")
        self.al_cambiar()

    def _confirmado(self, paso: P.Paso):
        """El Arduino respondió OK: se actualiza lo aplicado y el espejo de LEDs y secuencia."""
        previo, ahora = self.aplicado, self.ahora_ms()
        self.aplicado = P.confirmar(previo, paso)
        if paso.clave == "led":
            if previo.seq is not None or previo.termo is not None:   # el Arduino apagó lo automático
                self.vista = apagados()
                self.secuencia.detener()
                self.zona = -1
            self.vista[paso.color] = (paso.valor, ahora)
        elif paso.clave == "seq":
            self.secuencia.sincronizar(paso.valor, ahora)
            self.vista = apagados()
            self.zona = -1
        elif paso.clave == "termo":
            self.secuencia.detener()
            self.vista = apagados()
            self.zona = -1
            self.v_zona.set("")

    # ------------------------------------------------------------------ secuencias
    def _seleccion_seq(self) -> tuple:
        return self.v_seq.get(), int(self.v_vel.get())

    def _cambio_seq(self):
        self.v_vel_txt.set(f"{int(self.v_vel.get())} %")
        self._actualizar_botones_seq()

    def _actualizar_botones_seq(self):
        if not hasattr(self, "b_seq"):
            return
        seq = self.aplicado.seq
        if seq is None:
            texto = "Iniciar"
        elif (seq[0], seq[1]) != self._seleccion_seq():
            texto = "Cambiar"
        else:
            texto = "Seguir" if seq[2] else "Pausar"
        self.b_seq.configurar(texto=texto)
        self.b_stop.configurar(habilitado=seq is not None)

    def alternar_secuencia(self):
        seq = self.aplicado.seq
        try:
            if seq is None or (seq[0], seq[1]) != self._seleccion_seq():
                paso = P.paso_seq_iniciar(*self._seleccion_seq())
            else:
                paso = P.paso_seq_seguir(seq) if seq[2] else P.paso_seq_pausa(seq)
        except ValueError as e:
            messagebox.showwarning("Secuencia", str(e))
            return
        self._enviar_pasos([paso])

    def detener_secuencia(self):
        if self.aplicado.seq is not None:
            self._enviar_pasos([P.paso_seq_detener()])

    # ------------------------------------------------------------------ escenas y CSV
    def guardar_escena(self):
        try:
            leds, dht, termo = self._leds_ui(), *self.leer_ui()[1:]
        except ValueError as e:
            messagebox.showwarning("Escena", f"No se guardó nada.\n\n{e}")
            return
        ruta = filedialog.asksaveasfilename(title="Guardar escena", defaultextension=".json",
                                            initialfile="escena.json", filetypes=[("Escena de DuinoVisor", "*.json")])
        if not ruta:
            return
        try:
            escenas.guardar(ruta, leds, dht, termo, self._seleccion_seq())
        except OSError as e:
            messagebox.showerror("Escena", f"No se pudo guardar el archivo: {e}")
            return
        self.log(f"Escena guardada en {ruta}", "info")

    def cargar_escena(self):
        ruta = filedialog.askopenfilename(title="Cargar escena", filetypes=[("Escena de DuinoVisor", "*.json")])
        if not ruta:
            return
        try:
            leds, dht, termo, seq = escenas.cargar(ruta)
        except ValueError as e:
            messagebox.showwarning("Escena", f"No se cargó nada.\n\n{e}")
            return
        for c, cfg in leds.items():
            self.paneles[c].cargar(cfg)
        self.v_dht.set(str(dht))
        self.v_termo.set(termo is not None)
        if termo is not None:
            self.v_tmin.set(str(termo[0]))
            self.v_tmax.set(str(termo[1]))
        if seq is not None:
            self.v_seq.set(seq[0])
            self.v_vel.set(seq[1])
        self.log("Escena cargada. Pulsa Aplicar para enviarla.", "info")
        self.al_cambiar()

    def exportar_csv(self):
        if not self.lecturas:
            messagebox.showinfo("Exportar CSV", "Todavía no hay lecturas del sensor.")
            return
        ruta = filedialog.asksaveasfilename(title="Exportar lecturas", defaultextension=".csv",
                                            initialfile=f"lecturas_{datetime.now():%Y%m%d_%H%M%S}.csv",
                                            filetypes=[("CSV", "*.csv")])
        if not ruta:
            return
        try:
            n = escribir_csv(ruta, self.lecturas)
        except OSError as e:
            messagebox.showerror("Exportar CSV", f"No se pudo guardar el archivo: {e}")
            return
        self.log(f"{n} lecturas guardadas en {ruta}", "info")

    # ------------------------------------------------------------------ alarmas
    def _revisar_alarmas(self, t: Optional[float], h: Optional[float]):
        if not self.v_alarmas.get():
            if self.alarma_t.activa or self.alarma_h.activa:
                self.alarma_t.reiniciar()
                self.alarma_h.reiniciar()
                self._actualizar_banner()
            return
        try:
            self.alarma_t.configurar(float(self.v_amax_t.get().replace(",", ".")))
            self.alarma_h.configurar(float(self.v_amax_h.get().replace(",", ".")))
        except ValueError:
            return                                              # umbral a medio escribir: se ignora
        for alarma, valor in ((self.alarma_t, t), (self.alarma_h, h)):
            evento = alarma.evaluar(valor)
            if evento == "ACTIVA":
                self.log("Alarma: " + alarma.motivo, "err")
                self.bell()
            elif evento == "RESUELTA":
                self.log(f"{alarma.nombre} volvió a la normalidad.", "info")
        self._actualizar_banner()

    def _actualizar_banner(self):
        if not hasattr(self, "banner"):
            return
        motivos = [a.motivo for a in (self.alarma_t, self.alarma_h) if a.activa]
        if motivos:
            self.banner.configure(text="⚠  Aviso: " + " · ".join(motivos))
            self.banner.grid(row=2, column=0, sticky="ew", padx=self._px(24), pady=(0, self._px(14)))
        else:
            self.banner.grid_remove()

    # ------------------------------------------------------------------ recepción
    def _brillos_espejo(self) -> dict:
        if not self.enlace.conectado:
            return {c: 0 for c in P.COLORES}
        ahora = self.ahora_ms()
        if self.secuencia.activa:
            return self.secuencia.brillos(ahora)
        return {c: P.brillo_en(cfg, ahora - t0) for c, (cfg, t0) in self.vista.items()}

    def _texto_semaforo(self) -> str:
        if not self.enlace.conectado:
            return "Sin conexión con el Arduino"
        seq = self.aplicado.seq
        if seq is not None:
            return f"Animación «{P.NOMBRES_SEQ[seq[0]]}» " + ("en pausa" if seq[2] else "en marcha")
        if self.aplicado.termo is not None:
            return "Termómetro: " + (ZONAS[self.zona] if self.zona >= 0 else "esperando una lectura")
        return "Control manual"

    def _ciclo(self):
        try:
            while True:
                self._evento_ui(self.cola_ui.get_nowait())
        except queue.Empty:
            pass
        try:
            while True:
                tipo, dato = self.enlace.cola.get_nowait()
                if tipo == "rx":
                    self._recibir(dato)
                else:
                    self.log(dato, "err")
                    self.desconectar("Se perdió la conexión", avisar_arduino=False)
        except queue.Empty:
            pass
        if self._construido:
            brillos = self._brillos_espejo()
            self.semaforo.poner(brillos)
            self.protoboard.poner(brillos)
            for c, ch in self.chips.items():
                ch.configurar(brillo=int(brillos[c]))
            texto = self._texto_semaforo()
            if texto != self._texto_sem:
                self._texto_sem = texto
                self.v_sem.set(texto)
        self.after(POLL_MS, self._ciclo)

    def _evento_ui(self, ev):
        tipo, dato = ev
        if tipo == "progreso":
            self._poner_estado("Buscando tu Arduino…", "buscando")
            self.log(f"Probando {dato}…", "info")
        elif tipo == "detectado":
            if dato:
                self.v_puerto.set(dato)
                self.log(f"Arduino encontrado en {dato}.", "info")
                self.conectar()
            else:
                self._poner_estado("No encontramos el Arduino", "error")
                self.log("No se encontró el Arduino (ningún puerto respondió a PING). ¿Está cargado "
                         "control_leds.ino en la placa? Si lo está, elige el puerto a mano y pulsa Conectar.", "err")
        elif tipo == "conectado":
            self._al_conectar(dato)
            # Una placa con USB nativo (Arduino 101) no se reinicia al abrir el puerto y puede seguir con
            # LEDs, semáforo o secuencia de antes. TERMO OFF lo apaga todo y la deja igual que el espejo.
            self._enviar_pasos([P.Paso("TERMO OFF", "termo", valor=None)])
        elif tipo == "fallo":
            self._poner_estado("No se pudo conectar", "error")
            self.log(dato, "err")

    def _registrar(self, t: Optional[float], h: Optional[float]):
        self.lecturas.append((datetime.now(), t, h))
        if len(self.lecturas) > MAX_LECTURAS_CSV:
            del self.lecturas[: len(self.lecturas) - MAX_LECTURAS_CSV]

    def _espejo_termo(self, t: float):
        if self.aplicado.termo is None:
            return
        nueva = P.zona_termo(t, self.zona, *self.aplicado.termo)
        if nueva != self.zona:
            self.zona = nueva
            cfgs, ahora = P.leds_de_zona(nueva), self.ahora_ms()
            self.vista = {c: (cfgs[c], ahora) for c in P.COLORES}
        self.v_zona.set("Luces: " + ZONAS[self.zona])

    def _pintar_clima(self):
        """Medidor y barras con la última lectura (también tras reconstruir la ventana)."""
        if not self._construido:
            return
        if self._ultima is None:
            self.medidor.poner(0, "--")
        else:
            self.medidor.poner(self._ultima[0] / 50, f"{self._ultima[0]:.1f}")
        self.barras.poner([h for h in list(self._datos_h)[-6:]], 100)

    def _recibir(self, linea: str):
        m = P.interpretar(linea)
        if m.tipo == "DATA":
            self.v_temp.set(f"{m.temperatura:.1f}")
            self.v_hum.set(f"{m.humedad:.0f} %")
            self.grafica.agregar(m.temperatura, m.humedad)
            self._ultima = (m.temperatura, m.humedad)
            self._pintar_clima()
            self._registrar(m.temperatura, m.humedad)
            self._espejo_termo(m.temperatura)
            self._revisar_alarmas(m.temperatura, m.humedad)
        elif m.tipo == "DATA_ERR":
            self.v_temp.set("-- °C")
            self.v_hum.set("-- %")
            self.grafica.agregar(None, None)
            self._ultima = None
            self._pintar_clima()
            self._registrar(None, None)
            self.log("← DATA ERR (el sensor no responde: revisa el cable y la resistencia pull-up)", "err")
        elif m.tipo in ("OK", "ERR"):
            self.log("← " + linea, "rx" if m.tipo == "OK" else "err")
            if self.paso_actual is not None:
                self._cancelar_timeout()
                if m.tipo == "OK":
                    self._confirmado(self.paso_actual)
                    self._enviar_siguiente()
                else:
                    self._abortar(f"El Arduino rechazó «{self.paso_actual.texto}»: {m.texto}")
        else:
            self.log("← " + linea, "rx")

    def _cerrar(self):
        try:
            self._detener_arduino()
            self.enlace.cerrar()
        finally:
            self.destroy()
