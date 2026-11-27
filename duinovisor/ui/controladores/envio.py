"""Envío con confirmación: cada orden espera OK/ERR antes de la siguiente."""
from __future__ import annotations

from tkinter import messagebox

from duinovisor.dominio.protocolo import plan
from duinovisor.ui.constantes import SIN_RESPUESTA_MS


class EnvioMixin:
    """Lee la ventana, arma los pasos y los envía uno a uno con reintento."""

    def _leds_ui(self) -> dict:
        return {c: p.obtener() for c, p in self.paneles.items()}

    def leer_ui(self):
        """(leds, dht_ms, termo) de la ventana. Lanza ValueError con un mensaje claro."""
        try:
            dht = int(self.v_dht.get().strip())
        except ValueError:
            raise ValueError("«Leer el sensor cada (ms)» debe ser un número entero")
        termo = None
        if self.v_termo.get():
            try:
                termo = (int(self.v_tmin.get().strip()), int(self.v_tmax.get().strip()))
            except ValueError:
                raise ValueError("Las temperaturas del semáforo deben ser números enteros")
        return (self._leds_ui() if termo is None else {}), dht, termo

    def _enviar_pasos(self, pasos: list) -> bool:
        if not self.enlace.conectado:
            messagebox.showwarning("Sin conexión", "Conecta el Arduino primero.")
            return False
        if self.paso_actual is not None or self.pendientes:
            self.log("Ya hay un envío en curso.", "info")
            return False
        self.pendientes = list(pasos)
        self._enviar_siguiente()
        return True

    def aplicar(self):
        if not self.enlace.conectado:
            messagebox.showwarning("Sin conexión", "Conecta el Arduino primero.")
            return
        if self.paso_actual is not None or self.pendientes:
            self.log("Ya hay un envío en curso.", "info")
            return
        try:
            pasos = plan(*self.leer_ui(), self.aplicado)
        except ValueError as e:
            messagebox.showwarning("Valores inválidos", f"No se envió nada.\n\n{e}")
            return
        if not pasos:
            self.log("Nada que enviar: ya está aplicado.", "info")
            return
        self._enviar_pasos(pasos)

    def _enviar_siguiente(self, reintento: bool = False):
        if not reintento:
            if not self.pendientes:
                self.paso_actual = None
                self.log("Aplicado.", "info")
                self.al_cambiar()
                return
            self.paso_actual = self.pendientes.pop(0)
            self._intentos = 0
        paso = self.paso_actual
        try:
            self.enlace.enviar(paso.texto)
        except Exception as e:
            self._abortar(f"No se pudo enviar «{paso.texto}»: {e}")
            return
        self.log("→ " + paso.texto, "tx")
        self._id_timeout = self.after(SIN_RESPUESTA_MS, self._sin_respuesta, paso)

    def _sin_respuesta(self, paso):
        if self.paso_actual is not paso:
            return
        if self._intentos < 1:
            self._intentos += 1
            self.log(f"Sin respuesta a «{paso.texto}», reintentando…", "err")
            self._enviar_siguiente(reintento=True)
        else:
            self._abortar(f"El Arduino no respondió a «{paso.texto}». Se detuvo el envío. "
                          "Comprueba que la placa tenga cargado control_leds.ino.")

    def _cancelar_timeout(self):
        if self._id_timeout is not None:
            self.after_cancel(self._id_timeout)
            self._id_timeout = None

    def _abortar(self, mensaje: str):
        self._cancelar_timeout()
        self.pendientes, self.paso_actual = [], None
        self.log(mensaje, "err")
        self.al_cambiar()
