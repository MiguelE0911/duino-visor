"""Vista de protoboard: la placa Arduino 101, la protoboard, los LEDs del catálogo con su resistencia y el DHT11.

Los LEDs brillan igual que los del Arduino (mismo espejo que el semáforo). Un clic en un LED lo elige para
cambiar su comportamiento y un clic en el sensor lo marca; abajo flota la ficha del componente elegido.

Navegación: rueda del ratón (zoom suave alrededor del puntero), arrastrar, barra de herramientas (−, %, +,
ajustar y ficha), doble clic en un hueco para verlo todo y teclado (+, −, 0, flechas y Esc).

El dibujo de cada pieza está en `dibujo_placa`, la ficha en `ficha` y las cuentas en `geometria`. Lo que se
mueve cada fotograma (anillo que respira, corriente por el cable, pulso de datos) lo actualiza `animar` sin
redibujar la escena.
"""
from __future__ import annotations

import math
import tkinter as tk

from duinovisor.dominio.leds import COLORES
from duinovisor.dominio.placa import DHT, LEDS, PIN_DHT, PINES, RESISTENCIA_LED
from duinovisor.ui import tema as T
from duinovisor.ui.constantes import NOMBRE_LUZ
from duinovisor.ui.widgets import dibujo_placa as D
from duinovisor.ui.widgets.base import rect_redondo
from duinovisor.ui.widgets.ficha import ANCHO_MAX, MARGEN, dibujar_ficha
from duinovisor.ui.widgets.geometria import (
    encaje,
    limitar_origen,
    origen_centrado,
    punto_en,
    suavizar,
    zoom_en_punto,
)

