"""Ventana de DuinoVisor (Tkinter): tema oscuro con acento ámbar.

Columna 1: un panel por LED. Columna 2: semáforo 3D + secuencias, temperatura y humedad.
Columna 3: historial, sensor y alarmas, registro. El semáforo y los LEDs de la ventana espejan
lo que hace el Arduino: se calculan con el mismo modelo que el sketch, a partir de lo que la
placa confirmó con OK.
"""
from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
from typing import Optional

import escenas
import protocol as P
import tema as T
from alarmas import Alarma
from arduino_link import Enlace, PySerialNoDisponible, autodetectar, listar_puertos
from exportar import escribir_csv
from grafica import Grafica
from simulador import ArduinoSimulado
from widgets import (Barras, BotonPildora, BotonRedondo, Deslizador, Interruptor, LedVirtual, Medidor,
                     SemaforoVirtual, Segmentado, Tarjeta, entrada, etiqueta)

SIN_RESPUESTA_MS = 1500
POLL_MS = 50
MAX_LECTURAS_CSV = 100_000
MODOS = [("OFF", "Apagado"), ("ON", "Fijo"), ("BLINK", "Parpadeo"), ("FADE", "Respiración")]
SECUENCIAS = [(n, P.NOMBRES_SEQ[n]) for n in P.SECUENCIAS]


def apagados() -> dict:
    return {c: (P.LedConfig(color=c, modo="OFF"), 0.0) for c in P.COLORES}


class PanelLed(Tarjeta):
    def __init__(self, master, color: str, al_cambiar, fuente: str):
        super().__init__(master, titulo=f"LED {P.NOMBRES_COLOR[color].lower()}", fuente=fuente)
        self.titulo.configure(fg=T.TEXTO, font=(fuente, 11, "bold"))
        self.color, self.al_cambiar = color, al_cambiar
        self.v_modo = tk.StringVar(value="OFF")
        self.v_brillo = tk.IntVar(value=255)
        self.v_on, self.v_off, self.v_periodo = (tk.StringVar(value=v) for v in ("500", "500", "2000"))

        self.led = LedVirtual(self.extra, color, tamano=42)
        self.led.pack()
        c = self.contenido
        self.seg = Segmentado(c, self.v_modo, MODOS, ancho=250, fuente=fuente)
        self.seg.grid(row=0, column=0, sticky="w")

        self.f_brillo = tk.Frame(c, bg=T.TARJETA)
        etiqueta(self.f_brillo, "Brillo", fuente, 9).pack(side="left")
        self.desl = Deslizador(self.f_brillo, self.v_brillo, 0, 255, ancho=150)
        self.desl.pack(side="left", padx=4)
        etiqueta(self.f_brillo, "", fuente, 9, T.TEXTO, textvariable=self.v_brillo, width=4).pack(side="left")
        self.f_blink = tk.Frame(c, bg=T.TARJETA)
        self.f_fade = tk.Frame(c, bg=T.TARJETA)
        self.entradas = []
        for fila, (marco, texto, var) in enumerate((
                (self.f_blink, "Encendido (ms)", self.v_on), (self.f_blink, "Apagado (ms)", self.v_off),
                (self.f_fade, "Periodo (ms)", self.v_periodo))):
            etiqueta(marco, texto, fuente, 9).grid(row=fila % 2, column=0, sticky="w", pady=2)
            e = entrada(marco, var, 7, fuente)
            e.grid(row=fila % 2, column=1, padx=8, pady=2)
            self.entradas.append(e)
        self.f_brillo.grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.f_blink.grid(row=2, column=0, sticky="w")
        self.f_fade.grid(row=3, column=0, sticky="w")
        for v in (self.v_modo, self.v_brillo, self.v_on, self.v_off, self.v_periodo):
            v.trace_add("write", self._cambio)
        self._mostrar()

    def _cambio(self, *_):
        self._mostrar()
        self.al_cambiar()

    def _mostrar(self):
        modo = self.v_modo.get()
        (self.f_brillo.grid if modo != "OFF" else self.f_brillo.grid_remove)()
        (self.f_blink.grid if modo == "BLINK" else self.f_blink.grid_remove)()
        (self.f_fade.grid if modo == "FADE" else self.f_fade.grid_remove)()

    def habilitar(self, si: bool):
        self.seg.habilitar(si)
        self.desl.habilitar(si)
        for e in self.entradas:
            e.configure(state="normal" if si else "disabled")

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


