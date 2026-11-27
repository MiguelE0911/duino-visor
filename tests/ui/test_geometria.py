"""Cuentas de dibujo de la protoboard: curvas, degradados, encaje y zoom (no necesitan Tkinter)."""
import pytest

from duinovisor.ui.widgets.geometria import (
    bandas,
    curva_suave,
    encaje,
    limitar_origen,
    longitud,
    origen_centrado,
    punto_en,
    suavizar,
    zoom_en_punto,
)

ESCENA = (800, 340)


def test_curva_suave_va_de_extremo_a_extremo_dentro_de_sus_puntos():
    puntos = [(0, 0), (50, 100), (100, 0), (150, 80)]
    curva = curva_suave(puntos, 8)
    assert curva[0] == puntos[0] and curva[-1] == pytest.approx(puntos[-1])
    xs, ys = [x for x, _ in curva], [y for _, y in curva]
    assert min(xs) >= 0 and max(xs) <= 150 and min(ys) >= 0 and max(ys) <= 100     # dentro del casco
    assert curva_suave([(0, 0), (10, 10)]) == [(0, 0), (10, 10)]                      # dos puntos: recta


def test_punto_en_recorre_la_polilinea_por_su_largo():
    linea = [(0, 0), (10, 0), (10, 10)]
    assert longitud(linea) == 20
    assert punto_en(linea, 0) == (0, 0) and punto_en(linea, 1) == (10, 10)
    assert punto_en(linea, 0.25) == pytest.approx((5, 0)) and punto_en(linea, 0.75) == pytest.approx((10, 5))


def test_bandas_cubren_todo_sin_huecos():
    franjas = bandas(10, 70, 6)
    assert franjas[0][0] == 10 and franjas[-1][1] == pytest.approx(70)
    assert all(a[1] == pytest.approx(b[0]) for a, b in zip(franjas, franjas[1:]))
    assert franjas[0][2] == 0 and franjas[-1][2] == 1


def test_encaje_y_centrado_en_una_vista_con_margenes():
    vista = (10, 50, 810, 390)                       # 800 x 340: el montaje cabe justo con zoom 1
    assert encaje(vista, ESCENA) == pytest.approx(1)
    assert origen_centrado(vista, 1, ESCENA) == pytest.approx((10, 50))
    assert origen_centrado(vista, 0.5, ESCENA) == pytest.approx((210, 135))


def test_zoom_mantiene_quieto_el_punto_bajo_el_raton():
    origen = origen_centrado((0, 0, 800, 400), 1.0, ESCENA)
    px, py = 300, 120
    nuevo = zoom_en_punto(px, py, 1.0, 2.0, origen)
    vx, vy = px - origen[0], py - origen[1]
    assert (nuevo[0] + vx * 2.0, nuevo[1] + vy * 2.0) == pytest.approx((px, py))
    assert zoom_en_punto(px, py, 2.0, 1.0, nuevo) == pytest.approx(origen)      # y se puede deshacer


def test_limitar_centra_si_cabe_y_no_deja_huecos_si_no():
    vista = (20, 40, 820, 440)
    assert limitar_origen((123, -50), vista, 0.5, ESCENA) == origen_centrado(vista, 0.5, ESCENA)
    z = 3.0
    assert limitar_origen((500, 400), vista, z, ESCENA) == (20, 40)               # sin hueco arriba a la izquierda
    assert limitar_origen((-1e6, -1e6), vista, z, ESCENA) == (820 - 800 * z, 440 - 340 * z)
    assert limitar_origen((-100, -100), vista, z, ESCENA) == (-100, -100)


def test_suavizar():
    assert suavizar(0) == 0 and suavizar(1) == 1 and suavizar(2) == 1
    assert 0.5 < suavizar(0.5) < 1                                                # ease-out: va rápido al principio
