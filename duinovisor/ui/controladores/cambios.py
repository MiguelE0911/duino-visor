"""Barra del pie que avisa de los cambios sin aplicar, del envío en curso y de su resultado.

La «base» es lo que la ventana tenía cuando se conectó la placa o cuando terminó el último «Aplicar». Solo se
avisa de cambios si la ventana es distinta de esa base: recién conectado no aparece nada aunque el espejo
todavía no sepa qué tiene la placa, y si el usuario deshace lo que cambió, el aviso se va.
"""
from __future__ import annotations

from duinovisor.dominio.protocolo import plan

MS_LISTO = 1800              # cuánto se ve «Cambios aplicados» antes de irse
INVALIDO = "invalido"        # foto de una ventana con algún valor que no se puede leer


class CambiosMixin:
    """Decide qué muestra `barra_cambios` (widgets/avisos.BarraCambios)."""

    def _iniciar_cambios(self):
        self._base_ui = None
        self._cerrada_en = None                # foto de la ventana cuando se cerró la barra con ×
        self._envio_total = 0                  # pasos del «Aplicar» en curso (0 = no hay)
        self._listo = False
        self._id_listo = None
        self._fallo = None                     # (mensaje, foto) del último «Aplicar» que falló

    def _foto_ui(self):
        """Lo que la ventana pide al Arduino, o INVALIDO si algún valor no se puede leer o está fuera de rango."""
        try:
            foto = self.leer_ui()
            plan(*foto, self.aplicado)                  # también valida los rangos (p. ej. el periodo del sensor)
            return foto
        except ValueError:
            return INVALIDO

    def _marcar_base(self):
        self._base_ui = self._foto_ui()
        self._cerrada_en = None
        self._fallo = None

    def _cerrar_barra(self):
        self._cerrada_en = self._foto_ui()

    # ------------------------------------------------------------------ ganchos del envío
    def _empieza_aplicar(self, total: int):
        self._envio_total = total
        self._listo, self._fallo = False, None

    def _termina_envio(self):
        if self._envio_total:
            self._envio_total = 0
            self._marcar_base()
            self._listo = True
            if self._id_listo is not None:
                self.after_cancel(self._id_listo)
            self._id_listo = self.after(MS_LISTO, self._quitar_listo)

    def _falla_envio(self, mensaje: str):
        if self._envio_total:
            self._envio_total = 0
            self._fallo = (mensaje, self._foto_ui())

    def _quitar_listo(self):
        self._id_listo = None
        self._listo = False
        self._actualizar_barra()

    # ------------------------------------------------------------------ qué se muestra
    def _actualizar_barra(self):
        if not self._construido:
            return
        b = self.barra_cambios
        if not self.enlace.conectado:
            self._listo = False
            b.ocultar()
            return
        if self._envio_total and (self.paso_actual is not None or self.pendientes):
            hecho = self._envio_total - len(self.pendientes)
            b.mostrar("enviando", "Enviando al Arduino…", f"Orden {hecho} de {self._envio_total}",
                      progreso=(hecho - 1) / self._envio_total)
            return
        foto = self._foto_ui()
        cerrada = foto == self._cerrada_en
        if self._fallo is not None and self._fallo[1] == foto and not cerrada:
            b.mostrar("fallo", "No se pudieron aplicar los cambios", self._resumir(self._fallo[0]),
                      ("Reintentar", self.aplicar))
            return
        if foto == INVALIDO and not cerrada:
            b.mostrar("error", "Hay un valor que no es correcto",
                      "Hasta que lo corrijas no se puede enviar nada al Arduino.", ("Ver qué pasa", self.aplicar))
            return
        if foto != self._base_ui and not cerrada and plan(*foto, self.aplicado):
            b.mostrar("pendiente", "Tienes cambios sin aplicar",
                      "El Arduino aún no los tiene (Ctrl+Intro).",
                      ("Aplicar cambios", self.aplicar))
            return
        if self._listo:
            b.mostrar("listo", "Cambios aplicados", "El Arduino ya hace lo que ves en la pantalla.")
            return
        b.ocultar()

    @staticmethod
    def _resumir(mensaje: str, largo: int = 110) -> str:
        return mensaje if len(mensaje) <= largo else mensaje[: largo - 1] + "…"
