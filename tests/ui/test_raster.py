"""Dibujo con Pillow de la protoboard (sin Tkinter): el adaptador tipo Canvas, la mesa y los LEDs."""
import pytest

pytest.importorskip("PIL")

from duinovisor.ui import tema as T  # noqa: E402
from duinovisor.ui.widgets import dibujo_placa as D  # noqa: E402
from duinovisor.ui.widgets import raster  # noqa: E402
from duinovisor.ui.widgets.base import rect_redondo  # noqa: E402


def test_lienzo_imagen_dibuja_donde_toca():
    lienzo = raster.LienzoImagen(200, 100, z=2.0, origen=(10, 20), escala_letra=1.0)
    lienzo.create_rectangle(0, 0, 10, 10, fill="#ff0000")              # virtual (0..10) -> pantalla (10..30, 20..40)
    lienzo.create_oval(50, 20, 60, 30, fill="#00ff00", state="hidden")  # oculto: no se pinta
    rect_redondo(lienzo, 60, 0, 90, 20, 5, fill="#0000ff")             # usa el rectángulo redondeado nativo
    lienzo.create_text(20, 30, text="Hola", fill="#000000", font=("Arial", 9))
    lienzo.create_text(80, 35, text="GND", fill="#000000", font=("Arial", 7), angle=90, anchor="e")
    img = lienzo.imagen()
    assert img.size == (200, 100)
    assert img.getpixel((20, 30))[:3] == (255, 0, 0)
    assert img.getpixel((5, 5))[3] == 0                                 # fuera de todo: transparente
    assert img.getpixel((150, 40))[:3] == (0, 0, 255)                   # dentro del redondeado
    assert img.getpixel((130, 60))[3] == 0                              # donde iría el óvalo oculto


def test_el_montaje_entero_se_dibuja_en_imagen():
    z = 0.5
    lienzo = raster.LienzoImagen(D.ESCENA[0] * z, D.ESCENA[1] * z, z, (0, 0), 1.0)
    p = D.Pincel(lienzo, z, "Arial", 1.0, T.SUPERFICIE_2)
    D.placa_arduino(p, {"3", "5", "6", "2", "5V"})
    D.protoboard(p)
    img = lienzo.imagen()
    x, y = int(100 * z), int(200 * z)                                   # dentro de la placa: opaco y verdoso
    r, g, b, a = img.getpixel((x, y))
    assert a == 255 and g > r


def test_mesa_y_sprite_de_led():
    mesa = raster.mesa(120, 80, "#f1f3f6", "#8a929c", 20, 1.5)
    assert mesa.size == (120, 80) and mesa.getpixel((10, 10)) != mesa.getpixel((1, 1))   # hay puntos
    apagado, mitad = raster.sprite_led("#e5533d", 0.0, 1.0, D.R_LED, D.EXTRA_LUZ)
    encendido, _ = raster.sprite_led("#e5533d", 1.0, 1.0, D.R_LED, D.EXTRA_LUZ)
    assert apagado.size == encendido.size and mitad == pytest.approx(apagado.width / 2, abs=1)
    borde = (int(mitad - D.R_LED - 12), int(mitad))                     # fuera de la cúpula: solo el resplandor
    assert apagado.getpixel(borde)[3] == 0 and encendido.getpixel(borde)[3] > 0
