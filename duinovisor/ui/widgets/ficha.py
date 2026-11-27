"""Tarjeta flotante con la ficha de un componente, dibujada dentro del lienzo de la protoboard.

Todo lleva la etiqueta `ficha` (y `ficha_cerrar` / `ficha_accion` lo que se puede pulsar), en coordenadas de
pantalla: el zoom y el arrastre del montaje no la mueven. Recibe un `ui.fichas.Ficha`.
"""
from __future__ import annotations

from duinovisor.ui import tema as T
from duinovisor.ui.widgets.base import medir, rect_redondo

ANCHO_MAX = 860           # ancho lógico máximo de la tarjeta
MARGEN = 12               # separación con los bordes del lienzo


def dibujar_ficha(c, ficha, x0: float, x1: float, y_abajo: float, escala: float, fuente: str, mesa: str,
                  encima=None) -> float:
    """Dibuja la ficha con su borde inferior en `y_abajo` y devuelve su alto (0 si no se pudo medir)."""
    s = escala
    pad, r = 14 * s, 16 * s
    t = ("ficha",)
    color = ficha.color
    xi = x0 + pad + 5 * s                                       # después de la franja de color

    # --- icono
    ri = 19 * s
    icx, icy = xi + ri, pad + ri
    fondo_icono = T.mezclar(T.SUPERFICIE, color, 0.13)
    primero = c.create_oval(icx - ri, icy - ri, icx + ri, icy + ri, fill=fondo_icono,
                            outline=T.mezclar(T.SUPERFICIE, color, 0.35), width=max(1, round(s)), tags=t)
    b = ficha.nivel or 0.0
    if ficha.tipo == "led":
        for e, f in ((8, 0.18), (4.5, 0.35)):
            rr = (8 + e) * s
            c.create_oval(icx - rr, icy - rr, icx + rr, icy + rr, fill=T.mezclar(fondo_icono, color, f * b * ficha.activo),
                          outline="", tags=t)
        rl = 8 * s
        apagado = T.mezclar(T.PISTA, color, 0.35)
        c.create_oval(icx - rl, icy - rl, icx + rl, icy + rl, fill=T.mezclar(apagado, color, b if ficha.activo else 0),
                      outline=T.mezclar(apagado, "#000000", 0.15), tags=t)
        c.create_oval(icx - rl * 0.55, icy - rl * 0.6, icx - rl * 0.05, icy - rl * 0.1, fill="#ffffff", outline="",
                      tags=t)
    else:
        rect_redondo(c, icx - 9 * s, icy - 11 * s, icx + 9 * s, icy + 11 * s, 3 * s, fill=color, outline="", tags=t)
        for k in range(3):
            for j in range(2):
                x, y = icx - 4 * s + j * 8 * s, icy - 6 * s + k * 6 * s
                c.create_rectangle(x - 2.4 * s, y - 1.6 * s, x + 2.4 * s, y + 1.6 * s,
                                   fill=T.mezclar(color, "#000000", 0.45), outline="", tags=t)

    # --- título, subtítulo en pastilla y cerrar
    xt = icx + ri + 12 * s
    c.create_text(xt, pad, text=ficha.titulo, anchor="nw", fill=T.TEXTO, font=(fuente, T.TAM_SECCION, "bold"),
                  tags=t)
    if ficha.subtitulo:
        ancho = (medir(ficha.subtitulo, fuente, T.TAM_PEQ, True) + 18) * s
        y = pad + 25 * s
        rect_redondo(c, xt, y, xt + ancho, y + 20 * s, 10 * s, fill=T.mezclar(T.SUPERFICIE, color, 0.14), outline="",
                     tags=t)
        c.create_text(xt + ancho / 2, y + 10 * s, text=ficha.subtitulo, fill=T.mezclar(color, T.TEXTO, 0.45),
                      font=(fuente, T.TAM_PEQ, "bold"), tags=t)
    rc = 15 * s
    cx, cy = x1 - pad - rc + 4 * s, icy
    encima_cerrar = encima == "ficha_cerrar"
    c.create_oval(cx - rc, cy - rc, cx + rc, cy + rc, outline="", tags=t + ("ficha_cerrar",),
                  fill=T.SUPERFICIE_2 if encima_cerrar else T.SUPERFICIE)
    a = 4.5 * s
    for d in (-a, a):
        c.create_line(cx - a, cy - d, cx + a, cy + d, fill=T.TEXTO if encima_cerrar else T.TEXTO_2,
                      width=max(1, round(1.8 * s)), capstyle="round", tags=t + ("ficha_cerrar",))

    # --- acción, en la cabecera junto a la ×
    if ficha.accion:
        ancho = (medir(ficha.accion, fuente, T.TAM_PEQ, True) + 30) * s
        alto_b = 30 * s
        bx1 = cx - rc - 10 * s
        relleno = T.ACENTO_HOVER if encima == "ficha_accion" else T.ACENTO
        rect_redondo(c, bx1 - ancho, icy - alto_b / 2, bx1, icy + alto_b / 2, alto_b / 2, fill=relleno, outline="",
                     tags=t + ("ficha_accion",))
        c.create_text(bx1 - ancho / 2, icy, text=ficha.accion, fill=T.SOBRE_ACENTO, font=(fuente, T.TAM_PEQ, "bold"),
                      tags=t + ("ficha_accion",))

    # --- qué es
    y = pad + 2 * ri + 8 * s
    q = c.create_text(xi, y, text=ficha.que_es, anchor="nw", width=max(50, x1 - pad - xi), fill=T.TEXTO_2,
                      font=(fuente, T.TAM_PEQ), tags=t)
    caja = c.bbox(q)
    if not caja:
        c.delete("ficha")
        return 0
    y = caja[3] + 10 * s

    # --- casillas: Conectado a / Qué hace / Ahora
    n = max(1, len(ficha.filas))
    hueco = 10 * s
    tw = (x1 - pad - xi - hueco * (n - 1)) / n
    fondos, bajos, primeros = [], [], []
    for i, (etq, valor) in enumerate(ficha.filas):
        tx = xi + i * (tw + hueco)
        primeros.append(c.create_text(tx + 12 * s, y + 8 * s, text=etq.upper(), anchor="nw", fill=T.TEXTO_3,
                                      font=(fuente, T.TAM_MINI, "bold"), tags=t))
        vx, ancho_v = tx + 12 * s, tw - 24 * s
        if i == n - 1:                                            # «Ahora»: punto de estado
            punto = T.EXITO if ficha.activo and ficha.tipo == "sensor" else (color if ficha.activo else T.TEXTO_3)
            c.create_oval(vx, y + 28 * s, vx + 8 * s, y + 36 * s, fill=punto, outline="", tags=t)
            vx, ancho_v = vx + 14 * s, ancho_v - 14 * s
        v = c.create_text(vx, y + 24 * s, text=valor, anchor="nw", width=max(30, ancho_v), fill=T.TEXTO,
                          font=(fuente, T.TAM_PEQ), tags=t)
        bajos.append((c.bbox(v) or (0, 0, 0, y + 42 * s))[3])
    alto_casilla = max(bajos) - y + 10 * s
    if ficha.nivel is not None:
        alto_casilla += 8 * s
        tx = xi + (n - 1) * (tw + hueco)
        ny = y + alto_casilla - 10 * s
        gr = max(1, round(4 * s))
        c.create_line(tx + 12 * s, ny, tx + tw - 12 * s, ny, fill=T.PISTA, width=gr, capstyle="round", tags=t)
        fin = tx + 12 * s + (tw - 24 * s) * max(0.0, min(1.0, ficha.nivel))
        if fin > tx + 12 * s + 1:
            c.create_line(tx + 12 * s, ny, fin, ny, fill=color, width=gr, capstyle="round", tags=t)
    for i in range(n):
        tx = xi + i * (tw + hueco)
        fondos.append(rect_redondo(c, tx, y, tx + tw, y + alto_casilla, 10 * s, fill=T.SUPERFICIE_2, outline="",
                                   tags=t))
        c.tag_lower(fondos[-1], primeros[i])
    y += alto_casilla
    alto = y + pad

    # --- fondo (debajo de todo lo anterior): sombra, franja de color, tarjeta y borde
    capas = []
    for k, f in enumerate((0.04, 0.07, 0.11)):
        e = (3 - k) * 2 * s
        capas.append(rect_redondo(c, x0 - e + 2 * s, -e + 5 * s, x1 + e - 2 * s, alto + e + 5 * s, r + e,
                                  fill=T.mezclar(mesa, "#000000", f), outline="", tags=t))
    capas.append(rect_redondo(c, x0, 0, x1, alto, r, fill=color, outline="", tags=t))
    capas.append(rect_redondo(c, x0 + 5 * s, 0, x1, alto, r, fill=T.SUPERFICIE, outline="", tags=t))
    capas.append(rect_redondo(c, x0, 0, x1, alto, r, fill="", outline=T.mezclar(T.BORDE, color, 0.25),
                              width=max(1, round(s)), tags=t))
    for capa in capas:
        c.tag_lower(capa, primero)
    c.move("ficha", 0, y_abajo - alto)
    return alto
