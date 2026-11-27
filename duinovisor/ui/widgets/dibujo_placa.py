"""Dibujo de las piezas de la vista protoboard: placa Arduino 101, protoboard, cables, resistencias, LEDs y DHT11.

Todo se dibuja en unidades virtuales (la escena mide ESCENA) y después el lienzo lo escala y lo coloca. Como
el Canvas de Tk no tiene degradados, transparencias ni sombras, se simulan con capas de colores mezclados.
Los grosores y las letras se calculan con el zoom (`Pincel`) porque `Canvas.scale` no los cambia.
"""
from __future__ import annotations

from duinovisor.ui import tema as T
from duinovisor.ui.widgets.base import rect_redondo
from duinovisor.ui.widgets.geometria import bandas, curva_suave

ESCENA = (800, 340)                    # ancho y alto del montaje en unidades virtuales

# --- placa
PLACA = (20, 34, 340, 330)
PINES_DIGITALES = ["GND", "13", "12", "~11", "~10", "~9", "8", "7", "~6", "~5", "4", "~3", "2", "1", "0"]
PINES_POTENCIA = ["IOREF", "RST", "3V3", "5V", "GND", "GND", "VIN"]
PINES_ANALOGICOS = ["A0", "A1", "A2", "A3", "A4", "A5"]
HEADER_D = (116, 48, 14)               # x del primer pin, y del centro, separación
HEADER_P = (150, 316, 14)
HEADER_A = (254, 316, 14)

# --- protoboard
PROTO = (378, 40, 792, 312)
COLUMNAS, X0_COL, PASO = 30, 398, 13
FILAS_ARRIBA = [108 + i * PASO for i in range(5)]        # a-e
FILAS_ABAJO = [196 + i * PASO for i in range(5)]         # f-j
RIEL_POS, RIEL_NEG = 280, 294
RIELES_ARRIBA = (54, 68)

# --- colores de los objetos reales (no cambian con el tema)
PCB_ARRIBA, PCB_ABAJO, PCB_BORDE = "#16949f", "#0b6670", "#075158"
SERIGRAFIA, SERIGRAFIA_TENUE = "#effcfd", "#a9dde2"
ORO, ORO_OSCURO = "#dcb65f", "#a5832f"
BB_ARRIBA, BB_ABAJO, BB_BORDE = "#f8f4eb", "#e8e1d0", "#cfc6b1"
HUECO, HUECO_LUZ = "#4d483f", "#fffdf6"
TEXTO_BB = "#a29b8a"
COLOR_CABLE = {"5V": "#d6332f", "GND": "#25292d", "DHT": "#1c7ed6"}


def col_x(c: int) -> float:
    return X0_COL + c * PASO


def pin_x(etiqueta: str, cabecera=PINES_DIGITALES, header=HEADER_D) -> float:
    i = [e.lstrip("~") for e in cabecera].index(etiqueta)
    return header[0] + i * header[2]


def plano(puntos) -> list[float]:
    return [v for p in puntos for v in p]


class Pincel:
    """El lienzo con el zoom de este dibujo: grosores (`a`) y letras (`f`) a la escala correcta."""

    def __init__(self, lienzo, z: float, fuente: str, escala: float, mesa: str):
        self.c, self.z, self.fuente, self.S, self.mesa = lienzo, z, fuente, escala, mesa

    def a(self, w: float) -> float:
        return max(1, w * self.z)

    def f(self, tam: float, negrita=False):
        tam = max(5, round(tam * self.z / self.S))
        return (self.fuente, tam, "bold") if negrita else (self.fuente, tam)


# ---------------------------------------------------------------- piezas genéricas
def sombra(p: Pincel, x0, y0, x1, y1, r, desp=(3, 5), capas=(0.05, 0.08, 0.12), fondo=None):
    """Sombra suave: rectángulos redondeados que se oscurecen hacia el centro."""
    fondo = fondo or p.mesa
    n = len(capas)
    for k, f in enumerate(capas):
        e = (n - k) * 1.6
        rect_redondo(p.c, x0 + desp[0] - e, y0 + desp[1] - e, x1 + desp[0] + e, y1 + desp[1] + e, r + e,
                     fill=T.mezclar(fondo, "#000000", f), outline="")


