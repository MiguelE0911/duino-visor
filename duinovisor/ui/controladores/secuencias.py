"""Iniciar, pausar, seguir, cambiar y detener animaciones."""
from __future__ import annotations

from tkinter import messagebox

from duinovisor.dominio.secuencias import paso_seq_detener, paso_seq_iniciar, paso_seq_pausa, paso_seq_seguir


class SecuenciasMixin:
    """Botones de las animaciones."""

    def _seleccion_seq(self) -> tuple:
        return self.v_seq.get(), int(self.v_vel.get())

    def _cambio_seq(self):
        self.v_vel_txt.set(f"{int(self.v_vel.get())} %")
        self._actualizar_botones_seq()

    def _actualizar_botones_seq(self):
        if not hasattr(self, "b_seq"):
            return
        seq = self.aplicado.seq
        if seq is None:
            texto = "Iniciar"
        elif (seq[0], seq[1]) != self._seleccion_seq():
            texto = "Cambiar"
        else:
            texto = "Seguir" if seq[2] else "Pausar"
        self.b_seq.configurar(texto=texto)
        self.b_stop.configurar(habilitado=seq is not None)

    def alternar_secuencia(self):
        seq = self.aplicado.seq
        try:
            if seq is None or (seq[0], seq[1]) != self._seleccion_seq():
                paso = paso_seq_iniciar(*self._seleccion_seq())
            else:
                paso = paso_seq_seguir(seq) if seq[2] else paso_seq_pausa(seq)
        except ValueError as e:
            messagebox.showwarning("Secuencia", str(e))
            return
        self._enviar_pasos([paso])

    def detener_secuencia(self):
        if self.aplicado.seq is not None:
            self._enviar_pasos([paso_seq_detener()])
