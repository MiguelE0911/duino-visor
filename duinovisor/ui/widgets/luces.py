"""Luces virtuales que espejan al Arduino: LED suelto, chip de cada luz y semáforo 3D."""
from __future__ import annotations

from duinovisor.ui import tema as T
from duinovisor.ui.constantes import ORDEN_SEMAFORO
from duinovisor.ui.widgets.base import Lienzo, rect_redondo


def _resplandor(c, cx, cy, r, base, b, fondo, capas=((0.8, 0.10), (0.5, 0.18), (0.25, 0.32))):
    if b <= 0:
        return
    for extra, f in capas:
        e = r * extra
        c.create_oval(cx - r - e, cy - r - e, cx + r + e, cy + r + e, fill=T.mezclar(fondo, base, f * b), outline="")


class LedVirtual(Lienzo):
    """LED redondo que se enciende con el brillo recibido (0-255)."""

    def __init__(self, master, color, tamano=44, fondo=None):
        super().__init__(master, tamano, tamano, fondo)
        self.color = color
        self._brillo = -1
        self.poner(0)

    def poner(self, brillo):
        brillo = int(brillo)
        if brillo == self._brillo:
            return
        self._brillo = brillo
        self._dibujar()

    def _pintar(self):
        base, b = T.LED_BASE[self.color], max(0, self._brillo) / 255
        c, r = self.ancho / 2, self.ancho * 0.26
        _resplandor(self, c, c, r, base, b, self.fondo)
        apagado = T.mezclar(T.PISTA, base, 0.22)
        lente = T.mezclar(apagado, base, b)
        self.create_oval(c - r, c - r, c + r, c + r, fill=lente, outline=T.mezclar(apagado, base, 0.4 + 0.4 * b))
        s = r * 0.38
        self.create_oval(c - r * 0.55, c - r * 0.6, c - r * 0.55 + s, c - r * 0.6 + s,
                         fill=T.mezclar(lente, "#ffffff", 0.3 + 0.3 * b), outline="")


class Chip(Lienzo):
    """Tarjetita seleccionable de un LED: luz en miniatura, nombre y resumen («Parpadea»)."""

    def __init__(self, master, color, nombre, comando, ancho=172, alto=60, fuente="Helvetica", fondo=None):
        super().__init__(master, ancho, alto, fondo)
        self.color, self.nombre, self.comando, self._fuente = color, nombre, comando, fuente
        self.resumen, self.seleccionado, self._brillo, self._encima = "", False, 0, False
        self.configure(cursor="hand2")
        self.bind("<Enter>", lambda e: self._poner_encima(True))
        self.bind("<Leave>", lambda e: self._poner_encima(False))
        self.bind("<ButtonRelease-1>", lambda e: self.comando and self.comando())
        self._dibujar()

    def _poner_encima(self, si):
        self._encima = si
        self._dibujar()

    def configurar(self, resumen=None, seleccionado=None, brillo=None):
        cambio = False
        for nombre, valor in (("resumen", resumen), ("seleccionado", seleccionado), ("_brillo", brillo)):
            if valor is not None and getattr(self, nombre) != valor:
                setattr(self, nombre, valor)
                cambio = True
        if cambio:
            self._dibujar()

    def _pintar(self):
        sel = self.seleccionado
        relleno = T.ACENTO_SUAVE if sel else (T.SUPERFICIE_2 if self._encima else T.SUPERFICIE)
        borde = T.ACENTO if sel else T.BORDE
        rect_redondo(self, 1, 1, self.ancho - 1, self.alto - 1, 12, fill=relleno, outline=borde,
                     width=self.g(2 if sel else 1))
        base, b = T.LED_BASE[self.color], self._brillo / 255
        cx, cy, r = 28, self.alto / 2, 10
        _resplandor(self, cx, cy, r, base, b, relleno)
        apagado = T.mezclar(T.PISTA, base, 0.25)
        self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=T.mezclar(apagado, base, b),
                         outline=T.mezclar(apagado, base, 0.5))
        self.create_text(52, cy - 9, text=self.nombre, anchor="w", fill=T.TEXTO,
                         font=(self._fuente, T.TAM_CUERPO, "bold"))
        self.create_text(52, cy + 10, text=self.resumen, anchor="w", fill=T.TEXTO_2,
                         font=(self._fuente, T.TAM_PEQ))


