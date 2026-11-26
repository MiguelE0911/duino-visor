"""Widgets propios de DuinoVisor, dibujados sobre Canvas (solo Tkinter, sin dependencias)."""
from __future__ import annotations

import math
import tkinter as tk

import tema as T


def rect_redondo(c, x0, y0, x1, y1, r, **kw):
    r = max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1,
           x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
    return c.create_polygon(pts, smooth=True, **kw)


def entrada(master, variable, ancho=7, fuente="Helvetica", fondo=T.TARJETA):
    return tk.Entry(master, textvariable=variable, width=ancho, bg=T.TARJETA_2, fg=T.TEXTO,
                    insertbackground=T.AMBAR, relief="flat", highlightthickness=1,
                    highlightbackground=T.BORDE, highlightcolor=T.AMBAR, font=(fuente, 10),
                    justify="center", disabledbackground=fondo, disabledforeground=T.TEXTO_3)


def etiqueta(master, texto="", fuente="Helvetica", tam=10, color=T.TEXTO_2, fondo=T.TARJETA,
             negrita=False, **kw):
    return tk.Label(master, text=texto, bg=fondo, fg=color,
                    font=(fuente, tam, "bold") if negrita else (fuente, tam), **kw)


class _Lienzo(tk.Canvas):
    def __init__(self, master, ancho, alto, fondo):
        super().__init__(master, width=ancho, height=alto, bg=fondo, highlightthickness=0, bd=0)
        self.ancho, self.alto, self.fondo = ancho, alto, fondo
        self._habilitado = True

    def habilitar(self, si: bool) -> None:
        self._habilitado = bool(si)
        self._dibujar()

    def _dibujar(self) -> None:           # lo redefine cada widget
        pass


class Tarjeta(tk.Canvas):
    """Panel de esquinas redondas con título. El contenido va en `.contenido` (usar grid)."""
    PAD = 14

    def __init__(self, master, titulo="", fuente="Helvetica", radio=18, color=T.TARJETA, fondo=T.FONDO):
        super().__init__(master, bg=fondo, highlightthickness=0, bd=0, height=60, width=120)
        self._radio, self._color = radio, color
        self.cuerpo = tk.Frame(self, bg=color)
        self._ventana = self.create_window(self.PAD, self.PAD, anchor="nw", window=self.cuerpo)
        cabecera = tk.Frame(self.cuerpo, bg=color)
        cabecera.pack(fill="x")
        self.titulo = tk.Label(cabecera, text=titulo, bg=color, fg=T.TEXTO_2, font=(fuente, 10), anchor="w")
        self.titulo.pack(side="left")
        self.extra = tk.Frame(cabecera, bg=color)
        self.extra.pack(side="right")
        self.contenido = tk.Frame(self.cuerpo, bg=color)
        self.contenido.pack(fill="both", expand=True, pady=(8, 0))
        self.bind("<Configure>", self._al_cambiar_tamano)
        self.cuerpo.bind("<Configure>", self._al_cambiar_cuerpo)

    def _al_cambiar_tamano(self, e):
        self.delete("fondo")
        rect_redondo(self, 1, 1, e.width - 1, e.height - 1, self._radio, fill=self._color,
                     outline=T.BORDE, tags="fondo")
        self.tag_lower("fondo")
        self.itemconfigure(self._ventana, width=max(10, e.width - 2 * self.PAD))

    def _al_cambiar_cuerpo(self, e):
        self.configure(height=e.height + 2 * self.PAD)


class BotonPildora(_Lienzo):
    def __init__(self, master, texto, comando, ancho=110, alto=34, estilo="relleno",
                 fuente="Helvetica", fondo=T.FONDO):
        super().__init__(master, ancho, alto, fondo)
        self.texto, self.comando, self.estilo, self._fuente = texto, comando, estilo, fuente
        self._encima = False
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
        if self._habilitado and self.comando and 0 <= e.x <= self.ancho and 0 <= e.y <= self.alto:
            self.comando()

    def _dibujar(self):
        self.delete("all")
        if not self._habilitado:
            relleno, texto, borde = T.TARJETA_2, T.TEXTO_3, T.BORDE
        elif self.estilo == "relleno":
            relleno, texto, borde = (T.AMBAR_CLARO if self._encima else T.AMBAR), T.SOBRE_AMBAR, T.AMBAR
        else:
            relleno, texto, borde = (T.PISTA if self._encima else T.TARJETA_2), T.TEXTO, T.BORDE
        rect_redondo(self, 1, 1, self.ancho - 1, self.alto - 1, self.alto / 2, fill=relleno, outline=borde)
        self.create_text(self.ancho / 2, self.alto / 2, text=self.texto, fill=texto,
                         font=(self._fuente, 10, "bold" if self.estilo == "relleno" else "normal"))


