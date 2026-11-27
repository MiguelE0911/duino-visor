"""Las cuentas de la gota de humedad no necesitan Tkinter: se prueban en cualquier equipo."""
import math

import pytest

from duinovisor.ui.widgets.indicadores import contorno_gota, recortar_bajo


def area(puntos):
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(puntos, puntos[1:] + puntos[:1]))) / 2


def test_contorno_de_la_gota():
    pts = contorno_gota(100, 100, 40)
    assert pts[0] == (100, 20)                                           # la punta, a 2r por encima
    assert max(y for _, y in pts) == pytest.approx(140)                  # el fondo del círculo
    assert min(x for x, _ in pts) == pytest.approx(60) and max(x for x, _ in pts) == pytest.approx(140)


def test_recortar_vacia_llena_y_a_medias():
    pts = contorno_gota(100, 100, 40)
    assert recortar_bajo(pts, 141) == []                                 # nivel bajo el fondo: vacía
    assert recortar_bajo(pts, 19) == pts                                 # nivel sobre la punta: llena
    mitad = recortar_bajo(pts, 100)                                      # media gota: la mitad del círculo
    assert min(y for _, y in mitad) == pytest.approx(100)
    assert area(mitad) == pytest.approx(math.pi * 40 ** 2 / 2, rel=0.01)


def test_recortar_un_cuadrado():
    cuadrado = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert area(recortar_bajo(cuadrado, 4)) == pytest.approx(60)
    assert recortar_bajo([], 5) == []