def degradado_redondo(p: Pincel, x0, y0, x1, y1, r, arriba, abajo, n=20, borde="", ancho_borde=1.2, tags=()):
    """Rectángulo redondeado con degradado vertical: los extremos llevan su color y el centro, franjas."""
    rect_redondo(p.c, x0, y0, x1, y1, r, fill=arriba, outline="", tags=tags)
    rect_redondo(p.c, x0, y1 - 2 * r, x1, y1, r, fill=abajo, outline="", tags=tags)
    for ya, yb, f in bandas(y0 + r, y1 - r, n):
        color = T.mezclar(arriba, abajo, f)
        p.c.create_rectangle(x0, ya, x1, yb + 0.6, fill=color, outline="", tags=tags)
    if borde:
        rect_redondo(p.c, x0, y0, x1, y1, r, fill="", outline=borde, width=p.a(ancho_borde), tags=tags)


def pastilla(p: Pincel, cx, cy, texto, color, tags=()):
    """Etiqueta en forma de píldora con el color del componente (p. ej. «pin 3»)."""
    ancho = len(texto) * 4.4 + 14
    relleno = T.mezclar(p.mesa, color, 0.22 if T.OSCURO else 0.16)
    borde = T.mezclar(p.mesa, color, 0.5)
    tinta = T.mezclar(color, "#ffffff", 0.25) if T.OSCURO else T.mezclar(color, "#000000", 0.35)
    rect_redondo(p.c, cx - ancho / 2, cy - 7, cx + ancho / 2, cy + 7, 7, fill=relleno, outline=borde,
                 width=p.a(1), tags=tags)
    p.c.create_text(cx, cy, text=texto, fill=tinta, font=p.f(7.5, True), tags=tags)


