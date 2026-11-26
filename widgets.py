"""Widgets propios de DuinoVisor, dibujados sobre Canvas (solo Tkinter, sin dependencias).

Los colores se leen de `tema` al crear cada widget: tras `tema.aplicar()` hay que volver a crearlos.
Los lienzos dibujan en unidades lógicas (96 ppp) y luego se escalan con `tema.ESCALA`.
"""
from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk

import tema as T


def rect_redondo(c, x0, y0, x1, y1, r, **kw):
    r = max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1,
           x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
    return c.create_polygon(pts, smooth=True, **kw)


def entrada(master, variable, ancho=7, fuente="Helvetica", fondo=None):
    return tk.Entry(master, textvariable=variable, width=ancho, bg=T.SUPERFICIE_2, fg=T.TEXTO,
                    insertbackground=T.ACENTO, relief="flat", highlightthickness=1,
                    highlightbackground=T.BORDE, highlightcolor=T.ACENTO, font=(fuente, T.TAM_CUERPO),
                    justify="center", disabledbackground=fondo or T.SUPERFICIE, disabledforeground=T.TEXTO_3)


def etiqueta(master, texto="", fuente="Helvetica", tam=None, color=None, fondo=None, negrita=False, **kw):
    tam = tam or T.TAM_CUERPO
    return tk.Label(master, text=texto, bg=fondo or T.SUPERFICIE, fg=color or T.TEXTO_2,
                    font=(fuente, tam, "bold") if negrita else (fuente, tam), **kw)


def medir(texto: str, fuente: str, tam: int, negrita=False) -> float:
    """Ancho del texto en unidades lógicas (aproximado si no hay pantalla)."""
    try:
        from tkinter import font as tkfont
        px = tkfont.Font(family=fuente, size=tam, weight="bold" if negrita else "normal").measure(texto)
        return px / T.ESCALA
    except Exception:
        return len(texto) * tam * 0.62


class _Lienzo(tk.Canvas):
    """Base: tamaño lógico, escala de pantalla, habilitar/deshabilitar y traces que se limpian solos."""

    def __init__(self, master, ancho, alto, fondo=None, zoom=1.0):
        self.S = T.ESCALA
        self.zoom = zoom
        self.fondo = fondo or T.SUPERFICIE
        super().__init__(master, width=round(ancho * self.S), height=round(alto * self.S), bg=self.fondo,
                         highlightthickness=0, bd=0)
        self.ancho, self.alto = ancho / zoom, alto / zoom          # coordenadas de dibujo
        self._habilitado = True
        self._traces = []
        self.bind("<Destroy>", self._al_destruir, add="+")

    def _vigilar(self, variable, funcion):
        tid = variable.trace_add("write", lambda *_: funcion())
        self._traces.append((variable, tid))

    def _al_destruir(self, e=None):
        if e is not None and e.widget is not self:
            return
        for variable, tid in self._traces:
            try:
                variable.trace_remove("write", tid)
            except Exception:
                pass
        self._traces = []

    def _xy(self, e):
        f = self.S * self.zoom
        return e.x / f, e.y / f

    def g(self, w):
        """Grosor de línea escalado."""
        return max(1, round(w * self.S * self.zoom))

    def habilitar(self, si: bool) -> None:
        self._habilitado = bool(si)
        self._dibujar()

    def _dibujar(self) -> None:
        try:
            self.delete("all")
        except tk.TclError:
            return
        self._pintar()
        f = self.S * self.zoom
        if f != 1:
            self.scale("all", 0, 0, f, f)

    def _pintar(self) -> None:            # lo redefine cada widget
        pass


