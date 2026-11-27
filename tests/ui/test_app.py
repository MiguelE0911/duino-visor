"""Prueba la lógica de la ventana (duinovisor/ui) (Aplicar, confirmaciones, secuencias, escenas, CSV, alarmas) con un Tkinter de mentira.

No dibuja nada: sirve para comprobar el flujo ventana -> protocolo -> Arduino simulado
en cualquier equipo, incluso sin Tkinter ni pantalla. NO sustituye probar la ventana real.
"""
import csv
import sys
import time
import types

import pytest

from duinovisor.dominio.leds import COLORES


class _Widget:
    def __init__(self, *args, **kw):
        self._children = []
        if args and isinstance(args[0], _Widget):
            args[0]._children.append(self)

    def winfo_children(self):
        return self._children

    def winfo_width(self):
        return 100

    winfo_height = winfo_reqwidth = winfo_reqheight = winfo_width

    def winfo_screenwidth(self):
        return 1366

    def winfo_screenheight(self):
        return 768

    def index(self, *_):
        return "1.0"

    def __setitem__(self, clave, valor):
        pass

    def __getattr__(self, nombre):          # pack, grid, bind, configure, after, create_*, ...
        return lambda *a, **k: None


class _Var:
    def __init__(self, master=None, value=None, **kw):
        self._v, self._cb = value, []

    def get(self):
        return self._v

    def set(self, v):
        self._v = v
        for cb in self._cb:
            cb()

    def trace_add(self, modo, cb):
        self._cb.append(lambda: cb())


def modulos_ui():
    """Módulos que importan Tkinter: se recargan con el Tkinter de mentira y se descartan después."""
    return [m for m in sys.modules if m == "duinovisor.ui" or m.startswith("duinovisor.ui.")]


@pytest.fixture
def gui(monkeypatch, tmp_path):
    monkeypatch.setenv("DUINOVISOR_AJUSTES", str(tmp_path / "ajustes.json"))
    tk = types.ModuleType("tkinter")
    for nombre in ("Tk", "Canvas", "Scale", "Text", "Frame", "Label", "Entry", "Menu", "Toplevel"):
        setattr(tk, nombre, type(nombre, (_Widget,), {}))
    tk.StringVar = tk.IntVar = tk.BooleanVar = _Var
    tk.TclError = Exception
    ttk = types.ModuleType("tkinter.ttk")
    for nombre in ("Frame", "LabelFrame", "Label", "Entry", "Button", "Radiobutton",
                   "Checkbutton", "Combobox", "Scrollbar", "Style"):
        setattr(ttk, nombre, type(nombre, (_Widget,), {}))
    avisos = []
    mb = types.ModuleType("tkinter.messagebox")
    mb.showwarning = mb.showerror = mb.showinfo = lambda *a, **k: avisos.append(a)
    fd = types.ModuleType("tkinter.filedialog")
    fd.asksaveasfilename = fd.askopenfilename = lambda **k: ""
    fnt = types.ModuleType("tkinter.font")
    fnt.families = lambda root=None: ("DejaVu Sans",)
    tk.ttk, tk.messagebox, tk.filedialog, tk.font = ttk, mb, fd, fnt
    for nombre, mod in (("tkinter", tk), ("tkinter.ttk", ttk), ("tkinter.messagebox", mb),
                        ("tkinter.filedialog", fd), ("tkinter.font", fnt)):
        monkeypatch.setitem(sys.modules, nombre, mod)
    for nombre in modulos_ui():
        monkeypatch.delitem(sys.modules, nombre, raising=False)
    from duinovisor.ui import app as g
    app = g.App(demo=True)
    app.avisos, app.fd = avisos, fd
    yield app
    app.enlace.cerrar()
    for nombre in modulos_ui():
        sys.modules.pop(nombre, None)


def esperar(app, condicion, segundos=3.0):
    fin = time.time() + segundos
    while time.time() < fin:
        app._ciclo()
        if condicion():
            return True
        time.sleep(0.02)
    return False


def terminado(app):
    return app.paso_actual is None and not app.pendientes


def enviar_y_esperar(app, accion):
    accion()
    assert esperar(app, lambda: terminado(app))


# ------------------------------------------------------------------ Aplicar
def test_aplicar_envia_confirma_y_no_repite(gui):
    p = gui.paneles
    p["R"].v_modo.set("BLINK")
    p["R"].v_on.set("300")
    p["R"].v_off.set("100")
    p["G"].v_modo.set("ON")
    p["G"].v_brillo.set(100)
    enviar_y_esperar(gui, gui.aplicar)
    assert gui.sim.leds["R"]["modo"] == "BLINK" and gui.sim.leds["R"]["on"] == 300
    assert gui.sim.leds["G"]["brillo"] == 100
    assert gui.aplicado.leds["R"].modo == "BLINK" and gui.aplicado.dht_ms == 2000
    assert gui._brillos_espejo()["G"] == 100                     # el espejo de la ventana lo refleja
    gui.aplicar()                                                # sin cambios: nada que enviar
    assert terminado(gui)
    p["G"].v_brillo.set(10)
    gui.aplicar()
    assert [x.texto for x in [gui.paso_actual] + gui.pendientes] == ["LED G ON 10"]
    assert esperar(gui, lambda: terminado(gui))
    assert gui.sim.leds["G"]["brillo"] == 10


