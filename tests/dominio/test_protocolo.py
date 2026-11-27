import pytest

from duinovisor.dominio.leds import COLORES, LedConfig, brillo_en
from duinovisor.dominio.protocolo import (
    Aplicado,
    Mensaje,
    Paso,
    cambios,
    comando_dht,
    comando_led,
    comando_termo,
    confirmar,
    es_pong,
    interpretar,
    plan,
)
from duinovisor.dominio.secuencias import (
    SecuenciaLocal,
    paso_seq_detener,
    paso_seq_iniciar,
    paso_seq_pausa,
    paso_seq_seguir,
)
from duinovisor.dominio.termometro import leds_de_zona, zona_termo


def solo(**encendidos):
    """Brillo de todos los LEDs del catálogo: los nombrados con su valor, el resto en 0."""
    return {c: encendidos.get(c, 0) for c in COLORES}


def cfg(**k):
    return LedConfig(**{"color": "R", "modo": "ON", "brillo": 128, **k})


def test_comandos_led():
    assert comando_led(cfg(modo="OFF")) == "LED R OFF"
    assert comando_led(cfg(color="G", modo="ON", brillo=128)) == "LED G ON 128"
    assert comando_led(cfg(color="Y", modo="BLINK", brillo=255, on_ms=500, off_ms=250)) == "LED Y BLINK 255 500 250"
    assert comando_led(cfg(modo="FADE", brillo=200, periodo_ms=2000)) == "LED R FADE 200 2000"


@pytest.mark.parametrize("c", [
    cfg(brillo=256), cfg(brillo=-1),
    cfg(modo="BLINK", on_ms=19), cfg(modo="BLINK", off_ms=19),
    cfg(modo="FADE", periodo_ms=199), cfg(color="X"), cfg(modo="SALTAR"),
])
def test_validacion_rechaza(c):
    with pytest.raises(ValueError):
        comando_led(c)


def test_limites_validos():
    assert comando_led(cfg(brillo=0)) == "LED R ON 0"
    assert comando_led(cfg(brillo=255)) == "LED R ON 255"
    assert comando_led(cfg(modo="BLINK", on_ms=20, off_ms=20)).endswith("20 20")
    assert comando_led(cfg(modo="FADE", periodo_ms=200)).endswith("200")


def test_dht_y_termo():
    assert comando_dht(1000) == "DHT 1000"
    with pytest.raises(ValueError):
        comando_dht(999)
    assert comando_termo((22, 28)) == "TERMO 22 28"
    assert comando_termo(None) == "TERMO OFF"
    with pytest.raises(ValueError):
        comando_termo((28, 22))


def test_interpretar():
    m = interpretar("DATA T=24.5 H=51.0")
    assert (m.tipo, m.temperatura, m.humedad) == ("DATA", 24.5, 51.0)
    assert interpretar("DATA ERR").tipo == "DATA_ERR"
    assert interpretar("OK LED R") == Mensaje("OK", "LED R")
    assert interpretar("ERR brillo 0-255") == Mensaje("ERR", "brillo 0-255")
    assert interpretar("STATE G BLINK 200 100 300 2000").tipo == "STATE"
    assert interpretar("DATA T=abc H=1").tipo == "OTRO"
    assert interpretar("basura").tipo == "OTRO"
    assert es_pong("PONG OAC-LEDS 1") and not es_pong("PONG OTRA-COSA")


def test_cambios_solo_envia_lo_que_cambio():
    a = {"R": cfg(color="R"), "G": cfg(color="G"), "Y": cfg(color="Y", modo="OFF")}
    previo = dict(a)
    nuevo = {**a, "G": cfg(color="G", brillo=10)}
    assert cambios(nuevo, previo) == [("G", "LED G ON 10")]
    assert cambios(a, previo) == []
    assert len(cambios(a, {})) == 3          # al conectar se reenvía todo


def leds_todos():
    return {c: cfg(color=c) for c in COLORES}


