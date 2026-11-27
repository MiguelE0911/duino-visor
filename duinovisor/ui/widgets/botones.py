"""Botones: píldora, icono, selector segmentado y muestra de color."""
from __future__ import annotations

import math

from duinovisor.ui import tema as T
from duinovisor.ui.widgets.base import Lienzo, medir, rect_redondo


class BotonPildora(Lienzo):
    """Botón redondeado. Estilos: relleno (principal), suave (acento tenue), fantasma (borde) y texto."""

    def __init__(self, master, texto, comando, ancho=None, alto=36, estilo="relleno",
                 fuente="Helvetica", fondo=None, tam=None):
        self._fuente, self._tam = fuente, tam or T.TAM_CUERPO
        if ancho is None:
            ancho = medir(texto, fuente, self._tam, negrita=True) + 36
        super().__init__(master, ancho, alto, fondo)
        self.texto, self.comando, self.estilo = texto, comando, estilo
        self._encima = False
        self.configure(cursor="hand2")
        self.bind("<Enter>", lambda e: self._poner_encima(True))
        self.bind("<Leave>", lambda e: self._poner_encima(False))
        self.bind("<ButtonRelease-1>", self._soltar)
        self._dibujar()

    def configurar(self, texto=None, habilitado=None, estilo=None):
        if texto is not None:
            self.texto = texto
        if estilo is not None:
            self.estilo = estilo
        if habilitado is not None:
            self._habilitado = bool(habilitado)
        self._dibujar()

    def _poner_encima(self, si):
        self._encima = si
        self._dibujar()

    def _soltar(self, e):
        x, y = self._xy(e)
        if self._habilitado and self.comando and 0 <= x <= self.ancho and 0 <= y <= self.alto:
            self.comando()

    def _pintar(self):
        h = self._encima
        if not self._habilitado:
            relleno, texto, borde = T.SUPERFICIE_2, T.TEXTO_3, T.SUPERFICIE_2
        elif self.estilo == "relleno":
            relleno, texto, borde = (T.ACENTO_HOVER if h else T.ACENTO), T.SOBRE_ACENTO, (T.ACENTO_HOVER if h else T.ACENTO)
        elif self.estilo == "suave":
            relleno = T.mezclar(T.ACENTO_SUAVE, T.ACENTO, 0.12) if h else T.ACENTO_SUAVE
            texto, borde = T.ACENTO, relleno
        elif self.estilo == "texto":
            relleno = T.SUPERFICIE_2 if h else self.fondo
            texto, borde = T.TEXTO_2, relleno
        else:
            relleno, texto, borde = (T.SUPERFICIE_2 if h else self.fondo), T.TEXTO, T.BORDE
        rect_redondo(self, 1, 1, self.ancho - 1, self.alto - 1, self.alto / 2, fill=relleno, outline=borde)
        negrita = self.estilo in ("relleno", "suave")
        self.create_text(self.ancho / 2, self.alto / 2, text=self.texto, fill=texto,
                         font=(self._fuente, self._tam, "bold" if negrita else "normal"))


class BotonIcono(Lienzo):
    """Botón redondo con un icono dibujado: menu, sol, luna, refrescar, power o cerrar."""

    def __init__(self, master, icono, comando=None, diametro=36, fondo=None, borde=True):
        super().__init__(master, diametro, diametro, fondo)
        self.icono, self.comando, self._borde = icono, comando, borde
        self._encima = False
        self.activo = False
        self.configure(cursor="hand2")
        self.bind("<Enter>", lambda e: self._poner_encima(True))
        self.bind("<Leave>", lambda e: self._poner_encima(False))
        self.bind("<ButtonRelease-1>", self._soltar)
        self._dibujar()

    def configurar(self, icono=None, activo=None):
        if icono is not None:
            self.icono = icono
        if activo is not None:
            self.activo = activo
        self._dibujar()

    def _poner_encima(self, si):
        self._encima = si
        self._dibujar()

    def _soltar(self, e):
        x, y = self._xy(e)
        if self.comando and 0 <= x <= self.ancho and 0 <= y <= self.alto:
            self.comando()

    def _pintar(self):
        d, c = self.ancho, self.ancho / 2
        fondo = T.ACENTO_SUAVE if self.activo else (T.SUPERFICIE_2 if self._encima else self.fondo)
        borde = T.ACENTO if self.activo else (T.BORDE if self._borde else fondo)
        trazo = T.ACENTO if self.activo else T.TEXTO_2
        self.create_oval(1, 1, d - 1, d - 1, fill=fondo, outline=borde)
        g = self.g(2)
        if self.icono == "menu":
            for k in (-1, 0, 1):
                x = c + k * d * 0.18
                self.create_oval(x - 2, c - 2, x + 2, c + 2, fill=trazo, outline=trazo)
        elif self.icono == "sol":
            r = d * 0.13
            self.create_oval(c - r, c - r, c + r, c + r, outline=trazo, width=g)
            for k in range(8):
                a = math.radians(k * 45)
                self.create_line(c + math.cos(a) * d * 0.21, c + math.sin(a) * d * 0.21,
                                 c + math.cos(a) * d * 0.29, c + math.sin(a) * d * 0.29, fill=trazo, width=g,
                                 capstyle="round")
        elif self.icono == "luna":
            r = d * 0.24
            self.create_oval(c - r, c - r, c + r, c + r, fill=trazo, outline="")
            self.create_oval(c - r + d * 0.13, c - r - d * 0.06, c + r + d * 0.13, c + r - d * 0.06,
                             fill=fondo, outline="")
        elif self.icono == "refrescar":
            r = d * 0.22
            self.create_arc(c - r, c - r, c + r, c + r, start=100, extent=290, style="arc", outline=trazo, width=g)
            ang = math.radians(100 + 290)
            px, py = c + r * math.cos(ang), c - r * math.sin(ang)
            tx, ty = -math.sin(ang), -math.cos(ang)
            nx, ny = math.cos(ang), -math.sin(ang)
            s = d * 0.1
            self.create_polygon(px + tx * s * 1.7, py + ty * s * 1.7, px + nx * s, py + ny * s,
                                px - nx * s, py - ny * s, fill=trazo, outline=trazo)
        elif self.icono == "cerrar":
            r = d * 0.18
            self.create_line(c - r, c - r, c + r, c + r, fill=trazo, width=g, capstyle="round")
            self.create_line(c - r, c + r, c + r, c - r, fill=trazo, width=g, capstyle="round")


