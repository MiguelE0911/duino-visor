"""Compila control_leds.ino contra un Arduino simulado en C++ y prueba su comportamiento."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from duinovisor.dominio.leds import COLORES, LedConfig, brillo_en
from duinovisor.dominio.placa import PINES
from duinovisor.dominio.secuencias import SecuenciaLocal

AQUI = Path(__file__).parent
pytestmark = pytest.mark.skipif(shutil.which("g++") is None, reason="se necesita g++")


@pytest.fixture(scope="module")
def binario(tmp_path_factory):
    salida = tmp_path_factory.mktemp("sketch") / "sketch_test"
    r = subprocess.run(
        ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", f"-I{AQUI / 'shim'}",
         "-o", str(salida), str(AQUI / "driver.cpp")],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return salida


def correr(binario, *lineas):
    r = subprocess.run([str(binario)], input="\n".join(lineas) + "\n", capture_output=True, text=True, timeout=30)
    return r.stdout.splitlines()


def sin_datos(lineas):
    return [x for x in lineas if not x.startswith("DATA")]


def respuestas(salida):
    return [x[2:] for x in salida if x.startswith("< ")]


def cambios_pwm(salida, pin):
    """[(ms, valor)] de cada escritura PWM de un pin."""
    return [(int(m.group(1)), int(m.group(3))) for x in salida
            if (m := re.match(r"@(\d+) P(\d+)=(\d+)", x)) and int(m.group(2)) == pin]


def ultimo_pwm(salida):
    ln = [x for x in salida if x.startswith("PWM")][-1]
    return {int(k): int(v) for k, v in re.findall(r"(\d+)=(\d+)", ln)}


def test_ping(binario):
    assert respuestas(correr(binario, "> PING")) == ["PONG OAC-LEDS 1"]


def test_led_on_y_minusculas(binario):
    s = correr(binario, "> LED G ON 128", "> led r on 10", "t 5", "pwm")
    assert respuestas(s) == ["OK LED G", "OK LED R"]
    assert ultimo_pwm(s) == {3: 10, 5: 128, 6: 0}


def test_led_off(binario):
    s = correr(binario, "> LED G ON 255", "t 5", "> LED G OFF", "t 5", "pwm")
    assert ultimo_pwm(s)[5] == 0


@pytest.mark.parametrize("orden,error", [
    ("LED R ON 300", "ERR brillo 0-255"),
    ("LED R ON -1", "ERR brillo 0-255"),
    ("LED R ON abc", "ERR brillo 0-255"),
    ("LED X ON 10", "ERR led " + " ".join(COLORES)),            # ERR led R G Y
    ("LED R BLINK 255 10 100", "ERR tiempo 20-60000 ms"),
    ("LED R FADE 255 100", "ERR periodo 200-60000 ms"),
    ("LED R SALTAR", "ERR modo"),
    ("LED R", "ERR faltan argumentos"),
    ("DHT 500", "ERR periodo 1000-3600000 ms"),
    ("TERMO 30 20", "ERR uso TERMO tmin tmax (tmin<tmax) | TERMO OFF"),
    ("HOLA", "ERR comando"),
])
def test_errores(binario, orden, error):
    assert respuestas(correr(binario, f"> {orden}")) == [error]


def test_linea_larga_se_descarta(binario):
    s = correr(binario, "> " + "A" * 100, "> PING")
    assert respuestas(s) == ["ERR linea larga", "PONG OAC-LEDS 1"]


def test_error_no_cambia_el_led(binario):
    s = correr(binario, "> LED R ON 100", "> LED R ON 999", "t 5", "pwm")
    assert ultimo_pwm(s)[3] == 100


def test_blink_tiempos(binario):
    s = correr(binario, "> LED Y BLINK 255 500 250", "t 1400")
    assert cambios_pwm(s, 6)[1:] == [(0, 255), (500, 0), (750, 255), (1250, 0)]


def test_blink_sobrevive_al_desborde_de_millis(binario):
    s = correr(binario, "start 4294966800", "> LED Y BLINK 255 500 250", "t 1400")
    c = cambios_pwm(s, 6)[1:]
    base = 4294966800
    esperado = [(base + 0, 255), (base + 500, 0), (base + 750, 255), (base + 1250, 0)]
    # los tiempos que pasan de 2^32 vuelven a empezar en 0
    esperado = [(t % 2**32, v) for t, v in esperado]
    assert c == esperado


def test_fade_sube_y_baja(binario):
    s = correr(binario, "> LED R FADE 200 2000", "t 4100")
    c = cambios_pwm(s, 3)[1:]
    valores = [v for _, v in c]
    assert max(valores) == 200
    pico = [t for t, v in c if v == 200][0]
    assert 950 <= pico <= 1050                      # el pico está a mitad del periodo
    subida = [v for t, v in c if t <= pico]
    assert subida == sorted(subida)                 # sube sin retroceder
    assert (2000, 0) in c or (2000, 1) in c or any(t >= 1990 and v <= 1 for t, v in c)
    # el segundo ciclo se repite 2 s después
    pico2 = [t for t, v in c if v == 200 and t > 1500][0]
    assert 2950 <= pico2 <= 3050


def test_dht_periodo_y_formato(binario):
    s = correr(binario, "> DHT 1000", "dht 24.0 51.0", "t 2500")
    assert respuestas(s) == ["OK DHT", "DATA T=24.0 H=51.0", "DATA T=24.0 H=51.0"]


def test_dht_error(binario):
    s = correr(binario, "> DHT 1000", "dht nan", "t 1100")
    assert respuestas(s) == ["OK DHT", "DATA ERR"]


def pwm_ahora(binario, *pasos):
    return ultimo_pwm(correr(binario, *pasos, "pwm"))


def test_termo_zonas_e_histeresis(binario):
    base = ["> DHT 1000", "> TERMO 22 28"]
    assert pwm_ahora(binario, *base, "dht 20 50", "t 1100") == {3: 0, 5: 255, 6: 0}        # verde
    assert pwm_ahora(binario, *base, "dht 25 50", "t 1100") == {3: 0, 5: 0, 6: 255}        # amarillo
    s = correr(binario, *base, "dht 30 50", "t 1100", "pwm")                                  # rojo parpadea
    assert [v for _, v in cambios_pwm(s, 3)] == [0, 255]
    assert len(cambios_pwm(correr(binario, *base, "dht 30 50", "t 2000"), 3)) > 3
    # histéresis: tras estar en rojo, 27.5 sigue rojo y 26.5 ya baja a amarillo
    s = correr(binario, *base, "dht 30 50", "t 1100", "dht 27.5 50", "t 1000", "t 0", "pwm")
    assert 255 in [v for _, v in cambios_pwm(s, 3)] and ultimo_pwm(s)[6] == 0
    assert pwm_ahora(binario, *base, "dht 30 50", "t 1100", "dht 26.5 50", "t 1000")[6] == 255
    # sube sin histéresis: verde -> amarillo apenas llega a 22
    assert pwm_ahora(binario, *base, "dht 20 50", "t 1100", "dht 22 50", "t 1000")[6] == 255
    # bajar de amarillo a verde exige 21 °C o menos: 21.5 se queda amarillo
    assert pwm_ahora(binario, *base, "dht 25 50", "t 1100", "dht 21.5 50", "t 1000")[6] == 255


def test_led_manual_cancela_termo(binario):
    s = correr(binario, "> DHT 1000", "> TERMO 22 28", "dht 25 50", "t 1100",
               "> LED G ON 50", "dht 30 50", "t 1100", "pwm")
    assert ultimo_pwm(s) == {3: 0, 5: 50, 6: 0} or ultimo_pwm(s)[5] == 50
    assert ultimo_pwm(s)[6] == 0                    # el amarillo del semáforo se apagó


def test_termo_off(binario):
    s = correr(binario, "> DHT 1000", "> TERMO 22 28", "dht 25 50", "t 1100", "> TERMO OFF", "t 5", "pwm")
    assert ultimo_pwm(s) == {3: 0, 5: 0, 6: 0}


def test_status(binario):
    s = correr(binario, "> LED G BLINK 200 100 300", "> LED R FADE 200 2000", "> STATUS")
    r = respuestas(s)
    assert "STATE G BLINK 200 100 300 0" in r
    assert "STATE R FADE 200 0 0 2000" in r
    assert "STATE Y OFF 0 0 0 0" in r
    assert r[-1] == "OK STATUS"


# ---------------------------------------------------------------- secuencias
def test_seq_vial_tiempos(binario):
    s = correr(binario, "> SEQ VIAL", "t 12000")
    assert sin_datos(respuestas(s)) == ["OK SEQ"]
    assert cambios_pwm(s, 5)[1:] == [(0, 255), (5000, 0), (11500, 255)]      # verde
    assert cambios_pwm(s, 6)[1:] == [(5000, 255), (6500, 0)]                  # amarillo
    assert cambios_pwm(s, 3)[1:] == [(6500, 255), (11500, 0)]                  # rojo


def test_seq_velocidad(binario):
    s = correr(binario, "> SEQ VIAL 200", "t 3000")
    assert cambios_pwm(s, 5)[1:] == [(0, 255), (2500, 0)]                     # el doble de rápido
    s = correr(binario, "> SEQ VIAL 50", "t 11000")
    assert cambios_pwm(s, 5)[1:] == [(0, 255), (10000, 0)]


def test_seq_fantastico_barre_ida_y_vuelta(binario):
    s = correr(binario, "> SEQ FANTASTICO", "t 700")
    orden = sorted([(t, pin) for pin in (3, 5, 6) for t, v in cambios_pwm(s, pin)[1:] if v == 255])
    assert [p for _, p in orden] == [3, 6, 5, 6, 3]                         # R, Y, G, Y, R


def test_seq_pausa_y_seguir(binario):
    s = correr(binario, "> SEQ ALERTA", "t 700", "> SEQ PAUSA", "t 2000", "> SEQ SEGUIR", "t 400")
    assert sin_datos(respuestas(s)) == ["OK SEQ", "OK SEQ", "OK SEQ"]
    # amarillo: enciende en 0 y apaga en 500; en pausa (700-2700) no cambia;
    # al seguir faltaban 300 ms del paso apagado, así que vuelve a encender en 3000
    assert cambios_pwm(s, 6)[1:] == [(0, 255), (500, 0), (3000, 255)]


def test_seq_off_apaga_todo(binario):
    s = correr(binario, "> SEQ VIAL", "t 100", "> SEQ OFF", "t 6000", "pwm")
    assert ultimo_pwm(s) == {3: 0, 5: 0, 6: 0}


def test_led_manual_y_termo_cancelan_seq(binario):
    s = correr(binario, "> SEQ VIAL", "t 100", "> LED R ON 50", "t 6000", "pwm")
    assert ultimo_pwm(s) == {3: 50, 5: 0, 6: 0}
    # TERMO manda: la secuencia ya no corre (el rojo del VIAL llegaría a 6500) y queda el amarillo de 24 °C
    s = correr(binario, "> SEQ VIAL", "t 100", "> TERMO 22 28", "t 8000", "pwm")
    assert ultimo_pwm(s) == {3: 0, 5: 0, 6: 255}


def test_seq_cancela_termo(binario):
    s = correr(binario, "> DHT 1000", "> TERMO 22 28", "dht 25 50", "t 1100", "> SEQ ALERTA", "dht 30 50", "t 1100", "pwm")
    assert ultimo_pwm(s)[3] == 0                                                # no se puso rojo por TERMO


@pytest.mark.parametrize("orden,error", [
    ("SEQ", "ERR uso SEQ nombre [vel] | OFF | PAUSA | SEGUIR"),
    ("SEQ FOO", "ERR secuencia VIAL FANTASTICO ALERTA"),
    ("SEQ VIAL 10", "ERR velocidad 25-400"),
    ("SEQ VIAL 500", "ERR velocidad 25-400"),
    ("SEQ VIAL rapido", "ERR velocidad 25-400"),
    ("SEQ PAUSA", "ERR sin secuencia"),
    ("SEQ SEGUIR", "ERR sin secuencia"),
])
def test_seq_errores(binario, orden, error):
    assert respuestas(correr(binario, f"> {orden}")) == [error]


def test_status_incluye_secuencia(binario):
    r = respuestas(correr(binario, "> STATUS"))
    assert "STATE SEQ OFF" in r and r[-1] == "OK STATUS"
    r = respuestas(correr(binario, "> SEQ VIAL 150", "> SEQ PAUSA", "> STATUS"))
    assert "STATE SEQ VIAL 150 PAUSA" in r


# ------------------------------------- el modelo Python de la app coincide con el sketch
@pytest.mark.parametrize("nombre,vel,ms", [("VIAL", 100, 24000), ("VIAL", 150, 12000),
                                           ("FANTASTICO", 100, 2000), ("FANTASTICO", 300, 600),
                                           ("ALERTA", 100, 3500), ("ALERTA", 400, 500)])
def test_modelo_local_coincide_con_el_sketch(binario, nombre, vel, ms):
    orden = f"SEQ {nombre}" if vel == 100 else f"SEQ {nombre} {vel}"
    s = correr(binario, f"> {orden}", f"t {ms}")
    esperado = {}
    modelo = SecuenciaLocal()
    modelo.iniciar(nombre, vel, 0)
    previo = {c: 0 for c in COLORES}
    for t in range(ms + 1):                                  # el driver también ejecuta loop() en t = ms
        b = modelo.brillos(t)
        for c, pin in PINES.items():
            if b[c] != previo[c]:
                esperado.setdefault(pin, []).append((t, b[c]))
                previo[c] = b[c]
    for pin in PINES.values():
        real = cambios_pwm(s, pin)[1:]                       # sin la escritura inicial de setup()
        assert real == esperado.get(pin, []), f"{nombre} x{vel} pin {pin}"


def test_brillo_en_coincide_con_el_sketch_en_fade_y_blink(binario):
    s = correr(binario, "> LED R FADE 255 1001", "t 2100")      # periodo impar a propósito
    modelo = LedConfig(color="R", modo="FADE", brillo=255, periodo_ms=1001)
    real, valor = {}, 0
    for t, v in cambios_pwm(s, 3)[1:]:
        real[t] = v
    for t in range(2101):
        esperado = brillo_en(modelo, t)
        if t in real:
            valor = real[t]
        assert valor == esperado, f"t={t}"


# ---------------------------------------------------------------- canal BLE (celular)
def respuestas_ble(salida):
    return [x[3:] for x in salida if x.startswith("b< ")]


def notificaciones(salida):
    """[(ms, bytes)] de cada notificación BLE. El shim aborta si un trozo pasa de 20 bytes."""
    return [(int(m.group(1)), int(m.group(2))) for x in salida if (m := re.match(r"@(\d+) NOTIF (\d+)", x))]


def test_ble_ping(binario):
    s = correr(binario, "ble on", "b> PING", "t 50")
    assert respuestas_ble(s) == ["PONG OAC-LEDS 1"]
    assert respuestas(s) == []                                   # el puerto serie no se entera


def test_ble_orden_partida_en_trozos(binario):
    orden = f"LED {COLORES[-1]} BLINK 255 500 250"                 # 25 caracteres: llega en 2 trozos
    s = correr(binario, "ble on", f"b> {orden}", "t 50", "pwm")
    assert respuestas_ble(s) == [f"OK LED {COLORES[-1]}"]
    assert ultimo_pwm(s)[PINES[COLORES[-1]]] == 255


def test_ble_status_igual_que_por_serie_y_en_trozos(binario):
    por_serie = respuestas(correr(binario, "> SEQ FANTASTICO", "> STATUS"))
    s = correr(binario, "ble on", "b> SEQ FANTASTICO", "b> STATUS", "t 300")
    assert sin_datos(respuestas_ble(s)) == por_serie
    tiempos = [t for t, _ in notificaciones(s)]
    assert len(tiempos) > 3
    assert all(b - a >= 15 for a, b in zip(tiempos, tiempos[1:]))     # sin saturar la pila BLE


def test_cada_canal_recibe_su_respuesta(binario):
    c = COLORES[0]
    s = correr(binario, "ble on", "> PING", f"b> LED {c} ON 10", "t 50")
    assert respuestas(s) == ["PONG OAC-LEDS 1"]
    assert respuestas_ble(s) == [f"OK LED {c}"]


def test_data_sale_por_ambos_canales(binario):
    s = correr(binario, "ble on", "> DHT 1000", "dht 24.0 51.0", "t 1100")
    assert respuestas(s) == ["OK DHT", "DATA T=24.0 H=51.0"]
    assert respuestas_ble(s) == ["DATA T=24.0 H=51.0"]


def test_ble_linea_larga_se_descarta(binario):
    s = correr(binario, "ble on", "b> " + "A" * 100, "b> PING", "t 100")
    assert respuestas_ble(s) == ["ERR linea larga", "PONG OAC-LEDS 1"]


def test_ble_sin_suscripcion_ejecuta_pero_no_notifica(binario):
    c = COLORES[0]
    s = correr(binario, "ble nosub", f"b> LED {c} ON 10", "t 50", "pwm")
    assert notificaciones(s) == []
    assert ultimo_pwm(s)[PINES[c]] == 10


def test_ble_al_desconectar_vuelve_a_anunciar_y_olvida_lo_pendiente(binario):
    s = correr(binario, "ble on", "b> STATUS", "ble off", "t 100", "ble on", "b> PING", "t 100")
    assert sum(1 for x in s if x.endswith("ANUNCIO")) == 2             # al arrancar y al desconectarse
    assert respuestas_ble(s) == ["PONG OAC-LEDS 1"]                    # nada del STATUS anterior


# ----------------------------------- la placa simulada de la app del celular responde igual que el sketch
ORDENES_COMPARADAS = [
    "PING", "STATUS", "HOLA", "LED", "LED X ON 10", f"LED {COLORES[0]}{COLORES[0]} ON 1",
    f"led {COLORES[0].lower()} on 10", f"LED {COLORES[0]} ON 300", f"LED {COLORES[0]} ON -1", f"LED {COLORES[0]} ON -0",
    f"LED {COLORES[0]} ON abc", f"LED {COLORES[0]} ON", f"LED {COLORES[0]} ON 10 x y z", f"LED {COLORES[0]} OFF 3",
    f"LED {COLORES[1]} BLINK 200 100 300", f"LED {COLORES[1]} BLINK 255 10 100", f"LED {COLORES[1]} BLINK 255 100 70000",
    f"LED {COLORES[-1]} FADE 255 100", f"LED {COLORES[-1]} FADE 120 1500", f"LED {COLORES[-1]} SALTAR", "STATUS",
    "DHT 500", "DHT 1000", "DHT", "TERMO 30 20", "TERMO 22", "TERMO 22 28", "STATUS", "TERMO OFF",
    "SEQ", "SEQ FOO", "SEQ PAUSA", "SEQ SEGUIR", "SEQ VIAL 10", "SEQ VIAL rapido", "SEQ VIAL 150", "STATUS",
    "SEQ PAUSA", "STATUS", "SEQ SEGUIR", "SEQ FANTASTICO", "STATUS", f"LED {COLORES[0]} ON 9", "STATUS",
    "SEQ ALERTA 400", "SEQ OFF", "STATUS", "A" * 64, "A" * 63, "\tping\t",
]


def test_simulador_movil_responde_igual_que_el_sketch(binario):
    if shutil.which("node") is None:
        pytest.skip("se necesita node")
    sketch = respuestas(correr(binario, *(f"> {o}" for o in ORDENES_COMPARADAS)))
    puente = AQUI.parents[1] / "movil" / "pruebas" / "herramientas" / "puente.js"
    r = subprocess.run(["node", str(puente), "responder"], input="\n".join(ORDENES_COMPARADAS) + "\n",
                       capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    assert respuestas(r.stdout.splitlines()) == sketch


def separaciones(salida):
    tiempos = [t for t, _ in notificaciones(salida)]
    return [b - a for a, b in zip(tiempos, tiempos[1:])]


@pytest.mark.parametrize("intervalo,minimo", [(45, 46), (30, 31), (7, 15)])
def test_ble_un_trozo_por_intervalo_de_conexion(binario, intervalo, minimo):
    # La radio del 101 descarta sin avisar lo que no cabe: nunca más de un trozo por intervalo (ni cada menos de 15 ms).
    s = correr(binario, f"ble intervalo {intervalo}", "ble on", "b> SEQ FANTASTICO", "b> STATUS", "t 1000")
    assert len(notificaciones(s)) > 3
    assert min(separaciones(s)) >= minimo
    assert sin_datos(respuestas_ble(s))[-1] == "OK STATUS"           # llega todo, solo que a su ritmo


def test_ble_se_adapta_si_el_celular_cambia_el_intervalo(binario):
    s = correr(binario, "ble intervalo 50", "ble on", "ble intervalo 15", "t 1100", "b> STATUS", "t 500")
    assert max(separaciones(s)) < 50                                   # ya midió el intervalo nuevo


def test_ble_pide_un_intervalo_corto_una_vez_por_conexion(binario):
    s = correr(binario, "ble on", "t 5000", "ble off", "ble on", "t 2000")
    pedidos = [x for x in s if "PIDE_INTERVALO" in x]
    assert len(pedidos) == 2
    assert all(x.endswith("PIDE_INTERVALO 15 30") for x in pedidos)