# ---------------------------------------------------------------- placa Arduino 101
def placa_arduino(p: Pincel, usados: set[str]):
    c = p.c
    x0, y0, x1, y1 = PLACA
    sombra(p, x0, y0, x1, y1, 14)
    degradado_redondo(p, x0, y0, x1, y1, 14, PCB_ARRIBA, PCB_ABAJO, 28, PCB_BORDE, 1.6)
    # pistas de cobre bajo la máscara
    pista = T.mezclar(PCB_ARRIBA, "#ffffff", 0.10)
    for pts in (((124, 60), (124, 120), (196, 150)), ((180, 60), (180, 110), (232, 128)),
                ((236, 60), (236, 98), (262, 128)), ((300, 230), (300, 290), (260, 304)),
                ((150, 300), (150, 260), (196, 214)), ((70, 100), (150, 100), (196, 140)),
                ((60, 262), (120, 262), (196, 200))):
        c.create_line(*plano(pts), fill=pista, width=p.a(1.4), joinstyle="round", capstyle="round")
    # agujeros de montaje con anillo de cobre
    for hx, hy in ((x0 + 15, y0 + 15), (x1 - 15, y0 + 15), (x0 + 15, y1 - 15), (x1 - 15, y1 - 15)):
        c.create_oval(hx - 6.5, hy - 6.5, hx + 6.5, hy + 6.5, fill="#cfa960", outline="#a8873f", width=p.a(0.8))
        c.create_oval(hx - 3.6, hy - 3.6, hx + 3.6, hy + 3.6, fill=p.mesa, outline="")
    # USB-B metálico (asoma por la izquierda)
    degradado_redondo(p, 4, 74, 66, 124, 3, "#eef1f3", "#9aa2aa", 8, "#737b83", 1.2)
    c.create_rectangle(12, 84, 46, 114, fill="#2f3438", outline="#1d2124")
    c.create_rectangle(18, 92, 40, 106, fill="#e9ecef", outline="")
    c.create_line(6, 76.5, 64, 76.5, fill="#ffffff", width=p.a(1))
    # jack de alimentación
    degradado_redondo(p, 8, 238, 60, 286, 5, "#3a3f44", "#151719", 8, "#0d0f10", 1)
    c.create_oval(13, 249, 37, 275, fill="#0b0c0d", outline="#4a5056", width=p.a(1.2))
    c.create_oval(22, 258, 28, 266, fill="#8a9199", outline="")
    c.create_line(14, 241, 56, 241, fill="#5b6268", width=p.a(1))
    # circuito pequeño, cristal y botón de reset
    c.create_rectangle(76, 132, 104, 158, fill="#1b1e21", outline="#33383d")
    for k in range(4):
        y = 136 + k * 6
        c.create_line(72, y, 76, y, fill="#c9ced3", width=p.a(1.2))
        c.create_line(104, y, 108, y, fill="#c9ced3", width=p.a(1.2))
    c.create_oval(116, 138, 140, 152, fill="#d5dade", outline="#8f969d", width=p.a(1))
    c.create_line(121, 141, 135, 141, fill="#ffffff", width=p.a(1))
    rect_redondo(p.c, 306, 128, 330, 152, 3, fill="#dfe3e6", outline="#959ca3", width=p.a(1))
    c.create_oval(312, 134, 324, 146, fill="#c92a2a", outline="#8f1d1d", width=p.a(1))
    c.create_oval(314.5, 136, 318.5, 140, fill="#ff8787", outline="")
    c.create_text(318, 160, text="RESET", fill=SERIGRAFIA_TENUE, font=p.f(5.5, True))
    # módulo Intel Curie: lata metálica
    sombra(p, 196, 168, 296, 248, 6, desp=(1.5, 2.5), capas=(0.10, 0.18), fondo=PCB_ABAJO)
    degradado_redondo(p, 196, 168, 296, 248, 6, "#f3f5f7", "#aab2b9", 14, "#7f878f", 1.2)
    c.create_line(200, 171, 292, 171, fill="#ffffff", width=p.a(1))
    c.create_text(246, 200, text="intel", fill="#5d656d", font=p.f(11, True))
    c.create_text(246, 218, text="CURIE", fill="#79818a", font=p.f(6.5, True))
    c.create_oval(202, 240, 206, 244, fill="#8b939b", outline="")
    # serigrafía
    c.create_text(76, 186, text="ARDUINO", fill=SERIGRAFIA, font=p.f(15, True), anchor="w")
    c.create_text(76, 211, text="101", fill=SERIGRAFIA, font=p.f(19, True), anchor="w")
    c.create_line(76, 228, 180, 228, fill=SERIGRAFIA_TENUE, width=p.a(1))
    c.create_text(76, 238, text="Intel® Curie™ · 3,3 V", fill=SERIGRAFIA_TENUE, font=p.f(6), anchor="w")
    c.create_text(168, 108, text="DIGITAL (PWM ~)", fill=SERIGRAFIA, font=p.f(6.5, True))
    c.create_text(192, 266, text="POWER", fill=SERIGRAFIA, font=p.f(6.5, True))
    c.create_text(289, 266, text="ANALOG IN", fill=SERIGRAFIA, font=p.f(6.5, True))
    # LEDs de la placa: L (pin 13, apagado) y ON (encendido)
    for x, color, texto, encendido in ((262, "#f08c00", "L", False), (298, "#51cf66", "ON", True)):
        if encendido:
            for e, f in ((7, 0.25), (4.5, 0.45)):
                c.create_oval(x - e, 102 - e, x + e, 102 + e, fill=T.mezclar(PCB_ARRIBA, color, f), outline="")
        c.create_rectangle(x - 3, 99.5, x + 3, 104.5,
                           fill=color if encendido else T.mezclar(PCB_ARRIBA, color, 0.35), outline="")
        c.create_text(x, 113, text=texto, fill=SERIGRAFIA_TENUE, font=p.f(6, True))
    # cabeceras de pines
    for nombres, (hx, hy, paso), arriba in ((PINES_DIGITALES, HEADER_D, True), (PINES_POTENCIA, HEADER_P, False),
                                            (PINES_ANALOGICOS, HEADER_A, False)):
        fin = hx + paso * (len(nombres) - 1)
        rect_redondo(p.c, hx - 8, hy - 7.5, fin + 8, hy + 7.5, 2, fill="#1d2023", outline="#0e1012")
        c.create_line(hx - 7, hy - 6, fin + 7, hy - 6, fill="#3d434a", width=p.a(1))
        for i, nombre in enumerate(nombres):
            x = hx + i * paso
            usado = nombre.lstrip("~") in usados
            c.create_rectangle(x - 3.6, hy - 3.6, x + 3.6, hy + 3.6, fill=ORO if usado else ORO_OSCURO,
                               outline=ORO_OSCURO)
            c.create_rectangle(x - 1.7, hy - 1.7, x + 1.7, hy + 1.7, fill="#141618", outline="")
            color = "#ffffff" if usado else SERIGRAFIA_TENUE
            if arriba:
                c.create_text(x, hy + 12, text=nombre, angle=90, anchor="e", fill=color, font=p.f(6.5, usado))
            else:
                c.create_text(x, hy - 12, text=nombre, angle=90, anchor="w", fill=color, font=p.f(6.5, usado))


