"""Secuencias (SEQ): la misma tabla que el sketch, las órdenes para manejarlas y su copia local.

Para añadir una animación nueva basta con sumarla a SECUENCIAS y NOMBRES_SEQ (y a la tabla del sketch).
"""
from __future__ import annotations

from typing import Optional

from duinovisor.dominio.protocolo import Paso

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
