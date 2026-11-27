"""Textos de las fichas de la protoboard (sin Tkinter)."""
import pytest

from duinovisor.dominio.leds import LedConfig
from duinovisor.dominio.placa import DHT, LEDS
from duinovisor.ui.fichas import FILAS, comportamiento_led, ficha_led, ficha_sensor, segundos


def test_segundos():
    assert segundos(500) == "0,5 s" and segundos(2000) == "2 s" and segundos(150) == "0,15 s"
    assert segundos(60000) == "1 min" and segundos(90000) == "90 s"


@pytest.mark.parametrize("led", LEDS, ids=lambda led: led.id)
def test_ficha_de_cada_led(led):
    cfg = LedConfig(led.id, "BLINK", 255, 500, 1000)
    f = ficha_led(led, cfg, 255, None, conectado=True)
    filas = dict(f.filas)
    assert tuple(filas) == FILAS and led.luz in f.titulo and f.que_es
    assert f"Pin {led.pin}" in filas["Conectado a"]
    assert filas["Qué hace"] == "Parpadea: 0,5 s encendida y 1 s apagada, al 100 %"
    assert filas["Ahora"] == "Encendida al 100 %"
    assert dict(ficha_led(led, cfg, 0, None, True).filas)["Ahora"] == "Apagada"


def test_comportamiento_de_cada_modo():
    c = LEDS[0].id
    assert comportamiento_led(None) == comportamiento_led(LedConfig(c, "OFF")) == "Está apagada"
    assert comportamiento_led(LedConfig(c, "ON", 128)) == "Encendida fija al 50 %"
    assert "cada 2 s" in comportamiento_led(LedConfig(c, "FADE", 255, periodo_ms=2000))


def test_led_automatico_o_sin_conexion():
    led = LEDS[0]
    f = dict(ficha_led(led, None, 200, "Lo controla la animación «Semáforo vial»", True).filas)
    assert f["Qué hace"].startswith("Lo controla la animación") and f["Ahora"] == "Encendida al 78 %"
    f = dict(ficha_led(led, LedConfig(led.id, "ON"), 255, None, conectado=False).filas)
    assert "no hay conexión" in f["Qué hace"] and f["Ahora"] == "Apagada"


def test_ficha_del_sensor():
    f = ficha_sensor(DHT, 2000, (24.5, 51.0), True)
    filas = dict(f.filas)
    assert tuple(filas) == FILAS and DHT.nombre in f.titulo and f.que_es == DHT.descripcion
    assert f"pin {DHT.pin}" in filas["Conectado a"] and filas["Qué hace"] == "Mide cada 2 s"
    assert filas["Ahora"] == "24.5 °C y 51 % de humedad"
    assert dict(ficha_sensor(DHT, 2000, None, True).filas)["Ahora"] == "Esperando la primera lectura"
    assert "No responde" in dict(ficha_sensor(DHT, 2000, (None, None), True).filas)["Ahora"]
    assert "Sin conexión" in dict(ficha_sensor(DHT, None, None, False).filas)["Ahora"]
