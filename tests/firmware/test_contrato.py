"""El catálogo de componentes de Python (dominio/placa.py) y las tablas del sketch deben coincidir.

No compila nada: lee el .ino como texto. Así detecta, incluso sin g++, que se añadió un LED, un pin, una
zona del termómetro o una secuencia en un lado y no en el otro.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from duinovisor.dominio.leds import BRILLO_MAX, MAX_MS, MIN_BLINK_MS, MIN_FADE_MS, MODOS
from duinovisor.dominio.placa import LEDS, PIN_DHT
from duinovisor.dominio.protocolo import MAX_DHT_MS, MIN_DHT_MS, PONG
from duinovisor.dominio.secuencias import NOMBRES_SEQ, SECUENCIAS, VEL_MAX, VEL_MIN
from duinovisor.dominio.termometro import HISTERESIS_TERMO, LUZ_DE_ZONA
from duinovisor.ui.constantes import RITMOS

RAIZ = Path(__file__).resolve().parents[2]
INO = RAIZ / "firmware" / "control_leds" / "control_leds.ino"
SKETCH = INO.read_text(encoding="utf-8")
PUENTE = RAIZ / "movil" / "pruebas" / "herramientas" / "puente.js"
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


# ------------------------------------------------ la app del celular (movil/js/catalogo.js) usa los mismos datos
@pytest.fixture(scope="module")
def catalogo_movil():
    if shutil.which("node") is None:
        pytest.skip("se necesita node")
    r = subprocess.run(["node", str(PUENTE), "catalogo"], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_movil_mismos_leds(catalogo_movil):
    assert [(x["id"], x["nombre"], x["luz"], x["color"], x["fila"]) for x in catalogo_movil["LEDS"]] == \
        [(led.id, led.nombre, led.luz, led.color, led.fila) for led in LEDS]


def test_movil_mismos_uuid_que_el_sketch(catalogo_movil):
    ble = catalogo_movil["BLE"]
    assert re.search(r'#define\s+NOMBRE_BLE\s+"([^"]+)"', SKETCH).group(1) == ble["nombre"]
    for clave, define in (("servicio", "UUID_SERVICIO"), ("rx", "UUID_RX"), ("tx", "UUID_TX")):
        assert re.search(rf'#define\s+{define}\s+"([^"]+)"', SKETCH).group(1).lower() == ble[clave]
    assert int(re.search(r"#define\s+BLE_TROZO\s+(\d+)", SKETCH).group(1)) == ble["trozo"]


def test_movil_mismos_limites(catalogo_movil):
    c = catalogo_movil
    assert c["MODOS"] == list(MODOS)
    assert (c["BRILLO_MAX"], c["MIN_BLINK_MS"], c["MIN_FADE_MS"], c["MAX_MS"]) == (BRILLO_MAX, MIN_BLINK_MS, MIN_FADE_MS, MAX_MS)
    assert (c["MIN_DHT_MS"], c["MAX_DHT_MS"], c["VEL_MIN"], c["VEL_MAX"]) == (MIN_DHT_MS, MAX_DHT_MS, VEL_MIN, VEL_MAX)
    assert c["PONG"] == PONG
    assert c["RITMOS"] == RITMOS


def test_movil_mismas_animaciones_y_semaforo(catalogo_movil):
    c = catalogo_movil
    assert {n: [[ms, b] for ms, b in pasos] for n, pasos in SECUENCIAS.items()} == c["SECUENCIAS"]
    assert c["NOMBRES_SEQ"] == NOMBRES_SEQ
    assert c["HISTERESIS_TERMO"] == HISTERESIS_TERMO
    zonas = [{k: v for k, v in z.items() if k in ("color", "modo", "brillo", "on_ms", "off_ms")} for z in c["LUZ_DE_ZONA"]]
    esperado = [{"color": z.color, "modo": z.modo, "brillo": z.brillo,
                 **({"on_ms": z.on_ms, "off_ms": z.off_ms} if z.modo == "BLINK" else {})} for z in LUZ_DE_ZONA]
    assert zonas == esperado
