import csv
import json
from datetime import datetime

import pytest

import escenas
import protocol as P
from alarmas import Alarma
from exportar import escribir_csv


def leds():
    return {
        "R": P.LedConfig(color="R", modo="BLINK", brillo=255, on_ms=300, off_ms=100),
        "G": P.LedConfig(color="G", modo="FADE", brillo=200, periodo_ms=2000),
        "Y": P.LedConfig(color="Y", modo="OFF"),
    }


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


# ---------------------------------------------------------------- alarmas
def test_alarma_maxima_con_histeresis():
    a = Alarma("Humedad", " %", maximo=80, histeresis=2)
    assert a.evaluar(79) is None and not a.activa
    assert a.evaluar(81) == "ACTIVA" and a.activa and "81" in a.motivo and "80" in a.motivo
    assert a.evaluar(90) is None                                  # ya estaba activa: no repite el aviso
    assert a.evaluar(79) is None and a.activa                     # aún no baja lo suficiente
    assert a.evaluar(78) == "RESUELTA" and not a.activa


def test_alarma_minima_y_lecturas_fallidas():
    a = Alarma("Temperatura", " °C", maximo=35, minimo=10, histeresis=1)
    assert a.evaluar(None) is None
    assert a.evaluar(9) == "ACTIVA" and "bajo el mínimo" in a.motivo
    assert a.evaluar(None) is None and a.activa                   # un fallo del sensor no apaga la alarma
    assert a.evaluar(10.5) is None
    assert a.evaluar(11) == "RESUELTA"


def test_alarma_valida_umbrales_y_se_reinicia():
    with pytest.raises(ValueError):
        Alarma("x", "", maximo=10, minimo=20)
    a = Alarma("x", "", maximo=10)
    a.evaluar(11)
    a.reiniciar()
    assert not a.activa and a.evaluar(11) == "ACTIVA"


# ---------------------------------------------------------------- tema
def test_tema_mezclar_y_fuente():
    import tema as T
    assert T.mezclar("#000000", "#ffffff", 0) == "#000000"
    assert T.mezclar("#000000", "#ffffff", 1) == "#ffffff"
    assert T.mezclar("#000000", "#ffffff", 0.5) == "#808080"
    assert T.mezclar("#102030", "#ffffff", 5) == "#ffffff"                 # f se limita a 0..1
    assert T.elegir_fuente(["Arial", "DejaVu Sans"]) == "DejaVu Sans"      # respeta el orden de preferencia
    assert T.elegir_fuente(["Comic Sans"]) == "Helvetica"
    assert T.elegir_fuente(["segoe ui"]) == "Segoe UI"


def test_tema_aplicar_paletas_y_acentos():
    import tema as T
    try:
        T.aplicar("oscuro", "verde")
        assert T.FONDO == T.PALETAS["oscuro"]["FONDO"] and T.ACENTO == T.ACENTOS["verde"][2]
        T.aplicar("claro", "rosa")
        assert T.SUPERFICIE == "#ffffff" and T.ACENTO == T.ACENTOS["rosa"][1]
        T.aplicar("inventado", "nada")                                    # valores raros: los de por defecto
        assert (T.tema_actual, T.acento_actual) == (T.TEMA_POR_DEFECTO, T.ACENTO_POR_DEFECTO)
    finally:
        T.aplicar()


# ---------------------------------------------------------------- preferencias
def test_preferencias_guardar_cargar_y_archivo_roto(tmp_path, monkeypatch):
    import preferencias
    ruta = tmp_path / "sub" / "ajustes.json"
    monkeypatch.setenv("DUINOVISOR_AJUSTES", str(ruta))
    assert preferencias.cargar() == preferencias.POR_DEFECTO              # no existe
    assert preferencias.guardar({"tema": "oscuro", "acento": "ambar", "otra": 1})
    assert preferencias.cargar() == {"tema": "oscuro", "acento": "ambar"}
    ruta.write_text("{roto", encoding="utf-8")
    assert preferencias.cargar() == preferencias.POR_DEFECTO
    ruta.write_text('{"tema": 5}', encoding="utf-8")
    assert preferencias.cargar() == preferencias.POR_DEFECTO
