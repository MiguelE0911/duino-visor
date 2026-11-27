"""Protocolo serie de DuinoVisor: órdenes, respuestas y qué enviar al pulsar «Aplicar».

Es el contrato entre la app y el sketch (firmware/control_leds/control_leds.ino). Funciones puras.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Optional

from duinovisor.dominio.leds import COLORES, LedConfig, errores

MIN_DHT_MS = 1000
MAX_DHT_MS = 3_600_000

PONG = "PONG OAC-LEDS"


# ----------------------------------------------------------------------
# Construcción de órdenes
# ----------------------------------------------------------------------
def comando_led(cfg: LedConfig) -> str:
    e = errores(cfg)
    if e:
        raise ValueError("; ".join(e))
    if cfg.modo == "OFF":
        return f"LED {cfg.color} OFF"
    if cfg.modo == "ON":
        return f"LED {cfg.color} ON {cfg.brillo}"
    if cfg.modo == "BLINK":
        return f"LED {cfg.color} BLINK {cfg.brillo} {cfg.on_ms} {cfg.off_ms}"
    return f"LED {cfg.color} FADE {cfg.brillo} {cfg.periodo_ms}"


def comando_dht(periodo_ms: int) -> str:
    if not MIN_DHT_MS <= periodo_ms <= MAX_DHT_MS:
        raise ValueError(f"el periodo del sensor debe estar entre {MIN_DHT_MS} y {MAX_DHT_MS} ms")
    return f"DHT {periodo_ms}"


def comando_termo(termo: Optional[tuple[int, int]]) -> str:
    if termo is None:
        return "TERMO OFF"
    t_min, t_max = termo
    if t_min >= t_max:
        raise ValueError("la temperatura mínima debe ser menor que la máxima")
    return f"TERMO {t_min} {t_max}"


# ----------------------------------------------------------------------
# Interpretar líneas que llegan del Arduino
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Mensaje:
    tipo: str                       # PONG, DATA, DATA_ERR, OK, ERR, STATE, OTRO
    texto: str = ""                 # resto de la línea
    temperatura: Optional[float] = None
    humedad: Optional[float] = None


def interpretar(linea: str) -> Mensaje:
    linea = linea.strip()
    if linea.startswith(PONG):
        return Mensaje("PONG", linea)
    if linea == "DATA ERR":
        return Mensaje("DATA_ERR", linea)
    if linea.startswith("DATA "):
        try:
            campos = dict(p.split("=", 1) for p in linea[5:].split())
            return Mensaje("DATA", linea, float(campos["T"]), float(campos["H"]))
        except (KeyError, ValueError):
            return Mensaje("OTRO", linea)
    if linea == "OK" or linea.startswith("OK "):
        return Mensaje("OK", linea[3:])
    if linea == "ERR" or linea.startswith("ERR "):
        return Mensaje("ERR", linea[4:])
    if linea.startswith("STATE "):
        return Mensaje("STATE", linea[6:])
    return Mensaje("OTRO", linea)


def es_pong(linea: str) -> bool:
    return interpretar(linea).tipo == "PONG"


# ----------------------------------------------------------------------
# Qué enviar al pulsar "Aplicar"
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Aplicado:
    """Lo que el Arduino tiene confirmado (con OK) hasta ahora."""
    leds: dict = field(default_factory=dict)          # color -> LedConfig
    dht_ms: Optional[int] = None
    termo: Optional[tuple[int, int]] = None           # None = semáforo apagado
    seq: Optional[tuple[str, int, bool]] = None       # (nombre, velocidad %, en pausa) o None


@dataclass(frozen=True)
class Paso:
    texto: str                      # la orden a enviar
    clave: str                      # "led", "dht", "termo" o "seq"
    color: Optional[str] = None
    valor: Any = None


def cambios(nuevos: dict, aplicados: dict) -> list[tuple[str, str]]:
    """Órdenes (color, texto) solo de los LEDs que cambiaron o que no se conocen aún."""
    salida = []
    for color in COLORES:
        if color in nuevos and nuevos[color] != aplicados.get(color):
            salida.append((color, comando_led(nuevos[color])))
    return salida


def plan(leds: dict, dht_ms: int, termo: Optional[tuple[int, int]], aplicado: Aplicado) -> list[Paso]:
    """Pasos necesarios para llevar al Arduino a la configuración pedida.

    Valida todo antes de devolver nada: si algo es inválido lanza ValueError y no se envía nada.
    Con el semáforo térmico activo, los LEDs los gobierna el Arduino y no se envían.
    """
    comando_dht(dht_ms)
    comando_termo(termo)
    pasos: list[Paso] = []
    if termo is not None:
        if dht_ms != aplicado.dht_ms:
            pasos.append(Paso(comando_dht(dht_ms), "dht", valor=dht_ms))
        if termo != aplicado.termo:
            pasos.append(Paso(comando_termo(termo), "termo", valor=termo))
        return pasos

    previos = aplicado.leds
    if aplicado.termo is not None:                    # salir de TERMO deja los LEDs apagados
        pasos.append(Paso("TERMO OFF", "termo", valor=None))
        previos = {}
    for color, texto in cambios(leds, previos):
        pasos.append(Paso(texto, "led", color, leds[color]))
    if dht_ms != aplicado.dht_ms:
        pasos.append(Paso(comando_dht(dht_ms), "dht", valor=dht_ms))
    return pasos


def confirmar(aplicado: Aplicado, paso: Paso) -> Aplicado:
    """Nuevo estado aplicado después de que el Arduino respondió OK a un paso."""
    if paso.clave == "led":                            # una orden manual cancela secuencia y semáforo
        return replace(aplicado, leds={**aplicado.leds, paso.color: paso.valor}, seq=None)
    if paso.clave == "dht":
        return replace(aplicado, dht_ms=paso.valor)
    if paso.clave == "seq":                            # el Arduino toma los LEDs y cancela el semáforo
        return replace(aplicado, seq=paso.valor, termo=None, leds={})
    # termo: al entrar o salir, el Arduino cambia los LEDs por su cuenta y cancela la secuencia
    return replace(aplicado, termo=paso.valor, leds={}, seq=None)
