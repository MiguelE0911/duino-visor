import time

from duinovisor.dominio.leds import COLORES, MODOS, LedConfig
from duinovisor.dominio.protocolo import comando_dht, comando_led, comando_termo
from duinovisor.hardware.enlace import Enlace
from duinovisor.hardware.simulador import ArduinoSimulado


def sim():
    return ArduinoSimulado(hilo=False)


def test_ping_y_errores():
    s = sim()
    assert s.procesar("PING") == ["PONG OAC-LEDS 1"]
    assert s.procesar("LED R ON 300") == ["ERR brillo 0-255"]
    assert s.procesar("LED Q ON 1") == ["ERR led " + " ".join(COLORES)]       # ERR led R G Y
    assert s.procesar("DHT 10") == ["ERR periodo 1000-3600000 ms"]
    assert s.procesar("") == []


def test_led_y_status():
    s = sim()
    assert s.procesar("led g blink 200 100 300") == ["OK LED G"]
    filas = s.procesar("STATUS")
    assert "STATE G BLINK 200 100 300 0" in filas and filas[-1] == "OK STATUS"


def test_termo_zonas():
    reloj = [0.0]
    s = ArduinoSimulado(reloj=lambda: reloj[0], hilo=False)
    s.procesar("TERMO 22 28")
    s.lectura = lambda ahora: (30, 50)
    s.tick(5000)
    assert s.leds["R"]["modo"] == "BLINK"
    s.lectura = lambda ahora: (27, 50)           # 27 >= 28-1: histéresis, sigue rojo
    s.tick(10000)
    assert s.leds["R"]["modo"] == "BLINK"
    s.lectura = lambda ahora: (26, 50)
    s.tick(15000)
    assert s.leds["Y"]["modo"] == "ON" and s.leds["R"]["modo"] == "OFF"


def test_todas_las_ordenes_que_arma_el_protocolo_las_acepta_el_simulador():
    s = sim()
    for c in COLORES:
        for modo in MODOS:
            cmd = comando_led(LedConfig(color=c, modo=modo, brillo=100, on_ms=50, off_ms=50, periodo_ms=500))
            assert s.procesar(cmd) == [f"OK LED {c}"], cmd
    assert s.procesar(comando_dht(1000)) == ["OK DHT"]
    assert s.procesar(comando_termo((20, 30))) == ["OK TERMO"]
    assert s.procesar(comando_termo(None)) == ["OK TERMO"]


def test_enlace_con_el_simulador():
    e = Enlace()
    e.usar(ArduinoSimulado())
    try:
        e.enviar("PING")
        e.enviar("LED R ON 50")
        recibidos = []
        fin = time.time() + 2
        while len(recibidos) < 2 and time.time() < fin:
            try:
                recibidos.append(e.cola.get(timeout=0.2))
            except Exception:
                pass
        assert recibidos == [("rx", "PONG OAC-LEDS 1"), ("rx", "OK LED R")]
    finally:
        e.cerrar()
    assert not e.conectado


def test_enlace_avisa_si_se_pierde_el_puerto():
    class Roto:
        def readline(self):
            raise OSError("cable desconectado")

        def close(self):
            pass

        def write(self, d):
            pass

    e = Enlace()
    e.usar(Roto())
    tipo, texto = e.cola.get(timeout=2)
    assert tipo == "error" and "cable desconectado" in texto
    assert not e.conectado


# ---------------------------------------------------------------- secuencias en el simulador
def sim_reloj():
    reloj = [0.0]
    return ArduinoSimulado(reloj=lambda: reloj[0], hilo=False), reloj


def test_simulador_seq_vial_pausa_y_off():
    s, reloj = sim_reloj()
    assert s.procesar("SEQ VIAL") == ["OK SEQ"]
    assert s.brillo_actual("G") == 255
    reloj[0] = 5.5
    assert s.brillo_actual("G") == 0 and s.brillo_actual("Y") == 255
    assert s.procesar("SEQ PAUSA") == ["OK SEQ"]
    reloj[0] = 60
    assert s.brillo_actual("Y") == 255                               # congelado
    assert "STATE SEQ VIAL 100 PAUSA" in s.procesar("STATUS")
    s.procesar("SEQ SEGUIR")
    s.procesar("SEQ OFF")
    assert {s.brillo_actual(c) for c in COLORES} == {0}
    assert "STATE SEQ OFF" in s.procesar("STATUS")


def test_simulador_seq_errores_y_cancelaciones():
    s, reloj = sim_reloj()
    assert s.procesar("SEQ") == ["ERR uso SEQ nombre [vel] | OFF | PAUSA | SEGUIR"]
    assert s.procesar("SEQ FOO") == ["ERR secuencia VIAL FANTASTICO ALERTA"]
    assert s.procesar("SEQ VIAL 10") == ["ERR velocidad 25-400"]
    assert s.procesar("SEQ PAUSA") == ["ERR sin secuencia"]
    s.procesar("SEQ VIAL")
    s.procesar("LED R ON 50")
    assert {c: s.brillo_actual(c) for c in COLORES} == {c: 50 if c == "R" else 0 for c in COLORES}
    reloj[0] = 8
    assert {c: s.brillo_actual(c) for c in COLORES} == {c: 50 if c == "R" else 0 for c in COLORES}   # ya no corre
    s.procesar("SEQ ALERTA")
    s.procesar("TERMO 22 28")
    assert not s.seq.activa


def test_enlace_junta_lineas_que_llegan_en_trozos():
    """pyserial devuelve la línea a medias si vence el timeout (USB nativo): hay que juntarla."""
    class Troceado:
        def __init__(self):
            self.trozos = [b"DATA T=", b"24.0", b" H=51.0\r\n", b"OK LED ", b"R\r\n"]

        def readline(self):
            if self.trozos:
                return self.trozos.pop(0)
            time.sleep(0.01)
            return b""

        def close(self):
            pass

    e = Enlace()
    e.usar(Troceado())
    try:
        recibidos = [e.cola.get(timeout=2) for _ in range(2)]
        assert recibidos == [("rx", "DATA T=24.0 H=51.0"), ("rx", "OK LED R")]
    finally:
        e.cerrar()
