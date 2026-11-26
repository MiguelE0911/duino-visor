"""Arduino falso: imita al sketch control_leds.ino para trabajar sin la placa (modo --demo).

Implementa lo mínimo de la interfaz de pyserial.Serial que usa arduino_link
(write, readline, in_waiting, reset_input_buffer, close, timeout, is_open),
con las mismas órdenes y las mismas respuestas del sketch.
"""
from __future__ import annotations

import math
import queue
import threading
import time

import protocol as P

HISTERESIS = 1.0


class ArduinoSimulado:
    def __init__(self, reloj=time.monotonic, hilo: bool = True, retardo_arranque: float = 0.0):
        self.reloj = reloj
        self.timeout = 0.1
        self.is_open = True
        self._t0 = reloj()
        self._salida: "queue.Queue[bytes]" = queue.Queue()
        self._buf = b""
        self._lock = threading.Lock()
        # estado, igual que el sketch
        self.leds = {c: dict(modo="OFF", brillo=0, on=0, off=0, periodo=0, t0=0, fase=True)
                     for c in "RGY"}
        self.periodo_dht = 2000
        self._ultimo_dht = 0
        self.termo_activo = False
        self.termo = (22, 28)
        self.zona = -1
        self.seq = P.SecuenciaLocal()
        self._stop = threading.Event()
        self._hilo = None
        if hilo:
            self._hilo = threading.Thread(target=self._bucle, daemon=True)
            self._hilo.start()

    # ---- reloj ----
    def ms(self) -> int:
        return int((self.reloj() - self._t0) * 1000)

    # ---- interfaz estilo pyserial ----
    def write(self, datos: bytes) -> int:
        with self._lock:
            self._buf += datos
            while b"\n" in self._buf:
                linea, self._buf = self._buf.split(b"\n", 1)
                texto = linea.decode("ascii", "ignore").replace("\r", "")
                if len(texto) > 63:
                    respuestas = ["ERR linea larga"]
                else:
                    respuestas = self.procesar(texto)
                for r in respuestas:
                    self._salida.put((r + "\n").encode())
        return len(datos)

    def readline(self) -> bytes:
        try:
            return self._salida.get(timeout=self.timeout)
        except queue.Empty:
            return b""

    @property
    def in_waiting(self) -> int:
        return self._salida.qsize()

    def reset_input_buffer(self):
        while not self._salida.empty():
            self._salida.get_nowait()

    def close(self):
        self.is_open = False
        self._stop.set()

    # ---- lógica del sketch ----
    @staticmethod
    def _num(s):
        try:
            if s.lstrip("-").isdigit():
                return int(s)
        except AttributeError:
            pass
        return None

    def _cancelar_termo(self):
        """Una orden manual de LED cancela el semáforo térmico y las secuencias."""
        if self.termo_activo or self.seq.activa:
            self.termo_activo = False
            self.zona = -1
            self.seq.detener()
            self._apagar_todos()

    def _apagar_todos(self):
        for led in self.leds.values():
            led["modo"] = "OFF"

    def procesar(self, texto: str) -> list[str]:
        tok = texto.upper().split()
        if not tok:
            return []
        ahora = self.ms()
        if tok[0] == "PING":
            return ["PONG OAC-LEDS 1"]
        if tok[0] == "LED":
            return self._led(tok, ahora)
        if tok[0] == "DHT":
            a = self._num(tok[1]) if len(tok) == 2 else None
            if a is None or not 1000 <= a <= 3_600_000:
                return ["ERR periodo 1000-3600000 ms"]
            self.periodo_dht = a
            return ["OK DHT"]
        if tok[0] == "TERMO":
            if len(tok) == 2 and tok[1] == "OFF":
                self.termo_activo = False
                self.zona = -1
                self.seq.detener()
                self._apagar_todos()
                return ["OK TERMO"]
            a = self._num(tok[1]) if len(tok) == 3 else None
            b = self._num(tok[2]) if len(tok) == 3 else None
            if a is None or b is None or a >= b:
                return ["ERR uso TERMO tmin tmax (tmin<tmax) | TERMO OFF"]
            self.termo = (a, b)
            self.termo_activo = True
            self.zona = -1
            self.seq.detener()
            self._apagar_todos()
            return ["OK TERMO"]
        if tok[0] == "SEQ":
            return self._orden_seq(tok, ahora)
        if tok[0] == "STATUS":
            self._sincronizar_seq(ahora)
            filas = [f"STATE {c} {l['modo']} {l['brillo']} {l['on']} {l['off']} {l['periodo']}"
                     for c, l in self.leds.items()]
            if self.seq.activa:
                filas.append(f"STATE SEQ {self.seq.nombre} {self.seq.vel} {'PAUSA' if self.seq.pausada else 'RUN'}")
            else:
                filas.append("STATE SEQ OFF")
            return filas + ["OK STATUS"]
        return ["ERR comando"]

    def _led(self, tok, ahora):
        if len(tok) < 3:
            return ["ERR faltan argumentos"]
        if tok[1] not in self.leds:
            return ["ERR led R G Y"]
        led, modo, n = self.leds[tok[1]], tok[2], len(tok)
        brillo_err = ["ERR brillo 0-255"]
        if modo == "OFF":
            if n != 3:
                return ["ERR argumentos"]
            self._cancelar_termo()
            led["modo"] = "OFF"
        elif modo == "ON":
            if n != 4:
                return ["ERR uso LED c ON brillo"]
            a = self._num(tok[3])
            if a is None or not 0 <= a <= 255:
                return brillo_err
            self._cancelar_termo()
            led.update(modo="ON", brillo=a)
        elif modo == "BLINK":
            if n != 6:
                return ["ERR uso LED c BLINK brillo on off"]
            a, b, c = (self._num(x) for x in tok[3:6])
            if a is None or not 0 <= a <= 255:
                return brillo_err
            if b is None or c is None or not (20 <= b <= 60000 and 20 <= c <= 60000):
                return ["ERR tiempo 20-60000 ms"]
            self._cancelar_termo()
            led.update(modo="BLINK", brillo=a, on=b, off=c, t0=ahora, fase=True)
        elif modo == "FADE":
            if n != 5:
                return ["ERR uso LED c FADE brillo periodo"]
            a, b = self._num(tok[3]), self._num(tok[4])
            if a is None or not 0 <= a <= 255:
                return brillo_err
            if b is None or not 200 <= b <= 60000:
                return ["ERR periodo 200-60000 ms"]
            self._cancelar_termo()
            led.update(modo="FADE", brillo=a, periodo=b, t0=ahora)
        else:
            return ["ERR modo"]
        return [f"OK LED {tok[1]}"]

    def _orden_seq(self, tok, ahora):
        uso = "ERR uso SEQ nombre [vel] | OFF | PAUSA | SEGUIR"
        if not 2 <= len(tok) <= 3:
            return [uso]
        accion = tok[1]
        if accion == "OFF":
            if self.seq.activa:
                self.seq.detener()
                self._apagar_todos()
            return ["OK SEQ"]
        if accion in ("PAUSA", "SEGUIR"):
            if not self.seq.activa:
                return ["ERR sin secuencia"]
            (self.seq.pausar if accion == "PAUSA" else self.seq.seguir)(ahora)
            return ["OK SEQ"]
        if accion not in P.SECUENCIAS:
            return ["ERR secuencia VIAL FANTASTICO ALERTA"]
        vel = 100
        if len(tok) == 3:
            vel = self._num(tok[2])
            if vel is None or not P.VEL_MIN <= vel <= P.VEL_MAX:
                return ["ERR velocidad 25-400"]
        self.termo_activo = False
        self.zona = -1
        self.seq.iniciar(accion, vel, ahora)
        self._sincronizar_seq(ahora)
        return ["OK SEQ"]

    def _sincronizar_seq(self, ahora: int):
        """Si hay una secuencia, los LEDs toman el paso que toca ahora."""
        b = self.seq.brillos(ahora)
        if b is not None:
            for c, v in b.items():
                self.leds[c].update(modo="ON" if v else "OFF", brillo=v)

    def brillo_actual(self, color: str) -> int:
        """PWM (0-255) que tendría ese pin ahora; útil para dibujar LEDs virtuales."""
        self._sincronizar_seq(self.ms())
        led, ahora = self.leds[color], self.ms()
        if led["modo"] == "OFF":
            return 0
        if led["modo"] == "ON":
            return led["brillo"]
        if led["modo"] == "BLINK":
            ciclo = led["on"] + led["off"]
            return led["brillo"] if (ahora - led["t0"]) % ciclo < led["on"] else 0
        pos = (ahora - led["t0"]) % led["periodo"]
        mitad = led["periodo"] / 2
        x = pos if pos < mitad else led["periodo"] - pos
        return int(led["brillo"] * (x / mitad) ** 2 + 0.5)

    def _evaluar_termo(self, t: float, ahora: int):
        t_min, t_max = self.termo
        bruta = 0 if t < t_min else (1 if t < t_max else 2)
        nueva = self.zona
        if self.zona < 0 or bruta > self.zona:
            nueva = bruta
        elif bruta < self.zona:
            umbral = t_max if self.zona == 2 else t_min
            if t < umbral - HISTERESIS:
                nueva = bruta
        if nueva != self.zona:
            self.zona = nueva
            self._apagar_todos()
            if nueva == 0:
                self.leds["G"].update(modo="ON", brillo=255)
            elif nueva == 1:
                self.leds["Y"].update(modo="ON", brillo=255)
            else:
                self.leds["R"].update(modo="BLINK", brillo=255, on=250, off=250, t0=ahora, fase=True)

    def lectura(self, ahora: int) -> tuple[int, int]:
        """Temperatura y humedad simuladas (el DHT11 mide en enteros)."""
        s = ahora / 1000
        return round(25 + 5 * math.sin(s / 25)), round(55 + 10 * math.cos(s / 40))

    def tick(self, ahora: int | None = None) -> list[str]:
        """Lo que el sketch hace en leerSensor(): devuelve las líneas DATA que tocan."""
        ahora = self.ms() if ahora is None else ahora
        self._sincronizar_seq(ahora)
        if ahora - self._ultimo_dht < self.periodo_dht:
            return []
        self._ultimo_dht = ahora
        t, h = self.lectura(ahora)
        if self.termo_activo:
            self._evaluar_termo(t, ahora)
        return [f"DATA T={t:.1f} H={h:.1f}"]

    def _bucle(self):
        while not self._stop.is_set():
            with self._lock:
                for linea in self.tick():
                    self._salida.put((linea + "\n").encode())
            time.sleep(0.05)
