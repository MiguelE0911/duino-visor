"""El catálogo de componentes de Python (dominio/placa.py) y las tablas del sketch deben coincidir.

No compila nada: lee el .ino como texto. Así detecta, incluso sin g++, que se añadió un LED, un pin, una
zona del termómetro o una secuencia en un lado y no en el otro.
"""
import re
from pathlib import Path

from duinovisor.dominio.placa import LEDS, PIN_DHT
from duinovisor.dominio.secuencias import SECUENCIAS
from duinovisor.dominio.termometro import LUZ_DE_ZONA

INO = Path(__file__).resolve().parents[2] / "firmware" / "control_leds" / "control_leds.ino"
SKETCH = INO.read_text(encoding="utf-8")
MODO = {"M_OFF": "OFF", "M_ON": "ON", "M_BLINK": "BLINK", "M_FADE": "FADE"}


def bloque(inicio: str) -> str:
    """Texto entre la llave que sigue a `inicio` y su `};`."""
    i = SKETCH.index(inicio)
    return SKETCH[SKETCH.index("{", i): SKETCH.index("};", i)]


def test_leds_mismo_orden_letra_y_pin():
    tabla = re.findall(r"\{\s*'(\w)',\s*(\d+),", bloque("Led leds[] ="))
    assert tabla == [(led.id, str(led.pin)) for led in LEDS]


def test_pin_del_dht():
    assert int(re.search(r"#define\s+PIN_DHT\s+(\d+)", SKETCH).group(1)) == PIN_DHT


def test_zonas_del_termometro():
    tabla = re.findall(r"\{\s*'(\w)',\s*(M_\w+)\s*\}", bloque("const DefZona ZONAS_TERMO[] ="))
    assert [(c, MODO[m]) for c, m in tabla] == [(z.color, z.modo) for z in LUZ_DE_ZONA]


def test_secuencias_mismos_pasos():
    nombres = re.findall(r'\{\s*"(\w+)",\s*(\w+),', bloque("const DefSeq SECUENCIAS[] ="))
    assert [n for n, _ in nombres] == list(SECUENCIAS)
    for nombre, tabla in nombres:
        pasos = re.findall(r"\{\{([\d,\s]*)\},\s*(\d+)\}", bloque(f"const PasoSeq {tabla}[]"))
        en_sketch = []
        for brillos, ms in pasos:
            valores = [int(v) for v in brillos.split(",") if v.strip()]
            valores += [0] * (len(LEDS) - len(valores))              # las columnas que faltan valen 0
            en_sketch.append((int(ms), {led.id: v for led, v in zip(LEDS, valores) if v}))
        esperado = [(ms, {c: b for c, b in brillos.items() if b}) for ms, brillos in SECUENCIAS[nombre]]
        assert en_sketch == esperado, nombre
