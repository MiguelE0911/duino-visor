"""Enlace con el Arduino: listar puertos, autodetectar, hilo lector con cola, enviar.

La interfaz nunca lee el puerto: un hilo lee y deja cada línea en una cola
(`Enlace.cola`); la interfaz la vacía con after(). Así nunca se congela.
"""
from __future__ import annotations

import queue
import threading
import time
from typing import Callable, Optional

import protocol

BAUDIOS = 9600
ESPERA_REINICIO = 2.0          # abrir el puerto reinicia al Arduino UNO

# Fabricantes USB típicos: Arduino oficial, CH340 (clones), FTDI, CP210x
VID_ARDUINO = {0x2341, 0x2A03, 0x1A86, 0x0403, 0x10C4}


class PySerialNoDisponible(RuntimeError):
    pass


def _serial():
    try:
        import serial
        return serial
    except ImportError as exc:
        raise PySerialNoDisponible("Falta pyserial. Instálalo con:  pip install pyserial") from exc


def listar_puertos() -> list:
    """Puertos serie del sistema, con los de aspecto Arduino primero."""
    _serial()
    from serial.tools import list_ports
    puertos = list(list_ports.comports())
    puertos.sort(key=lambda p: (p.vid not in VID_ARDUINO, p.device))
    return puertos


def probar_puerto(dispositivo: str, espera: float = ESPERA_REINICIO, limite: float = 1.5) -> bool:
    """True si ese puerto responde PONG OAC-LEDS a PING."""
    serial = _serial()
    try:
        with serial.Serial(dispositivo, BAUDIOS, timeout=0.2, write_timeout=1) as s:
            time.sleep(espera)
            s.reset_input_buffer()
            s.write(b"PING\n")
            fin = time.monotonic() + limite
            while time.monotonic() < fin:
                linea = s.readline().decode("ascii", "ignore")
                if protocol.es_pong(linea):
                    return True
    except (OSError, serial.SerialException):
        pass
    return False


def autodetectar(progreso: Optional[Callable[[str], None]] = None) -> Optional[str]:
    """Nombre del puerto donde está la placa, o None. Tarda ~2 s por puerto: usar en un hilo."""
    for p in listar_puertos():
        if progreso:
            progreso(p.device)
        if probar_puerto(p.device):
            return p.device
    return None


class Enlace:
    """Conexión abierta con el Arduino (real o simulado)."""

    def __init__(self):
        self.cola: "queue.Queue[tuple[str, str]]" = queue.Queue()   # ("rx", línea) | ("error", texto)
        self._dev = None
        self._hilo: Optional[threading.Thread] = None
        self._activo = threading.Event()
        self._lock = threading.Lock()

    @property
    def conectado(self) -> bool:
        return self._dev is not None and self._activo.is_set()

    def conectar(self, puerto: str) -> None:
        """Abre un puerto real. Bloquea ~2 s (reinicio del Arduino): llamar desde un hilo."""
        serial = _serial()
        dev = serial.Serial(puerto, BAUDIOS, timeout=0.1, write_timeout=1)
        time.sleep(ESPERA_REINICIO)
        dev.reset_input_buffer()
        self.usar(dev)

    def usar(self, dispositivo) -> None:
        """Usa un objeto tipo Serial ya abierto (por ejemplo, el ArduinoSimulado)."""
        self.cerrar()
        self._dev = dispositivo
        self._activo.set()
        self._hilo = threading.Thread(target=self._leer, daemon=True)
        self._hilo.start()

    def _leer(self):
        dev = self._dev
        while self._activo.is_set():
            try:
                datos = dev.readline()
            except Exception as exc:                  # cable desconectado, puerto cerrado, ...
                if self._activo.is_set():
                    self.cola.put(("error", f"Se perdió la conexión: {exc}"))
                    self._activo.clear()
                break
            if datos:
                self.cola.put(("rx", datos.decode("ascii", "ignore").strip()))

    def enviar(self, linea: str) -> None:
        with self._lock:
            if not self.conectado:
                raise ConnectionError("no hay conexión con el Arduino")
            self._dev.write((linea.strip() + "\n").encode("ascii"))
            flush = getattr(self._dev, "flush", None)
            if flush:
                flush()                                   # que los bytes salgan antes de cerrar el puerto

    def cerrar(self) -> None:
        self._activo.clear()
        dev, self._dev = self._dev, None
        if dev is not None:
            try:
                dev.close()
            except Exception:
                pass
        if self._hilo is not None and self._hilo is not threading.current_thread():
            self._hilo.join(timeout=1)
        self._hilo = None
        while not self.cola.empty():                  # descarta lo que quedó de la sesión anterior
            try:
                self.cola.get_nowait()
            except queue.Empty:
                break