class BotonRedondo(_Lienzo):
    """Botón circular con un icono dibujado (refrescar, power, check o logo)."""

    def __init__(self, master, icono, comando=None, diametro=40, relleno=False, fuente="Helvetica",
                 fondo=T.BARRA):
        super().__init__(master, diametro, diametro, fondo)
        self.icono, self.comando, self.relleno, self._fuente = icono, comando, relleno, fuente
        self._encima = False
        self.activo = False
        self.bind("<Enter>", lambda e: self._poner_encima(True))
        self.bind("<Leave>", lambda e: self._poner_encima(False))
        self.bind("<ButtonRelease-1>", self._soltar)
        self._dibujar()

    def configurar(self, relleno=None, activo=None):
        if relleno is not None:
            self.relleno = relleno
        if activo is not None:
            self.activo = activo
        self._dibujar()

    def _poner_encima(self, si):
        self._encima = si and self.comando is not None
        self._dibujar()

    def _soltar(self, e):
        if self.comando and 0 <= e.x <= self.ancho and 0 <= e.y <= self.alto:
            self.comando()

    def _dibujar(self):
        self.delete("all")
        d, c = self.ancho, self.ancho / 2
        if self.relleno:
            fondo, trazo, borde = (T.AMBAR_CLARO if self._encima else T.AMBAR), T.SOBRE_AMBAR, T.AMBAR
        else:
            fondo, trazo, borde = (T.PISTA if self._encima else T.TARJETA_2), T.AMBAR, T.mezclar(T.TARJETA_2, T.AMBAR, 0.35)
        if self.activo and not self.relleno:
            fondo, borde = T.TARJETA, T.AMBAR
        self.create_oval(1, 1, d - 1, d - 1, fill=fondo, outline=borde, width=2 if self.activo else 1)
        r = d * 0.24
        if self.icono == "power":
            self.create_arc(c - r, c - r + 1, c + r, c + r + 1, start=120, extent=300, style="arc", outline=trazo, width=3)
            self.create_line(c, c - r - 2, c, c - 1, fill=trazo, width=3, capstyle="round")
        elif self.icono == "refrescar":
            r = d * 0.26
            self.create_arc(c - r, c - r, c + r, c + r, start=100, extent=290, style="arc", outline=trazo, width=3)
            ang = math.radians(100 + 290)                      # extremo del arco (el arco gira en sentido antihorario)
            px, py = c + r * math.cos(ang), c - r * math.sin(ang)
            tx, ty = -math.sin(ang), -math.cos(ang)            # hacia donde sigue girando
            nx, ny = math.cos(ang), -math.sin(ang)
            s = d * 0.12
            self.create_polygon(px + tx * s * 1.7, py + ty * s * 1.7, px + nx * s, py + ny * s,
                                px - nx * s, py - ny * s, fill=trazo, outline=trazo)
        elif self.icono == "semaforo":
            w, h = d * 0.18, d * 0.31
            self.create_rectangle(c - w, c - h, c + w, c + h, outline=trazo, width=3)
            rl = d * 0.065
            for k in (-1, 0, 1):
                y = c + k * h * 0.56
                self.create_oval(c - rl, y - rl, c + rl, y + rl, fill=trazo, outline=trazo)
        elif self.icono == "clima":
            x0, x1 = c - d * 0.15, c + d * 0.15                  # termómetro a la izquierda, gota a la derecha
            self.create_line(x0, c - d * 0.26, x0, c + d * 0.06, fill=trazo, width=3, capstyle="round")
            self.create_oval(x0 - d * 0.09, c + d * 0.04, x0 + d * 0.09, c + d * 0.24, fill=trazo, outline=trazo)
            rg = d * 0.11
            self.create_polygon(x1, c - d * 0.24, x1 - rg * 0.95, c + d * 0.02, x1 + rg * 0.95, c + d * 0.02,
                                fill=trazo, outline=trazo)
            self.create_oval(x1 - rg, c + d * 0.02 - rg * 0.6, x1 + rg, c + d * 0.02 + rg * 1.7,
                             fill=trazo, outline=trazo)
        elif self.icono == "check":
            self.create_line(c - r, c, c - r / 3, c + r * 0.7, c + r, c - r * 0.7, fill=trazo, width=3,
                             capstyle="round", joinstyle="round")
        else:
            self.create_text(c, c, text=self.icono, fill=trazo, font=(self._fuente, int(d * 0.38), "bold"))