ESCENA = D.ESCENA
COL_DHT = 24                                             # VCC, DATA y GND en 24, 25 y 26
# Columna del ánodo de cada LED, de izquierda a derecha, repartidas antes del DHT11 (3 LEDs: 4, 11 y 18).
_PASO_LED = min(7, (COL_DHT - 3) // max(1, len(LEDS)))
COLS_LED = tuple(4 + i * _PASO_LED for i in range(len(LEDS)))

# --- navegación y animación
ZOOM_MAX = 4.0                 # respecto a «todo el montaje a la vista»
PASO_ZOOM = 1.25               # por cada paso de la rueda, clic en + / − o tecla
UMBRAL_ARRASTRE = 5            # px que hay que mover el ratón para que un clic pase a ser arrastre
FOTOGRAMAS_ZOOM = 5
FOTOGRAMAS_FICHA = 10
PERIODO_ANILLO_MS = 1600
PERIODO_CORRIENTE_MS = 1500
DURACION_PULSO_MS = 750


def color_cable(id_led: str) -> str:
    """Cable de cada LED: su mismo color, algo más oscuro."""
    return T.mezclar(T.LED_BASE[id_led], "#000000", 0.12)


def orden_leds() -> list[str]:
    """LEDs de izquierda a derecha como en el montaje real (`columna` del catálogo); los que no la tienen, al
    final y por pin descendente."""
    return [led.id for led in sorted(LEDS, key=lambda led: (led.columna, -led.pin))]


class Protoboard(tk.Canvas):
    def __init__(self, master, ancho=560, alto=240, fuente="Helvetica", al_elegir=None, al_accion=None, fondo=None):
        self.S = T.ESCALA
        self.fondo = fondo or T.SUPERFICIE
        self.mesa = T.SUPERFICIE_2
        super().__init__(master, width=round(ancho * self.S), height=round(alto * self.S), bg=self.fondo,
                         highlightthickness=0, bd=0, takefocus=1)
        self._fuente, self.al_elegir, self.al_accion = fuente, al_elegir, al_accion
        self._brillos = {c: 0 for c in COLORES}
        self.seleccionado = None
        self.componente = None            # id del sensor elegido; None = el LED elegido
        self._z, self._wh = 1.0, (1, 1)
        self._zoom, self._origen = 1.0, None          # None = centrado (sin zoom)
        self._centros, self._rutas = {}, {}
        self._inicio = self._ultimo = None
        self._arrastrando, self._bajo = False, ()
        self._encima_comp = self._encima_ctl = None
        self._anim_zoom = self._id_anim_zoom = None
        # ficha
        self._ficha = None
        self.ficha_abierta = True
        self._alto_ficha = 0.0
        self._desp_ficha = 0.0             # cuánto baja respecto a su sitio (0 = a la vista)
        self._anim_ficha = None
        self._entrada_pendiente = True     # al mostrarse, la ficha entra deslizándose
        self._pulso = None
        self.bind("<Configure>", lambda e: self._dibujar(e.width, e.height))
        self.bind("<Map>", lambda e: self._al_mostrarse())
        self.bind("<ButtonPress-1>", self._pulsar)
        self.bind("<B1-Motion>", self._arrastrar)
        self.bind("<ButtonRelease-1>", self._soltar)
        self.bind("<Double-Button-1>", self._doble_clic)
        self.bind("<Motion>", self._mover)
        self.bind("<Leave>", lambda e: self._mover(None))
        self.bind("<MouseWheel>", lambda e: self._rueda(e.x, e.y, e.delta > 0))
        self.bind("<Button-4>", lambda e: self._rueda(e.x, e.y, True))           # Linux
        self.bind("<Button-5>", lambda e: self._rueda(e.x, e.y, False))
        self.bind("<Key>", self._tecla)

    # ================================================================ API
    def poner(self, brillos: dict) -> None:
        for c in COLORES:
            b = int(brillos.get(c, 0))
            if b != self._brillos[c]:
                self._brillos[c] = b
                self._pintar_led(c)

    def seleccionar(self, color) -> None:
        if color != self.seleccionado:
            self.seleccionado = color
            self._marcar_seleccion()

    def seleccionar_forzado(self, color):
        self.seleccionado = color
        self._marcar_seleccion()

    def ver_componente(self, id_sensor) -> None:
        """Elige un sensor (su ficha y su anillo) o, con None, vuelve al LED elegido."""
        self.componente = id_sensor
        self._marcar_seleccion()

    def acercar(self) -> None:
        self._zoom_a(self._zoom * PASO_ZOOM)

    def alejar(self) -> None:
        self._zoom_a(self._zoom / PASO_ZOOM)

    def ajustar(self) -> None:
        """Vuelve a ver todo el montaje."""
        self._cancelar_zoom()
        self._zoom, self._origen = 1.0, None
        self._redibujar()

    def poner_ficha(self, ficha) -> None:
        """Contenido de la ficha. Solo se redibuja si cambió."""
        if ficha == self._ficha:
            return
        self._ficha = ficha
        if not self._listo():
            return
        if self._entrada_pendiente and self.ficha_abierta:
            self._entrar_ficha()
            return
        alto = self._alto_ficha
        self._dibujar_ficha()
        if self.ficha_abierta and abs(self._alto_ficha - alto) > 2 and self._anim_ficha is None:
            self._redibujar()                      # cambió su alto: se recoloca el montaje

    def abrir_ficha(self) -> None:
        if self.ficha_abierta and self._anim_ficha is None:
            return
        self.ficha_abierta = True
        self._entrar_ficha()

    def cerrar_ficha(self) -> None:
        if not self.ficha_abierta:
            return
        self.ficha_abierta = False
        self._entrada_pendiente = False
        if not self._listo():
            return
        self._animar_ficha(self._alto_ficha + 3 * MARGEN * self.S, al_terminar=self._redibujar)
        self._barra_herramientas()

    def pulso_dato(self, ms: float) -> None:
        """Llegó una lectura: un pulso viaja del sensor al Arduino."""
        self._pulso = ms

    def animar(self, ms: float) -> None:
        """Un fotograma: anillo que respira, corriente por el cable del LED elegido y pulso de datos."""
        if not self._listo() or self._anim_zoom is not None:
            return
        self.delete("anim")
        clave = self._clave_elegida()
        fase = (math.sin(ms / PERIODO_ANILLO_MS * 2 * math.pi) + 1) / 2
        self.itemconfigure(f"anillo_{clave}", width=max(1, (1.8 + 1.6 * fase) * self._z),
                           outline=T.mezclar(T.ACENTO, D.BB_ARRIBA, 0.45 * (1 - fase)))
        if self._origen_actual() is None:
            return
        if clave in COLORES and self._brillos[clave] > 0 and clave in self._rutas:
            base = T.LED_BASE[clave]
            for k in range(3):
                f = (ms / PERIODO_CORRIENTE_MS + k / 3) % 1
                self._punto_anim(self._rutas[clave], f, 2.4, T.mezclar(base, "#ffffff", 0.65), base)
        if self._pulso is not None and DHT.id in self._rutas:
            f = (ms - self._pulso) / DURACION_PULSO_MS
            if 0 <= f <= 1:
                self._punto_anim(self._rutas[DHT.id], 1 - f, 3.0, "#ffffff", D.COLOR_CABLE["DHT"])
            elif f > 1:
                self._pulso = None
        # Justo encima del montaje y debajo de la ficha y la barra: subir esas capas cada fotograma obligaría a
        # Tk a repintar toda su superficie (y con la pantalla escalada no le da tiempo).
        if self.find_withtag("anim"):
            self.tag_raise("anim", "escena")

    # ================================================================ estado y utilidades
    def _listo(self) -> bool:
        return self._wh[0] > 20 and self._wh[1] > 20

    def _clave_elegida(self):
        return self.componente or self.seleccionado

    def _vista(self):
        """Rectángulo útil del lienzo: todo menos los márgenes, la barra de herramientas y la ficha abierta."""
        w, h = self._wh
        s, m = self.S, MARGEN * self.S
        abajo = h - m
        if self.ficha_abierta and self._ficha is not None:
            abajo -= (self._alto_ficha or 170 * s) + m
        arriba = m + 24 * s                        # la barra de herramientas puede rozar el borde del montaje
        return (m, arriba, w - m, max(arriba + 120 * s, abajo))

    def _origen_actual(self):
        if not self._listo():
            return None
        return self._origen or origen_centrado(self._vista(), self._z, ESCENA)

    def _a_pantalla(self, x, y):
        ox, oy = self._origen_actual()
        return ox + x * self._z, oy + y * self._z

    def _punto_anim(self, ruta, fraccion, radio, relleno, borde):
        x, y = self._a_pantalla(*punto_en(ruta, fraccion))
        r = max(2, radio * self._z)
        self.create_oval(x - r * 1.9, y - r * 1.9, x + r * 1.9, y + r * 1.9, fill="", outline=borde,
                         width=max(1, self._z * 0.8), tags=("anim",))
        self.create_oval(x - r, y - r, x + r, y + r, fill=relleno, outline=borde, width=max(1, self._z * 0.6),
                         tags=("anim",))

    # ================================================================ dibujo
    def _redibujar(self):
        self._dibujar(*self._wh)

    def _dibujar(self, w, h):
        self._wh = (w, h)
        try:
            self.delete("all")
        except tk.TclError:
            return
        if not self._listo():
            return
        vista = self._vista()
        z = encaje(vista, ESCENA) * self._zoom
        origen = limitar_origen(self._origen or origen_centrado(vista, z, ESCENA), vista, z, ESCENA)
        self._z, self._origen = z, (origen if self._zoom > 1.0001 else None)
        p = D.Pincel(self, z, self._fuente, self.S, self.mesa)
        self._escena(p)
        self.scale("all", 0, 0, z, z)
        self.move("all", *origen)
        self.addtag_all("escena")
        self._mesa(w, h)
        for c in COLORES:
            self._pintar_led(c)
        self._marcar_seleccion()
        self._barra_herramientas()
        alto = self._alto_ficha
        self._dibujar_ficha()
        if self._entrada_pendiente and self.ficha_abierta and self._ficha is not None:
            self.after_idle(self._entrar_ficha)     # se mostró antes de saber su tamaño
        elif self.ficha_abierta and self._anim_ficha is None and abs(self._alto_ficha - alto) > 2:
            self.after_idle(self._redibujar)        # la primera vez no se sabía cuánto ocupa la ficha

    def _mesa(self, w, h):
        """Fondo de mesa de trabajo con una rejilla de puntos, fijo aunque se mueva el montaje.

        Tk no recorta: con zoom, el montaje se saldría por las esquinas redondeadas. Por eso encima del montaje
        van unas máscaras del color de la tarjeta en las cuatro esquinas y el borde (etiqueta `marco`).
        """
        s = self.S
        self.create_rectangle(0, 0, w, h, fill=self.mesa, outline="", tags=("fondo",))
        punto = T.mezclar(self.mesa, T.TEXTO_3, 0.28)
        paso, r = 22 * s, max(1, 1.1 * s)
        y = paso / 2
        while y < h - 4:
            x = paso / 2
            while x < w - 4:
                self.create_oval(x - r, y - r, x + r, y + r, fill=punto, outline="", tags=("fondo",))
                x += paso
            y += paso
        self.tag_lower("fondo")
        radio = 14 * s
        x1, y1 = w - 1, h - 1
        for esquina, (cx, cy), desde in (((0, 0), (radio, radio), 90), ((w, 0), (x1 - radio, radio), 0),
                                        ((w, h), (x1 - radio, y1 - radio), 270), ((0, h), (radio, y1 - radio), 180)):
            arco = [(cx + radio * math.cos(math.radians(desde + k * 9)), cy - radio * math.sin(math.radians(desde + k * 9)))
                    for k in range(11)]
            self.create_polygon(*esquina, *[v for p in arco for v in p], fill=self.fondo, outline="", tags=("marco",))
            self.create_arc(cx - radio, cy - radio, cx + radio, cy + radio, start=desde, extent=90, style="arc",
                            outline=T.BORDE, tags=("marco",))
        for linea in ((radio, 0.5, x1 - radio, 0.5), (radio, y1 - 0.5, x1 - radio, y1 - 0.5),
                      (0.5, radio, 0.5, y1 - radio), (x1 - 0.5, radio, x1 - 0.5, y1 - radio)):
            self.create_line(*linea, fill=T.BORDE, tags=("marco",))

    def _escena(self, p: D.Pincel):
        usados = {str(pin) for pin in (*PINES.values(), PIN_DHT)} | {"5V"}
        D.placa_arduino(p, usados)
        D.protoboard(p)
        self._montaje(p)

    def _anillo_pin(self, p, clave, x, y):
        """Anillo que marca en la cabecera el pin de un componente (al resaltarlo)."""
        self.create_oval(x - 7, y - 7, x + 7, y + 7, outline=T.ACENTO, width=p.a(2.2), state="hidden",
                         tags=(f"pin_{clave}",))

    def _montaje(self, p: D.Pincel):
        col_x, fa, fb = D.col_x, D.FILAS_ARRIBA, D.FILAS_ABAJO
        # alimentación: 5V y GND de la placa a los rieles de abajo
        D.cable(p, ((D.pin_x("5V", D.PINES_POTENCIA, D.HEADER_P), D.HEADER_P[1]), (360, 312), (col_x(0), D.RIEL_POS)),
                D.COLOR_CABLE["5V"])
        D.cable(p, ((D.pin_x("GND", D.PINES_POTENCIA, D.HEADER_P) + 14, D.HEADER_P[1]), (366, 322),
                    (col_x(1), D.RIEL_NEG)), D.COLOR_CABLE["GND"])
        # LEDs
        self._centros, self._rutas = {}, {}
        for i, c in enumerate(orden_leds()):
            ca = COLS_LED[i]
            xa, xk = col_x(ca), col_x(ca + 1)
            tag = (f"sel_{c}",)
            px = D.pin_x(str(PINES[c]))
            self._anillo_pin(p, c, px, D.HEADER_D[1])
            puntos = ((px, D.HEADER_D[1]), ((px + xa) / 2, 6 + i * 4), (xa, fa[0]))
            self._rutas[c] = D.cable(p, puntos, color_cable(c), tag, ruta_tag=f"ruta_{c}")
            D.resistencia(p, xa, fa[3], fb[0], ("#c92a2a", "#c92a2a", "#7a4a12", "#d4af37"), tag)
            D.cable(p, ((xk, fb[4]), (xk + 4, D.RIEL_NEG - 12), (xk, D.RIEL_NEG)), D.COLOR_CABLE["GND"], tag, 2.6)
            cx, cy = (xa + xk) / 2, fb[2]
            self._centros[c] = (cx, cy)
            D.led(p, c, cx, cy, ((xa, fb[1]), (xk, fb[1])), tag)
            D.pastilla(p, cx, 326, f"pin {PINES[c]}", T.LED_BASE[c], tag)
        # DHT11: VCC, DATA y GND en columnas seguidas
        xv, xd, xg = col_x(COL_DHT), col_x(COL_DHT + 1), col_x(COL_DHT + 2)
        tag = (f"sel_{DHT.id}",)
        px = D.pin_x(str(PIN_DHT))
        self._anillo_pin(p, DHT.id, px, D.HEADER_D[1])
        self._rutas[DHT.id] = D.cable(p, ((px, D.HEADER_D[1]), ((px + xd) / 2, 2), (xd + 40, 40), (xd + 34, 180),
                                          (xd, fb[1])), D.COLOR_CABLE["DHT"], ruta_tag=f"ruta_{DHT.id}")
        D.dht(p, DHT.id, xv, xd, xg, tag)
        D.cable(p, ((xv, fb[4]), (xv - 4, D.RIEL_POS - 12), (xv, D.RIEL_POS)), D.COLOR_CABLE["5V"], ancho=2.6)
        D.cable(p, ((xg, fb[4]), (xg + 4, D.RIEL_NEG - 12), (xg, D.RIEL_NEG)), D.COLOR_CABLE["GND"], ancho=2.6)
        D.resistencia(p, xd, fb[3], D.RIEL_POS, ("#7a4a12", "#212529", "#e8590c", "#d4af37"))
        D.pastilla(p, xd, 326, f"pin {PIN_DHT}", DHT.color, tag)

    def _pintar_led(self, c):
        D.pintar_led(self, c, T.LED_BASE[c], self._brillos[c] / 255)

    def _marcar_seleccion(self):
        elegido = self._clave_elegida()
        for clave in (*COLORES, DHT.id):
            self.itemconfigure(f"anillo_{clave}", state="normal" if clave == elegido else "hidden")
        self._resaltar(self._encima_comp)

    def _resaltar(self, encima):
        """Halo del componente bajo el puntero y la ruta de su cable hasta el pin (fuerte); la del elegido, suave."""
        elegido = self._clave_elegida()
        for clave in (*COLORES, DHT.id):
            self.itemconfigure(f"halo_{clave}", state="normal" if clave == encima else "hidden")
            if clave in (encima, elegido):
                fuerte = clave == encima
                self.itemconfigure(f"ruta_{clave}", state="normal",
                                   fill=T.mezclar(self.mesa, T.ACENTO, 0.55 if fuerte else 0.28))
                self.itemconfigure(f"pin_{clave}", state="normal", width=max(1, (2.4 if fuerte else 1.6) * self._z))
            else:
                self.itemconfigure(f"ruta_{clave}", state="hidden")
                self.itemconfigure(f"pin_{clave}", state="hidden")

    # ================================================================ barra de herramientas
    def _barra_herramientas(self):
        """Píldora flotante arriba a la derecha: −, %, +, ajustar y ficha."""
        self.delete("ctl")
        if not self._listo():
            return
        s = self.S
        w = self._wh[0]
        alto, m = 36 * s, MARGEN * s
        botones = [("ctl_menos", 32, self._zoom > 1), ("zoom", 50, False), ("ctl_mas", 32, self._zoom < ZOOM_MAX),
                   ("sep", 9, False), ("ctl_ajustar", 32, self._zoom > 1), ("sep", 9, False),
                   ("ctl_ficha", 74, True)]
        total = sum(b[1] for b in botones) * s + 12 * s
        x0, y0 = w - m - total, m
        for k, f in enumerate((0.05, 0.08, 0.12)):
            e = (3 - k) * 1.5 * s
            rect_redondo(self, x0 - e, y0 - e + 3 * s, x0 + total + e, y0 + alto + e + 3 * s, alto / 2 + e,
                         fill=T.mezclar(self.mesa, "#000000", f), outline="", tags=("ctl",))
        rect_redondo(self, x0, y0, x0 + total, y0 + alto, alto / 2, fill=T.SUPERFICIE, outline=T.BORDE,
                     tags=("ctl",))
        x = x0 + 6 * s
        cy = y0 + alto / 2
        g = max(1, round(1.9 * s))
        for clave, ancho, activo in botones:
            bw = ancho * s
            if clave == "sep":
                self.create_line(x + bw / 2, y0 + 9 * s, x + bw / 2, y0 + alto - 9 * s, fill=T.BORDE, tags=("ctl",))
                x += bw
                continue
            if clave == "zoom":
                self.create_text(x + bw / 2, cy, text=f"{round(self._zoom * 100)} %", fill=T.TEXTO_2,
                                 font=(self._fuente, T.TAM_PEQ, "bold"), tags=("ctl",))
                x += bw
                continue
            tags = ("ctl", clave)
            encendido = clave == "ctl_ficha" and self.ficha_abierta
            if self._encima_ctl == clave and activo:
                relleno = T.SUPERFICIE_2
            elif encendido:
                relleno = T.ACENTO_SUAVE
            else:
                relleno = T.SUPERFICIE
            rect_redondo(self, x + 2 * s, y0 + 5 * s, x + bw - 2 * s, y0 + alto - 5 * s, 13 * s, fill=relleno,
                         outline="", tags=tags)
            tinta = (T.ACENTO if encendido else T.TEXTO) if activo else T.TEXTO_3
            cx = x + bw / 2
            a = 5.5 * s
            if clave in ("ctl_menos", "ctl_mas"):
                self.create_line(cx - a, cy, cx + a, cy, fill=tinta, width=g, capstyle="round", tags=tags)
                if clave == "ctl_mas":
                    self.create_line(cx, cy - a, cx, cy + a, fill=tinta, width=g, capstyle="round", tags=tags)
            elif clave == "ctl_ajustar":                      # cuatro esquinas
                a, lado = 6 * s, 3.5 * s
                for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                    ex, ey = cx + dx * a, cy + dy * a
                    self.create_line(ex - dx * lado, ey, ex, ey, ex, ey - dy * lado, fill=tinta, width=g,
                                     capstyle="round", joinstyle="round", tags=tags)
            else:                                             # ficha: «i» en un círculo y el texto
                ix, ri = x + 16 * s, 7.5 * s
                self.create_oval(ix - ri, cy - ri, ix + ri, cy + ri, outline=tinta, width=max(1, round(1.5 * s)),
                                 tags=tags)
                self.create_line(ix, cy - 0.5 * s, ix, cy + 3.5 * s, fill=tinta, width=g, capstyle="round", tags=tags)
                self.create_oval(ix - s, cy - 4 * s, ix + s, cy - 2 * s, fill=tinta, outline="", tags=tags)
                self.create_text(ix + 13 * s, cy, text="Ficha", anchor="w", fill=tinta,
                                 font=(self._fuente, T.TAM_PEQ, "bold"), tags=tags)
            x += bw

    # ================================================================ ficha
    def _dibujar_ficha(self):
        self.delete("ficha")
        if self._ficha is None or not self._listo() or (not self.ficha_abierta and self._anim_ficha is None):
            return
        w, h = self._wh
        s, m = self.S, MARGEN * self.S
        ancho = min(w - 2 * m, ANCHO_MAX * s)
        x0 = (w - ancho) / 2
        alto = dibujar_ficha(self, self._ficha, x0, x0 + ancho, h - m + self._desp_ficha, s, self._fuente, self.mesa,
                             self._encima_ctl)
        if alto:
            self._alto_ficha = alto

    def _entrar_ficha(self):
        self._entrada_pendiente = False
        if not self._listo() or self._ficha is None:
            self._entrada_pendiente = True
            return
        self._desp_ficha = (self._alto_ficha or 200 * self.S) + 3 * MARGEN * self.S
        self._redibujar()
        self._animar_ficha(0.0)

    def _animar_ficha(self, destino, al_terminar=None):
        if self._anim_ficha is not None and self._anim_ficha[0] is not None:
            self.after_cancel(self._anim_ficha[0])
        self._anim_ficha = [None, self._desp_ficha, destino, 0, al_terminar]
        self._paso_ficha()

    def _paso_ficha(self):
        _, inicio, destino, k, al_terminar = self._anim_ficha
        k += 1
        nuevo = inicio + (destino - inicio) * suavizar(k / FOTOGRAMAS_FICHA)
        try:
            self.move("ficha", 0, nuevo - self._desp_ficha)
        except tk.TclError:
            self._anim_ficha = None
            return
        self._desp_ficha = nuevo
        if k >= FOTOGRAMAS_FICHA:
            self._anim_ficha = None
            self._desp_ficha = destino
            if al_terminar:
                al_terminar()
            return
        self._anim_ficha[3] = k
        self._anim_ficha[0] = self.after(16, self._paso_ficha)

    def _al_mostrarse(self):
        if self.ficha_abierta:
            self._entrada_pendiente = True
            if self._listo():
                self._entrar_ficha()

    # ================================================================ ayuda al pasar el ratón
    def _texto_ayuda(self, clave):
        if clave in COLORES:
            return NOMBRE_LUZ[clave], f"Pin {PINES[clave]} · resistencia {RESISTENCIA_LED} · clic para elegirla"
        return f"Sensor {DHT.nombre}", f"Datos en el pin {PIN_DHT} · clic para ver su ficha"

    def _mostrar_ayuda(self, x, y, clave):
        self.delete("ayuda")
        s = self.S
        titulo, linea = self._texto_ayuda(clave)
        t1 = self.create_text(0, 0, text=titulo, anchor="nw", fill=T.TEXTO, font=(self._fuente, T.TAM_CUERPO, "bold"),
                              tags=("ayuda",))
        t2 = self.create_text(0, 20 * s, text=linea, anchor="nw", fill=T.TEXTO_2, font=(self._fuente, T.TAM_PEQ),
                              tags=("ayuda",))
        c1, c2 = self.bbox(t1), self.bbox(t2)
        if not c1 or not c2:
            return
        ancho, alto = max(c1[2], c2[2]) + 30 * s, c2[3] + 20 * s
        px, py = x + 16 * s, y + 18 * s
        w, h = self._wh
        if px + ancho > w - 6 * s:
            px = x - ancho - 12 * s
        if py + alto > h - 6 * s:
            py = y - alto - 12 * s
        for t in (t1, t2):
            self.move(t, px + 18 * s, py + 10 * s)
        for k, f in enumerate((0.06, 0.12)):
            e = (2 - k) * 2 * s
            sombra = rect_redondo(self, px - e, py - e + 3 * s, px + ancho + e, py + alto + e + 3 * s, 10 * s + e,
                                  fill=T.mezclar(self.mesa, "#000000", f), outline="", tags=("ayuda",))
            self.tag_lower(sombra, t1)
        caja = rect_redondo(self, px, py, px + ancho, py + alto, 10 * s, fill=T.SUPERFICIE, outline=T.BORDE,
                            tags=("ayuda",))
        self.tag_lower(caja, t1)
        color = T.LED_BASE.get(clave, DHT.color)
        rect_redondo(self, px + 7 * s, py + 10 * s, px + 10 * s, py + alto - 10 * s, 1.5 * s, fill=color,
                     outline="", tags=("ayuda",))

    # ================================================================ ratón y teclado
    @staticmethod
    def _componente_de(etiquetas):
        return next((et[4:] for et in etiquetas if et.startswith("sel_")), None)

    @staticmethod
    def _control_de(etiquetas):
        return next((et for et in etiquetas if et.startswith("ctl_") or et in ("ficha_cerrar", "ficha_accion")), None)

    def _mover(self, e):
        if self._arrastrando:
            return
        etiquetas = (self.gettags("current") or ()) if e is not None else ()
        encima_de_algo = "ficha" in etiquetas or "ctl" in etiquetas
        comp = None if encima_de_algo else self._componente_de(etiquetas)
        ctl = self._control_de(etiquetas)
        if comp != self._encima_comp:
            self._encima_comp = comp
            self._resaltar(comp)
        if ctl != self._encima_ctl:
            anterior, self._encima_ctl = self._encima_ctl, ctl
            if (anterior or "").startswith("ctl_") or (ctl or "").startswith("ctl_"):
                self._barra_herramientas()
            if (anterior or "").startswith("ficha") or (ctl or "").startswith("ficha"):
                self._dibujar_ficha()
        try:
            self.configure(cursor="hand2" if comp or ctl else "")
        except tk.TclError:
            pass
        if comp and e is not None:
            self._mostrar_ayuda(e.x, e.y, comp)
        else:
            self.delete("ayuda")

    def _pulsar(self, e):
        try:
            self.focus_set()
        except tk.TclError:
            pass
        self._inicio = self._ultimo = (e.x, e.y)
        self._arrastrando = False
        self._bajo = self.gettags("current") or ()

    def _arrastrar(self, e):
        if self._inicio is None or self._origen is None:          # sin zoom no hay nada que desplazar
            return
        if "ficha" in self._bajo or "ctl" in self._bajo:
            return
        if not self._arrastrando:
            if abs(e.x - self._inicio[0]) + abs(e.y - self._inicio[1]) < UMBRAL_ARRASTRE:
                return
            self._arrastrando = True
            self.delete("ayuda")
            self.configure(cursor="fleur")
        self._desplazar(e.x - self._ultimo[0], e.y - self._ultimo[1])
        self._ultimo = (e.x, e.y)

    def _desplazar(self, dx, dy):
        if self._origen is None:
            return
        ox, oy = self._origen
        nuevo = limitar_origen((ox + dx, oy + dy), self._vista(), self._z, ESCENA)
        self.move("escena", nuevo[0] - ox, nuevo[1] - oy)
        self._origen = nuevo

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
        acciones = {"ctl_mas": self.acercar, "ctl_menos": self.alejar, "ctl_ajustar": self.ajustar,
                    "ctl_ficha": lambda: self.cerrar_ficha() if self.ficha_abierta else self.abrir_ficha(),
                    "ficha_cerrar": self.cerrar_ficha,
                    "ficha_accion": lambda: self.al_accion and self.al_accion(self.componente)}
        for et in etiquetas:
            if et in acciones:
                acciones[et]()
                return
        if "ficha" in etiquetas or "ctl" in etiquetas:
            return
        clave = self._componente_de(etiquetas)
        if clave is None:
            return
        if clave in COLORES:
            self.ver_componente(None)
            if self.al_elegir:
                self.al_elegir(clave)
        else:
            self.ver_componente(clave)
        self.abrir_ficha()

    def _doble_clic(self, e):
        """Doble clic en un hueco: volver a ver todo."""
        etiquetas = self.gettags("current") or ()
        if not any(et.startswith(("sel_", "ctl", "ficha")) for et in etiquetas):
            self.ajustar()

    def _rueda(self, x, y, acercar):
        if "ficha" in (self.gettags("current") or ()):
            return
        self.delete("ayuda")
        self._zoom_a(self._zoom * (PASO_ZOOM if acercar else 1 / PASO_ZOOM), x, y)

    def _tecla(self, e):
        k = e.keysym
        paso = 60 * self.S
        if k in ("plus", "KP_Add", "equal"):
            self.acercar()
        elif k in ("minus", "KP_Subtract"):
            self.alejar()
        elif k in ("0", "KP_0"):
            self.ajustar()
        elif k == "Escape":
            self.cerrar_ficha()
        elif k in ("Left", "Right", "Up", "Down"):
            dx = {"Left": paso, "Right": -paso}.get(k, 0)
            dy = {"Up": paso, "Down": -paso}.get(k, 0)
            self._desplazar(dx, dy)

    # ================================================================ zoom suave
    def _cancelar_zoom(self):
        if self._id_anim_zoom is not None:
            self.after_cancel(self._id_anim_zoom)
            self._id_anim_zoom = None
            self._anim_zoom = None
            self._redibujar()

    def _zoom_a(self, nuevo, px=None, py=None):
        nuevo = max(1.0, min(ZOOM_MAX, nuevo))
        if abs(nuevo - self._zoom) < 1e-9 or not self._listo():
            return
        self._cancelar_zoom()
        vista = self._vista()
        base = encaje(vista, ESCENA)
        if px is None:
            px, py = (vista[0] + vista[2]) / 2, (vista[1] + vista[3]) / 2
        z0, z1 = base * self._zoom, base * nuevo
        origen = self._origen or origen_centrado(vista, z0, ESCENA)
        self._origen = zoom_en_punto(px, py, z0, z1, origen)
        self._zoom = nuevo
        self.delete("anim")
        self._anim_zoom = [FOTOGRAMAS_ZOOM, (z1 / z0) ** (1 / FOTOGRAMAS_ZOOM), px, py]
        self._paso_zoom()

    def _paso_zoom(self):
        n, factor, px, py = self._anim_zoom
        self.scale("escena", px, py, factor, factor)
        n -= 1
        if n <= 0:
            self._anim_zoom = self._id_anim_zoom = None
            self._redibujar()                       # nítido: grosores y letras al nuevo zoom
            return
        self._anim_zoom[0] = n
        self._id_anim_zoom = self.after(14, self._paso_zoom)
