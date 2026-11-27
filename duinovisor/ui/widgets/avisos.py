"""Aviso flotante del pie de la ventana: cambios sin aplicar, envío en curso, aplicado o fallo.

Es una ventanita sin bordes que flota sobre el pie de la ventana principal y la acompaña al moverla o cambiar de
tamaño: aparece y desaparece sin desplazar nada. Sus esquinas redondeadas usan un color «transparente»
(`-transparentcolor`, en Windows); donde no existe, las esquinas toman el color de fondo de la ventana.
"""
from __future__ import annotations

import tkinter as tk

from duinovisor.ui import tema as T
from duinovisor.ui.widgets.base import medir, rect_redondo

ALTO = 64                 # alto lógico del aviso
ANCHO_MAX = 540           # ancho lógico máximo
MARGEN_ABAJO = 18         # distancia a los bordes inferior y derecho de la ventana
SUBIDA = 14               # px lógicos que sube al aparecer
FOTOGRAMAS = 9
CLAVE = "#ff00fe"         # color que Windows vuelve transparente (no lo usa nada más)


def _colores(estado: str) -> tuple[str, str, str]:
    """(relleno, texto, borde) de la tarjeta para cada estado."""
    if estado == "pendiente":
        return T.ACENTO, T.SOBRE_ACENTO, T.mezclar(T.ACENTO, "#000000", 0.18)
    if estado in ("error", "fallo"):
        return T.ERROR, T.SOBRE_ACENTO, T.mezclar(T.ERROR, "#000000", 0.18)
    if estado == "listo":
        return T.EXITO, T.SOBRE_ACENTO, T.mezclar(T.EXITO, "#000000", 0.18)
    return T.SUPERFICIE, T.TEXTO, T.BORDE                    # enviando


