"""Fichas técnicas de los componentes de la protoboard: qué es, a qué está conectado, qué hace y su estado.

Solo arma textos (sin Tkinter): la ventana le pasa lo que sabe del espejo y la ficha se dibuja en
`widgets/protoboard.FichaComponente`. Todas las fichas tienen las mismas tres filas.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from duinovisor.dominio.leds import BRILLO_MAX, LedConfig
from duinovisor.dominio.placa import RESISTENCIA_DHT, RESISTENCIA_LED, Led, Sensor

QUE_ES_LED = ("Un LED (diodo emisor de luz) se enciende cuando el Arduino le da corriente. La resistencia limita "
              "esa corriente para que no se queme, y un pin con PWM permite elegir su brillo encendiéndolo y "
              "apagándolo muy rápido.")
FILAS = ("Conectado a", "Qué hace", "Ahora")


@dataclass(frozen=True)
class Ficha:
    titulo: str
    que_es: str
    filas: tuple[tuple[str, str], ...]       # (etiqueta, valor), siempre las de FILAS
    tipo: str = "led"                        # "led" o "sensor": qué icono lleva
    subtitulo: str = ""                      # «LED · pin 3 (PWM)»
    color: str = "#888888"                   # el del componente real (franja e icono)
    nivel: Optional[float] = None            # 0-1 para la barrita de «Ahora» (brillo o humedad)
    activo: bool = False                     # punto de estado encendido en «Ahora»
    accion: str = ""                         # texto del botón de la ficha


def segundos(ms: int) -> str:
    """500 -> «0,5 s»; 2000 -> «2 s»; 60000 -> «1 min»."""
    if ms >= 60000 and ms % 60000 == 0:
        return f"{ms // 60000} min"
    return f"{ms / 1000:g}".replace(".", ",") + " s"


def porcentaje(brillo: int, paso: int = 1) -> str:
    """Brillo PWM en %, redondeado a múltiplos de `paso`."""
    return f"{round(brillo * 100 / BRILLO_MAX / paso) * paso} %"


def comportamiento_led(cfg: Optional[LedConfig]) -> str:
    """Qué hace un LED con esa configuración, en lenguaje llano."""
    if cfg is None or cfg.modo == "OFF":
        return "Está apagada"
    if cfg.modo == "ON":
        return f"Encendida fija al {porcentaje(cfg.brillo)}"
    if cfg.modo == "BLINK":
        return (f"Parpadea: {segundos(cfg.on_ms)} encendida y {segundos(cfg.off_ms)} apagada, "
                f"al {porcentaje(cfg.brillo)}")
    return f"Respira: se enciende y se apaga poco a poco cada {segundos(cfg.periodo_ms)}"


def ficha_led(led: Led, cfg: Optional[LedConfig], brillo: int, automatico: Optional[str],
              conectado: bool) -> Ficha:
    """`cfg` es lo que el Arduino confirmó, `brillo` el valor PWM de este instante y `automatico` quién
    manda si no es el control manual (una animación o el termómetro)."""
    if not conectado:
        hace, ahora = "Nada: no hay conexión con el Arduino", "Apagada"
    else:
        hace = automatico or comportamiento_led(cfg)
        # De 5 en 5: con una luz que respira, la ficha no tiene que redibujarse en cada fotograma.
        ahora = f"Encendida al {porcentaje(brillo, 5)}" if brillo > 0 else "Apagada"
    conexion = f"Pin {led.pin} (con PWM), con una resistencia de {RESISTENCIA_LED} hacia GND"
    return Ficha(led.luz, QUE_ES_LED, tuple(zip(FILAS, (conexion, hace, ahora))), tipo="led",
                 subtitulo=f"LED · pin {led.pin} (PWM)", color=led.color,
                 nivel=round(brillo / BRILLO_MAX * 20) / 20 if conectado else 0.0, activo=conectado and brillo > 0,
                 accion="Cambiar qué hace")


def ficha_sensor(sensor: Sensor, periodo_ms: Optional[int], ultima: Optional[tuple], conectado: bool) -> Ficha:
    """`ultima` es (temperatura, humedad) de la última lectura, (None, None) si falló, o None si no hay."""
    conexion = (f"Datos al pin {sensor.pin}, alimentado con {sensor.alimentacion} y GND, con una resistencia de "
                f"{RESISTENCIA_DHT} entre datos y {sensor.alimentacion}")
    hace = f"Mide cada {segundos(periodo_ms)}" if periodo_ms else "Mide cuando el Arduino se lo pide"
    nivel, activo = None, False
    if not conectado:
        ahora = "Sin conexión con el Arduino"
    elif ultima is None:
        ahora = "Esperando la primera lectura"
    elif ultima[0] is None:
        ahora = "No responde: revisa sus cables y la resistencia"
    else:
        ahora = f"{ultima[0]:.1f} °C y {ultima[1]:.0f} % de humedad"
        nivel, activo = max(0.0, min(1.0, ultima[1] / 100)), True
    return Ficha(f"Sensor {sensor.nombre}", sensor.descripcion, tuple(zip(FILAS, (conexion, hace, ahora))),
                 tipo="sensor", subtitulo=f"Sensor de clima · pin {sensor.pin}", color=sensor.color, nivel=nivel,
                 activo=activo, accion="Ver el clima")