def test_valores_invalidos_no_envian_nada(gui):
    p = gui.paneles
    p["Y"].v_modo.set("BLINK")
    p["Y"].v_on.set("5")                      # menos de 20 ms
    gui.aplicar()
    assert gui.avisos and terminado(gui)
    assert gui.sim.leds["Y"]["modo"] == "OFF"
    p["Y"].v_on.set("abc")
    gui.avisos.clear()
    gui.aplicar()
    assert gui.avisos
    gui.v_dht.set("500")
    p["Y"].v_modo.set("OFF")
    gui.avisos.clear()
    gui.aplicar()
    assert gui.avisos and gui.sim.periodo_dht == 2000


def test_error_del_arduino_detiene_el_envio_sin_marcar_aplicado(gui):
    gui.paneles["R"].v_modo.set("ON")
    gui.paneles["G"].v_modo.set("ON")
    original = gui.sim.procesar
    gui.sim.procesar = lambda t: ["ERR brillo 0-255"] if t.startswith("LED G") else original(t)
    gui.aplicar()
    assert esperar(gui, lambda: terminado(gui))
    assert "R" in gui.aplicado.leds and "G" not in gui.aplicado.leds
    assert "Y" not in gui.aplicado.leds                # no se llegó a enviar
    assert gui.sim.leds["Y"]["modo"] == "OFF"


def test_semaforo_termico_espejo_y_datos_en_vivo(gui):
    gui.v_dht.set("1000")
    gui.v_termo.set(True)
    gui.v_tmin.set("22")
    gui.v_tmax.set("28")
    enviar_y_esperar(gui, gui.aplicar)
    assert gui.sim.termo_activo and gui.aplicado.termo == (22, 28)
    assert esperar(gui, lambda: gui.v_temp.get() != "-- °C", 3)       # llegó un DATA
    assert len(gui.grafica.temperaturas) >= 1
    assert gui.zona == gui.sim.zona >= 0                              # la ventana y el Arduino coinciden
    if gui.zona != 2:                                                 # en zona roja el LED parpadea
        assert gui._brillos_espejo() == {c: 255 if gui.sim.leds[c]["modo"] == "ON" else 0 for c in COLORES}
    gui.v_termo.set(False)
    gui.aplicar()
    assert [x.texto for x in [gui.paso_actual] + gui.pendientes][0] == "TERMO OFF"
    assert len([gui.paso_actual] + gui.pendientes) == 1 + len(COLORES)      # TERMO OFF y cada LED
    assert esperar(gui, lambda: terminado(gui))
    assert not gui.sim.termo_activo and gui.zona == -1


# ------------------------------------------------------------------ secuencias
def test_secuencia_iniciar_pausar_seguir_cambiar_y_detener(gui):
    assert gui.b_seq.texto == "Iniciar"
    gui.v_seq.set("ALERTA")
    gui.v_vel.set(200)
    enviar_y_esperar(gui, gui.alternar_secuencia)
    assert gui.aplicado.seq == ("ALERTA", 200, False)
    assert gui.sim.seq.activa and gui.sim.seq.vel == 200 and gui.secuencia.activa
    assert gui.b_seq.texto == "Pausar" and set(gui._brillos_espejo()) == set(COLORES)

    enviar_y_esperar(gui, gui.alternar_secuencia)                       # pausa
    assert gui.aplicado.seq[2] and gui.sim.seq.pausada and gui.secuencia.pausada
    assert gui.b_seq.texto == "Seguir"
    enviar_y_esperar(gui, gui.alternar_secuencia)                       # seguir
    assert not gui.sim.seq.pausada and not gui.secuencia.pausada

    gui.v_seq.set("VIAL")                                               # otra secuencia mientras corre
    assert gui.b_seq.texto == "Cambiar"
    enviar_y_esperar(gui, gui.alternar_secuencia)
    assert gui.sim.seq.nombre == "VIAL" and gui.secuencia.nombre == "VIAL" and gui.v_vel.get() == 200

    enviar_y_esperar(gui, gui.detener_secuencia)
    assert not gui.sim.seq.activa and gui.aplicado.seq is None and not gui.secuencia.activa
    assert gui.b_seq.texto == "Iniciar"
    assert gui._brillos_espejo() == {c: 0 for c in COLORES}


