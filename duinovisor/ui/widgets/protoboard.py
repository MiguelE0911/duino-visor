"""Vista de protoboard: la placa Arduino, la protoboard, los LEDs del catálogo con su resistencia y el DHT11.

Los LEDs brillan igual que los del Arduino (mismo espejo que el semáforo) y se pueden elegir con un clic
para cambiar su comportamiento; un clic en el sensor muestra su ficha. Se navega con la rueda del ratón
(zoom alrededor del puntero), arrastrando (desplazamiento) y con los botones +, − y Ajustar. El montaje es
el del README.

Las cuentas de la navegación (`origen_centrado`, `zoom_en_punto`, `limitar_origen`) no necesitan Tkinter.
"""
from __future__ import annotations

import tkinter as tk

from duinovisor.dominio.leds import COLORES
from duinovisor.dominio.placa import DHT, LEDS, PIN_DHT, PINES, RESISTENCIA_LED
from duinovisor.ui import tema as T
from duinovisor.ui.constantes import NOMBRE_LUZ
from duinovisor.ui.widgets.base import rect_redondo

ANCHO, ALTO = 800, 340                 # coordenadas virtuales; se escalan al tamaño del lienzo

# --- placa
PLACA = (20, 34, 340, 330)
PINES_DIGITALES = ["GND", "13", "12", "~11", "~10", "~9", "8", "7", "~6", "~5", "4", "~3", "2", "1", "0"]
PINES_POTENCIA = ["IOREF", "RST", "3V3", "5V", "GND", "GND", "VIN"]
HEADER_D = (116, 48, 14)               # x del primer pin, y del centro, separación
HEADER_P = (150, 316, 14)