class SemaforoVirtual(Lienzo):
    """Semáforo con aspecto 3D (carcasa, visera, lente con brillo). Espeja a los LEDs reales.

    Tiene una luz por LED, en `orden` (de arriba abajo; por defecto el de dominio/placa.py). Se dibuja en una
    geometría base de 112 de ancho y 76 de alto por luz (más el poste) y se amplía a `ancho`. Con `al_elegir`
    cada luz es un botón.
    """
    BASE_W = 112
    ALTO_LUZ, ALTO_EXTRA = 76, 34       # 3 luces: 112×262

    def __init__(self, master, ancho=112, fondo=None, al_elegir=None, orden=ORDEN_SEMAFORO):
        self.ORDEN = tuple(orden)
        self.BASE_H = self.ALTO_EXTRA + self.ALTO_LUZ * len(self.ORDEN)
        zoom = ancho / self.BASE_W
        super().__init__(master, ancho, self.BASE_H * zoom, fondo, zoom=zoom)
        self.al_elegir = al_elegir
        self._brillos = None
        self.seleccionado = None
        self._encima = None
        if al_elegir:
            self.bind("<Button-1>", self._clic)
            self.bind("<Motion>", self._mover)
            self.bind("<Leave>", lambda e: self._poner_encima(None))
        self.poner({})

    def redimensionar(self, ancho: float) -> None:
        """Nuevo ancho lógico (el alto sigue la proporción del semáforo)."""
        zoom = ancho / self.BASE_W
        if abs(zoom - self.zoom) < 0.02:
            return
        self.zoom = zoom
        self.configure(width=round(ancho * self.S), height=round(self.BASE_H * zoom * self.S))
        self._dibujar()

    def _centro(self, i):
        paso = (self.alto - self.ALTO_EXTRA) / len(self.ORDEN)
        return self.ancho / 2, 4 + paso * (i + 0.5) + 2

    def _luz_en(self, e):
        x, y = self._xy(e)
        for i, color in enumerate(self.ORDEN):
            cx, cy = self._centro(i)
            if (x - cx) ** 2 + (y - cy) ** 2 <= 32 ** 2:
                return color
        return None

    def _poner_encima(self, color):
        if color != self._encima:
            self._encima = color
            self.configure(cursor="hand2" if color else "")
            self._dibujar()

    def _mover(self, e):
        self._poner_encima(self._luz_en(e))

    def _clic(self, e):
        color = self._luz_en(e)
        if color and self.al_elegir:
            self.al_elegir(color)

    def seleccionar(self, color):
        if color != self.seleccionado:
            self.seleccionado = color
            self._dibujar()

    def poner(self, brillos):
        clave = tuple(int(brillos.get(c, 0)) for c in self.ORDEN)
        if clave == self._brillos:
            return
        self._brillos = clave
        self._dibujar()

    def _pintar(self):
        w, h = self.ancho, self.alto
        cx = w / 2
        z = self.zoom
        self.create_rectangle(cx - 6, h - 28, cx + 6, h, fill="#1d1d1f", outline="#2b2b2e")          # poste
        self.create_rectangle(cx - 22, h - 6, cx + 22, h - 1, fill="#1d1d1f", outline="#2b2b2e")
        rect_redondo(self, 12, 4, w - 12, h - 26, 18, fill="#121214", outline="#34343a", width=max(1, 2 * z))
        self.create_line(18, 24, 18, h - 46, fill="#2c2c30", width=max(1, 2 * z))                    # bisel (luz)
        self.create_line(w - 18, 24, w - 18, h - 46, fill="#050505", width=max(1, 3 * z))            # bisel (sombra)
        radio = 24
        for i, color in enumerate(self.ORDEN):
            b = self._brillos[i] / 255
            _, y = self._centro(i)
            base = T.LED_BASE[color]
            if b > 0:
                for extra, f in ((16, 0.08), (11, 0.16), (6, 0.30)):
                    self.create_oval(cx - radio - extra, y - radio - extra, cx + radio + extra, y + radio + extra,
                                     fill=T.mezclar("#121214", base, f * b), outline="")
            self.create_oval(cx - radio - 3, y - radio - 3, cx + radio + 3, y + radio + 3, fill="#050505", outline="#26262a")
            lente = T.mezclar(T.mezclar("#17171a", base, 0.18), base, b)
            self.create_oval(cx - radio, y - radio, cx + radio, y + radio, fill=lente, outline="")
            self.create_oval(cx - radio * 0.66, y - radio * 0.62, cx + radio * 0.52, y + radio * 0.56,
                             fill=T.mezclar(lente, "#ffffff", 0.07 + 0.16 * b), outline="")
            self.create_oval(cx - radio * 0.62, y - radio * 0.70, cx - radio * 0.14, y - radio * 0.36,
                             fill=T.mezclar(lente, "#ffffff", 0.22 + 0.38 * b), outline="")
            self.create_arc(cx - radio - 6, y - radio - 12, cx + radio + 6, y - radio + 14, start=0, extent=180,
                            style="chord", fill="#070708", outline="#1d1d20")                          # visera
            if color == self.seleccionado or color == self._encima:
                anillo = T.ACENTO if color == self.seleccionado else "#6b6b73"
                self.create_oval(cx - radio - 7, y - radio - 7, cx + radio + 7, y + radio + 7, outline=anillo,
                                 width=max(1, 2.5 * z * self.S))