class Segmentado(_Lienzo):
    """Selector de píldoras ligado a una StringVar."""

    def __init__(self, master, variable, opciones, ancho=240, columnas=2, alto_fila=30, hueco=6,
                 fuente="Helvetica", fondo=T.TARJETA):
        filas = math.ceil(len(opciones) / columnas)
        super().__init__(master, ancho, filas * alto_fila + (filas - 1) * hueco, fondo)
        self.variable, self.opciones, self.columnas = variable, opciones, columnas
        self.alto_fila, self.hueco, self._fuente = alto_fila, hueco, fuente
        self.bind("<Button-1>", self._clic)
        variable.trace_add("write", lambda *_: self._dibujar())
        self._dibujar()

    def _celda(self, i):
        col, fila = i % self.columnas, i // self.columnas
        w = (self.ancho - (self.columnas - 1) * self.hueco) / self.columnas
        x0, y0 = col * (w + self.hueco), fila * (self.alto_fila + self.hueco)
        return x0, y0, x0 + w, y0 + self.alto_fila

    def _clic(self, e):
        if not self._habilitado:
            return
        for i, (valor, _) in enumerate(self.opciones):
            x0, y0, x1, y1 = self._celda(i)
            if x0 <= e.x <= x1 and y0 <= e.y <= y1:
                self.variable.set(valor)
                return

    def _dibujar(self):
        self.delete("all")
        for i, (valor, texto) in enumerate(self.opciones):
            x0, y0, x1, y1 = self._celda(i)
            sel = self.variable.get() == valor
            if not self._habilitado:
                relleno, borde, color = (T.mezclar(T.TARJETA_2, T.AMBAR, 0.25) if sel else T.TARJETA), T.BORDE, T.TEXTO_3
            else:
                relleno = T.AMBAR if sel else T.TARJETA_2
                borde = T.AMBAR if sel else T.BORDE
                color = T.SOBRE_AMBAR if sel else T.TEXTO_2
            rect_redondo(self, x0 + 1, y0 + 1, x1 - 1, y1 - 1, self.alto_fila / 2, fill=relleno, outline=borde)
            self.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=texto, fill=color, font=(self._fuente, 9))


class Deslizador(_Lienzo):
    """Deslizador entero con pista fina y asa redonda, ligado a una IntVar."""
    M = 10

    def __init__(self, master, variable, desde, hasta, ancho=180, fondo=T.TARJETA):
        super().__init__(master, ancho, 24, fondo)
        self.variable, self.desde, self.hasta = variable, desde, hasta
        self.bind("<Button-1>", self._mover)
        self.bind("<B1-Motion>", self._mover)
        variable.trace_add("write", lambda *_: self._dibujar())
        self._dibujar()

    def _x(self, valor):
        f = (valor - self.desde) / (self.hasta - self.desde)
        return self.M + (self.ancho - 2 * self.M) * max(0.0, min(1.0, f))

    def _mover(self, e):
        if not self._habilitado:
            return
        f = max(0.0, min(1.0, (e.x - self.M) / (self.ancho - 2 * self.M)))
        v = round(self.desde + f * (self.hasta - self.desde))
        if v != self.variable.get():
            self.variable.set(v)

    def _dibujar(self):
        self.delete("all")
        y = self.alto / 2
        x = self._x(self.variable.get())
        activo = self._habilitado
        self.create_line(self.M, y, self.ancho - self.M, y, fill=T.PISTA, width=4, capstyle="round")
        self.create_line(self.M, y, x, y, fill=T.AMBAR if activo else T.TEXTO_3, width=4, capstyle="round")
        self.create_oval(x - 8, y - 8, x + 8, y + 8, fill=T.AMBAR if activo else T.TEXTO_3, outline=self.fondo, width=2)
        self.create_oval(x - 3, y - 3, x + 3, y + 3, fill=T.SOBRE_AMBAR, outline="")


