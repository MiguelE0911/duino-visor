"""Pintar con Pillow lo que no se mueve de la vista protoboard (y los LEDs, como «sprites»).

Tk repinta de una vez el rectángulo que abarca todo lo que cambió, y con ~2000 elementos vectoriales eso cuesta
~50 ms: más que un fotograma. Por eso la placa, la protoboard, los cables y las resistencias se pintan en una sola
imagen (repintarla cuesta ~5 ms) y en el lienzo solo quedan como elementos lo que cambia.

`LienzoImagen` imita la parte de la API de `tk.Canvas` que usa `dibujo_placa` (create_line, create_oval,
create_rectangle, create_polygon, create_text y los rectángulos redondeados), así las mismas funciones dibujan
en el lienzo de Tk (sin Pillow) o en la imagen. Se pinta al doble de tamaño y se reduce: queda con antialiasing.

Pillow es opcional: si no está, `disponible()` es False y la protoboard se dibuja como antes.
"""
from __future__ import annotations

import math
import sys
from functools import lru_cache

try:                                     # Pillow es opcional
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:                      # pragma: no cover - depende de la instalación
    Image = None

from duinovisor.ui import tema as T

SUPERMUESTREO = 2


def disponible() -> bool:
    if Image is None:
        return False
    try:
        from PIL import ImageTk  # noqa: F401
        return True
    except ImportError:          # pragma: no cover
        return False


def foto(imagen):
    """PhotoImage de Tk para una imagen de Pillow."""
    from PIL import ImageTk
    return ImageTk.PhotoImage(imagen)


