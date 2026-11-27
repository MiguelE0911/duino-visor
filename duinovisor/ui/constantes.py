"""Textos y ajustes de la ventana que comparten varias vistas."""
from duinovisor.dominio.placa import LEDS
from duinovisor.dominio.secuencias import NOMBRES_SEQ
from duinovisor.dominio.secuencias import SECUENCIAS as _TABLA_SEQ

SIN_RESPUESTA_MS = 1500
POLL_MS = 50
MAX_LECTURAS_CSV = 100_000
MODOS = [("OFF", "Apagada"), ("ON", "Encendida"), ("BLINK", "Parpadea"), ("FADE", "Respira")]
SECUENCIAS = [(n, NOMBRES_SEQ[n]) for n in _TABLA_SEQ]
NOMBRE_LUZ = {led.id: led.luz for led in LEDS}
ORDEN_SEMAFORO = tuple(led.id for led in sorted(LEDS, key=lambda led: led.fila))   # de arriba abajo
# Ritmos sencillos: Parpadea usa el mismo tiempo encendida y apagada; Respira, el periodo completo.
RITMOS = {"BLINK": {"lento": 1000, "normal": 500, "rapido": 200},
          "FADE": {"lento": 4000, "normal": 2000, "rapido": 1000}}
OPCIONES_RITMO = [("lento", "Lento"), ("normal", "Normal"), ("rapido", "Rápido")]
ZONAS = ["hace fresco (verde)", "templado (amarillo)", "hace calor (rojo)"]
ANCHO_LATERAL = 340
