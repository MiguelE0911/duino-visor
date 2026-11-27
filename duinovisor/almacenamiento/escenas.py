"""Guardar y cargar escenas: la configuración de los 3 LEDs, el sensor y el semáforo en un .json."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from duinovisor.dominio.leds import COLORES, NOMBRES_COLOR, LedConfig, errores
from duinovisor.dominio.protocolo import comando_dht, comando_termo
from duinovisor.dominio.secuencias import paso_seq_iniciar

VERSION = 1
CAMPOS_LED = ("modo", "brillo", "on_ms", "off_ms", "periodo_ms")


def a_dict(leds: dict, dht_ms: int, termo: Optional[tuple[int, int]],
           secuencia: Optional[tuple[str, int]] = None) -> dict:
    return {
        "version": VERSION,
        "leds": {c: {k: getattr(leds[c], k) for k in CAMPOS_LED} for c in COLORES},
        "dht_ms": dht_ms,
        "termo": list(termo) if termo else None,
        "secuencia": {"nombre": secuencia[0], "velocidad": secuencia[1]} if secuencia else None,
    }


def _entero(valor, nombre: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ValueError(f"«{nombre}» debe ser un número entero")
    return valor


def de_dict(d) -> tuple[dict, int, Optional[tuple[int, int]], Optional[tuple[str, int]]]:
    """Valida y convierte un dict leído de un .json. Lanza ValueError con un mensaje claro."""
    if not isinstance(d, dict) or d.get("version") != VERSION:
        raise ValueError("el archivo no es una escena de DuinoVisor (o es de otra versión)")
    leds = {}
    for c in COLORES:
        try:
            datos = d["leds"][c]
            cfg = LedConfig(color=c, **{k: (datos[k] if k == "modo" else _entero(datos[k], k)) for k in CAMPOS_LED})
        except (KeyError, TypeError):
            raise ValueError(f"falta o está mal la configuración del LED {NOMBRES_COLOR[c]}")
        problemas = errores(cfg)
        if problemas:
            raise ValueError(f"LED {NOMBRES_COLOR[c]}: " + "; ".join(problemas))
        leds[c] = cfg
    dht_ms = _entero(d.get("dht_ms"), "dht_ms")
    comando_dht(dht_ms)
    termo = d.get("termo")
    if termo is not None:
        if not (isinstance(termo, list) and len(termo) == 2):
            raise ValueError("«termo» debe ser [tmin, tmax] o null")
        termo = (_entero(termo[0], "tmin"), _entero(termo[1], "tmax"))
        comando_termo(termo)
    sec = d.get("secuencia")
    if sec is not None:
        try:
            sec = (sec["nombre"], _entero(sec["velocidad"], "velocidad"))
        except (KeyError, TypeError):
            raise ValueError("«secuencia» debe tener nombre y velocidad")
        paso_seq_iniciar(*sec)                       # valida nombre y velocidad
    return leds, dht_ms, termo, sec


def guardar(ruta, leds: dict, dht_ms: int, termo=None, secuencia=None) -> None:
    Path(ruta).write_text(json.dumps(a_dict(leds, dht_ms, termo, secuencia), indent=2, ensure_ascii=False),
                          encoding="utf-8")


def cargar(ruta):
    try:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as e:
        raise ValueError(f"no se pudo leer el archivo: {e}")
    except json.JSONDecodeError:
        raise ValueError("el archivo no es un JSON válido")
    return de_dict(datos)
