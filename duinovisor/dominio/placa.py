"""Componentes conectados a la placa: la única lista de LEDs y sensores de DuinoVisor.

El resto del programa (protocolo, secuencias, simulador, ventana, escenas) se arma a partir de esta lista; no
hay que repetir los LEDs en ningún otro sitio de Python.

Debe coincidir con firmware/control_leds/control_leds.ino: la tabla `leds[]` (mismo orden, letra y pin) y
`PIN_DHT`. Lo comprueba tests/firmware/test_contrato.py.

Para añadir un LED: una entrada en LEDS y una línea en `leds[]` del sketch, en un pin con PWM
(en el Arduino 101 solo 3, 5, 6 y 9). Las secuencias que no lo nombran lo dejan apagado.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Led:
    id: str          # letra del protocolo: «LED <id> ON 128»
    nombre: str      # para mensajes: «LED Rojo: ...»
    luz: str         # para la ventana: «Luz roja»
    pin: int         # pin con PWM
    color: str       # color del LED real (#rrggbb), para dibujarlo igual
    fila: int        # posición de arriba abajo en el semáforo y en los chips


@dataclass(frozen=True)
class Sensor:
    id: str
    nombre: str
    pin: int             # pin de datos
    descripcion: str = ""   # qué es, en lenguaje llano (para su ficha en la protoboard)
    alimentacion: str = "5V"


# En el mismo orden que `leds[]` del sketch (es el orden de STATUS y de las columnas de sus secuencias).
LEDS: tuple[Led, ...] = (
    Led("R", "Rojo", "Luz roja", pin=3, color="#e5533d", fila=0),
    Led("G", "Verde", "Luz verde", pin=5, color="#4fbf5f", fila=2),
    Led("Y", "Amarillo", "Luz amarilla", pin=6, color="#f2c14e", fila=1),
)
DHT = Sensor("DHT", "DHT11", pin=2,
             descripcion="Un sensor que mide la temperatura (de 0 a 50 °C, con unos 2 °C de margen) y la "
                         "humedad del aire (de 20 a 90 %). Envía las dos medidas por un solo cable de datos.")
SENSORES: tuple[Sensor, ...] = (DHT,)

RESISTENCIA_LED = "220 Ω"
RESISTENCIA_DHT = "10 kΩ"           # pull-up entre DATA y 5V

# Atajos derivados de la lista
PINES = {led.id: led.pin for led in LEDS}
PIN_DHT = DHT.pin
_POR_ID = {led.id: led for led in LEDS}


_SENSOR_POR_ID = {s.id: s for s in SENSORES}


def led(id_: str) -> Led:
    """Definición del LED con esa letra (KeyError si no existe)."""
    return _POR_ID[id_]


def sensor(id_: str) -> Sensor:
    """Definición del sensor con ese id (KeyError si no existe)."""
    return _SENSOR_POR_ID[id_]
