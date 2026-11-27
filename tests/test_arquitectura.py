"""Hace cumplir las capas: cada una solo puede importar de las capas interiores.

    dominio  <-  hardware, almacenamiento  <-  ui  <-  __main__

Si esta prueba falla, la dependencia va en el sentido equivocado: mueve el código a la capa correcta
(ver docs/ARQUITECTURA.md) en lugar de añadir una excepción.
"""
import ast
from pathlib import Path

import pytest

PAQUETE = Path(__file__).resolve().parent.parent / "duinovisor"

PERMITIDAS = {
    "dominio": {"dominio"},
    "hardware": {"dominio", "hardware"},
    "almacenamiento": {"dominio", "almacenamiento"},
    "ui": {"dominio", "hardware", "almacenamiento", "ui"},
}
# Bibliotecas externas que cada capa no debe tocar.
PROHIBIDAS = {
    "dominio": {"tkinter", "serial", "json", "csv", "os", "threading"},
    "hardware": {"tkinter"},
    "almacenamiento": {"tkinter", "serial"},
}


def imports(ruta: Path) -> set[str]:
    salida = set()
    for n in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Import):
            salida |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
            salida.add(n.module)
    return salida


def modulos(capa: str):
    return sorted((PAQUETE / capa).rglob("*.py"))


@pytest.mark.parametrize("capa", sorted(PERMITIDAS))
def test_cada_capa_solo_importa_capas_interiores(capa):
    malos = []
    for ruta in modulos(capa):
        for mod in imports(ruta):
            partes = mod.split(".")
            if partes[0] == "duinovisor" and len(partes) > 1 and partes[1] not in PERMITIDAS[capa]:
                malos.append(f"{ruta.relative_to(PAQUETE)} importa {mod}")
            if partes[0] in PROHIBIDAS.get(capa, ()):
                malos.append(f"{ruta.relative_to(PAQUETE)} usa {mod}")
    assert not malos, "\n".join(malos)


def test_todas_las_carpetas_son_capas_conocidas():
    carpetas = {p.name for p in PAQUETE.iterdir() if p.is_dir() and p.name != "__pycache__"}
    assert carpetas == set(PERMITIDAS), "capa nueva: añádela a PERMITIDAS y a docs/ARQUITECTURA.md"