def test_orden_manual_cancela_secuencia_en_arduino_y_ventana(gui):
    gui.v_seq.set("VIAL")
    enviar_y_esperar(gui, gui.alternar_secuencia)
    assert gui.secuencia.activa
    gui.paneles["R"].v_modo.set("ON")
    gui.paneles["R"].v_brillo.set(80)
    # los paneles están bloqueados mientras corre la secuencia, pero Aplicar sigue siendo válido
    enviar_y_esperar(gui, gui.aplicar)
    assert not gui.sim.seq.activa and not gui.secuencia.activa and gui.aplicado.seq is None
    assert gui._brillos_espejo() == {c: 80 if c == "R" else 0 for c in COLORES}


def test_cerrar_o_desconectar_detiene_la_secuencia_del_arduino(gui):
    sim = gui.sim
    gui.v_seq.set("FANTASTICO")
    enviar_y_esperar(gui, gui.alternar_secuencia)
    assert sim.seq.activa
    gui.desconectar()
    assert not sim.seq.activa


def test_sin_conexion_no_se_envia(gui):
    gui.desconectar()
    gui.avisos.clear()
    gui.alternar_secuencia()
    assert gui.avisos and terminado(gui)


# ------------------------------------------------------------------ escenas, CSV y alarmas
def test_escena_guardar_y_cargar(gui, tmp_path):
    ruta = str(tmp_path / "e.json")
    gui.fd.asksaveasfilename = lambda **k: ruta
    gui.fd.askopenfilename = lambda **k: ruta
    p = gui.paneles
    p["R"].v_modo.set("FADE")
    p["R"].v_periodo.set("3000")
    p["G"].v_modo.set("ON")
    p["G"].v_brillo.set(42)
    gui.v_dht.set("1500")
    gui.v_seq.set("FANTASTICO")
    gui.v_vel.set(150)
    gui.guardar_escena()
    p["R"].v_modo.set("OFF")
    p["G"].v_brillo.set(255)
    gui.v_dht.set("2000")
    gui.v_seq.set("VIAL")
    gui.cargar_escena()
    assert p["R"].v_modo.get() == "FADE" and p["R"].v_periodo.get() == "3000"
    assert p["G"].v_modo.get() == "ON" and p["G"].v_brillo.get() == 42
    assert gui.v_dht.get() == "1500" and gui.v_seq.get() == "FANTASTICO" and gui.v_vel.get() == 150
    enviar_y_esperar(gui, gui.aplicar)                                  # la escena cargada se puede aplicar
    assert gui.sim.leds["R"]["modo"] == "FADE" and gui.sim.periodo_dht == 1500


def test_escena_invalida_no_cambia_nada(gui, tmp_path):
    mala = tmp_path / "mala.json"
    mala.write_text('{"version": 1}', encoding="utf-8")
    gui.fd.askopenfilename = lambda **k: str(mala)
    gui.paneles["G"].v_brillo.set(7)
    gui.cargar_escena()
    assert gui.avisos and gui.paneles["G"].v_brillo.get() == 7


def test_csv_y_alarmas(gui, tmp_path):
    gui.exportar_csv()                                                  # sin lecturas: avisa
    assert gui.avisos
    gui.v_dht.set("1000")
    gui.v_alarmas.set(True)
    gui.v_amax_t.set("10")                                              # el simulador da ~25 °C
    enviar_y_esperar(gui, gui.aplicar)
    assert esperar(gui, lambda: len(gui.lecturas) >= 1, 3)
    assert gui.alarma_t.activa and "Temperatura" in gui.alarma_t.motivo
    gui.v_alarmas.set(False)                                            # al desactivarlas se apagan
    gui.sim.lectura = lambda ahora: (25, 50)
    assert esperar(gui, lambda: not gui.alarma_t.activa, 3)
    ruta = tmp_path / "lecturas.csv"
    gui.fd.asksaveasfilename = lambda **k: str(ruta)
    gui.exportar_csv()
    filas = list(csv.reader(ruta.read_text(encoding="utf-8-sig").splitlines()))
    assert filas[0] == ["fecha_hora", "temperatura_c", "humedad_pct", "estado"] and len(filas) >= 2
    assert filas[1][3] == "ok"


def test_cambiar_de_vista_no_pierde_la_configuracion(gui):
    app = gui
    assert app.vista_actual == "semaforo"
    app.paneles["R"].v_modo.set("ON")
    app.mostrar_vista("clima")
    assert app.vista_actual == "clima"
    app.mostrar_vista("semaforo")
    assert app.paneles["R"].v_modo.get() == "ON"
    assert set(app.vistas) == {"semaforo", "clima", "config"}