TODOS_ON = [f"LED {c} ON 128" for c in COLORES]       # un LED ON 128 por cada LED del catálogo


def test_plan_primera_vez_envia_todo():
    pasos = plan(leds_todos(), 2000, None, Aplicado())
    assert [p.texto for p in pasos] == TODOS_ON + ["DHT 2000"]          # LED R/G/Y ON 128 y DHT 2000


def test_plan_valida_antes_de_enviar():
    malos = {**leds_todos(), "Y": cfg(color="Y", brillo=999)}
    with pytest.raises(ValueError):
        plan(malos, 2000, None, Aplicado())


def test_confirmar_y_replan_vacio():
    ap = Aplicado()
    for paso in plan(leds_todos(), 2000, None, ap):
        ap = confirmar(ap, paso)
    assert plan(leds_todos(), 2000, None, ap) == []


def test_un_paso_sin_confirmar_se_vuelve_a_enviar():
    ap = Aplicado()
    pasos = plan(leds_todos(), 2000, None, ap)
    ap = confirmar(ap, pasos[0])               # solo el primero recibió OK
    restantes = plan(leds_todos(), 2000, None, ap)
    assert [p.texto for p in restantes] == TODOS_ON[1:] + ["DHT 2000"]


def test_termo_envia_termo_y_no_leds():
    ap = Aplicado(dht_ms=2000)
    pasos = plan(leds_todos(), 2000, (22, 28), ap)
    assert [p.texto for p in pasos] == ["TERMO 22 28"]
    ap = confirmar(ap, pasos[0])
    assert plan(leds_todos(), 2000, (22, 28), ap) == []


def test_salir_de_termo_reenvia_los_leds():
    ap = Aplicado(dht_ms=2000, termo=(22, 28))
    pasos = plan(leds_todos(), 2000, None, ap)
    assert [p.texto for p in pasos] == ["TERMO OFF"] + TODOS_ON


# ---------------------------------------------------------------- secuencias y modelo local
def test_comandos_seq():
    assert paso_seq_iniciar("VIAL").texto == "SEQ VIAL"
    assert paso_seq_iniciar("VIAL", 150).texto == "SEQ VIAL 150"
    assert paso_seq_detener().texto == "SEQ OFF"
    actual = ("VIAL", 100, False)
    assert paso_seq_pausa(actual).valor == ("VIAL", 100, True)
    assert paso_seq_seguir(("VIAL", 100, True)).valor == ("VIAL", 100, False)
    for malo in (("FOO", 100), ("VIAL", 24), ("VIAL", 401)):
        with pytest.raises(ValueError):
            paso_seq_iniciar(*malo)


def test_confirmar_seq_limpia_lo_que_el_arduino_cancela():
    ap = Aplicado(leds={"R": cfg()}, termo=(22, 28), dht_ms=2000)
    ap = confirmar(ap, paso_seq_iniciar("ALERTA"))
    assert ap.seq == ("ALERTA", 100, False) and ap.termo is None and ap.leds == {}
    ap = confirmar(ap, Paso("LED R ON 5", "led", "R", cfg(brillo=5)))
    assert ap.seq is None                                        # una orden manual cancela la secuencia


def test_plan_despues_de_secuencia_reenvia_los_leds():
    ap = confirmar(Aplicado(dht_ms=2000), paso_seq_iniciar("VIAL"))
    assert [p.texto for p in plan(leds_todos(), 2000, None, ap)] == TODOS_ON


def test_secuencia_local_vial():
    s = SecuenciaLocal()
    assert s.brillos(0) is None and not s.activa
    s.iniciar("VIAL", 100, 1000)
    assert s.brillos(1000) == solo(G=255)
    assert s.brillos(5999) == solo(G=255)
    assert s.brillos(6000) == solo(Y=255)
    assert s.brillos(7500) == solo(R=255)
    assert s.brillos(12500) == solo(G=255)       # vuelve a empezar: ciclo de 11,5 s


