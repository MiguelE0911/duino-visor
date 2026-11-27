"""Alarmas por umbral con histéresis: avisan cuando un valor se pasa y cuando vuelve a la normalidad."""
from __future__ import annotations

from typing import Optional


class Alarma:
    def __init__(self, nombre: str, unidad: str, maximo: Optional[float] = None,
                 minimo: Optional[float] = None, histeresis: float = 1.0):
        if maximo is not None and minimo is not None and minimo >= maximo:
            raise ValueError("el mínimo debe ser menor que el máximo")
        self.nombre, self.unidad = nombre, unidad
        self.maximo, self.minimo, self.histeresis = maximo, minimo, histeresis
        self.activa = False
        self.motivo = ""

    def configurar(self, maximo: Optional[float], minimo: Optional[float] = None) -> None:
        if maximo is not None and minimo is not None and minimo >= maximo:
            raise ValueError("el mínimo debe ser menor que el máximo")
        self.maximo, self.minimo = maximo, minimo

    def reiniciar(self) -> None:
        self.activa, self.motivo = False, ""

    def evaluar(self, valor: Optional[float]) -> Optional[str]:
        """Devuelve "ACTIVA" al saltar, "RESUELTA" al normalizarse y None si no cambia nada."""
        if valor is None:
            return None                                   # una lectura fallida no dispara ni apaga nada
        if not self.activa:
            if self.maximo is not None and valor > self.maximo:
                self.activa = True
                self.motivo = f"{self.nombre} {valor:g}{self.unidad} supera el máximo de {self.maximo:g}{self.unidad}"
                return "ACTIVA"
            if self.minimo is not None and valor < self.minimo:
                self.activa = True
                self.motivo = f"{self.nombre} {valor:g}{self.unidad} está bajo el mínimo de {self.minimo:g}{self.unidad}"
                return "ACTIVA"
            return None
        arriba_ok = self.maximo is None or valor <= self.maximo - self.histeresis
        abajo_ok = self.minimo is None or valor >= self.minimo + self.histeresis
        if arriba_ok and abajo_ok:
            self.activa, self.motivo = False, ""
            return "RESUELTA"
        return None