class Tarjeta(tk.Canvas):
    """Panel de esquinas redondas con título. El contenido va en `.contenido`.

    Con `llenar=True` el contenido ocupa todo el alto que el layout le dé a la tarjeta; si no, la tarjeta
    toma el alto de su contenido.
    """
    PAD = 18

    def __init__(self, master, titulo="", fuente="Helvetica", radio=14, color=None, fondo=None, llenar=False,
                 subtitulo=""):
        color, fondo = color or T.SUPERFICIE, fondo or T.FONDO
        super().__init__(master, bg=fondo, highlightthickness=0, bd=0, height=60, width=120)
        self.S = T.ESCALA
        self._pad = round(self.PAD * self.S)
        self._radio, self._color, self._llenar = radio * self.S, color, llenar
        self.cuerpo = tk.Frame(self, bg=color)
        self._ventana = self.create_window(self._pad, self._pad, anchor="nw", window=self.cuerpo)
        cabecera = tk.Frame(self.cuerpo, bg=color)
        self.titulo = tk.Label(cabecera, text=titulo, bg=color, fg=T.TEXTO, font=(fuente, T.TAM_SECCION, "bold"),
                               anchor="w")
        self.titulo.pack(side="left")
        self.extra = tk.Frame(cabecera, bg=color)
        self.extra.pack(side="right")
        if titulo or subtitulo:
            cabecera.pack(fill="x")
        if subtitulo:
            tk.Label(self.cuerpo, text=subtitulo, bg=color, fg=T.TEXTO_2, font=(fuente, T.TAM_PEQ), anchor="w",
                     justify="left").pack(fill="x")
        self.contenido = tk.Frame(self.cuerpo, bg=color)
        self.contenido.pack(fill="both", expand=True, pady=(round(12 * self.S) if titulo else 0, 0))
        self.bind("<Configure>", self._al_cambiar_tamano)
        if not llenar:
            self.cuerpo.bind("<Configure>", self._al_cambiar_cuerpo)

    def _al_cambiar_tamano(self, e):
        self.delete("fondo")
        rect_redondo(self, 1, 1, e.width - 1, e.height - 1, self._radio, fill=self._color,
                     outline=T.BORDE, tags="fondo")
        self.tag_lower("fondo")
        kw = {"width": max(10, e.width - 2 * self._pad)}
        if self._llenar:
            kw["height"] = max(10, e.height - 2 * self._pad)
        self.itemconfigure(self._ventana, **kw)

    def _al_cambiar_cuerpo(self, e):
        self.configure(height=e.height + 2 * self._pad)


class BotonPildora(_Lienzo):
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


class BotonIcono(_Lienzo):
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


class Segmentado(_Lienzo):
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


class Deslizador(_Lienzo):
    """Deslizador entero con pista fina y asa redonda, ligado a una IntVar."""
    M = 11

    def __init__(self, master, variable, desde, hasta, ancho=180, fondo=None):
        super().__init__(master, ancho, 26, fondo)
        self.variable, self.desde, self.hasta = variable, desde, hasta
        self.configure(cursor="hand2")
        self.bind("<Button-1>", self._mover)
        self.bind("<B1-Motion>", self._mover)
        self._vigilar(variable, self._dibujar)
        self._dibujar()

    def _x(self, valor):
        f = (valor - self.desde) / (self.hasta - self.desde)
        return self.M + (self.ancho - 2 * self.M) * max(0.0, min(1.0, f))

    def _mover(self, e):
        if not self._habilitado:
            return
        x, _ = self._xy(e)
        f = max(0.0, min(1.0, (x - self.M) / (self.ancho - 2 * self.M)))
        v = round(self.desde + f * (self.hasta - self.desde))
        if v != self.variable.get():
            self.variable.set(v)

    def _pintar(self):
        y = self.alto / 2
        x = self._x(self.variable.get())
        color = T.ACENTO if self._habilitado else T.TEXTO_3
        self.create_line(self.M, y, self.ancho - self.M, y, fill=T.PISTA, width=self.g(5), capstyle="round")
        self.create_line(self.M, y, x, y, fill=color, width=self.g(5), capstyle="round")
        self.create_oval(x - 9, y - 9, x + 9, y + 9, fill=T.SUPERFICIE, outline=color, width=self.g(2.5))