class App(tk.Tk):
    def __init__(self, demo: bool = False):
        super().__init__()
        self.title("DuinoVisor — control de Arduino" + (" (modo demo)" if demo else ""))
        self.configure(bg=T.FONDO)
        ancho, alto = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{min(1240, ancho - 40)}x{min(800, alto - 90)}")     # que quepa en pantallas pequeñas
        self.minsize(1080, 640)
        self.demo = demo
        self.f = T.fuente(self)
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

        self._estilo()
        self._construir()
        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        self.al_cambiar()
        self.after(POLL_MS, self._ciclo)
        if demo:
            self.conectar_demo()
        else:
            self.buscar_placa()

    def ahora_ms(self) -> float:
        return (time.monotonic() - self._t0) * 1000

    # ------------------------------------------------------------------ interfaz
    def _estilo(self):
        try:
            est = ttk.Style(self)
            est.theme_use("clam")
            est.configure("Oscuro.TCombobox", fieldbackground=T.TARJETA_2, background=T.TARJETA_2,
                          foreground=T.TEXTO, arrowcolor=T.AMBAR, bordercolor=T.BORDE,
                          lightcolor=T.TARJETA_2, darkcolor=T.TARJETA_2, selectbackground=T.TARJETA_2,
                          selectforeground=T.TEXTO)
            est.map("Oscuro.TCombobox",
                    fieldbackground=[("readonly", T.TARJETA_2)],
                    foreground=[("readonly", T.TEXTO)],
                    background=[("active", T.PISTA), ("readonly", T.TARJETA_2)],
                    arrowcolor=[("active", T.AMBAR_CLARO)],
                    selectbackground=[("readonly", T.TARJETA_2), ("focus", T.TARJETA_2)],
                    selectforeground=[("readonly", T.TEXTO), ("focus", T.TEXTO)])
            self.option_add("*TCombobox*Listbox.background", T.TARJETA_2)
            self.option_add("*TCombobox*Listbox.foreground", T.TEXTO)
            self.option_add("*TCombobox*Listbox.selectBackground", T.AMBAR)
            self.option_add("*TCombobox*Listbox.selectForeground", T.SOBRE_AMBAR)
        except tk.TclError:
            pass

    def _construir(self):
        f = self.f
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # --- barra lateral
        barra = tk.Frame(self, bg=T.BARRA, width=72)
        barra.grid(row=0, column=0, sticky="ns")
        barra.pack_propagate(False)                  # sin esto la barra se encoge al ancho de los botones
        BotonRedondo(barra, "D", None, 46, relleno=True, fuente=f).pack(pady=(16, 20))

        def fila_boton(icono, comando, texto):
            """Botón redondo con su rótulo debajo y, a la izquierda, una barrita que marca la vista activa."""
            fila = tk.Frame(barra, bg=T.BARRA)
            fila.pack(fill="x", pady=(0, 10))
            marca = tk.Frame(fila, bg=T.BARRA, width=3, height=34)
            marca.place(x=0, y=6)
            b = BotonRedondo(fila, icono, comando, 46, fuente=f)
            b.pack()
            etiqueta(fila, texto, f, 8, T.TEXTO_3, T.BARRA).pack(pady=(2, 0))
            return b, marca

        self.nav, self.marcas = {}, {}
        for nombre, texto in (("semaforo", "Semáforo"), ("clima", "Clima")):
            self.nav[nombre], self.marcas[nombre] = fila_boton(nombre, lambda n=nombre: self.mostrar_vista(n), texto)
        tk.Frame(barra, bg=T.BORDE, height=1, width=36).pack(pady=(4, 14))
        self.b_refrescar, _ = fila_boton("refrescar", self.actualizar_puertos, "Puertos")
        self.b_power, _ = fila_boton("power", self.alternar_conexion, "Conexión")
        self.punto = tk.Canvas(barra, width=14, height=14, bg=T.BARRA, highlightthickness=0, bd=0)
        self.punto.pack(side="bottom", pady=18)
        self.punto.create_oval(2, 2, 12, 12, fill=T.TEXTO_3, outline="", tags="punto")

        # --- contenido
        cont = tk.Frame(self, bg=T.FONDO)
        cont.grid(row=0, column=1, sticky="nsew", padx=16, pady=14)
        cont.columnconfigure(0, weight=1)
        cont.rowconfigure(1, weight=1)

        cab = tk.Frame(cont, bg=T.FONDO)
        cab.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        titulos = tk.Frame(cab, bg=T.FONDO)
        titulos.pack(side="left")
        etiqueta(titulos, "DuinoVisor", f, 18, T.TEXTO, T.FONDO, negrita=True).pack(anchor="w")
        self.v_estado = tk.StringVar(value="Sin conexión")
        etiqueta(titulos, "", f, 10, T.TEXTO_2, T.FONDO, textvariable=self.v_estado).pack(anchor="w")
        self.b_aplicar = BotonPildora(cab, "Aplicar", self.aplicar, 116, 38, "relleno", f)
        self.b_aplicar.pack(side="right")
        self.b_csv = BotonPildora(cab, "Exportar CSV", self.exportar_csv, 118, 38, "fantasma", f)
        self.b_csv.pack(side="right", padx=8)
        self.b_cargar = BotonPildora(cab, "Cargar escena", self.cargar_escena, 122, 38, "fantasma", f)
        self.b_cargar.pack(side="right")
        self.b_guardar = BotonPildora(cab, "Guardar escena", self.guardar_escena, 128, 38, "fantasma", f)
        self.b_guardar.pack(side="right", padx=8)
        self.v_pendiente = tk.StringVar(value="")
        etiqueta(cab, "", f, 10, T.AMBAR, T.FONDO, textvariable=self.v_pendiente).pack(side="right", padx=12)
        self.v_puerto = tk.StringVar()
        self.cb_puerto = ttk.Combobox(cab, textvariable=self.v_puerto, width=20, style="Oscuro.TCombobox")
        self.cb_puerto.pack(side="right", padx=8)
        self.banner = tk.Label(cont, text="", bg=T.ROJO_ALARMA, fg="#ffffff", font=(f, 10, "bold"), anchor="w",
                               padx=12, pady=5)

        # --- las dos vistas comparten el mismo hueco; solo una se muestra a la vez
        vistas = tk.Frame(cont, bg=T.FONDO)
        vistas.grid(row=1, column=0, sticky="nsew")
        vistas.columnconfigure(0, weight=1)
        vistas.rowconfigure(0, weight=1)
        self.vistas = {}

        # === vista Semáforo: LEDs a la izquierda, semáforo y secuencias a la derecha
        vs = tk.Frame(vistas, bg=T.FONDO)
        vs.columnconfigure(0, weight=3, uniform="vs")
        vs.columnconfigure(1, weight=2, uniform="vs")
        vs.rowconfigure(0, weight=1)
        self.vistas["semaforo"] = vs
        col1 = tk.Frame(vs, bg=T.FONDO)
        col1.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        self.paneles = {}
        for c in P.COLORES:
            p = PanelLed(col1, c, self.al_cambiar, f)
            p.pack(fill="x", pady=(0, 10))
            self.paneles[c] = p
        tsem = Tarjeta(vs, "Semáforo (espejo del Arduino)", f)
        tsem.grid(row=0, column=1, sticky="nsew", padx=(7, 0), pady=(0, 10))
        izq = tk.Frame(tsem.contenido, bg=T.TARJETA)
        izq.grid(row=0, column=0, sticky="n")
        self.semaforo = SemaforoVirtual(izq)
        self.semaforo.pack()
        self.v_sem = tk.StringVar(value="Sin conexión")
        etiqueta(izq, "", f, 9, T.TEXTO_2, textvariable=self.v_sem, wraplength=120, justify="center").pack(pady=(6, 0))
        der = tk.Frame(tsem.contenido, bg=T.TARJETA)
        der.grid(row=0, column=1, sticky="n", padx=(14, 0))
        etiqueta(der, "Secuencia", f, 9).pack(anchor="w")
        self.v_seq = tk.StringVar(value="VIAL")
        Segmentado(der, self.v_seq, SECUENCIAS, ancho=156, columnas=1, fuente=f).pack(anchor="w", pady=(4, 10))
        self.v_vel = tk.IntVar(value=100)
        fila_vel = tk.Frame(der, bg=T.TARJETA)
        fila_vel.pack(anchor="w", fill="x")
        etiqueta(fila_vel, "Velocidad", f, 9).pack(side="left")
        self.v_vel_txt = tk.StringVar(value="100 %")
        etiqueta(fila_vel, "", f, 9, T.TEXTO, textvariable=self.v_vel_txt).pack(side="right")
        self.desl_vel = Deslizador(der, self.v_vel, P.VEL_MIN, P.VEL_MAX, ancho=156)
        self.desl_vel.pack(anchor="w")
        botones = tk.Frame(der, bg=T.TARJETA)
        botones.pack(anchor="w", pady=(10, 0))
        self.b_seq = BotonPildora(botones, "Iniciar", self.alternar_secuencia, 84, 32, "relleno", f, T.TARJETA)
        self.b_seq.pack(side="left")
        self.b_stop = BotonPildora(botones, "Detener", self.detener_secuencia, 84, 32, "fantasma", f, T.TARJETA)
        self.b_stop.pack(side="left", padx=(8, 0))
        for v in (self.v_seq, self.v_vel):
            v.trace_add("write", lambda *_: self._cambio_seq())

        # === vista Clima: temperatura, humedad, sensor y alarmas a la izquierda; historial a la derecha
        vc = tk.Frame(vistas, bg=T.FONDO)
        vc.columnconfigure(0, weight=4, uniform="vc")
        vc.columnconfigure(1, weight=5, uniform="vc")
        vc.rowconfigure(0, weight=1)
        self.vistas["clima"] = vc
        izq_c = tk.Frame(vc, bg=T.FONDO)
        izq_c.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        fila_sens = tk.Frame(izq_c, bg=T.FONDO)
        fila_sens.pack(fill="x", pady=(0, 10))
        fila_sens.columnconfigure((0, 1), weight=1, uniform="s")
        ttemp = Tarjeta(fila_sens, "Temperatura", f)
        ttemp.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.v_temp = tk.StringVar(value="-- °C")
        self.v_hum = tk.StringVar(value="-- %")
        self.v_zona = tk.StringVar(value="")
        etiqueta(ttemp.extra, "", f, 9, T.TEXTO_3, textvariable=self.v_zona).pack()
        self.medidor = Medidor(ttemp.contenido, fuente=f)
        self.medidor.pack()
        thum = Tarjeta(fila_sens, "Humedad", f)
        thum.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        etiqueta(thum.extra, "", f, 13, T.TEXTO, textvariable=self.v_hum, negrita=True).pack()
        self.barras = Barras(thum.contenido)
        self.barras.pack()

        fila_cfg = tk.Frame(izq_c, bg=T.FONDO)
        fila_cfg.pack(fill="x")
        fila_cfg.columnconfigure((0, 1), weight=1, uniform="c")
        tsen = Tarjeta(fila_cfg, "Sensor", f)
        tsen.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        s = tsen.contenido
        self.v_dht = tk.StringVar(value="2000")
        etiqueta(s, "Leer cada (ms)", f, 9).grid(row=0, column=0, sticky="w", pady=2)
        entrada(s, self.v_dht, 7, f).grid(row=0, column=1, padx=8)
        self.v_termo = tk.BooleanVar(value=False)
        etiqueta(s, "Semáforo térmico", f, 9).grid(row=1, column=0, sticky="w", pady=(8, 2))
        Interruptor(s, self.v_termo).grid(row=1, column=1, padx=8, pady=(8, 2))
        self.v_tmin, self.v_tmax = tk.StringVar(value="22"), tk.StringVar(value="28")
        etiqueta(s, "Verde bajo (°C)", f, 9).grid(row=2, column=0, sticky="w", pady=2)
        entrada(s, self.v_tmin, 5, f).grid(row=2, column=1, padx=8)
        etiqueta(s, "Rojo desde (°C)", f, 9).grid(row=3, column=0, sticky="w", pady=2)
        entrada(s, self.v_tmax, 5, f).grid(row=3, column=1, padx=8)
        talar = Tarjeta(fila_cfg, "Alarmas", f)
        talar.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        a = talar.contenido
        self.v_alarmas = tk.BooleanVar(value=False)
        self.v_amax_t, self.v_amax_h = tk.StringVar(value="35"), tk.StringVar(value="80")
        etiqueta(a, "Activadas", f, 9).grid(row=0, column=0, sticky="w", pady=2)
        Interruptor(a, self.v_alarmas).grid(row=0, column=1, padx=8)
        etiqueta(a, "Temp. máx (°C)", f, 9).grid(row=1, column=0, sticky="w", pady=(8, 2))
        entrada(a, self.v_amax_t, 5, f).grid(row=1, column=1, padx=8, pady=(8, 2))
        etiqueta(a, "Humedad máx (%)", f, 9).grid(row=2, column=0, sticky="w", pady=2)
        entrada(a, self.v_amax_h, 5, f).grid(row=2, column=1, padx=8)
        for v in (self.v_dht, self.v_termo, self.v_tmin, self.v_tmax):
            v.trace_add("write", lambda *_: self.al_cambiar())

        thist = Tarjeta(vc, "Historial", f)
        thist.grid(row=0, column=1, sticky="nsew", padx=(7, 0), pady=(0, 10))
        etiqueta(thist.extra, "● temperatura  ", f, 9, T.AMBAR).pack(side="left")
        etiqueta(thist.extra, "● humedad", f, 9, T.TEXTO_2).pack(side="left")
        self.grafica = Grafica(thist.contenido, 420, 300, f)
        self.grafica.pack(fill="both", expand=True)

        # --- registro: franja inferior visible en las dos vistas
        treg = Tarjeta(cont, "Registro", f)
        treg.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.txt = tk.Text(treg.contenido, height=5, state="disabled", wrap="word", bg=T.TARJETA, fg=T.TEXTO_2,
                           relief="flat", bd=0, highlightthickness=0, font=("TkFixedFont", 9), padx=0, pady=0)
        self.txt.pack(fill="both", expand=True)
        self.txt.tag_configure("tx", foreground=T.AMBAR)
        self.txt.tag_configure("rx", foreground=T.VERDE)
        self.txt.tag_configure("err", foreground=T.ROJO)
        self.txt.tag_configure("info", foreground=T.TEXTO_2)
        self.mostrar_vista("semaforo")
        self.actualizar_puertos(silencioso=True)

    def mostrar_vista(self, nombre: str):
        """Cambia entre Semáforo y Clima. No toca nada de lo aplicado en el Arduino."""
        for n, v in self.vistas.items():
            if n == nombre:
                v.grid(row=0, column=0, sticky="nsew")
            else:
                v.grid_remove()
        for n, b in self.nav.items():
            b.configurar(activo=(n == nombre))
            self.marcas[n].configure(bg=T.AMBAR if n == nombre else T.BARRA)
        self.vista_actual = nombre

    def log(self, texto: str, etiqueta_: str = "info"):
        self.txt.configure(state="normal")
        self.txt.insert("end", texto + "\n", etiqueta_)
        if int(self.txt.index("end-1c").split(".")[0]) > 500:
            self.txt.delete("1.0", "50.0")
        self.txt.see("end")
        self.txt.configure(state="disabled")

    # ------------------------------------------------------------------ estado de la ventana
    def _leds_ui(self) -> dict:
        return {c: p.obtener() for c, p in self.paneles.items()}

    def leer_ui(self):
        """(leds, dht_ms, termo) de la ventana. Lanza ValueError con un mensaje claro."""
        try:
            dht = int(self.v_dht.get().strip())
        except ValueError:
            raise ValueError("«Leer cada (ms)» debe ser un número entero")
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
        if not self.enlace.conectado:
            self.v_pendiente.set("")
            return
        try:
            pasos = P.plan(*self.leer_ui(), self.aplicado)
            self.v_pendiente.set("Hay cambios sin aplicar" if pasos else "")
        except ValueError:
            self.v_pendiente.set("Hay cambios sin aplicar (revisa los valores)")

    # ------------------------------------------------------------------ conexión
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
        self.v_estado.set("Buscando el Arduino…")

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
        self.v_estado.set(f"Conectando a {puerto}…")

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
        self.punto.itemconfigure("punto", fill=T.VERDE)
        self.b_power.configurar(relleno=True)
        self.v_estado.set(f"Conectado a {puerto}")
        self.log(f"Conectado a {puerto}. Configura los LEDs y pulsa Aplicar.", "info")
        self.al_cambiar()

    def desconectar(self, motivo: str = "", avisar_arduino: bool = True):
        self._cancelar_timeout()
        if avisar_arduino:
            self._detener_arduino()
        self.enlace.cerrar()
        self.sim = None
        self._reiniciar_espejo()
        self.punto.itemconfigure("punto", fill=T.TEXTO_3)
        self.b_power.configurar(relleno=False)
        self.v_estado.set(motivo or "Sin conexión")
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
        motivos = [a.motivo for a in (self.alarma_t, self.alarma_h) if a.activa]
        if motivos:
            self.banner.configure(text="Alarma: " + " · ".join(motivos))
            self.banner.grid(row=2, column=0, sticky="ew", pady=(10, 0))
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
            return "Sin conexión"
        seq = self.aplicado.seq
        if seq is not None:
            return f"{P.NOMBRES_SEQ[seq[0]]} · {seq[1]} %\n" + ("en pausa" if seq[2] else "en marcha")
        if self.aplicado.termo is not None:
            return "Semáforo térmico\n" + (["zona verde", "zona amarilla", "zona roja"][self.zona] if self.zona >= 0 else "esperando lectura")
        return "Manual"

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
                    self.desconectar("Conexión perdida", avisar_arduino=False)
        except queue.Empty:
            pass
        brillos = self._brillos_espejo()
        self.semaforo.poner(brillos)
        for c, p in self.paneles.items():
            p.led.poner(brillos[c])
        texto = self._texto_semaforo()
        if texto != self._texto_sem:
            self._texto_sem = texto
            self.v_sem.set(texto)
        self.after(POLL_MS, self._ciclo)

    def _evento_ui(self, ev):
        tipo, dato = ev
        if tipo == "progreso":
            self.v_estado.set(f"Probando {dato}…")
        elif tipo == "detectado":
            if dato:
                self.v_puerto.set(dato)
                self.log(f"Arduino encontrado en {dato}.", "info")
                self.conectar()
            else:
                self.v_estado.set("No se encontró la placa")
                self.log("No se encontró el Arduino (ningún puerto respondió a PING). ¿Está cargado "
                         "control_leds.ino en la placa? Si lo está, elige el puerto a mano y pulsa Conexión.", "err")
        elif tipo == "conectado":
            self._al_conectar(dato)
            # Una placa con USB nativo (Arduino 101) no se reinicia al abrir el puerto y puede seguir con
            # LEDs, semáforo o secuencia de antes. TERMO OFF lo apaga todo y la deja igual que el espejo.
            self._enviar_pasos([P.Paso("TERMO OFF", "termo", valor=None)])
        elif tipo == "fallo":
            self.v_estado.set("Sin conexión")
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
        self.v_zona.set(["zona verde", "zona amarilla", "zona roja"][self.zona])

    def _recibir(self, linea: str):
        m = P.interpretar(linea)
        if m.tipo == "DATA":
            self.v_temp.set(f"{m.temperatura:.1f}")
            self.v_hum.set(f"{m.humedad:.0f} %")
            self.grafica.agregar(m.temperatura, m.humedad)
            self.medidor.poner(m.temperatura / 50, self.v_temp.get())
            self.barras.poner([h for h in list(self.grafica.humedades)[-6:]], 100)
            self._registrar(m.temperatura, m.humedad)
            self._espejo_termo(m.temperatura)
            self._revisar_alarmas(m.temperatura, m.humedad)
        elif m.tipo == "DATA_ERR":
            self.v_temp.set("-- °C")
            self.v_hum.set("-- %")
            self.grafica.agregar(None, None)
            self.medidor.poner(0, "--")
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
