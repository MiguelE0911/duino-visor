"""Protocolo serial de DuinoVisor: funciones puras, sin puerto serie ni interfaz.

Es el contrato entre la app y el sketch (control_leds.ino).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Optional

COLORES = ("R", "G", "Y")
NOMBRES_COLOR = {"R": "Rojo", "G": "Verde", "Y": "Amarillo"}
MODOS = ("OFF", "ON", "BLINK", "FADE")

BRILLO_MAX = 255
MIN_BLINK_MS = 20
MIN_FADE_MS = 200
MIN_DHT_MS = 1000
MAX_MS = 60000
MAX_DHT_MS = 3_600_000

PONG = "PONG OAC-LEDS"


@dataclass(frozen=True)
class LedConfig:
    color: str = "R"
    modo: str = "OFF"
    brillo: int = 255
    on_ms: int = 500
    off_ms: int = 500
    periodo_ms: int = 2000


# ----------------------------------------------------------------------
# Validación y construcción de órdenes
# ----------------------------------------------------------------------
def errores(cfg: LedConfig) -> list[str]:
    """Lista de problemas de una configuración (vacía si es válida)."""
    e = []
    if cfg.color not in COLORES:
        e.append(f"color inválido: {cfg.color!r}")
    if cfg.modo not in MODOS:
        e.append(f"modo inválido: {cfg.modo!r}")
        return e
    if cfg.modo != "OFF" and not 0 <= cfg.brillo <= BRILLO_MAX:
        e.append(f"brillo debe estar entre 0 y {BRILLO_MAX}")
    if cfg.modo == "BLINK":
        for nombre, v in (("tiempo encendido", cfg.on_ms), ("tiempo apagado", cfg.off_ms)):
            if not MIN_BLINK_MS <= v <= MAX_MS:
                e.append(f"{nombre} debe estar entre {MIN_BLINK_MS} y {MAX_MS} ms")
    if cfg.modo == "FADE" and not MIN_FADE_MS <= cfg.periodo_ms <= MAX_MS:
        e.append(f"periodo debe estar entre {MIN_FADE_MS} y {MAX_MS} ms")
    return e


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


# ----------------------------------------------------------------------
# Secuencias (SEQ): misma tabla que el sketch, para espejarlas en la app
# ----------------------------------------------------------------------
# Cada paso: (rojo, verde, amarillo, duración en ms)
SECUENCIAS: dict[str, list[tuple[int, int, int, int]]] = {
    "VIAL": [(0, 255, 0, 5000), (0, 0, 255, 1500), (255, 0, 0, 5000)],
    "FANTASTICO": [(255, 0, 0, 150), (0, 0, 255, 150), (0, 255, 0, 150), (0, 0, 255, 150)],
    "ALERTA": [(0, 0, 255, 500), (0, 0, 0, 500)],
}
NOMBRES_SEQ = {"VIAL": "Semáforo vial", "FANTASTICO": "Auto fantástico", "ALERTA": "Alerta amarilla"}
VEL_MIN, VEL_MAX = 25, 400
MIN_PASO_MS = 20


def duracion_paso(ms: int, vel: int) -> int:
    return max(MIN_PASO_MS, ms * 100 // vel)


def _validar_seq(nombre: str, vel: int) -> None:
    if nombre not in SECUENCIAS:
        raise ValueError(f"secuencia desconocida: {nombre!r}")
    if not VEL_MIN <= vel <= VEL_MAX:
        raise ValueError(f"la velocidad debe estar entre {VEL_MIN} y {VEL_MAX} %")


def paso_seq_iniciar(nombre: str, vel: int = 100) -> Paso:
    _validar_seq(nombre, vel)
    texto = f"SEQ {nombre}" if vel == 100 else f"SEQ {nombre} {vel}"
    return Paso(texto, "seq", valor=(nombre, vel, False))


def paso_seq_detener() -> Paso:
    return Paso("SEQ OFF", "seq", valor=None)


def paso_seq_pausa(actual: tuple[str, int, bool]) -> Paso:
    return Paso("SEQ PAUSA", "seq", valor=(actual[0], actual[1], True))


def paso_seq_seguir(actual: tuple[str, int, bool]) -> Paso:
    return Paso("SEQ SEGUIR", "seq", valor=(actual[0], actual[1], False))


class SecuenciaLocal:
    """Copia local de la secuencia que corre en el Arduino. Todos los tiempos en ms."""

    def __init__(self):
        self.nombre: Optional[str] = None
        self.vel = 100
        self._inicio = 0.0
        self._congelado: Optional[float] = None

    @property
    def activa(self) -> bool:
        return self.nombre is not None

    @property
    def pausada(self) -> bool:
        return self.activa and self._congelado is not None

    def iniciar(self, nombre: str, vel: int, t_ms: float) -> None:
        _validar_seq(nombre, vel)
        self.nombre, self.vel, self._inicio, self._congelado = nombre, vel, t_ms, None

    def pausar(self, t_ms: float) -> None:
        if self.activa and not self.pausada:
            self._congelado = t_ms - self._inicio

    def seguir(self, t_ms: float) -> None:
        if self.pausada:
            self._inicio = t_ms - self._congelado
            self._congelado = None

    def detener(self) -> None:
        self.nombre, self._congelado = None, None

    def _transcurrido(self, t_ms: float) -> float:
        return self._congelado if self._congelado is not None else t_ms - self._inicio

    def paso(self, t_ms: float) -> int:
        pasos = SECUENCIAS[self.nombre]
        duraciones = [duracion_paso(p[3], self.vel) for p in pasos]
        e = self._transcurrido(t_ms) % sum(duraciones)
        acumulado = 0
        for i, d in enumerate(duraciones):
            acumulado += d
            if e < acumulado:
                return i
        return len(pasos) - 1

    def brillos(self, t_ms: float) -> Optional[dict]:
        """{"R": .., "G": .., "Y": ..} del paso actual, o None si no hay secuencia."""
        if not self.activa:
            return None
        r, g, y, _ = SECUENCIAS[self.nombre][self.paso(t_ms)]
        return {"R": r, "G": g, "Y": y}

    def sincronizar(self, valor: Optional[tuple[str, int, bool]], t_ms: float) -> None:
        """Ajusta la copia a lo que el Arduino confirmó (Aplicado.seq)."""
        if valor is None:
            self.detener()
        elif not self.activa or (self.nombre, self.vel) != (valor[0], valor[1]):
            self.iniciar(valor[0], valor[1], t_ms)
            if valor[2]:
                self.pausar(t_ms)
        elif valor[2]:
            self.pausar(t_ms)
        else:
            self.seguir(t_ms)


# ----------------------------------------------------------------------
# Modelo local de los LEDs (para el semáforo virtual de la ventana)
# ----------------------------------------------------------------------
def brillo_en(cfg: LedConfig, ms: float) -> int:
    """PWM (0-255) que tendría el pin `ms` milisegundos después de recibir `cfg`. Igual que el sketch."""
    if cfg.modo == "OFF":
        return 0
    if cfg.modo == "ON":
        return cfg.brillo
    if cfg.modo == "BLINK":
        return cfg.brillo if ms % (cfg.on_ms + cfg.off_ms) < cfg.on_ms else 0
    pos = ms % cfg.periodo_ms
    mitad = cfg.periodo_ms // 2
    x = pos if pos < mitad else cfg.periodo_ms - pos
    return min(cfg.brillo, int(cfg.brillo * (x / mitad) ** 2 + 0.5))


HISTERESIS_TERMO = 1.0


def zona_termo(t: float, zona: int, t_min: float, t_max: float, histeresis: float = HISTERESIS_TERMO) -> int:
    """Zona del semáforo térmico: 0 verde, 1 amarillo, 2 rojo intermitente. Igual que el sketch."""
    bruta = 0 if t < t_min else (1 if t < t_max else 2)
    if zona < 0 or bruta > zona:
        return bruta
    if bruta < zona:
        umbral = t_max if zona == 2 else t_min
        if t < umbral - histeresis:
            return bruta
    return zona


def leds_de_zona(zona: int) -> dict:
    """Configuración que el Arduino da a cada LED en una zona del semáforo térmico."""
    apagados = {c: LedConfig(color=c, modo="OFF") for c in COLORES}
    if zona == 0:
        apagados["G"] = LedConfig(color="G", modo="ON", brillo=255)
    elif zona == 1:
        apagados["Y"] = LedConfig(color="Y", modo="ON", brillo=255)
    elif zona == 2:
        apagados["R"] = LedConfig(color="R", modo="BLINK", brillo=255, on_ms=250, off_ms=250)
    return apagados
