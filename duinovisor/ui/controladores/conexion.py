"""Buscar la placa, conectar, desconectar y mostrar el estado de la conexión."""
from __future__ import annotations

import threading
from tkinter import messagebox

from duinovisor.dominio.protocolo import Paso
from duinovisor.hardware.enlace import PySerialNoDisponible, autodetectar, listar_puertos
from duinovisor.hardware.simulador import ArduinoSimulado
from duinovisor.ui import tema as T


class ConexionMixin:
    """Conexión con la placa real o con el simulador. Los hilos hablan con la ventana por `cola_ui`."""

    def _poner_estado(self, texto: str, tipo: str):
        """tipo: ok, buscando, error u off. Pinta el punto y muestra «Reintentar» cuando hace falta."""
        self._estado_tipo = tipo
        self.v_estado.set(texto)
        if not self._construido:
            return
        color = {"ok": T.EXITO, "buscando": T.ACENTO, "error": T.ERROR}.get(tipo, T.TEXTO_3)
        self.punto.itemconfigure("punto", fill=color)
        if tipo in ("error", "off"):
            self.b_reintentar.pack(side="left", padx=(self._px(6), 0))
        else:
            self.b_reintentar.pack_forget()
        self.b_power.configurar(texto="Desconectar" if self.enlace.conectado else "Conectar")

    def reintentar(self):
        if self.demo:
            self.conectar_demo()
        else:
            self.buscar_placa()

    def actualizar_puertos(self, silencioso: bool = False):
        try:
            nombres = [p.device for p in listar_puertos()]
        except PySerialNoDisponible as e:
            nombres = []
            if not silencioso:
                messagebox.showerror("Falta pyserial", str(e))
        if self.demo:
            nombres = ["SIMULADOR"] + nombres
        self.cb_puerto["values"] = nombres

    def buscar_placa(self):
        self._poner_estado("Buscando tu Arduino…", "buscando")

        def trabajo():
            try:
                puerto = autodetectar(progreso=lambda p: self.cola_ui.put(("progreso", p)))
                self.cola_ui.put(("detectado", puerto))
            except PySerialNoDisponible as e:
                self.cola_ui.put(("fallo", str(e)))
            except Exception as e:
                self.cola_ui.put(("fallo", f"Error al buscar la placa: {e}"))
        threading.Thread(target=trabajo, daemon=True).start()

    def alternar_conexion(self):
        if self.enlace.conectado:
            self.desconectar()
        else:
            self.conectar()

    def conectar(self):
        puerto = self.v_puerto.get().strip()
        if not puerto:
            messagebox.showinfo("Puerto", "Elige un puerto de la lista o pulsa el botón de actualizar.")
            return
        if self.demo and puerto == "SIMULADOR":
            self.conectar_demo()
            return
        self._poner_estado("Conectando…", "buscando")

        def trabajo():
            try:
                self.enlace.conectar(puerto)
                self.cola_ui.put(("conectado", puerto))
            except PySerialNoDisponible as e:
                self.cola_ui.put(("fallo", str(e)))
            except Exception as e:
                self.cola_ui.put(("fallo", f"No se pudo abrir {puerto}: {e}"))
        threading.Thread(target=trabajo, daemon=True).start()

    def conectar_demo(self):
        self.sim = ArduinoSimulado()
        self.enlace.usar(self.sim)
        self.v_puerto.set("SIMULADOR")
        self._al_conectar("SIMULADOR")

    def _al_conectar(self, puerto: str):
        self._reiniciar_espejo()
        self._marcar_base()                     # lo que hay en pantalla al conectar no cuenta como cambio
        if puerto == "SIMULADOR":
            self._poner_estado("Modo demostración: Arduino simulado", "ok")
        else:
            self._poner_estado(f"Arduino conectado ({puerto})", "ok")
        self.log(f"Conectado a {puerto}. Configura los LEDs y pulsa Aplicar.", "info")
        self.al_cambiar()

    def desconectar(self, motivo: str = "", avisar_arduino: bool = True):
        self._cancelar_timeout()
        if avisar_arduino:
            self._detener_arduino()
        self.enlace.cerrar()
        self.sim = None
        self._reiniciar_espejo()
        self._poner_estado(motivo or "Sin conexión", "error" if motivo else "off")
        self._envio_total, self._listo, self._fallo = 0, False, None
        self.al_cambiar()

    def _detener_arduino(self):
        """Si la app para o se cierra, la secuencia del Arduino también se detiene."""
        if self.enlace.conectado and self.aplicado.seq is not None:
            try:
                self.enlace.enviar("SEQ OFF")
            except Exception:
                pass

    def _evento_ui(self, ev):
        tipo, dato = ev
        if tipo == "progreso":
            self._poner_estado("Buscando tu Arduino…", "buscando")
            self.log(f"Probando {dato}…", "info")
        elif tipo == "detectado":
            if dato:
                self.v_puerto.set(dato)
                self.log(f"Arduino encontrado en {dato}.", "info")
                self.conectar()
            else:
                self._poner_estado("No encontramos el Arduino", "error")
                self.log("No se encontró el Arduino (ningún puerto respondió a PING). ¿Está cargado "
                         "control_leds.ino en la placa? Si lo está, elige el puerto a mano y pulsa Conectar.", "err")
        elif tipo == "conectado":
            self._al_conectar(dato)
            # Una placa con USB nativo (Arduino 101) no se reinicia al abrir el puerto y puede seguir con
            # LEDs, semáforo o secuencia de antes. TERMO OFF lo apaga todo y la deja igual que el espejo.
            self._enviar_pasos([Paso("TERMO OFF", "termo", valor=None)])
        elif tipo == "fallo":
            self._poner_estado("No se pudo conectar", "error")
            self.log(dato, "err")
