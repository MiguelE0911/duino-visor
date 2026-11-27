"""Ventana de DuinoVisor (Tkinter): une vistas y controladores.

Dos vistas: «Luces» (el semáforo, o la protoboard, en el centro; al hacer clic en una luz se edita en el
panel de la derecha) y «Clima» (temperatura, humedad, gráfica, avisos y semáforo térmico). Lo técnico
(puerto, registro, milisegundos, PWM) queda detrás de «Mostrar detalles».

El semáforo, la protoboard y los chips espejan lo que hace el Arduino: se calculan con el mismo modelo que el
sketch, a partir de lo que la placa confirmó con OK.

Las variables de Tk (la configuración) viven en la App y no en los widgets: así la ventana se puede
reconstruir entera al cambiar de tema o de color sin perder nada.

Cada parte vive en su módulo como un mixin: `vistas/` crea widgets y `controladores/` tiene la
lógica (conexión, envío, espejo, secuencias, archivos, sensor). Todos comparten `self`.
"""
from __future__ import annotations

import queue
import time
import tkinter as tk
from collections import deque
from tkinter import ttk
from typing import Optional

from duinovisor.almacenamiento import preferencias
from duinovisor.dominio.alarmas import Alarma
from duinovisor.dominio.leds import COLORES
from duinovisor.dominio.protocolo import Aplicado, Paso, interpretar, plan
from duinovisor.dominio.secuencias import SecuenciaLocal
from duinovisor.hardware.enlace import Enlace
from duinovisor.hardware.simulador import ArduinoSimulado
from duinovisor.ui import tema as T
from duinovisor.ui.constantes import NOMBRE_LUZ, ORDEN_SEMAFORO, POLL_MS
from duinovisor.ui.controladores.archivos import ArchivosMixin
from duinovisor.ui.controladores.conexion import ConexionMixin
from duinovisor.ui.controladores.envio import EnvioMixin
from duinovisor.ui.controladores.espejo import EspejoMixin, apagados
from duinovisor.ui.controladores.secuencias import SecuenciasMixin
from duinovisor.ui.controladores.sensor import SensorMixin
from duinovisor.ui.estado_led import LedUI
from duinovisor.ui.vistas.ajustes import AjustesMixin
from duinovisor.ui.vistas.cabecera import CabeceraMixin
from duinovisor.ui.vistas.clima import ClimaMixin
from duinovisor.ui.vistas.detalles import DetallesMixin
from duinovisor.ui.vistas.luces import LucesMixin
from duinovisor.ui.widgets.grafica import MAX_LECTURAS


class App(CabeceraMixin, LucesMixin, ClimaMixin, DetallesMixin, AjustesMixin,
          ConexionMixin, EnvioMixin, EspejoMixin, SecuenciasMixin, ArchivosMixin, SensorMixin, tk.Tk):
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
        self.aplicado = Aplicado()
        self.pendientes: list[Paso] = []
        self.paso_actual: Optional[Paso] = None
        self._intentos = 0
        self._id_timeout = None
        self.cola_ui: "queue.Queue[tuple]" = queue.Queue()
        self._t0 = time.monotonic()
        self.secuencia = SecuenciaLocal()          # espejo de la secuencia que corre en el Arduino
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
        self.paneles = {c: LedUI(c, self.al_cambiar) for c in COLORES}
        self.v_sel = tk.StringVar(value=ORDEN_SEMAFORO[0])        # LED que se edita
        self.v_vista = tk.StringVar(value="semaforo")              # pestaña: semaforo (Luces) o clima
        self.v_modo_luces = tk.StringVar(value="semaforo")         # semaforo o protoboard
        self.v_detalles = tk.BooleanVar(value=False)
        self.v_tema = tk.StringVar(value=T.tema_actual)
        self.v_acento = tk.StringVar(value=T.acento_actual)
        self.v_estado = tk.StringVar(value="Sin conexión")
        self.v_pendiente = tk.StringVar(value="")
        self.v_puerto = tk.StringVar()
        self.v_sem = tk.StringVar(value="Sin conexión")
        self.v_titulo_editor = tk.StringVar(value=NOMBRE_LUZ[ORDEN_SEMAFORO[0]])
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

    # ------------------------------------------------------------------ cambios en la ventana
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
                pasos = plan(*self.leer_ui(), self.aplicado)
                pendiente = bool(pasos)
                self.v_pendiente.set("Tienes cambios sin aplicar" if pasos else "")
            except ValueError:
                pendiente = True
                self.v_pendiente.set("Revisa los valores: hay alguno incorrecto")
        if hasattr(self, "b_aplicar"):
            self.b_aplicar.configurar(estilo="relleno" if pendiente or not self.enlace.conectado else "suave")

    # ------------------------------------------------------------------ bucle y recepción
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

    def _recibir(self, linea: str):
        m = interpretar(linea)
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