# --- protoboard
PROTO = (378, 40, 792, 312)
COLUMNAS, X0_COL, PASO = 30, 398, 13
FILAS_ARRIBA = [108 + i * PASO for i in range(5)]        # a-e
FILAS_ABAJO = [196 + i * PASO for i in range(5)]         # f-j
RIEL_POS, RIEL_NEG = 280, 294
COL_DHT = 24                                             # VCC, DATA y GND en 24, 25 y 26
# Columna del ánodo de cada LED, de izquierda a derecha, repartidas antes del DHT11 (3 LEDs: 4, 11 y 18).
_PASO_LED = min(7, (COL_DHT - 3) // max(1, len(LEDS)))
COLS_LED = tuple(4 + i * _PASO_LED for i in range(len(LEDS)))

COLOR_CABLE = {"5V": "#c92a2a", "GND": "#212529", "DHT": "#1c7ed6"}

# --- navegación
ZOOM_MAX = 4.0                 # respecto a «todo el montaje a la vista»
PASO_ZOOM = 1.25               # por cada paso de la rueda o clic en + / −
UMBRAL_ARRASTRE = 5            # px que hay que mover el ratón para que un clic pase a ser arrastre


def color_cable(id_led: str) -> str:
    """Cable de cada LED: su mismo color, algo más oscuro."""
    return T.mezclar(T.LED_BASE[id_led], "#000000", 0.12)


def col_x(c: int) -> float:
    return X0_COL + c * PASO


def pin_x(etiqueta: str, cabecera=PINES_DIGITALES, header=HEADER_D) -> float:
    i = [e.lstrip("~") for e in cabecera].index(etiqueta)
    return header[0] + i * header[2]


def origen_centrado(w: float, h: float, z: float) -> tuple[float, float]:
    """Dónde cae la esquina (0, 0) del montaje para que quede centrado con zoom z."""
    return (w - ANCHO * z) / 2, (h - ALTO * z) / 2


def zoom_en_punto(px: float, py: float, z0: float, z1: float, origen) -> tuple[float, float]:
    """Nuevo origen al pasar de z0 a z1 sin mover el punto del montaje que está bajo (px, py)."""
    ox, oy = origen
    return px - (px - ox) * z1 / z0, py - (py - oy) * z1 / z0


def limitar_origen(origen, w: float, h: float, z: float) -> tuple[float, float]:
    """Si el montaje cabe en un eje, queda centrado; si no, no se puede alejar tanto que se vea un hueco."""
    res = []
    for o, tam, vista in ((origen[0], ANCHO * z, w), (origen[1], ALTO * z, h)):
        res.append((vista - tam) / 2 if tam <= vista else min(0.0, max(vista - tam, o)))
    return res[0], res[1]


def orden_leds() -> list[str]:
    """LEDs de izquierda a derecha: por pin descendente, así los cables no se cruzan."""
    return sorted(COLORES, key=lambda c: -PINES[c])


class Protoboard(tk.Canvas):
    def __init__(self, master, ancho=560, alto=240, fuente="Helvetica", al_elegir=None, fondo=None):
        self.S = T.ESCALA
        self.fondo = fondo or T.SUPERFICIE
        super().__init__(master, width=round(ancho * self.S), height=round(alto * self.S), bg=self.fondo,
                         highlightthickness=0, bd=0)
        self._fuente, self.al_elegir = fuente, al_elegir
        self._brillos = {c: 0 for c in COLORES}
        self.seleccionado = None
        self.componente = None            # id del sensor cuya ficha se ve; None = la del LED elegido
        self._z, self._centros = 1.0, {}
        self._wh = (1, 1)
        self._zoom, self._origen = 1.0, None          # None = centrado (sin zoom)
        self._inicio = self._ultimo = None
        self._arrastrando, self._bajo = False, ()
        self.bind("<Configure>", self._al_redimensionar)
        self.bind("<ButtonPress-1>", self._pulsar)
        self.bind("<B1-Motion>", self._arrastrar)
        self.bind("<ButtonRelease-1>", self._soltar)
        self.bind("<Double-Button-1>", self._doble_clic)
        self.bind("<MouseWheel>", lambda e: self._rueda(e.x, e.y, e.delta > 0))
        self.bind("<Button-4>", lambda e: self._rueda(e.x, e.y, True))           # Linux
        self.bind("<Button-5>", lambda e: self._rueda(e.x, e.y, False))
        ayudas = {c: f"{NOMBRE_LUZ[c]} · pin {PINES[c]} · resistencia {RESISTENCIA_LED}\nClic para cambiarla"
                  for c in COLORES}
        ayudas[DHT.id] = f"Sensor {DHT.nombre} · datos en el pin {PIN_DHT}\nClic para ver su ficha"
        for clave, texto in ayudas.items():
            etiqueta = f"sel_{clave}"
            self.tag_bind(etiqueta, "<Enter>", lambda e, t=texto: self._mostrar_ayuda(e, t))
            self.tag_bind(etiqueta, "<Motion>", lambda e, t=texto: self._mostrar_ayuda(e, t))
            self.tag_bind(etiqueta, "<Leave>", lambda e: self._ocultar_ayuda())
        self.tag_bind("ctl", "<Enter>", lambda e: self.configure(cursor="hand2"))
        self.tag_bind("ctl", "<Leave>", lambda e: self.configure(cursor=""))

    # ---------------------------------------------------------------- API
    def poner(self, brillos: dict) -> None:
        for c in COLORES:
            b = int(brillos.get(c, 0))
            if b != self._brillos[c]:
                self._brillos[c] = b
                self._pintar_led(c)

    def seleccionar(self, color) -> None:
        if color != self.seleccionado:
            self.seleccionado = color
            for c in COLORES:
                self.itemconfigure(f"anillo_{c}", state="normal" if c == color else "hidden")

    def ver_componente(self, id_sensor) -> None:
        """Muestra la ficha de un sensor (o, con None, la del LED elegido) y lo marca en el dibujo."""
        self.componente = id_sensor
        self.itemconfigure(f"anillo_{DHT.id}", state="normal" if id_sensor == DHT.id else "hidden")

    def acercar(self) -> None:
        self._zoom_a(self._zoom * PASO_ZOOM)

    def alejar(self) -> None:
        self._zoom_a(self._zoom / PASO_ZOOM)

    def ajustar(self) -> None:
        """Vuelve a ver todo el montaje."""
        self._zoom, self._origen = 1.0, None
        self._redibujar()

    # ---------------------------------------------------------------- dibujo
    def _al_redimensionar(self, e):
        self._dibujar(e.width, e.height)

    def _redibujar(self):
        self._dibujar(*self._wh)

    def _f(self, tam, negrita=False):
        tam = max(6, round(tam * self._z / self.S))
        return (self._fuente, tam, "bold") if negrita else (self._fuente, tam)

    def _dibujar(self, w, h):
        self._wh = (w, h)
        self.delete("all")
        z = min(w / ANCHO, h / ALTO) * self._zoom
        origen = limitar_origen(self._origen or origen_centrado(w, h, z), w, h, z)
        self._z, self._origen = z, (origen if self._zoom > 1 else None)
        self._placa()
        self._protoboard()
        self._montaje()
        self.scale("all", 0, 0, z, z)
        self.move("all", *origen)
        self.addtag_all("escena")                      # lo que se mueve al arrastrar (no los controles)
        for c in COLORES:
            self._pintar_led(c)
        self.seleccionar_forzado(self.seleccionado)
        self.ver_componente(self.componente)
        self._controles()

    def seleccionar_forzado(self, color):
        self.seleccionado = None
        self.seleccionar(color)

    def _ancho(self, w):
        return max(1, w * self._z)

    def _placa(self):
        x0, y0, x1, y1 = PLACA
        rect_redondo(self, x0, y0, x1, y1, 14, fill="#0e7c86", outline="#0a5f67", width=self._ancho(2))
        for hx, hy in ((x0 + 14, y0 + 14), (x1 - 14, y0 + 14), (x0 + 14, y1 - 14), (x1 - 14, y1 - 14)):
            self.create_oval(hx - 5, hy - 5, hx + 5, hy + 5, fill=self.fondo, outline="#cfd8dc")
        self.create_rectangle(4, 74, 66, 124, fill="#adb5bd", outline="#868e96", width=self._ancho(1.5))   # USB
        self.create_rectangle(8, 238, 58, 286, fill="#212529", outline="#343a40")                          # alimentación
        self.create_rectangle(176, 196, 306, 228, fill="#1b1e21", outline="#343a40")                       # microcontrolador
        for k in range(10):
            x = 184 + k * 12.5
            self.create_line(x, 192, x, 196, fill="#ced4da", width=self._ancho(2))
            self.create_line(x, 228, x, 232, fill="#ced4da", width=self._ancho(2))
        self.create_text(112, 168, text="Arduino", fill="#ffffff", font=self._f(15, True), anchor="w")
        self.create_oval(298, 98, 306, 106, fill="#69db7c", outline="")                                    # LED de encendido
        self.create_text(296, 102, text="ON", fill="#e6fcf5", font=self._f(7), anchor="e")
        for nombres, (hx, hy, paso), arriba in ((PINES_DIGITALES, HEADER_D, True), (PINES_POTENCIA, HEADER_P, False)):
            self.create_rectangle(hx - 8, hy - 7, hx + paso * (len(nombres) - 1) + 8, hy + 7, fill="#1b1e21",
                                  outline="#1b1e21")
            for i, nombre in enumerate(nombres):
                x = hx + i * paso
                usado = nombre.lstrip("~") in {str(p) for p in (*PINES.values(), PIN_DHT)} or nombre in ("5V",) \
                    or (nombre == "GND" and not arriba and i == 4)
                self.create_rectangle(x - 3, hy - 3, x + 3, hy + 3, fill="#495057", outline="#868e96")
                color = "#ffffff" if usado else "#b2dfe3"
                if arriba:
                    self.create_text(x, hy + 11, text=nombre, angle=90, anchor="e", fill=color,
                                     font=self._f(7, usado))
                else:
                    self.create_text(x, hy - 11, text=nombre, angle=90, anchor="w", fill=color,
                                     font=self._f(7, usado))
        self.create_text(HEADER_D[0] + HEADER_D[2] * 7, 22, text="DIGITAL (~ = PWM)", fill=T.TEXTO_3,
                         font=self._f(8))

    def _protoboard(self):
        x0, y0, x1, y1 = PROTO
        rect_redondo(self, x0, y0, x1, y1, 8, fill="#f3efe6", outline="#d6cfbf", width=self._ancho(1.5))
        self.create_rectangle(x0 + 6, 178, x1 - 6, 184, fill="#e6e0d2", outline="")                      # canal central
        hueco = "#8d8778"
        for y, color in ((54, "#e03131"), (68, "#1971c2"), (RIEL_POS, "#e03131"), (RIEL_NEG, "#1971c2")):
            signo = "+" if color == "#e03131" else "−"
            self.create_text(x0 + 9, y, text=signo, fill=color, font=self._f(9, True))
            for c in range(COLUMNAS):
                if c % 6 == 5:
                    continue                                                                 # huecos de grupo
                x = col_x(c)
                self.create_rectangle(x - 2, y - 2, x + 2, y + 2, fill=hueco, outline="")
        for y in (61, RIEL_POS + 7):
            self.create_line(x0 + 18, y, x1 - 10, y, fill="#e9e3d6")
        for fila, y in enumerate(FILAS_ARRIBA + FILAS_ABAJO):
            self.create_text(x0 + 9, y, text="abcdefghij"[fila], fill="#a39d8d", font=self._f(7))
            for c in range(COLUMNAS):
                x = col_x(c)
                self.create_rectangle(x - 2, y - 2, x + 2, y + 2, fill=hueco, outline="")

    def _cable(self, puntos, color, etiqueta=None, ancho=3.2):
        tags = ("cable",) + ((etiqueta,) if etiqueta else ())
        self.create_line(*puntos, fill=T.mezclar(color, "#000000", 0.35), width=self._ancho(ancho + 1.6),
                         capstyle="round", joinstyle="round", smooth=True, tags=tags)
        self.create_line(*puntos, fill=color, width=self._ancho(ancho), capstyle="round", joinstyle="round",
                         smooth=True, tags=tags)
        for x, y in (puntos[:2], puntos[-2:]):
            self.create_oval(x - 3, y - 3, x + 3, y + 3, fill="#495057", outline="#212529", tags=tags)

    def _resistencia(self, x, ya, yb, bandas, etiqueta=None):
        tags = ("resistencia",) + ((etiqueta,) if etiqueta else ())
        self.create_line(x, ya, x, yb, fill="#adb5bd", width=self._ancho(1.6), tags=tags)
        m, largo = (ya + yb) / 2, min(26, abs(yb - ya) - 6)
        rect_redondo(self, x - 5, m - largo / 2, x + 5, m + largo / 2, 4, fill="#e9d8a6", outline="#c9b37e", tags=tags)
        for k, color in enumerate(bandas):
            y = m - largo / 2 + 5 + k * (largo - 8) / max(1, len(bandas) - 1)
            self.create_rectangle(x - 5, y - 1.2, x + 5, y + 1.2, fill=color, outline="", tags=tags)

    def _montaje(self):
        # Alimentación: 5V y GND de la placa a los rieles de abajo
        self._cable((pin_x("5V", PINES_POTENCIA, HEADER_P), HEADER_P[1], 360, 312, col_x(0), RIEL_POS),
                    COLOR_CABLE["5V"])
        self._cable((pin_x("GND", PINES_POTENCIA, HEADER_P) + 14, HEADER_P[1], 366, 322, col_x(1), RIEL_NEG),
                    COLOR_CABLE["GND"])
        # LEDs
        self._centros = {}
        for i, c in enumerate(orden_leds()):
            ca = COLS_LED[i]
            xa, xk = col_x(ca), col_x(ca + 1)
            tag = f"sel_{c}"
            px = pin_x(str(PINES[c]))
            medio = (px + xa) / 2
            self._cable((px, HEADER_D[1], medio, 6 + i * 4, xa, FILAS_ARRIBA[0]), color_cable(c), tag)
            self._resistencia(xa, FILAS_ARRIBA[3], FILAS_ABAJO[0], ("#c92a2a", "#c92a2a", "#8a4b08", "#d4af37"), tag)
            self._cable((xk, FILAS_ABAJO[4], xk + 4, RIEL_NEG - 12, xk, RIEL_NEG), COLOR_CABLE["GND"], tag, 2.6)
            cx, cy = (xa + xk) / 2, FILAS_ABAJO[2]
            self._centros[c] = (cx, cy)
            for k, extra in enumerate((14, 9, 5)):
                self.create_oval(cx - 11 - extra, cy - 11 - extra, cx + 11 + extra, cy + 11 + extra, outline="",
                                 fill="#f3efe6", state="hidden", tags=(tag, f"brillo_{c}", f"brillo_{c}_{k}"))
            self.create_oval(cx - 14, cy - 14, cx + 14, cy + 14, outline=T.ACENTO, width=self._ancho(2.5),
                             state="hidden", tags=(f"anillo_{c}",))
            self.create_oval(cx - 11, cy - 11, cx + 11, cy + 11, outline="", fill="#ffffff", tags=(tag, f"aro_{c}"))
            self.create_oval(cx - 9, cy - 9, cx + 9, cy + 9, outline="", fill="#ffffff", tags=(tag, f"lente_{c}"))
            self.create_oval(cx - 6, cy - 6, cx - 1, cy - 1, outline="", fill="#ffffff", tags=(tag, f"reflejo_{c}"))
            self.create_text(cx, 324, text=f"pin {PINES[c]}", fill=T.TEXTO_2, font=self._f(8), tags=(tag,))
        # DHT11: VCC, DATA y GND en columnas seguidas; el cuerpo asoma sobre la mitad de arriba
        xv, xd, xg = col_x(COL_DHT), col_x(COL_DHT + 1), col_x(COL_DHT + 2)
        for x in (xv, xd, xg):
            self.create_line(x, FILAS_ARRIBA[1], x, FILAS_ABAJO[0], fill="#adb5bd", width=self._ancho(1.6))
        sel = f"sel_{DHT.id}"
        rect_redondo(self, xv - 24, 78, xg + 24, 168, 8, fill="", outline=T.ACENTO, width=self._ancho(2.5),
                     state="hidden", tags=(f"anillo_{DHT.id}",))
        rect_redondo(self, xv - 18, 84, xg + 18, 150, 6, fill="#4dabf7", outline="#1c7ed6", width=self._ancho(1.5),
                     tags=(sel,))
        for k in range(4):
            for j in range(3):
                x, y = xv - 8 + j * 18, 94 + k * 12
                self.create_rectangle(x - 4, y - 3, x + 4, y + 3, fill="#1c7ed6", outline="", tags=(sel,))
        self.create_text(xd, 160, text=DHT.nombre, fill=T.TEXTO_2, font=self._f(8, True), tags=(sel,))
        self._cable((xv, FILAS_ABAJO[4], xv - 4, RIEL_POS - 12, xv, RIEL_POS), COLOR_CABLE["5V"], ancho=2.6)
        self._cable((xg, FILAS_ABAJO[4], xg + 4, RIEL_NEG - 12, xg, RIEL_NEG), COLOR_CABLE["GND"], ancho=2.6)
        self._resistencia(xd, FILAS_ABAJO[3], RIEL_POS, ("#8a4b08", "#212529", "#e8590c", "#d4af37"))
        px = pin_x(str(PIN_DHT))
        self._cable((px, HEADER_D[1], (px + xd) / 2, 2, xd + 40, 40, xd + 34, 180, xd, FILAS_ABAJO[1]),
                    COLOR_CABLE["DHT"])
        self.create_text(xd, 324, text=f"pin {PIN_DHT}", fill=T.TEXTO_2, font=self._f(8))

    def _pintar_led(self, c):
        base, b = T.LED_BASE[c], self._brillos[c] / 255
        fondo = "#f3efe6"
        apagado = T.mezclar("#d9d4c7", base, 0.35)
        lente = T.mezclar(apagado, base, b)
        self.itemconfigure(f"aro_{c}", fill=T.mezclar(apagado, "#000000", 0.12))
        self.itemconfigure(f"lente_{c}", fill=lente)
        self.itemconfigure(f"reflejo_{c}", fill=T.mezclar(lente, "#ffffff", 0.45 + 0.3 * b))
        for k, f in enumerate((0.15, 0.3, 0.5)):
            self.itemconfigure(f"brillo_{c}_{k}", fill=T.mezclar(fondo, base, f * b),
                               state="normal" if b > 0.02 else "hidden")

    # ---------------------------------------------------------------- ayuda al pasar el ratón
    def _mostrar_ayuda(self, e, texto):
        if self._arrastrando:
            return
        self.delete("ayuda")
        t = self.create_text(e.x + 14, e.y + 16, text=texto, anchor="nw", fill=T.TEXTO,
                             font=(self._fuente, T.TAM_PEQ), tags="ayuda")
        x0, y0, x1, y1 = self.bbox(t)
        if x1 + 8 > self.winfo_width():                                  # que no se salga por la derecha
            self.move(t, -(x1 - x0) - 30, 0)
            x0, y0, x1, y1 = self.bbox(t)
        r = self.create_rectangle(x0 - 8, y0 - 6, x1 + 8, y1 + 6, fill=T.SUPERFICIE, outline=T.BORDE, tags="ayuda")
        self.tag_raise(t, r)
        self.configure(cursor="hand2")

    def _ocultar_ayuda(self):
        self.delete("ayuda")
        self.configure(cursor="")

    # ---------------------------------------------------------------- navegación
    def _zoom_a(self, nuevo, px=None, py=None):
        nuevo = max(1.0, min(ZOOM_MAX, nuevo))
        if abs(nuevo - self._zoom) < 1e-9:
            return
        w, h = self._wh
        base = min(w / ANCHO, h / ALTO)
        if px is None:
            px, py = w / 2, h / 2
        z0, z1 = base * self._zoom, base * nuevo
        self._origen = zoom_en_punto(px, py, z0, z1, self._origen or origen_centrado(w, h, z0))
        self._zoom = nuevo
        self._redibujar()

    def _rueda(self, x, y, acercar):
        self._ocultar_ayuda()
        self._zoom_a(self._zoom * (PASO_ZOOM if acercar else 1 / PASO_ZOOM), x, y)

    def _pulsar(self, e):
        self._inicio = self._ultimo = (e.x, e.y)
        self._arrastrando = False
        self._bajo = self.gettags("current") or ()

    def _arrastrar(self, e):
        if self._inicio is None or self._origen is None:          # sin zoom no hay nada que desplazar
            return
        if not self._arrastrando:
            if abs(e.x - self._inicio[0]) + abs(e.y - self._inicio[1]) < UMBRAL_ARRASTRE:
                return
            self._arrastrando = True
            self._ocultar_ayuda()
            self.configure(cursor="fleur")
        w, h = self._wh
        ox, oy = self._origen
        nuevo = limitar_origen((ox + e.x - self._ultimo[0], oy + e.y - self._ultimo[1]), w, h, self._z)
        self.move("escena", nuevo[0] - ox, nuevo[1] - oy)
        self._origen, self._ultimo = nuevo, (e.x, e.y)

    def _soltar(self, e):
        if self._inicio is None:
            return
        arrastre, etiquetas = self._arrastrando, self._bajo
        self._inicio, self._arrastrando = None, False
        if arrastre:
            self.configure(cursor="")
        else:
            self._clic(etiquetas)

    def _clic(self, etiquetas):
        acciones = {"ctl_mas": self.acercar, "ctl_menos": self.alejar, "ctl_ajustar": self.ajustar}
        for et in etiquetas:
            if et in acciones:
                acciones[et]()
                return
            if et.startswith("sel_"):
                clave = et[4:]
                if clave in COLORES:
                    self.ver_componente(None)
                    if self.al_elegir:
                        self.al_elegir(clave)
                else:
                    self.ver_componente(clave)
                return

    def _doble_clic(self, e):
        """Doble clic en un hueco: volver a ver todo."""
        if not any(et.startswith(("sel_", "ctl")) for et in (self.gettags("current") or ())):
            self.ajustar()

    def _controles(self):
        """Botones +, − y Ajustar arriba a la derecha, fijos aunque se mueva el montaje."""
        w = self._wh[0]
        s, m = self.S, round(10 * self.S)
        f = (self._fuente, T.TAM_PEQ, "bold")
        x1 = w - m
        for clave, texto, ancho, activo in (("ctl_ajustar", "Ajustar", 64, self._zoom > 1),
                                            ("ctl_menos", "−", 30, self._zoom > 1),
                                            ("ctl_mas", "+", 30, self._zoom < ZOOM_MAX)):
            x0 = x1 - round(ancho * s)
            tags = ("ctl", clave)
            rect_redondo(self, x0, m, x1, m + round(30 * s), round(8 * s), fill=T.SUPERFICIE, outline=T.BORDE,
                         tags=tags)
            self.create_text((x0 + x1) / 2, m + round(15 * s), text=texto, font=f, tags=tags,
                             fill=T.TEXTO if activo else T.TEXTO_3)
            x1 = x0 - round(6 * s)


class FichaComponente(tk.Frame):
    """Ficha técnica del componente elegido en la protoboard: título, qué es y tres columnas
    (a qué está conectado, qué hace y cómo está ahora). Recibe un `ui.fichas.Ficha`."""

    COLUMNAS = 3

    def __init__(self, master, fuente="Helvetica", fondo=None):
        fondo = fondo or T.SUPERFICIE
        super().__init__(master, bg=fondo)
        self._ficha = None
        s = T.ESCALA
        tk.Frame(self, bg=T.BORDE, height=1).grid(row=0, column=0, columnspan=self.COLUMNAS, sticky="ew",
                                                  pady=(0, round(10 * s)))
        self.titulo = tk.Label(self, bg=fondo, fg=T.TEXTO, font=(fuente, T.TAM_CUERPO, "bold"), anchor="w")
        self.titulo.grid(row=1, column=0, columnspan=self.COLUMNAS, sticky="w")
        self.que_es = tk.Label(self, bg=fondo, fg=T.TEXTO_2, font=(fuente, T.TAM_PEQ), anchor="w", justify="left")
        self.que_es.grid(row=2, column=0, columnspan=self.COLUMNAS, sticky="w")
        self.celdas = []
        for i in range(self.COLUMNAS):
            self.columnconfigure(i, weight=1, uniform="ficha")
            nombre = tk.Label(self, bg=fondo, fg=T.TEXTO_3, font=(fuente, T.TAM_MINI), anchor="w")
            nombre.grid(row=3, column=i, sticky="w", pady=(round(8 * s), 0), padx=(0, round(12 * s)))
            valor = tk.Label(self, bg=fondo, fg=T.TEXTO, font=(fuente, T.TAM_PEQ), anchor="w", justify="left")
            valor.grid(row=4, column=i, sticky="nw", padx=(0, round(12 * s)))
            self.celdas.append((nombre, valor))
        self.bind("<Configure>", self._ajustar)

    def _ajustar(self, e):
        self.que_es.configure(wraplength=max(100, e.width))
        for _, valor in self.celdas:
            valor.configure(wraplength=max(80, e.width // self.COLUMNAS - round(16 * T.ESCALA)))

    def poner(self, ficha) -> None:
        if ficha == self._ficha:
            return
        self._ficha = ficha
        self.titulo.configure(text=ficha.titulo)
        self.que_es.configure(text=ficha.que_es)
        for (nombre, valor), (etq, texto) in zip(self.celdas, ficha.filas):
            nombre.configure(text=etq.upper())
            valor.configure(text=texto)