# ---------------------------------------------------------------- protoboard
def hueco(p: Pincel, x, y):
    p.c.create_rectangle(x - 2.2, y - 2.2, x + 2.2, y + 2.2, fill=HUECO, outline="")
    p.c.create_line(x - 2.2, y + 2.6, x + 2.2, y + 2.6, fill=HUECO_LUZ, width=p.a(0.9))


def protoboard(p: Pincel):
    c = p.c
    x0, y0, x1, y1 = PROTO
    sombra(p, x0, y0, x1, y1, 9)
    degradado_redondo(p, x0, y0, x1, y1, 9, BB_ARRIBA, BB_ABAJO, 18, BB_BORDE, 1.4)
    c.create_line(x0 + 9, y0 + 1.5, x1 - 9, y0 + 1.5, fill="#ffffff", width=p.a(1.2))
    # canal central con sombra interior
    c.create_rectangle(x0 + 6, 175, x1 - 6, 187, fill=T.mezclar(BB_ABAJO, "#000000", 0.06), outline="")
    c.create_line(x0 + 6, 175.6, x1 - 6, 175.6, fill=T.mezclar(BB_ABAJO, "#000000", 0.16), width=p.a(1.2))
    c.create_line(x0 + 6, 186.6, x1 - 6, 186.6, fill="#ffffff", width=p.a(1))
    # rieles de alimentación: línea roja (+) y azul (−) a lo largo
    rojo, azul = "#e03131", "#1971c2"
    for y_pos, y_neg, linea_pos, linea_neg in ((RIELES_ARRIBA[0], RIELES_ARRIBA[1], 46, 76),
                                               (RIEL_POS, RIEL_NEG, 272, 302)):
        c.create_line(x0 + 18, linea_pos, x1 - 12, linea_pos, fill=rojo, width=p.a(1.4))
        c.create_line(x0 + 18, linea_neg, x1 - 12, linea_neg, fill=azul, width=p.a(1.4))
        for x in (x0 + 9, x1 - 7):
            c.create_text(x, y_pos, text="+", fill=rojo, font=p.f(9, True))
            c.create_text(x, y_neg, text="−", fill=azul, font=p.f(9, True))
        for y in (y_pos, y_neg):
            for col in range(COLUMNAS):
                if col % 6 != 5:                                 # los rieles van en grupos de 5
                    hueco(p, col_x(col), y)
    # números de columna y letras de fila
    for col in [0] + list(range(4, COLUMNAS, 5)):
        for y in (FILAS_ARRIBA[0] - 13, FILAS_ABAJO[4] + 13):
            c.create_text(col_x(col), y, text=str(col + 1), fill=TEXTO_BB, font=p.f(5.5))
    for fila, y in enumerate(FILAS_ARRIBA + FILAS_ABAJO):
        for x in (x0 + 9, x1 - 7):
            c.create_text(x, y, text="abcdefghij"[fila], fill=TEXTO_BB, font=p.f(6.5))
        for col in range(COLUMNAS):
            hueco(p, col_x(col), y)