# ---------------------------------------------------------------- letras
_ARCHIVOS = {
    "win32": (("segoeui.ttf", "segoeuib.ttf"), ("arial.ttf", "arialbd.ttf")),
    "darwin": (("/System/Library/Fonts/SFNS.ttf", "/System/Library/Fonts/SFNS.ttf"),
               ("/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Helvetica.ttc")),
}
_LINUX = (("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"), ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                                                       "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))


@lru_cache(maxsize=64)
def fuente(px: int, negrita: bool):
    for normal, gruesa in _ARCHIVOS.get(sys.platform, _LINUX):
        try:
            return ImageFont.truetype(gruesa if negrita else normal, max(4, px))
        except OSError:
            continue
    try:
        return ImageFont.load_default(max(4, px))
    except TypeError:                     # Pillow antiguo: sin tamaño
        return ImageFont.load_default()


_ANCLAS = {"center": "mm", "n": "mt", "s": "mb", "e": "rm", "w": "lm", "ne": "rt", "nw": "lt", "se": "rb", "sw": "lb"}


def _plano(args):
    """Coordenadas en una lista plana, vengan sueltas, en tuplas o en una lista."""
    salida = []
    for a in args:
        if isinstance(a, (list, tuple)):
            salida.extend(_plano(a))
        else:
            salida.append(float(a))
    return salida


def _rgba(color, alfa=255):
    if not color:
        return None
    r, g, b = T.hex_a_rgb(color)
    return (r, g, b, alfa)


class LienzoImagen:
    """Una imagen RGBA que se dibuja como un Canvas: coordenadas virtuales × `z` + `origen` (en píxeles)."""

    def __init__(self, ancho: int, alto: int, z: float, origen, escala_letra: float, fondo=None):
        self.ss = SUPERMUESTREO
        self.z, self.ox, self.oy = z, origen[0], origen[1]
        self.escala_letra = escala_letra
        self.ancho, self.alto = max(1, int(ancho)), max(1, int(alto))
        self.img = Image.new("RGBA", (self.ancho * self.ss, self.alto * self.ss), _rgba(fondo) or (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)
        self._textos = []          # las letras se escriben al final, ya reducida la imagen (FreeType las suaviza)

    # ------------------------------------------------------------ conversión
    def _x(self, x):
        return (x * self.z + self.ox) * self.ss

    def _y(self, y):
        return (y * self.z + self.oy) * self.ss

    def _puntos(self, args):
        v = _plano(args)
        return [(self._x(v[i]), self._y(v[i + 1])) for i in range(0, len(v) - 1, 2)]

    def _g(self, ancho):
        """Grosor (ya en píxeles de pantalla, como lo da Pincel.a) al tamaño de la imagen."""
        return max(1, round(float(ancho) * self.ss))

    # ------------------------------------------------------------ API tipo Canvas
    def create_rectangle(self, *coords, fill="", outline="", width=1, state="normal", **_):
        if state == "hidden":
            return
        (x0, y0), (x1, y1) = self._puntos(coords)
        caja = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        self.d.rectangle(caja, fill=_rgba(fill), outline=_rgba(outline), width=self._g(width) if outline else 0)

    def create_oval(self, *coords, fill="", outline="", width=1, state="normal", **_):
        if state == "hidden":
            return
        (x0, y0), (x1, y1) = self._puntos(coords)
        caja = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        self.d.ellipse(caja, fill=_rgba(fill), outline=_rgba(outline), width=self._g(width) if outline else 0)

    def create_line(self, *coords, fill="#000000", width=1, capstyle="butt", state="normal", **_):
        if state == "hidden" or not fill:
            return
        pts = self._puntos(coords)
        g = self._g(width)
        color = _rgba(fill)
        self.d.line(pts, fill=color, width=g, joint="curve" if len(pts) > 2 else None)
        if capstyle == "round" and g > 2:
            r = g / 2
            for x, y in (pts[0], pts[-1]):
                self.d.ellipse((x - r, y - r, x + r, y + r), fill=color)

    def create_polygon(self, *coords, fill="", outline="", width=1, smooth=False, state="normal", **_):
        if state == "hidden":
            return
        pts = self._puntos(coords)
        if smooth:
            from duinovisor.ui.widgets.geometria import curva_cerrada
            pts = curva_cerrada(pts, 6)
        self.d.polygon(pts, fill=_rgba(fill), outline=_rgba(outline), width=self._g(width) if outline else 1)

    def redondo(self, x0, y0, x1, y1, r, fill="", outline="", width=1, state="normal", **_):
        """Rectángulo redondeado nativo (lo usa base.rect_redondo)."""
        if state == "hidden":
            return
        caja = (self._x(min(x0, x1)), self._y(min(y0, y1)), self._x(max(x0, x1)), self._y(max(y0, y1)))
        radio = max(0, min(r * self.z * self.ss, (caja[2] - caja[0]) / 2, (caja[3] - caja[1]) / 2))
        self.d.rounded_rectangle(caja, radio, fill=_rgba(fill), outline=_rgba(outline),
                                 width=self._g(width) if outline else 0)

    def create_text(self, x, y, text="", fill="#000000", font=None, anchor="center", angle=0, state="normal", **_):
        if state == "hidden" or not text:
            return
        self._textos.append((x * self.z + self.ox, y * self.z + self.oy, text, fill, font, anchor, angle))

    def _escribir(self, img, d, x, y, text, fill, font, anchor, angle):
        """Escribe un texto en la imagen final (x, y en píxeles de pantalla)."""
        tam = font[1] if font else 9
        negrita = bool(font and len(font) > 2 and "bold" in font[2])
        px = round(tam * 4 / 3 * self.escala_letra)                 # puntos -> píxeles, como hace Tk
        letra = fuente(px, negrita)
        ancla = _ANCLAS.get(anchor, "mm")
        if not angle:
            d.text((x, y), text, fill=_rgba(fill), font=letra, anchor=ancla)
            return
        # texto girado: se pinta aparte y se pega rotado con su ancla en su sitio
        caja = d.textbbox((0, 0), text, font=letra, anchor="lt")
        w, h = caja[2] - caja[0] + 4, caja[3] - caja[1] + 4
        capa = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(capa).text((2 - caja[0], 2 - caja[1]), text, fill=_rgba(fill), font=letra, anchor="lt")
        ax = {"l": 0, "m": w / 2, "r": w}[ancla[0]]
        ay = {"t": 0, "m": h / 2, "b": h, "s": h}.get(ancla[1], h / 2)
        girada = capa.rotate(angle, expand=True)
        a = math.radians(angle)
        cx, cy = ax - w / 2, ay - h / 2                                 # ancla respecto al centro
        rx, ry = cx * math.cos(a) + cy * math.sin(a), -cx * math.sin(a) + cy * math.cos(a)
        destino = (round(x - (girada.width / 2 + rx)), round(y - (girada.height / 2 + ry)))
        if 0 <= destino[0] < img.width and 0 <= destino[1] < img.height:
            img.alpha_composite(girada, destino)
        else:
            img.paste(girada, destino, girada)

    # ------------------------------------------------------------ resultado
    def imagen(self):
        """La imagen al tamaño de pantalla: reducida (con antialiasing) y con sus letras."""
        img = self.img.reduce(self.ss) if self.ss > 1 else self.img
        d = ImageDraw.Draw(img)
        for texto in self._textos:
            self._escribir(img, d, *texto)
        return img


# ---------------------------------------------------------------- fondo de mesa
def mesa(ancho: int, alto: int, color: str, punto: str, paso: float, radio: float):
    """Fondo de la mesa de trabajo con su rejilla de puntos."""
    img = Image.new("RGB", (max(1, int(ancho)), max(1, int(alto))), color)
    d = ImageDraw.Draw(img)
    p = _rgba(punto)[:3]
    y = paso / 2
    while y < alto:
        x = paso / 2
        while x < ancho:
            d.ellipse((x - radio, y - radio, x + radio, y + radio), fill=p)
            x += paso
        y += paso
    return img


# ---------------------------------------------------------------- LED encendido / apagado
def sprite_led(base: str, b: float, z: float, r_led: float, extra: float):
    """LED visto desde arriba con su resplandor (alfa real y desenfoque). Devuelve (imagen, mitad del lado)."""
    ss = SUPERMUESTREO
    radio_total = (r_led + extra) * z
    lado = max(8, int(math.ceil(radio_total * 2 * ss)))
    c = lado / 2
    k = z * ss                                                    # unidades virtuales -> píxeles de la imagen
    img = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    color = T.hex_a_rgb(base)
    if b > 0.02:                                                  # resplandor sobre la protoboard
        # Es difuso: se desenfoca a 1/4 de resolución y se amplía (mucho más rápido y no se nota).
        q = 4
        chico = max(4, lado // q)
        halo = Image.new("RGBA", (chico, chico), color + (0,))
        dh = ImageDraw.Draw(halo)
        cc, kk = chico / 2, k / q * chico / (lado / q)
        for radio, alfa in (((r_led + extra * 0.62) * kk, 0.40), ((r_led + extra * 0.28) * kk, 0.55)):
            dh.ellipse((cc - radio, cc - radio, cc + radio, cc + radio), fill=color + (int(255 * alfa * b),))
        halo = halo.filter(ImageFilter.GaussianBlur(max(0.5, extra * 0.28 * kk)))
        img.alpha_composite(halo.resize((lado, lado), Image.BILINEAR))
    d = ImageDraw.Draw(img)
    r = r_led * k
    apagado = T.mezclar("#d8d2c4", base, 0.42)
    lente = T.mezclar(apagado, base, b)
    oscuro = T.mezclar(lente, "#000000", 0.30 - 0.12 * b)
    claro = T.mezclar(lente, "#ffffff", 0.22 + 0.38 * b)
    sombra = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).ellipse((c - r + 1.5 * k, c - r + 3 * k, c + r + 2.5 * k, c + r + 3.5 * k),
                                   fill=(0, 0, 0, 70))
    img.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(1.6 * k)))
    rp = r + 1.8 * k
    d.ellipse((c - rp, c - rp, c + rp, c + rp), fill=_rgba(T.mezclar(lente, "#000000", 0.22)))
    capas = 10                                                    # «degradado radial» hacia arriba a la izquierda
    for i in range(capas):
        rk = r * (1 - i * 0.085)
        dd = (r - rk) * 0.45
        d.ellipse((c - rk - dd, c - rk - dd, c + rk - dd, c + rk - dd),
                  fill=_rgba(T.mezclar(oscuro, claro, i / (capas - 1))))
    if b > 0.05:
        nucleo = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
        ImageDraw.Draw(nucleo).ellipse((c - 3.6 * k, c - 2.6 * k, c + 3.6 * k, c + 4.6 * k),
                                       fill=_rgba(T.mezclar(base, "#ffffff", 0.8), int(255 * min(1, b * 1.2))))
        img.alpha_composite(nucleo.filter(ImageFilter.GaussianBlur(1.2 * k)))
    d = ImageDraw.Draw(img)
    d.ellipse((c - r * 0.62, c - r * 0.68, c - r * 0.12, c - r * 0.22), fill=(255, 255, 255, 200))
    d.ellipse((c + r * 0.28, c + r * 0.3, c + r * 0.46, c + r * 0.48), fill=(255, 255, 255, 110))
    return img.reduce(ss), lado / ss / 2


def resplandor_ruta(ruta_pantalla, color: str, ancho: float):
    """Imagen con un brillo difuso a lo largo de un recorrido (en píxeles de pantalla). Devuelve (imagen, x0, y0)."""
    margen = ancho * 2 + 4
    xs, ys = [p[0] for p in ruta_pantalla], [p[1] for p in ruta_pantalla]
    x0, y0 = min(xs) - margen, min(ys) - margen
    w, h = int(max(xs) - x0 + margen) + 1, int(max(ys) - y0 + margen) + 1
    img = Image.new("RGBA", (w, h), _rgba(color, 0))
    d = ImageDraw.Draw(img)
    pts = [(x - x0, y - y0) for x, y in ruta_pantalla]
    d.line(pts, fill=_rgba(color, 170), width=max(2, int(ancho)), joint="curve")
    for x, y in (pts[0], pts[-1]):
        r = ancho / 2
        d.ellipse((x - r, y - r, x + r, y + r), fill=_rgba(color, 170))
    return img.filter(ImageFilter.GaussianBlur(max(1.0, ancho * 0.35))), x0, y0