class Segmentado(Lienzo):
    """Selector ligado a una StringVar.

    estilo="pildoras": una píldora por opción (la elegida en color de acento).
    estilo="pista": control segmentado sobre una pista gris (para pestañas y conmutadores de vista).
    """

    def __init__(self, master, variable, opciones, ancho=240, columnas=2, alto_fila=34, hueco=8,
                 fuente="Helvetica", fondo=None, estilo="pildoras", tam=None):
        filas = math.ceil(len(opciones) / columnas)
        if estilo == "pista":
            hueco = 0
        super().__init__(master, ancho, filas * alto_fila + (filas - 1) * hueco, fondo)
        self.variable, self.opciones, self.columnas = variable, opciones, columnas
        self.alto_fila, self.hueco, self._fuente, self.estilo = alto_fila, hueco, fuente, estilo
        self._tam = tam or T.TAM_CUERPO
        self._encima = None
        self.configure(cursor="hand2")
        self.bind("<Button-1>", self._clic)
        self.bind("<Motion>", self._mover)
        self.bind("<Leave>", lambda e: self._poner_encima(None))
        self._vigilar(variable, self._dibujar)
        self._dibujar()

    def _celda(self, i):
        col, fila = i % self.columnas, i // self.columnas
        w = (self.ancho - (self.columnas - 1) * self.hueco) / self.columnas
        x0, y0 = col * (w + self.hueco), fila * (self.alto_fila + self.hueco)
        return x0, y0, x0 + w, y0 + self.alto_fila

    def _indice(self, e):
        x, y = self._xy(e)
        for i in range(len(self.opciones)):
            x0, y0, x1, y1 = self._celda(i)
            if x0 <= x <= x1 and y0 <= y <= y1:
                return i
        return None

    def _poner_encima(self, i):
        if i != self._encima:
            self._encima = i
            self._dibujar()

    def _mover(self, e):
        self._poner_encima(self._indice(e))

    def _clic(self, e):
        i = self._indice(e)
        if self._habilitado and i is not None:
            self.variable.set(self.opciones[i][0])

    def _pintar(self):
        if self.estilo == "pista":
            rect_redondo(self, 0, 0, self.ancho, self.alto, 10, fill=T.SUPERFICIE_2, outline=T.SUPERFICIE_2)
        for i, (valor, texto) in enumerate(self.opciones):
            x0, y0, x1, y1 = self._celda(i)
            sel = self.variable.get() == valor
            encima = self._encima == i and self._habilitado
            negrita = sel
            if self.estilo == "pista":
                if sel:
                    rect_redondo(self, x0 + 3, y0 + 3, x1 - 3, y1 - 3, 8, fill=T.SUPERFICIE, outline=T.BORDE)
                color = (T.TEXTO if sel or encima else T.TEXTO_2) if self._habilitado else T.TEXTO_3
            else:
                if not self._habilitado:
                    relleno, borde, color = (T.PISTA if sel else T.SUPERFICIE_2), T.SUPERFICIE_2, T.TEXTO_3
                elif sel:
                    relleno, borde, color = T.ACENTO, T.ACENTO, T.SOBRE_ACENTO
                else:
                    relleno = T.mezclar(T.SUPERFICIE_2, T.PISTA, 0.6) if encima else T.SUPERFICIE_2
                    borde, color = relleno, T.TEXTO
                rect_redondo(self, x0 + 1, y0 + 1, x1 - 1, y1 - 1, 10, fill=relleno, outline=borde)
            self.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=texto, fill=color,
                             font=(self._fuente, self._tam, "bold" if negrita else "normal"))


class MuestraColor(Lienzo):
    """Círculo de color para elegir el acento; el elegido lleva un aro."""

    def __init__(self, master, color, comando, seleccionado=False, diametro=38, fondo=None):
        super().__init__(master, diametro, diametro, fondo)
        self.color, self.comando, self.seleccionado = color, comando, seleccionado
        self.configure(cursor="hand2")
        self.bind("<ButtonRelease-1>", lambda e: self.comando and self.comando())
        self._dibujar()

    def _pintar(self):
        d = self.ancho
        if self.seleccionado:
            self.create_oval(1, 1, d - 1, d - 1, outline=T.TEXTO, width=self.g(2))
        self.create_oval(6, 6, d - 6, d - 6, fill=self.color, outline="")