# ---------------------------------------------------------------- cables y resistencias
def cable(p: Pincel, puntos, color, tags=(), ancho=3.2, ruta_tag=None):
    """Cable con aspecto de tubo (borde, cuerpo y reflejo) y puntas metálicas. Devuelve su recorrido.

    Con `ruta_tag` dibuja debajo un resplandor oculto que se enciende al resaltar ese componente."""
    c = p.c
    ruta = curva_suave(list(puntos), 12)
    xy = plano(ruta)
    kw = {"capstyle": "round", "joinstyle": "round"}
    if ruta_tag:
        c.create_line(*xy, fill=T.ACENTO, width=p.a(ancho + 7), state="hidden", tags=(ruta_tag,), **kw)
    sombra_xy = [v + (1.3 if i % 2 == 0 else 2.0) for i, v in enumerate(xy)]
    c.create_line(*sombra_xy, fill=T.mezclar(p.mesa, "#000000", 0.22), width=p.a(ancho + 0.6), tags=tags, **kw)
    c.create_line(*xy, fill=T.mezclar(color, "#000000", 0.42), width=p.a(ancho + 1.5), tags=tags, **kw)
    c.create_line(*xy, fill=color, width=p.a(ancho), tags=tags, **kw)
    brillo = [v - 0.55 for v in xy]
    c.create_line(*brillo, fill=T.mezclar(color, "#ffffff", 0.5), width=p.a(ancho * 0.3), tags=tags, **kw)
    for x, y in (ruta[0], ruta[-1]):
        c.create_oval(x - 3.1, y - 3.1, x + 3.1, y + 3.1, fill="#b9bfc5", outline="#69717a", width=p.a(0.8),
                      tags=tags)
        c.create_oval(x - 1.3, y - 1.3, x + 1.3, y + 1.3, fill="#4a5158", outline="", tags=tags)
    return ruta


def resistencia(p: Pincel, x, ya, yb, colores, tags=()):
    """Resistencia vertical con forma de hueso, sus bandas de color (la de tolerancia aparte) y sus patas."""
    c = p.c
    c.create_line(x, ya, x, yb, fill="#9ea4aa", width=p.a(1.5), tags=tags)
    for y in (ya, yb):
        c.create_oval(x - 1.5, y - 1.5, x + 1.5, y + 1.5, fill="#6c737a", outline="", tags=tags)
    m, largo = (ya + yb) / 2, min(28, abs(yb - ya) - 8)
    arriba, abajo = m - largo / 2, m + largo / 2
    cuerpo, borde = "#e7d29f", "#b8995a"
    c.create_oval(x - 5.4, arriba + 1.5, x + 6.4, abajo + 2.5, fill=T.mezclar(BB_ABAJO, "#000000", 0.14), outline="",
                  tags=tags)
    for y0_, y1_ in ((arriba, arriba + 9), (abajo - 9, abajo)):
        c.create_oval(x - 5.3, y0_, x + 5.3, y1_, fill=cuerpo, outline=borde, width=p.a(0.9), tags=tags)
    c.create_rectangle(x - 4.2, arriba + 4.5, x + 4.2, abajo - 4.5, fill=cuerpo, outline="", tags=tags)
    for dx in (-4.2, 4.2):
        c.create_line(x + dx, arriba + 6, x + dx, abajo - 6, fill=borde, width=p.a(0.9), tags=tags)
    *cifras, tolerancia = colores
    for k, color in enumerate(cifras):
        y = arriba + 6 + k * 4.2
        ancho = 5.0 if k == 0 else 4.3
        c.create_rectangle(x - ancho, y - 1.3, x + ancho, y + 1.3, fill=color, outline="", tags=tags)
    c.create_rectangle(x - 5.0, abajo - 7.3, x + 5.0, abajo - 4.7, fill=tolerancia, outline="", tags=tags)
    c.create_line(x - 2.3, arriba + 3, x - 2.3, abajo - 3, fill=T.mezclar(cuerpo, "#ffffff", 0.6), width=p.a(1.1),
                  tags=tags)


