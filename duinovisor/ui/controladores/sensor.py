"""Lecturas del sensor: historial para el CSV y alarmas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from duinovisor.ui.constantes import MAX_LECTURAS_CSV


class SensorMixin:
    """Registra cada lectura y revisa las alarmas."""

    def _registrar(self, t: Optional[float], h: Optional[float]):
        self.lecturas.append((datetime.now(), t, h))
        if len(self.lecturas) > MAX_LECTURAS_CSV:
            del self.lecturas[: len(self.lecturas) - MAX_LECTURAS_CSV]

    def _revisar_alarmas(self, t: Optional[float], h: Optional[float]):
        if not self.v_alarmas.get():
            if self.alarma_t.activa or self.alarma_h.activa:
                self.alarma_t.reiniciar()
                self.alarma_h.reiniciar()
                self._actualizar_banner()
            return
        try:
            self.alarma_t.configurar(float(self.v_amax_t.get().replace(",", ".")))
            self.alarma_h.configurar(float(self.v_amax_h.get().replace(",", ".")))
        except ValueError:
            return                                              # umbral a medio escribir: se ignora
        for alarma, valor in ((self.alarma_t, t), (self.alarma_h, h)):
            evento = alarma.evaluar(valor)
            if evento == "ACTIVA":
                self.log("Alarma: " + alarma.motivo, "err")
                self.bell()
            elif evento == "RESUELTA":
                self.log(f"{alarma.nombre} volvió a la normalidad.", "info")
        self._actualizar_banner()
