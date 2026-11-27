"""Espejo de lo que hace el Arduino: LEDs, secuencia y semáforo térmico, calculados desde lo confirmado."""
from __future__ import annotations

from duinovisor.dominio.leds import COLORES, LedConfig, brillo_en
from duinovisor.dominio.protocolo import Aplicado, Paso, confirmar
from duinovisor.dominio.secuencias import NOMBRES_SEQ
from duinovisor.dominio.termometro import leds_de_zona, zona_termo
from duinovisor.ui.constantes import ZONAS


def apagados() -> dict:
    return {c: (LedConfig(color=c, modo="OFF"), 0.0) for c in COLORES}


class EspejoMixin:
    """Mantiene `aplicado`, `vista`, `secuencia` y `zona` al día."""

    def _reiniciar_espejo(self):
        self.aplicado = Aplicado()               # no se sabe qué tiene la placa: se reenvía todo
        self.pendientes, self.paso_actual = [], None
        self.secuencia.detener()
        self.vista = apagados()
        self.zona = -1
        self.alarma_t.reiniciar()
        self.alarma_h.reiniciar()
        self._actualizar_banner()

    def _confirmado(self, paso: Paso):
        """El Arduino respondió OK: se actualiza lo aplicado y el espejo de LEDs y secuencia."""
        previo, ahora = self.aplicado, self.ahora_ms()
        self.aplicado = confirmar(previo, paso)
        if paso.clave == "led":
            if previo.seq is not None or previo.termo is not None:   # el Arduino apagó lo automático
                self.vista = apagados()
                self.secuencia.detener()
                self.zona = -1
            self.vista[paso.color] = (paso.valor, ahora)
        elif paso.clave == "seq":
            self.secuencia.sincronizar(paso.valor, ahora)
            self.vista = apagados()
            self.zona = -1
        elif paso.clave == "termo":
            self.secuencia.detener()
            self.vista = apagados()
            self.zona = -1
            self.v_zona.set("")

    def _brillos_espejo(self) -> dict:
        if not self.enlace.conectado:
            return {c: 0 for c in COLORES}
        ahora = self.ahora_ms()
        if self.secuencia.activa:
            return self.secuencia.brillos(ahora)
        return {c: brillo_en(cfg, ahora - t0) for c, (cfg, t0) in self.vista.items()}

    def _texto_semaforo(self) -> str:
        if not self.enlace.conectado:
            return "Sin conexión con el Arduino"
        seq = self.aplicado.seq
        if seq is not None:
            return f"Animación «{NOMBRES_SEQ[seq[0]]}» " + ("en pausa" if seq[2] else "en marcha")
        if self.aplicado.termo is not None:
            return "Termómetro: " + (ZONAS[self.zona] if self.zona >= 0 else "esperando una lectura")
        return "Control manual"

    def _espejo_termo(self, t: float):
        if self.aplicado.termo is None:
            return
        nueva = zona_termo(t, self.zona, *self.aplicado.termo)
        if nueva != self.zona:
            self.zona = nueva
            cfgs, ahora = leds_de_zona(nueva), self.ahora_ms()
            self.vista = {c: (cfgs[c], ahora) for c in COLORES}
        self.v_zona.set("Luces: " + ZONAS[self.zona])