def test_secuencia_local_velocidad_pausa_y_seguir():
    s = SecuenciaLocal()
    s.iniciar("ALERTA", 100, 0)
    s.pausar(700)
    assert s.pausada and s.brillos(5000) == solo()     # congelada en el paso apagado
    s.seguir(2700)
    assert s.brillos(2999) == solo() and s.brillos(3000)["Y"] == 255   # faltaban 300 ms
    s.iniciar("VIAL", 200, 0)
    assert s.brillos(2499)["G"] == 255 and s.brillos(2500)["Y"] == 255
    s.detener()
    assert not s.activa and s.brillos(0) is None


def test_sincronizar_con_lo_confirmado():
    s = SecuenciaLocal()
    s.sincronizar(("VIAL", 100, False), 0)
    assert s.activa and not s.pausada
    s.sincronizar(("VIAL", 100, True), 100)
    assert s.pausada
    s.sincronizar(("VIAL", 100, False), 600)
    assert not s.pausada
    s.sincronizar(None, 700)
    assert not s.activa


def test_brillo_en_igual_que_el_sketch():
    assert brillo_en(cfg(modo="OFF"), 123) == 0
    assert brillo_en(cfg(modo="ON", brillo=77), 123) == 77
    b = cfg(modo="BLINK", brillo=255, on_ms=500, off_ms=250)
    assert [brillo_en(b, t) for t in (0, 499, 500, 749, 750)] == [255, 255, 0, 0, 255]
    f = cfg(modo="FADE", brillo=200, periodo_ms=2000)
    assert brillo_en(f, 0) == 0 and brillo_en(f, 1000) == 200 and brillo_en(f, 2000) == 0
    assert brillo_en(f, 500) == 50                              # gamma: 200 * 0.5^2


def test_zona_termo_y_leds():
    z = zona_termo(20, -1, 22, 28)
    assert z == 0
    assert zona_termo(22, z, 22, 28) == 1                      # sube sin histéresis
    assert zona_termo(21.5, 1, 22, 28) == 1                    # baja solo bajo 21
    assert zona_termo(20.9, 1, 22, 28) == 0
    assert zona_termo(30, 1, 22, 28) == 2 and zona_termo(27.5, 2, 22, 28) == 2
    assert zona_termo(26.9, 2, 22, 28) == 1
    assert leds_de_zona(0)["G"].modo == "ON" and leds_de_zona(1)["Y"].modo == "ON"
    assert leds_de_zona(2)["R"].modo == "BLINK" and leds_de_zona(-1)["R"].modo == "OFF"


# ---------------------------------------------------------------- catálogo de componentes
def test_catalogo_es_la_unica_fuente_de_los_leds():
    from duinovisor.dominio.leds import NOMBRES_COLOR
    from duinovisor.dominio.placa import LEDS, PINES, led
    assert COLORES == tuple(x.id for x in LEDS) and set(NOMBRES_COLOR) == set(COLORES)
    assert len(set(COLORES)) == len(COLORES) and len(set(PINES.values())) == len(PINES)
    assert led("R").pin == PINES["R"]
    assert sorted(x.fila for x in LEDS) == list(range(len(LEDS)))          # posiciones del semáforo sin huecos


def test_secuencias_y_zonas_solo_nombran_leds_del_catalogo():
    from duinovisor.dominio.secuencias import SECUENCIAS
    from duinovisor.dominio.termometro import LUZ_DE_ZONA
    for pasos in SECUENCIAS.values():
        for ms, brillos in pasos:
            assert ms > 0 and set(brillos) <= set(COLORES)
            assert all(0 <= b <= 255 for b in brillos.values())
    assert {z.color for z in LUZ_DE_ZONA} <= set(COLORES)


def test_secuencia_local_da_brillo_a_todos_los_leds():
    s = SecuenciaLocal()
    s.iniciar("ALERTA", 100, 0)
    assert s.brillos(0) == {c: (255 if c == "Y" else 0) for c in COLORES}
    assert s.brillos(600) == {c: 0 for c in COLORES}