class Interruptor(_Lienzo):
    """Interruptor on/off ligado a una BooleanVar."""

    def __init__(self, master, variable, fondo=T.TARJETA):
        super().__init__(master, 42, 24, fondo)
        self.variable = variable
        self.bind("<Button-1>", self._clic)
        variable.trace_add("write", lambda *_: self._dibujar())
        self._dibujar()

    def _clic(self, e):
        if self._habilitado:
            self.variable.set(not self.variable.get())

    def _dibujar(self):
        self.delete("all")
        on = bool(self.variable.get())
        pista = (T.AMBAR if on else T.PISTA) if self._habilitado else T.TARJETA_2
        rect_redondo(self, 1, 3, 41, 21, 9, fill=pista, outline=T.BORDE if not on else T.AMBAR)
        x = 31 if on else 11
        self.create_oval(x - 7, 12 - 7, x + 7, 12 + 7, fill=T.SOBRE_AMBAR if on else T.TEXTO_2, outline="")


class LedVirtual(_Lienzo):
    """LED redondo que se enciende con el brillo recibido (0-255)."""

    def __init__(self, master, color, tamano=44, fondo=T.TARJETA):
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

    def _dibujar(self):
        self.delete("all")
        base, b = T.LED_BASE[self.color], max(0, self._brillo) / 255
        c, r = self.ancho / 2, self.ancho * 0.26
        for extra, f in ((self.ancho * 0.20, 0.10), (self.ancho * 0.13, 0.18), (self.ancho * 0.07, 0.32)):
            if b > 0:
                self.create_oval(c - r - extra, c - r - extra, c + r + extra, c + r + extra,
                                 fill=T.mezclar(self.fondo, base, f * b), outline="")
        lente = T.mezclar(T.PISTA, base, b)
        self.create_oval(c - r, c - r, c + r, c + r, fill=lente, outline=T.mezclar(T.BORDE, base, 0.6 * b), width=2)
        s = r * 0.38
        self.create_oval(c - r * 0.55, c - r * 0.6, c - r * 0.55 + s, c - r * 0.6 + s,
                         fill=T.mezclar(lente, "#ffffff", 0.25 + 0.3 * b), outline="")


class SemaforoVirtual(_Lienzo):
    """Semáforo con aspecto 3D (carcasa, visera, lente con brillo). Espeja a los LEDs reales."""
    ORDEN = ("R", "Y", "G")          # de arriba abajo, como un semáforo de verdad

    def __init__(self, master, ancho=112, alto=262, fondo=T.TARJETA):
        super().__init__(master, ancho, alto, fondo)
        self._brillos = None
        self.poner({"R": 0, "G": 0, "Y": 0})

    def poner(self, brillos):
        clave = tuple(int(brillos.get(c, 0)) for c in self.ORDEN)
        if clave == self._brillos:
            return
        self._brillos = clave
        self._dibujar()

    def _dibujar(self):
        self.delete("all")
        w, h = self.ancho, self.alto
        cx = w / 2
        self.create_rectangle(cx - 6, h - 28, cx + 6, h, fill="#1d1d1f", outline="#2b2b2e")          # poste
        self.create_rectangle(cx - 22, h - 6, cx + 22, h - 1, fill="#1d1d1f", outline="#2b2b2e")
        rect_redondo(self, 12, 4, w - 12, h - 26, 18, fill="#0d0d0e", outline="#34343a", width=2)    # carcasa
        self.create_line(18, 24, 18, h - 46, fill="#2c2c30", width=2)                                 # bisel (luz)
        self.create_line(w - 18, 24, w - 18, h - 46, fill="#050505", width=3)                         # bisel (sombra)
        radio, paso = 24, (h - 26 - 8) / 3
        for i, color in enumerate(self.ORDEN):
            b = self._brillos[i] / 255
            y = 4 + paso * (i + 0.5) + 2
            base = T.LED_BASE[color]
            if b > 0:
                for extra, f in ((16, 0.08), (11, 0.16), (6, 0.30)):
                    self.create_oval(cx - radio - extra, y - radio - extra, cx + radio + extra, y + radio + extra,
                                     fill=T.mezclar("#0d0d0e", base, f * b), outline="")
            self.create_oval(cx - radio - 3, y - radio - 3, cx + radio + 3, y + radio + 3, fill="#050505", outline="#26262a")
            lente = T.mezclar(T.mezclar("#17171a", base, 0.16), base, b)
            self.create_oval(cx - radio, y - radio, cx + radio, y + radio, fill=lente, outline="")
            self.create_oval(cx - radio * 0.66, y - radio * 0.62, cx + radio * 0.52, y + radio * 0.56,
                             fill=T.mezclar(lente, "#ffffff", 0.07 + 0.16 * b), outline="")
            self.create_oval(cx - radio * 0.62, y - radio * 0.70, cx - radio * 0.14, y - radio * 0.36,
                             fill=T.mezclar(lente, "#ffffff", 0.22 + 0.38 * b), outline="")
            self.create_arc(cx - radio - 6, y - radio - 12, cx + radio + 6, y - radio + 14, start=0, extent=180,
                            style="chord", fill="#070708", outline="#1d1d20")                          # visera (solo asoma sobre la lente)


