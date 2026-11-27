"""Estado editable de un LED en la ventana (variables de Tk, sin widgets)."""
from __future__ import annotations

import tkinter as tk

from duinovisor.dominio.leds import NOMBRES_COLOR, LedConfig, errores
from duinovisor.ui.constantes import OPCIONES_RITMO, RITMOS


class LedUI:
    """Lo que la ventana tiene configurado para un LED (sin widgets).

    Mantiene `v_ritmo` (Lento/Normal/Rápido) sincronizado con los milisegundos exactos: elegir un ritmo
    escribe los ms y, si los ms no coinciden con ningún ritmo, no queda ninguno marcado.
    """

    def __init__(self, color: str, al_cambiar):
        self.color, self.al_cambiar = color, al_cambiar
        self.v_modo = tk.StringVar(value="OFF")
        self.v_brillo = tk.IntVar(value=255)
        self.v_on, self.v_off, self.v_periodo = (tk.StringVar(value=v) for v in ("500", "500", "2000"))
        self.v_ritmo = tk.StringVar(value="normal")
        self.v_pct = tk.StringVar(value="100 %")
        self.habilitado = True
        self._ocupado = False
        for v in (self.v_modo, self.v_brillo, self.v_on, self.v_off, self.v_periodo):
            v.trace_add("write", self._cambio)
        self.v_ritmo.trace_add("write", self._elegir_ritmo)

    def _cambio(self, *_):
        if self._ocupado:
            return
        self.v_pct.set(f"{round(int(self.v_brillo.get()) * 100 / 255)} %")
        self._sincronizar_ritmo()
        self.al_cambiar()

    def ritmo_actual(self) -> str:
        modo = self.v_modo.get()
        if modo == "BLINK":
            on, off = self.v_on.get().strip(), self.v_off.get().strip()
            for nombre, ms in RITMOS["BLINK"].items():
                if on == off == str(ms):
                    return nombre
        elif modo == "FADE":
            for nombre, ms in RITMOS["FADE"].items():
                if self.v_periodo.get().strip() == str(ms):
                    return nombre
        return ""

    def _sincronizar_ritmo(self):
        r = self.ritmo_actual()
        if self.v_ritmo.get() != r:
            self._ocupado = True
            try:
                self.v_ritmo.set(r)
            finally:
                self._ocupado = False

    def _elegir_ritmo(self, *_):
        if self._ocupado:
            return
        ms = RITMOS.get(self.v_modo.get(), {}).get(self.v_ritmo.get())
        if ms is None:
            return
        self._ocupado = True
        try:
            if self.v_modo.get() == "BLINK":
                self.v_on.set(str(ms))
                self.v_off.set(str(ms))
            else:
                self.v_periodo.set(str(ms))
        finally:
            self._ocupado = False
        self._cambio()

    def resumen(self) -> str:
        modo = self.v_modo.get()
        if modo == "OFF":
            return "Apagada"
        if modo == "ON":
            return f"Encendida · {self.v_pct.get()}"
        ritmo = dict(OPCIONES_RITMO).get(self.ritmo_actual(), "a medida").lower()
        return f"{'Parpadea' if modo == 'BLINK' else 'Respira'} · {ritmo}"

    def habilitar(self, si: bool):
        self.habilitado = bool(si)

    def _entero(self, var: tk.StringVar, nombre: str) -> int:
        try:
            return int(var.get().strip())
        except ValueError:
            raise ValueError(f"LED {NOMBRES_COLOR[self.color]}: «{nombre}» debe ser un número entero")

    def obtener(self) -> LedConfig:
        modo = self.v_modo.get()
        on = self._entero(self.v_on, "encendido") if modo == "BLINK" else 500
        off = self._entero(self.v_off, "apagado") if modo == "BLINK" else 500
        per = self._entero(self.v_periodo, "periodo") if modo == "FADE" else 2000
        cfg = LedConfig(self.color, modo, int(self.v_brillo.get()), on, off, per)
        problemas = errores(cfg)
        if problemas:
            raise ValueError(f"LED {NOMBRES_COLOR[self.color]}: " + "; ".join(problemas))
        return cfg

    def cargar(self, cfg: LedConfig):
        self.v_modo.set(cfg.modo)
        self.v_brillo.set(cfg.brillo)
        self.v_on.set(str(cfg.on_ms))
        self.v_off.set(str(cfg.off_ms))
        self.v_periodo.set(str(cfg.periodo_ms))


# Se mantiene el nombre antiguo por compatibilidad con código de la rama de funcionalidades.
PanelLed = LedUI
