"""Escenas .json, CSV de lecturas y preferencias."""
import csv
import json
from datetime import datetime

import pytest

from duinovisor.almacenamiento import escenas, preferencias
from duinovisor.almacenamiento.exportar import escribir_csv
from duinovisor.dominio.leds import COLORES, LedConfig


def leds():
    configurados = {
        "R": LedConfig(color="R", modo="BLINK", brillo=255, on_ms=300, off_ms=100),
        "G": LedConfig(color="G", modo="FADE", brillo=200, periodo_ms=2000),
    }
    return {c: configurados.get(c, LedConfig(color=c, modo="OFF")) for c in COLORES}


# ---------------------------------------------------------------- escenas
def test_escena_ida_y_vuelta(tmp_path):
    ruta = tmp_path / "escena.json"
    escenas.guardar(ruta, leds(), 1500, (20, 30), ("VIAL", 150))
    assert escenas.cargar(ruta) == (leds(), 1500, (20, 30), ("VIAL", 150))
    escenas.guardar(ruta, leds(), 2000)
    assert escenas.cargar(ruta)[2:] == (None, None)


@pytest.mark.parametrize("cambio", [
    lambda d: d.update(version=99),
    lambda d: d["leds"].pop("G"),
    lambda d: d["leds"]["R"].update(brillo=999),
    lambda d: d["leds"]["R"].update(on_ms=5),
    lambda d: d["leds"]["R"].update(brillo="alto"),
    lambda d: d.update(dht_ms=10),
    lambda d: d.update(termo=[30, 20]),
    lambda d: d.update(termo=[1]),
    lambda d: d.update(secuencia={"nombre": "FOO", "velocidad": 100}),
    lambda d: d.update(secuencia={"nombre": "VIAL"}),
])
def test_escena_invalida_se_rechaza(cambio):
    d = escenas.a_dict(leds(), 2000, None)
    cambio(d)
    with pytest.raises(ValueError):
        escenas.de_dict(d)


def test_cargar_archivos_malos(tmp_path):
    with pytest.raises(ValueError):
        escenas.cargar(tmp_path / "no_existe.json")
    mal = tmp_path / "mal.json"
    mal.write_text("{esto no es json", encoding="utf-8")
    with pytest.raises(ValueError):
        escenas.cargar(mal)
    mal.write_text(json.dumps([1, 2]), encoding="utf-8")
    with pytest.raises(ValueError):
        escenas.cargar(mal)


# ---------------------------------------------------------------- CSV
def test_csv(tmp_path):
    ruta = tmp_path / "lecturas.csv"
    n = escribir_csv(ruta, [
        (datetime(2026, 11, 25, 10, 0, 0), 24.0, 51.0),
        (datetime(2026, 11, 25, 10, 0, 2), None, None),
    ])
    assert n == 2
    filas = list(csv.reader(ruta.read_text(encoding="utf-8-sig").splitlines()))
    assert filas == [["fecha_hora", "temperatura_c", "humedad_pct", "estado"],
                     ["2026-11-25 10:00:00", "24.0", "51.0", "ok"],
                     ["2026-11-25 10:00:02", "", "", "error de sensor"]]


# ---------------------------------------------------------------- preferencias
def test_preferencias_guardar_cargar_y_archivo_roto(tmp_path, monkeypatch):
    ruta = tmp_path / "sub" / "ajustes.json"
    monkeypatch.setenv("DUINOVISOR_AJUSTES", str(ruta))
    assert preferencias.cargar() == preferencias.POR_DEFECTO              # no existe
    assert preferencias.guardar({"tema": "oscuro", "acento": "ambar", "otra": 1})
    assert preferencias.cargar() == {"tema": "oscuro", "acento": "ambar"}
    ruta.write_text("{roto", encoding="utf-8")
    assert preferencias.cargar() == preferencias.POR_DEFECTO
    ruta.write_text('{"tema": 5}', encoding="utf-8")
    assert preferencias.cargar() == preferencias.POR_DEFECTO