class BarraCambios:
    """`mostrar(estado, titulo, detalle, boton, progreso)` y `ocultar()`. `estado` es None si no se ve.

    La ventana principal debe llamar a `recolocar()` cuando se mueve o cambia de tamaño y a `al_minimizar(si)`.
    """

    def __init__(self, raiz, fuente="Helvetica", al_cerrar=None):
        self.S = T.ESCALA
        self.raiz, self._fuente, self.al_cerrar = raiz, fuente, al_cerrar
        self.estado = self.titulo = self.detalle = None
        self.boton = None                     # (texto, comando) o None
        self.progreso = None                  # 0..1 o None
        self._encima = None
        self._giro = 0
        self._paso = None                     # animación: [id_after, fotograma, entrando]
        self._minimizada = False
        self.ventana = v = tk.Toplevel(raiz)
        v.withdraw()
        v.overrideredirect(True)
        v.transient(raiz)
        fondo = T.FONDO
        try:
            v.attributes("-transparentcolor", CLAVE)
            fondo = CLAVE
        except (tk.TclError, AttributeError):
            pass
        self.lienzo = tk.Canvas(v, bg=fondo, highlightthickness=0, bd=0, width=round(ANCHO_MAX * self.S),
                                height=round(ALTO * self.S))
        self.lienzo.pack(fill="both", expand=True)
        self.lienzo.bind("<Configure>", lambda e: self._pintar())      # al tomar su tamaño real
        self.lienzo.bind("<Motion>", self._mover)
        self.lienzo.bind("<Leave>", lambda e: self._poner_encima(None))
        self.lienzo.bind("<ButtonRelease-1>", self._clic)

    # ------------------------------------------------------------------ API
    def mostrar(self, estado, titulo, detalle="", boton=None, progreso=None):
        nuevo = (estado, titulo, detalle, boton and boton[0], progreso)
        actual = (self.estado, self.titulo, self.detalle, self.boton and self.boton[0], self.progreso)
        self.boton = boton
        if nuevo == actual:
            return
        entra = self.estado is None
        self.estado, self.titulo, self.detalle, self.progreso = estado, titulo, detalle, progreso
        self._pintar()
        if entra:
            self._animar(entrando=True)
        if estado == "enviando":
            self._girar()

    def ocultar(self):
        if self.estado is None:
            return
        self.estado = self.titulo = self.detalle = self.boton = self.progreso = None
        self._animar(entrando=False)

    def recolocar(self, subida: float = 0.0):
        """Ancho y posición según la ventana principal: abajo a la derecha, donde no tapa los controles."""
        try:
            ancho_raiz = self.raiz.winfo_width()
            if not isinstance(ancho_raiz, int) or ancho_raiz < 100:
                return
            s = self.S
            ancho = round(min(ancho_raiz - 48 * s, ANCHO_MAX * s))
            alto = round(ALTO * s)
            x = self.raiz.winfo_rootx() + ancho_raiz - ancho - round(24 * s)
            y = self.raiz.winfo_rooty() + self.raiz.winfo_height() - alto - round(MARGEN_ABAJO * s) + round(subida)
            self.ventana.geometry(f"{ancho}x{alto}+{x}+{y}")
        except (tk.TclError, TypeError):
            pass

    def al_minimizar(self, minimizada: bool):
        self._minimizada = minimizada
        try:
            if minimizada:
                self.ventana.withdraw()
            elif self.estado is not None:
                self.recolocar()
                self.ventana.deiconify()
        except tk.TclError:
            pass

    def destruir(self):
        try:
            self.ventana.destroy()
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ aparecer y desaparecer
    def _animar(self, entrando: bool):
        if self._paso is not None and self._paso[0] is not None:
            try:
                self.ventana.after_cancel(self._paso[0])
            except (tk.TclError, ValueError):
                pass
        self._paso = [None, 0, entrando]
        if entrando and not self._minimizada:
            self._alfa(0.0)
            self.recolocar(SUBIDA * self.S)
            try:
                self.ventana.deiconify()
                self.ventana.lift(self.raiz)
            except tk.TclError:
                return
        self._fotograma()

    def _fotograma(self):
        _, k, entrando = self._paso
        k += 1
        t = k / FOTOGRAMAS
        f = 1 - (1 - t) ** 3 if entrando else 1 - t ** 2           # ease-out al entrar
        self._alfa(f)
        self.recolocar((1 - f) * SUBIDA * self.S)
        if k >= FOTOGRAMAS:
            self._paso = None
            if not entrando:
                try:
                    self.ventana.withdraw()
                except tk.TclError:
                    pass
            return
        self._paso[1] = k
        try:
            self._paso[0] = self.ventana.after(16, self._fotograma)
        except tk.TclError:
            self._paso = None

    def _alfa(self, valor):
        try:
            self.ventana.attributes("-alpha", max(0.0, min(1.0, valor)))
        except (tk.TclError, AttributeError):
            pass

    def _girar(self):
        """Mientras se envía, el icono gira."""
        if self.estado != "enviando":
            return
        self._giro = (self._giro + 30) % 360
        try:
            self.lienzo.itemconfigure("giro", start=self._giro)
            self.lienzo.after(60, self._girar)
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ interacción
    def _zona(self):
        for etiqueta in self.lienzo.gettags("current") or ():
            if etiqueta in ("boton", "cerrar"):
                return etiqueta
        return None

    def _mover(self, e):
        self._poner_encima(self._zona())

    def _poner_encima(self, zona):
        if zona != self._encima:
            self._encima = zona
            self.lienzo.configure(cursor="hand2" if zona else "")
            self._pintar()

    def _clic(self, e):
        zona = self._zona()
        if zona == "boton" and self.boton:
            self.boton[1]()
        elif zona == "cerrar":
            if self.al_cerrar:
                self.al_cerrar()
            self.ocultar()

    # ------------------------------------------------------------------ dibujo
    def _pintar(self):
        c = self.lienzo
        try:
            c.delete("all")
            w, h = c.winfo_width(), c.winfo_height()
        except tk.TclError:
            return
        if self.estado is None or not isinstance(w, int) or w < 50:
            return
        s = self.S
        x0, y0, x1, y1 = 1, 1, w - 2, h - 2
        r = 16 * s
        relleno, texto, borde = _colores(self.estado)
        rect_redondo(c, x0, y0, x1, y1, r, fill=relleno, outline=borde, width=max(1, round(s)))
        cy = (y0 + y1) / 2
        # icono
        ic, ri = x0 + 34 * s, 15 * s
        c.create_oval(ic - ri, cy - ri, ic + ri, cy + ri, fill=T.mezclar(relleno, texto, 0.18), outline="")
        g = max(1, round(2.4 * s))
        if self.estado == "enviando":
            c.create_arc(ic - ri * 0.6, cy - ri * 0.6, ic + ri * 0.6, cy + ri * 0.6, start=self._giro, extent=270,
                         style="arc", outline=T.ACENTO, width=g, tags=("giro",))
        elif self.estado == "listo":
            c.create_line(ic - ri * 0.42, cy, ic - ri * 0.1, cy + ri * 0.35, ic + ri * 0.45, cy - ri * 0.35,
                          fill=texto, width=g, capstyle="round", joinstyle="round")
        elif self.estado == "fallo":
            a = ri * 0.36
            c.create_line(ic - a, cy - a, ic + a, cy + a, fill=texto, width=g, capstyle="round")
            c.create_line(ic - a, cy + a, ic + a, cy - a, fill=texto, width=g, capstyle="round")
        else:
            c.create_line(ic, cy - ri * 0.45, ic, cy + ri * 0.12, fill=texto, width=g, capstyle="round")
            c.create_oval(ic - g * 0.7, cy + ri * 0.36, ic + g * 0.7, cy + ri * 0.36 + g * 1.4, fill=texto, outline="")
        # textos
        xt = ic + ri + 14 * s
        c.create_text(xt, cy - (9 * s if self.detalle else 0), text=self.titulo, anchor="w", fill=texto,
                      font=(self._fuente, T.TAM_CUERPO, "bold"))
        derecha = x1 - 14 * s
        if self.estado != "enviando":                              # cerrar
            rc = 13 * s
            cx = derecha - rc
            fondo_x = T.mezclar(relleno, texto, 0.15) if self._encima == "cerrar" else relleno
            c.create_oval(cx - rc, cy - rc, cx + rc, cy + rc, fill=fondo_x, outline="", tags=("cerrar",))
            a = 4.5 * s
            for dx in (-a, a):
                c.create_line(cx - a, cy - dx, cx + a, cy + dx, fill=texto, width=max(1, round(1.8 * s)),
                              capstyle="round", tags=("cerrar",))
            derecha = cx - rc - 10 * s
        if self.boton:                                             # botón
            ancho = (medir(self.boton[0], self._fuente, T.TAM_CUERPO, True) + 36) * s
            bx0 = derecha - ancho
            fondo_b = texto if self.estado != "enviando" else T.ACENTO
            if self._encima == "boton":
                fondo_b = T.mezclar(fondo_b, relleno, 0.15)
            rect_redondo(c, bx0, cy - 17 * s, derecha, cy + 17 * s, 17 * s, fill=fondo_b, outline="", tags=("boton",))
            c.create_text((bx0 + derecha) / 2, cy, text=self.boton[0], fill=relleno,
                          font=(self._fuente, T.TAM_CUERPO, "bold"), tags=("boton",))
            derecha = bx0 - 16 * s
        if self.detalle:
            c.create_text(xt, cy + 11 * s, text=self.detalle, anchor="w", fill=T.mezclar(texto, relleno, 0.2),
                          font=(self._fuente, T.TAM_PEQ), width=max(50, derecha - xt))
        if self.progreso is not None:                              # progreso del envío
            px0, px1, py = xt, max(xt + 40 * s, derecha), y1 - 9 * s
            c.create_line(px0, py, px1, py, fill=T.PISTA, width=max(1, round(4 * s)), capstyle="round")
            fin = px0 + (px1 - px0) * max(0.02, min(1.0, self.progreso))
            c.create_line(px0, py, fin, py, fill=T.ACENTO, width=max(1, round(4 * s)), capstyle="round")
