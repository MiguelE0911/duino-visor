"""Semáforo térmico (TERMO): zona según la temperatura, con histéresis, y LEDs de cada zona. Igual que el sketch."""
from __future__ import annotations

from duinovisor.dominio.leds import COLORES, LedConfig

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