# ---------------------------------------------------------------- LED de 5 mm
R_LED = 11
CAPAS_DOMO = 5


EXTRA_LUZ = 34          # cuánto se derrama la luz del LED alrededor de su cúpula


def led_patas(p: Pincel, cx: float, cy: float, patas, tags=()):
    """Las patas del LED hasta sus agujeros (no cambian: van en la imagen fija)."""
    c = p.c
    for (x, y) in patas:
        c.create_line(cx + (x - cx) * 0.3, cy, x, y, fill="#a7adb3", width=p.a(1.3), tags=tags)
        c.create_oval(x - 1.4, y - 1.4, x + 1.4, y + 1.4, fill="#6c737a", outline="", tags=tags)


def marcas(p: Pincel, clave: str, cx: float, cy: float, r: float):
    """Halo (al pasar el ratón) y anillo (elegido) de un componente redondo: ocultos hasta que hagan falta."""
    p.c.create_oval(cx - r - 6, cy - r - 6, cx + r + 6, cy + r + 6, outline=T.ACENTO, width=p.a(2.2),
                    state="hidden", tags=(f"halo_{clave}",))
    p.c.create_oval(cx - r - 5, cy - r - 5, cx + r + 5, cy + r + 5, outline=T.ACENTO, width=p.a(2.4),
                    state="hidden", tags=(f"anillo_{clave}",))


def led(p: Pincel, clave: str, cx: float, cy: float, patas, tags=()):
    """LED visto desde arriba, todo con elementos del lienzo (sin Pillow). Los rellenos los pone `pintar_led`."""
    c, r = p.c, R_LED
    for k, extra in enumerate((EXTRA_LUZ, 22, 13, 6)):          # luz que se derrama sobre la protoboard
        e = r + extra
        c.create_oval(cx - e, cy - e, cx + e, cy + e, outline="", fill=BB_ARRIBA, state="hidden",
                      tags=tags + (f"luz_{clave}", f"luz_{clave}_{k}"))
    led_patas(p, cx, cy, patas, tags)
    c.create_oval(cx - r + 1.5, cy - r + 3, cx + r + 2.5, cy + r + 3.5, fill=T.mezclar(BB_ABAJO, "#000000", 0.2),
                  outline="", tags=tags)
    c.create_oval(cx - r - 1.8, cy - r - 1.8, cx + r + 1.8, cy + r + 1.8, outline="", fill="#cccccc",
                  tags=tags + (f"pestana_{clave}",))
    for k in range(CAPAS_DOMO):                                  # «degradado radial» hacia arriba a la izquierda
        rk = r * (1 - k * 0.17)
        d = (r - rk) * 0.45
        c.create_oval(cx - rk - d, cy - rk - d, cx + rk - d, cy + rk - d, outline="", fill="#dddddd",
                      tags=tags + (f"domo_{clave}_{k}",))
    c.create_oval(cx - 3.2, cy - 2.2, cx + 3.2, cy + 4.2, outline="", fill="#ffffff", state="hidden",
                  tags=tags + (f"nucleo_{clave}",))
    c.create_oval(cx - r * 0.62, cy - r * 0.68, cx - r * 0.12, cy - r * 0.22, outline="", fill="#ffffff",
                  tags=tags + (f"reflejo_{clave}",))
    c.create_oval(cx + r * 0.28, cy + r * 0.3, cx + r * 0.46, cy + r * 0.48, outline="", fill="#ffffff",
                  tags=tags + (f"reflejo2_{clave}",))
    marcas(p, clave, cx, cy, r)


