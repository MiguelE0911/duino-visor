"""Modelo de un LED: colores, modos, validación y brillo en cada instante (igual que el sketch).

Funciones puras: sin puerto serie, sin interfaz y sin archivos.
"""
from __future__ import annotations

from dataclasses import dataclass

COLORES = ("R", "G", "Y")
NOMBRES_COLOR = {"R": "Rojo", "G": "Verde", "Y": "Amarillo"}
MODOS = ("OFF", "ON", "BLINK", "FADE")

BRILLO_MAX = 255
MIN_BLINK_MS = 20
MIN_FADE_MS = 200
MAX_MS = 60000


@dataclass(frozen=True)
class LedConfig:
    color: str = "R"
    modo: str = "OFF"
    brillo: int = 255
    on_ms: int = 500
    off_ms: int = 500
    periodo_ms: int = 2000


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