class Interruptor(_Lienzo):
    """Interruptor on/off ligado a una BooleanVar."""

    def __init__(self, master, variable, fondo=None):
        super().__init__(master, 44, 26, fondo)
        self.variable = variable
        self.configure(cursor="hand2")
        self.bind("<Button-1>", self._clic)
        self._vigilar(variable, self._dibujar)
        self._dibujar()

    def _clic(self, e):
        if self._habilitado:
            self.variable.set(not self.variable.get())

    def _pintar(self):
        on = bool(self.variable.get())
        pista = (T.ACENTO if on else T.PISTA) if self._habilitado else T.SUPERFICIE_2
        rect_redondo(self, 1, 2, 43, 24, 11, fill=pista, outline=pista)
        x = 32 if on else 12
        self.create_oval(x - 8, 13 - 8, x + 8, 13 + 8, fill="#ffffff", outline=T.mezclar(pista, "#000000", 0.08))


def _resplandor(c, cx, cy, r, base, b, fondo, capas=((0.8, 0.10), (0.5, 0.18), (0.25, 0.32))):
    if b <= 0:
        return
    for extra, f in capas:
        e = r * extra
        c.create_oval(cx - r - e, cy - r - e, cx + r + e, cy + r + e, fill=T.mezclar(fondo, base, f * b), outline="")


class LedVirtual(_Lienzo):
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


class Chip(_Lienzo):
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


class SemaforoVirtual(_Lienzo):
    """Semáforo con aspecto 3D (carcasa, visera, lente con brillo). Espeja a los LEDs reales.

    Se dibuja en una geometría base de 112×262 y se amplía a `ancho`. Con `al_elegir` cada luz es un botón.
    """
    ORDEN = ("R", "Y", "G")          # de arriba abajo, como un semáforo de verdad
    BASE_W, BASE_H = 112, 262

    def __init__(self, master, ancho=112, fondo=None, al_elegir=None):
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
        self.poner({"R": 0, "G": 0, "Y": 0})

    def redimensionar(self, ancho: float) -> None:
        """Nuevo ancho lógico (el alto sigue la proporción del semáforo)."""
        zoom = ancho / self.BASE_W
        if abs(zoom - self.zoom) < 0.02:
            return
        self.zoom = zoom
        self.configure(width=round(ancho * self.S), height=round(self.BASE_H * zoom * self.S))
        self._dibujar()

    def _centro(self, i):
        paso = (self.alto - 26 - 8) / 3
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


class Medidor(_Lienzo):
    """Medidor circular de 270 grados con el valor en el centro."""

    def __init__(self, master, ancho=170, alto=150, fuente="Helvetica", fondo=None):
        super().__init__(master, ancho, alto, fondo)
        self._fuente = fuente
        self._estado = (0.0, "--", "°C")
        self._dibujar()

    def poner(self, fraccion, texto, unidad="°C"):
        self._estado = (max(0.0, min(1.0, fraccion)), texto, unidad)
        self._dibujar()

    def _pintar(self):
        f, texto, unidad = self._estado
        cx, cy = self.ancho / 2, self.alto / 2 + 4
        r = min(self.ancho, self.alto) / 2 - 14
        self.create_arc(cx - r, cy - r, cx + r, cy + r, start=225, extent=-270, style="arc", outline=T.PISTA,
                        width=self.g(11))
        if f > 0:
            self.create_arc(cx - r, cy - r, cx + r, cy + r, start=225, extent=-270 * f, style="arc",
                            outline=T.ACENTO, width=self.g(11))
        self.create_text(cx, cy - 4, text=texto, fill=T.TEXTO, font=(self._fuente, 24, "bold"))
        self.create_text(cx, cy + 22, text=unidad, fill=T.TEXTO_2, font=(self._fuente, T.TAM_PEQ))


class Barras(_Lienzo):
    """Barras verticales con extremos redondeados (las últimas lecturas)."""

    def __init__(self, master, n=6, ancho=170, alto=120, fondo=None):
        super().__init__(master, ancho, alto, fondo)
        self.n = n
        self._valores, self._maximo = [None] * n, 100.0
        self._dibujar()

    def poner(self, valores, maximo=100.0):
        v = list(valores)[-self.n:]
        self._valores = [None] * (self.n - len(v)) + v
        self._maximo = float(maximo)
        self._dibujar()

    def _pintar(self):
        grosor = 16
        paso = (self.ancho - 20) / self.n
        base, tope = self.alto - 6 - grosor / 2, 6 + grosor / 2
        for i, v in enumerate(self._valores):
            x = 10 + paso * (i + 0.5)
            self.create_line(x, base, x, tope, fill=T.PISTA, width=self.g(grosor), capstyle="round")
            if v is not None:
                frac = max(0.0, min(1.0, v / self._maximo))
                color = T.ACENTO if i == self.n - 1 else T.mezclar(T.SUPERFICIE, T.ACENTO, 0.55)
                self.create_line(x, base, x, base - (base - tope) * frac, fill=color, width=self.g(grosor),
                                 capstyle="round")