class Medidor(_Lienzo):
    """Medidor circular de 270 grados con el valor en el centro."""

    def __init__(self, master, ancho=150, alto=132, fuente="Helvetica", fondo=T.TARJETA):
        super().__init__(master, ancho, alto, fondo)
        self._fuente = fuente
        self._estado = (0.0, "--", "°C")
        self._dibujar()

    def poner(self, fraccion, texto, unidad="°C"):
        self._estado = (max(0.0, min(1.0, fraccion)), texto, unidad)
        self._dibujar()

    def _dibujar(self):
        self.delete("all")
        f, texto, unidad = self._estado
        cx, cy = self.ancho / 2, self.alto / 2 + 2
        r = min(self.ancho, self.alto) / 2 - 14
        self.create_arc(cx - r, cy - r, cx + r, cy + r, start=225, extent=-270, style="arc", outline=T.PISTA, width=10)
        if f > 0:
            self.create_arc(cx - r, cy - r, cx + r, cy + r, start=225, extent=-270 * f, style="arc",
                            outline=T.AMBAR, width=10)
        for k in (0, 0.5, 1):                                   # puntitos ámbar, como en el diseño
            a = math.radians(225 - 270 * k)
            x, y = cx + (r + 11) * math.cos(a), cy - (r + 11) * math.sin(a)
            self.create_oval(x - 2.5, y - 2.5, x + 2.5, y + 2.5, fill=T.AMBAR if f >= k else T.PISTA, outline="")
        self.create_text(cx, cy - 4, text=texto, fill=T.TEXTO, font=(self._fuente, 20, "bold"))
        self.create_text(cx, cy + 18, text=unidad, fill=T.TEXTO_2, font=(self._fuente, 10))


class Barras(_Lienzo):
    """Barras verticales con extremos redondeados (las últimas lecturas)."""

    def __init__(self, master, n=6, ancho=150, alto=112, fondo=T.TARJETA):
        super().__init__(master, ancho, alto, fondo)
        self.n = n
        self._valores, self._maximo = [None] * n, 100.0
        self._dibujar()

    def poner(self, valores, maximo=100.0):
        v = list(valores)[-self.n:]
        self._valores = [None] * (self.n - len(v)) + v
        self._maximo = float(maximo)
        self._dibujar()

    def _dibujar(self):
        self.delete("all")
        grosor = 16
        paso = (self.ancho - 20) / self.n
        base, tope = self.alto - 6 - grosor / 2, 6 + grosor / 2
        for i, v in enumerate(self._valores):
            x = 10 + paso * (i + 0.5)
            self.create_line(x, base, x, tope, fill=T.PISTA, width=grosor, capstyle="round")
            if v is not None:
                frac = max(0.0, min(1.0, v / self._maximo))
                color = T.AMBAR_CLARO if i == self.n - 1 else T.AMBAR
                self.create_line(x, base, x, base - (base - tope) * frac, fill=color, width=grosor, capstyle="round")