# ------------------------------------------------------------------ interfaz nueva (luces, ritmos, tema)
def test_elegir_led_cambia_el_editor(gui):
    assert gui.v_sel.get() == "R" and gui.led_editor is gui.paneles["R"]
    gui.semaforo.al_elegir("G")                                          # clic en una luz del semáforo
    assert gui.led_editor is gui.paneles["G"] and gui.v_titulo_editor.get() == "Luz verde"
    gui.protoboard.al_elegir("Y")                                        # clic en un LED de la protoboard
    assert gui.led_editor is gui.paneles["Y"]
    gui.chips["R"].comando()                                             # clic en un chip
    assert gui.led_editor is gui.paneles["R"] and gui.chips["R"].seleccionado


def test_ritmos_escriben_los_milisegundos(gui):
    led = gui.paneles["R"]
    led.v_modo.set("BLINK")
    assert led.v_ritmo.get() == "normal"                                 # 500/500 por defecto
    led.v_ritmo.set("rapido")
    assert (led.v_on.get(), led.v_off.get()) == ("200", "200")
    led.v_on.set("350")                                                  # a medida desde los detalles
    assert led.v_ritmo.get() == "" and "a medida" in led.resumen()
    led.v_modo.set("FADE")
    led.v_ritmo.set("lento")
    assert led.v_periodo.get() == "4000" and led.obtener().periodo_ms == 4000
    enviar_y_esperar(gui, gui.aplicar)
    assert gui.sim.leds["R"]["modo"] == "FADE"


def test_animacion_bloquea_el_editor_y_se_puede_detener(gui):
    gui.v_seq.set("ALERTA")
    enviar_y_esperar(gui, gui.alternar_secuencia)
    assert not gui.paneles["R"].habilitado and gui._bloqueo_editor
    assert gui.chips["R"].resumen == "Automático"
    gui._desbloquear()                                                   # botón «Detener animación»
    assert esperar(gui, lambda: terminado(gui))
    assert gui.aplicado.seq is None and gui.paneles["R"].habilitado


def test_cambiar_tema_conserva_todo(gui):
    from duinovisor.almacenamiento import preferencias
    from duinovisor.ui import tema as T
    gui.paneles["G"].v_modo.set("ON")
    enviar_y_esperar(gui, gui.aplicar)
    gui.grafica.agregar(24.0, 50.0)
    gui.log("línea de prueba")
    aplicado = gui.aplicado
    gui.v_tema.set("oscuro")
    gui.v_acento.set("violeta")
    assert T.tema_actual == "oscuro" and T.ACENTO == T.ACENTOS["violeta"][2]
    assert preferencias.cargar() == {**preferencias.POR_DEFECTO, "tema": "oscuro", "acento": "violeta"}
    assert gui.aplicado is aplicado and gui.paneles["G"].v_modo.get() == "ON"
    assert list(gui.grafica.temperaturas)[-1] == 24.0                    # la gráfica nueva tiene el historial
    assert ("línea de prueba", "info") in gui._lineas_log
    gui.alternar_tema()
    assert T.tema_actual == "claro"


# ------------------------------------------------------------------ configuración y acerca de
def test_configuracion_es_una_pestana_y_sobrevive_al_cambio_de_tema(gui):
    gui.v_vista.set("config")
    assert gui.vista_actual == "config"
    gui.v_tema.set("oscuro")                                             # reconstruye la ventana
    assert gui.vista_actual == "config"


def test_periodo_del_sensor_con_selector_y_valor_exacto(gui):
    assert gui.v_dht.get() == "2000" and gui.v_dht_preset.get() == "2000"
    gui.v_dht_preset.set("5000")                                         # elegir «5 s»
    assert gui.v_dht.get() == "5000"
    gui.v_dht.set("1234")                                                # a medida desde los detalles
    assert gui.v_dht_preset.get() == ""
    gui.v_dht.set("60000")
    assert gui.v_dht_preset.get() == "60000"
    enviar_y_esperar(gui, gui.aplicar)
    assert gui.sim.periodo_dht == 60000


def test_conexion_automatica_se_recuerda(gui, monkeypatch):
    from duinovisor.almacenamiento import preferencias
    gui.v_auto.set(False)
    assert preferencias.cargar()["auto_conectar"] is False
    from duinovisor.ui import app as g
    buscadas = []
    monkeypatch.setattr(g.App, "buscar_placa", lambda self: buscadas.append(1))
    otra = g.App(demo=False)                                             # sin demo y sin conexión automática
    try:
        assert not buscadas and not otra.enlace.conectado
        assert "Configuración" in otra.v_estado.get()
    finally:
        otra.enlace.cerrar()


def test_acerca_de_se_abre_una_sola_vez(gui):
    gui.abrir_acerca()
    ventana = gui._ventana_acerca
    assert ventana is not None
    gui.abrir_acerca()
    assert gui._ventana_acerca is ventana
    gui._cerrar_acerca()
    assert gui._ventana_acerca is None