class MuestraColor(_Lienzo):
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


class Desplazable(tk.Frame):
    """Columna con desplazamiento vertical: la barra solo aparece si el contenido no cabe.

    El contenido va en `.interior`. A la derecha queda siempre un margen (`MARGEN`) donde se dibuja la barra.
    La rueda del ratón desplaza la columna que está bajo el puntero.
    """
    MARGEN = 12
    _instancias: list = []
    _instalado = False

    def __init__(self, master, fondo=None):
        fondo = fondo or T.FONDO
        super().__init__(master, bg=fondo)
        self._margen = round(self.MARGEN * T.ESCALA)
        self.lienzo = tk.Canvas(self, bg=fondo, highlightthickness=0, bd=0, width=10, height=10)
        self.lienzo.pack(fill="both", expand=True)
        self.barra = ttk.Scrollbar(self, orient="vertical", command=self.lienzo.yview, style="Duino.Vertical.TScrollbar")
        self.lienzo.configure(yscrollcommand=self.barra.set)
        self.interior = tk.Frame(self.lienzo, bg=fondo)
        self._ventana = self.lienzo.create_window(0, 0, anchor="nw", window=self.interior)
        self._visible = False
        self.interior.bind("<Configure>", self._ajustar)
        self.lienzo.bind("<Configure>", self._ajustar)
        Desplazable._instancias.append(self)
        self.bind("<Destroy>", lambda e: e.widget is self and self in Desplazable._instancias
                  and Desplazable._instancias.remove(self), add="+")
        if not Desplazable._instalado:
            try:
                self.bind_all("<MouseWheel>", Desplazable._rueda, add="+")
                Desplazable._instalado = True
            except Exception:
                pass

    def _ajustar(self, e=None):
        try:
            ancho, alto = self.lienzo.winfo_width(), self.lienzo.winfo_height()
            req = self.interior.winfo_reqheight()
            self.lienzo.itemconfigure(self._ventana, width=max(10, ancho - self._margen))
            self.lienzo.configure(scrollregion=(0, 0, ancho, req))
            sobra = req > alto + 1
            if sobra and not self._visible:
                self.barra.place(relx=1, rely=0, relheight=1, anchor="ne", width=self._margen)
            elif not sobra and self._visible:
                self.barra.place_forget()
                self.lienzo.yview_moveto(0)
            self._visible = sobra
        except (tk.TclError, TypeError):
            pass

    @staticmethod
    def _rueda(e):
        destino = str(e.widget)
        for d in Desplazable._instancias:
            if d._visible and destino.startswith(str(d)):
                d.lienzo.yview_scroll(int(-e.delta / 120) or (-1 if e.delta > 0 else 1), "units")
                return


class Aviso(tk.Frame):
    """Caja informativa con una barra de color a la izquierda (texto en lenguaje llano)."""

    def __init__(self, master, texto="", fuente="Helvetica", fondo=None, color=None, ancho_texto=280):
        color = color or T.ACENTO
        relleno = T.mezclar(fondo or T.SUPERFICIE, color, 0.10)
        super().__init__(master, bg=relleno)
        tk.Frame(self, bg=color, width=round(4 * T.ESCALA)).pack(side="left", fill="y")
        self.etiqueta = tk.Label(self, text=texto, bg=relleno, fg=T.TEXTO, font=(fuente, T.TAM_PEQ), justify="left",
                                 anchor="w", wraplength=round(ancho_texto * T.ESCALA), padx=12, pady=10)
        self.etiqueta.pack(side="left", fill="both", expand=True)

    def configurar(self, texto):
        self.etiqueta.configure(text=texto)
