"""calcular_puntos no necesita Tkinter: se prueba en cualquier equipo."""
from duinovisor.ui.widgets.grafica import calcular_puntos


def test_grafica_puntos():
    m = (10, 10, 10, 10)
    seg = calcular_puntos([0, 50], 120, 120, 0, 50, m, capacidad=2)
    assert seg == [[(10.0, 110.0), (110.0, 10.0)]]
    assert len(calcular_puntos([1, None, 3], 120, 120, 0, 50, m, capacidad=3)) == 2   # el hueco corta la línea
    ultimo = calcular_puntos([5], 120, 120, 0, 50, m, capacidad=60)[0][0]
    assert ultimo[0] == 110.0                                                           # alineada a la derecha
