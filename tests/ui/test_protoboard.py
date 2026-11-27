"""Cuentas del zoom y el desplazamiento de la protoboard (no necesitan Tkinter)."""
import pytest

from duinovisor.ui.widgets.protoboard import ALTO, ANCHO, limitar_origen, origen_centrado, zoom_en_punto


def test_zoom_mantiene_quieto_el_punto_bajo_el_raton():
    origen = origen_centrado(800, 400, 1.0)
    px, py = 300, 120
    nuevo = zoom_en_punto(px, py, 1.0, 2.0, origen)
    # el punto del montaje que estaba bajo el ratón sigue en el mismo sitio de la pantalla
    vx, vy = (px - origen[0]) / 1.0, (py - origen[1]) / 1.0
    assert (nuevo[0] + vx * 2.0, nuevo[1] + vy * 2.0) == pytest.approx((px, py))
    assert zoom_en_punto(px, py, 2.0, 1.0, nuevo) == pytest.approx(origen)      # y se puede deshacer


def test_limitar_centra_si_cabe_y_no_deja_huecos_si_no():
    w, h = 800, 400
    assert limitar_origen((123, -50), w, h, 0.5) == origen_centrado(w, h, 0.5)   # cabe entero: centrado
    z = 3.0                                                                       # mucho más grande que la vista
    assert limitar_origen((50, 40), w, h, z) == (0, 0)                           # no se ve hueco a la izquierda
    assert limitar_origen((-1e6, -1e6), w, h, z) == (w - ANCHO * z, h - ALTO * z)
    assert limitar_origen((-100, -100), w, h, z) == (-100, -100)                 # dentro de los límites: igual