def pintar_led(c, clave: str, base: str, b: float):
    """Colores del LED con brillo b (0-1): cúpula, núcleo encendido y luz sobre la protoboard."""
    apagado = T.mezclar("#d8d2c4", base, 0.42)
    lente = T.mezclar(apagado, base, b)
    oscuro = T.mezclar(lente, "#000000", 0.30 - 0.12 * b)
    claro = T.mezclar(lente, "#ffffff", 0.22 + 0.38 * b)
    c.itemconfigure(f"pestana_{clave}", fill=T.mezclar(lente, "#000000", 0.22))
    for k in range(CAPAS_DOMO):
        c.itemconfigure(f"domo_{clave}_{k}", fill=T.mezclar(oscuro, claro, k / (CAPAS_DOMO - 1)))
    c.itemconfigure(f"nucleo_{clave}", fill=T.mezclar(base, "#ffffff", 0.75), state="normal" if b > 0.05 else "hidden")
    c.itemconfigure(f"reflejo_{clave}", fill=T.mezclar(claro, "#ffffff", 0.7))
    c.itemconfigure(f"reflejo2_{clave}", fill=T.mezclar(claro, "#ffffff", 0.35))
    for k, f in enumerate((0.10, 0.18, 0.30, 0.46)):
        c.itemconfigure(f"luz_{clave}_{k}", fill=T.mezclar(BB_ARRIBA, base, f * b),
                        state="normal" if b > 0.02 else "hidden")


# ---------------------------------------------------------------- DHT11
def dht(p: Pincel, clave: str, xv, xd, xg, tags=()):
    """Sensor DHT11: carcasa azul con rejilla de ranuras, patas en tres columnas seguidas."""
    c = p.c
    x0, y0, x1, y1 = xv - 18, 84, xg + 18, 150
    for x in (xv, xd, xg):
        c.create_line(x, y1 - 4, x, FILAS_ABAJO[0], fill="#a7adb3", width=p.a(1.6), tags=tags)
        c.create_oval(x - 1.5, FILAS_ABAJO[0] - 1.5, x + 1.5, FILAS_ABAJO[0] + 1.5, fill="#6c737a", outline="",
                      tags=tags)
    sombra(p, x0, y0, x1, y1, 6, desp=(2, 3), capas=(0.06, 0.12), fondo=BB_ARRIBA)
    degradado_redondo(p, x0, y0, x1, y1, 6, "#63b3f6", "#1f6fc0", 14, "#155a9c", 1.3, tags=tags)
    c.create_line(x0 + 5, y0 + 1.8, x1 - 5, y0 + 1.8, fill="#b4dcfd", width=p.a(1.1), tags=tags)
    for k in range(4):
        for j in range(3):
            x, y = xv - 8 + j * 18, 95 + k * 13
            rect_redondo(c, x - 5, y - 3.4, x + 5, y + 3.4, 2.2, fill="#124f8d", outline="", tags=tags)
            c.create_line(x - 3.5, y + 3.6, x + 3.5, y + 3.6, fill="#7cc0f8", width=p.a(0.8), tags=tags)
    c.create_text(xd, 160, text="DHT11", fill="#6b6457", font=p.f(7, True), tags=tags)


def dht_marcas(p: Pincel, clave: str, xv, xg):
    """Halo y anillo del DHT11 (ocultos hasta que hagan falta)."""
    rect_redondo(p.c, xv - 25, 77, xg + 25, 168, 9, fill="", outline=T.ACENTO, width=p.a(2.2), state="hidden",
                 tags=(f"halo_{clave}",))
    rect_redondo(p.c, xv - 23, 79, xg + 23, 166, 8, fill="", outline=T.ACENTO, width=p.a(2.4), state="hidden",
                 tags=(f"anillo_{clave}",))
