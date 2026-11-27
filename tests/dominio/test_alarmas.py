import pytest

from duinovisor.dominio.alarmas import Alarma


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
