"""Barra de avisos del pie de la ventana: cambios sin aplicar, envío en curso, aplicado o fallo.

Sube desde abajo animando su alto y se dibuja en un Canvas con el color del fondo de la ventana, así sus
esquinas redondeadas y su sombra quedan limpias.
"""
from __future__ import annotations

import tkinter as tk

from duinovisor.ui import tema as T
from duinovisor.ui.widgets.base import medir, rect_redondo

ALTO = 68                 # alto lógico de la barra desplegada (con su sombra)
PASOS_ANIMACION = 8
MS_FOTOGRAMA = 16


def _colores(estado: str) -> tuple[str, str, str]:
    """(relleno, texto, borde) de la tarjeta para cada estado."""
    if estado == "pendiente":
        return T.ACENTO, T.SOBRE_ACENTO, T.ACENTO
    if estado in ("error", "fallo"):
        return T.ERROR, T.SOBRE_ACENTO, T.ERROR
    if estado == "listo":
        return T.EXITO, T.SOBRE_ACENTO, T.EXITO
    return T.SUPERFICIE, T.TEXTO, T.BORDE                    # enviando


class BarraCambios(tk.Canvas):
    """`mostrar(estado, titulo, detalle, boton, progreso)` y `ocultar()`. `estado` es None si no se ve."""

    def __init__(self, master, fuente="Helvetica", al_cerrar=None):
        self.S = T.ESCALA
        super().__init__(master, height=1, bg=T.FONDO, highlightthickness=0, bd=0)
        self._fuente, self.al_cerrar = fuente, al_cerrar
        self.estado = self.titulo = self.detalle = None
        self.boton = None                     # (texto, comando) o None
        self.progreso = None                  # 0..1 o None
        self._alto, self._objetivo, self._anim = 0.0, 0.0, None
        self._encima = None
        self._giro = 0
        self.bind("<Configure>", lambda e: self._pintar())
        self.bind("<Motion>", self._mover)
        self.bind("<Leave>", lambda e: self._poner_encima(None))
        self.bind("<ButtonRelease-1>", self._clic)

    # ------------------------------------------------------------------ API
    def mostrar(self, estado, titulo, detalle="", boton=None, progreso=None):
        nuevo = (estado, titulo, detalle, boton and boton[0], progreso)
        actual = (self.estado, self.titulo, self.detalle, self.boton and self.boton[0], self.progreso)
        self.boton = boton
        if nuevo == actual:
            return
        entra = self.estado is None
        self.estado, self.titulo, self.detalle, self.progreso = estado, titulo, detalle, progreso
        if entra:
            self._animar_a(ALTO)
        self._pintar()
        if estado == "enviando":
            self._girar()

    def ocultar(self):
        if self.estado is None:
            return
        self.estado = self.titulo = self.detalle = self.boton = self.progreso = None
        self._animar_a(0)

    # ------------------------------------------------------------------ animación de entrada y salida
    def _animar_a(self, objetivo):
        self._objetivo = objetivo
        if self._anim is None:
            if objetivo > 0:
                self.grid()
            self._paso()

    def _paso(self):
        self._anim = None
        restante = self._objetivo - self._alto
        if abs(restante) < 1:
            self._alto = self._objetivo
        else:
            self._alto += restante * 0.45 if abs(restante) > ALTO / PASOS_ANIMACION else restante
        try:
            self.configure(height=max(1, round(self._alto * self.S)))
            if self._alto == 0 and self._objetivo == 0:
                self.grid_remove()
                return
            self._pintar()
            if self._alto != self._objetivo:
                self._anim = self.after(MS_FOTOGRAMA, self._paso)
        except tk.TclError:
            pass

    def _girar(self):
        """Mientras se envía, el icono gira."""
        if self.estado != "enviando":
            return
        self._giro = (self._giro + 30) % 360
        try:
            self.itemconfigure("giro", start=self._giro)
            self.after(60, self._girar)
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ interacción
    def _zona(self, e):
        for etiqueta in self.gettags("current") or ():
            if etiqueta in ("boton", "cerrar"):
                return etiqueta
        return None

    def _mover(self, e):
        self._poner_encima(self._zona(e))

    def _poner_encima(self, zona):
        if zona != self._encima:
            self._encima = zona
            self.configure(cursor="hand2" if zona else "")
            self._pintar()

    def _clic(self, e):
        zona = self._zona(e)
        if zona == "boton" and self.boton:
            self.boton[1]()
        elif zona == "cerrar":
            if self.al_cerrar:
                self.al_cerrar()
            self.ocultar()

    # ------------------------------------------------------------------ dibujo
    def _pintar(self):
        try:
            self.delete("all")
            w = self.winfo_width()
        except tk.TclError:
            return
        if self.estado is None or not isinstance(w, int) or w < 50:
            return
        s = self.S
        alto = ALTO * s
        y0 = self._alto * s - alto                         # la tarjeta asoma desde abajo
        x0, x1, y1 = 2 * s, w - 2 * s, y0 + alto - 8 * s
        r = 14 * s
        relleno, texto, borde = _colores(self.estado)
        for k, f in enumerate((0.05, 0.08, 0.12)):        # sombra suave
            d = (3 - k) * s
            rect_redondo(self, x0 - d + 1, y0 + 2 * s, x1 + d - 1, y1 + d + 2 * s, r + d,
                         fill=T.mezclar(T.FONDO, "#000000", f), outline="")
        rect_redondo(self, x0, y0, x1, y1, r, fill=relleno, outline=borde)
        cy = (y0 + y1) / 2
        # icono
        ic, ri = x0 + 34 * s, 15 * s
        fondo_icono = T.mezclar(relleno, texto, 0.18)
        self.create_oval(ic - ri, cy - ri, ic + ri, cy + ri, fill=fondo_icono, outline="")
        g = max(1, round(2.4 * s))
        if self.estado == "enviando":
            self.create_arc(ic - ri * 0.6, cy - ri * 0.6, ic + ri * 0.6, cy + ri * 0.6, start=self._giro, extent=270,
                            style="arc", outline=T.ACENTO, width=g, tags=("giro",))
        elif self.estado == "listo":
            self.create_line(ic - ri * 0.42, cy, ic - ri * 0.1, cy + ri * 0.35, ic + ri * 0.45, cy - ri * 0.35,
                             fill=texto, width=g, capstyle="round", joinstyle="round")
        elif self.estado == "fallo":
            a = ri * 0.36
            self.create_line(ic - a, cy - a, ic + a, cy + a, fill=texto, width=g, capstyle="round")
            self.create_line(ic - a, cy + a, ic + a, cy - a, fill=texto, width=g, capstyle="round")
        else:
            self.create_line(ic, cy - ri * 0.45, ic, cy + ri * 0.12, fill=texto, width=g, capstyle="round")
            self.create_oval(ic - g * 0.7, cy + ri * 0.36, ic + g * 0.7, cy + ri * 0.36 + g * 1.4, fill=texto,
                             outline="")
        # textos
        xt = ic + ri + 14 * s
        self.create_text(xt, cy - (9 * s if self.detalle else 0), text=self.titulo, anchor="w", fill=texto,
                         font=(self._fuente, T.TAM_CUERPO, "bold"))
        derecha = x1 - 14 * s
        # cerrar
        if self.estado != "enviando":
            rc = 13 * s
            cx = derecha - rc
            if self._encima == "cerrar":
                self.create_oval(cx - rc, cy - rc, cx + rc, cy + rc, fill=T.mezclar(relleno, texto, 0.15),
                                 outline="", tags=("cerrar",))
            else:
                self.create_oval(cx - rc, cy - rc, cx + rc, cy + rc, fill=relleno, outline="", tags=("cerrar",))
            a = 4.5 * s
            for dx in (-a, a):
                self.create_line(cx - a, cy - dx, cx + a, cy + dx, fill=texto, width=max(1, round(1.8 * s)),
                                 capstyle="round", tags=("cerrar",))
            derecha = cx - rc - 10 * s
        # botón
        if self.boton:
            ancho = (medir(self.boton[0], self._fuente, T.TAM_CUERPO, True) + 36) * s
            bx0, by0, by1 = derecha - ancho, cy - 17 * s, cy + 17 * s
            fondo_b = texto if self.estado != "enviando" else T.ACENTO
            if self._encima == "boton":
                fondo_b = T.mezclar(fondo_b, relleno, 0.15)
            rect_redondo(self, bx0, by0, derecha, by1, 17 * s, fill=fondo_b, outline="", tags=("boton",))
            self.create_text((bx0 + derecha) / 2, cy, text=self.boton[0], fill=relleno,
                             font=(self._fuente, T.TAM_CUERPO, "bold"), tags=("boton",))
            derecha = bx0 - 16 * s
        if self.detalle:
            self.create_text(xt, cy + 11 * s, text=self.detalle, anchor="w", fill=T.mezclar(texto, relleno, 0.2),
                             font=(self._fuente, T.TAM_PEQ), width=max(50, derecha - xt))
        # progreso del envío
        if self.progreso is not None:
            px0, px1, py = xt, max(xt + 40 * s, derecha), y1 - 9 * s
            self.create_line(px0, py, px1, py, fill=T.PISTA, width=max(1, round(4 * s)), capstyle="round")
            fin = px0 + (px1 - px0) * max(0.02, min(1.0, self.progreso))
            self.create_line(px0, py, fin, py, fill=T.ACENTO, width=max(1, round(4 * s)), capstyle="round")

