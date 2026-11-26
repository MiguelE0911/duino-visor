# DuinoVisor — control de Arduino en tiempo real con Python

App de escritorio (Tkinter + pyserial) con tema oscuro y acento ámbar que detecta sola el Arduino,
configura 3 LEDs (apagado, fijo con brillo, parpadeo, respiración) y muestra temperatura y humedad
del DHT11 en vivo. El sketch del Arduino no usa `delay()`: todo va con `millis()`.

Funciones: secuencias (semáforo vial, auto fantástico, alerta) con pausa, velocidad y detención, un
**semáforo 3D en la ventana que espeja al Arduino**, semáforo térmico, escenas `.json`, exportar lecturas a
CSV y alarmas por temperatura o humedad.

## Contenido

| Ruta | Qué es |
| --- | --- |
| `arduino/control_leds/control_leds.ino` | Sketch (carpeta y archivo con el mismo nombre, como pide el IDE) |
| `main.py` | Arranque; `--demo` usa el Arduino simulado |
| `gui.py` | Ventana Tkinter: tres columnas de tarjetas y barra lateral |
| `tema.py`, `widgets.py` | Paleta oscura/ámbar y widgets propios dibujados en Canvas (tarjetas, píldoras, deslizador, interruptor, medidor, barras, LED y semáforo 3D) |
| `protocol.py` | Órdenes, validación, interpretación de líneas, qué enviar al pulsar Aplicar, tabla de secuencias y modelo local que espeja al Arduino (funciones puras) |
| `arduino_link.py` | Puertos, autodetección, hilo lector con cola, envío |
| `grafica.py` | Gráfica de área en vivo sobre un Canvas |
| `escenas.py`, `exportar.py`, `alarmas.py` | Escenas `.json` validadas, CSV de lecturas y alarmas con histéresis |
| `simulador.py` | Arduino falso con la misma lógica del sketch |
| `docs/vista_previa_widgets.png` | Vista previa de los widgets (semáforo en cuatro estados, medidor, barras, botones, gráfica) |
| `tests/` | `test_protocol`, `test_extras`, `test_simulador`, `test_gui_logica` (Python) y `test_sketch` (compila el `.ino` con g++ contra un Arduino simulado) |

## Instalación y uso

```bash
pip install pyserial            # Python 3.10+
# Linux (Ubuntu/Debian): Tkinter y permisos del puerto
sudo apt install python3-tk
sudo usermod -aG dialout $USER  # cerrar sesión y volver a entrar

python main.py --demo           # sin placa
python main.py                  # con la placa: se conecta sola
```

Cargar el sketch: en el IDE de Arduino instala las librerías **DHT sensor library** y
**Adafruit Unified Sensor**, abre `control_leds.ino`, elige *Arduino UNO* y sube.
Cierra el Monitor Serie antes de abrir la app (el puerto solo lo puede usar un programa).

Probar a mano desde el Monitor Serie (9600 baudios, "Nueva línea"): `PING`, `LED G ON 128`,
`LED Y BLINK 255 500 250`, `LED R FADE 200 2000`, `DHT 2000`, `TERMO 22 28`, `SEQ VIAL`, `SEQ PAUSA`,
`SEQ SEGUIR`, `SEQ OFF`, `STATUS`.

## Conexiones

| Componente | Pin | Conexión |
| --- | --- | --- |
| LED rojo | 9 (PWM) | pin → 220 Ω → ánodo (pata larga); cátodo → GND |
| LED verde | 10 (PWM) | igual |
| LED amarillo | 11 (PWM) | igual |
| DHT11 VCC | 5V | directo |
| DHT11 DATA | 2 | directo + 10 kΩ entre DATA y 5V (si es módulo de 3 patas ya la trae) |
| DHT11 GND | GND | directo |

Sensor suelto de 4 patas: la tercera no se conecta.

## Protocolo (9600 baudios, texto, una orden por línea)

| PC → Arduino | Qué hace |
| --- | --- |
| `PING` | Responde `PONG OAC-LEDS 1` |
| `LED <R\|G\|Y> OFF` | Apaga |
| `LED <c> ON <brillo 0-255>` | Encendido fijo |
| `LED <c> BLINK <brillo> <on_ms> <off_ms>` | Intermitente (mínimo 20 ms) |
| `LED <c> FADE <brillo> <periodo_ms>` | Respiración (mínimo 200 ms) |
| `DHT <periodo_ms>` | Cada cuánto se lee el sensor (mínimo 1000 ms) |
| `TERMO <tmin> <tmax>` / `TERMO OFF` | Semáforo térmico |
| `SEQ <VIAL\|FANTASTICO\|ALERTA> [vel]` | Inicia la secuencia; `vel` es el % de velocidad (25-400, por defecto 100) |
| `SEQ PAUSA` / `SEQ SEGUIR` / `SEQ OFF` | Pausa (los LEDs se quedan como están), continúa o detiene y apaga |
| `STATUS` | Una línea `STATE <c> <modo> <brillo> <on> <off> <periodo>` por LED, una `STATE SEQ <nombre> <vel> <RUN\|PAUSA>` (o `STATE SEQ OFF`) y `OK STATUS` |

| Arduino → PC | Cuándo |
| --- | --- |
| `DATA T=24.0 H=51.0` / `DATA ERR` | Cada periodo del DHT / el sensor no respondió |
| `OK …` / `ERR <motivo>` | Respuesta a cada orden |

## Secuencias y semáforo espejo

| Secuencia | Pasos |
| --- | --- |
| `VIAL` | verde 5 s, amarillo 1,5 s, rojo 5 s |
| `FANTASTICO` | rojo, amarillo, verde, amarillo, 150 ms cada uno |
| `ALERTA` | amarillo 0,5 s encendido y 0,5 s apagado |

La velocidad escala todas las duraciones (mínimo 20 ms por paso). Una orden `LED` manual, `TERMO` o `SEQ` nuevo
cancela lo anterior: **la última orden manda**.

El semáforo 3D y los LEDs de cada tarjeta no leen nada del Arduino: calculan lo mismo con el modelo de
`protocol.py` (`SecuenciaLocal`, `brillo_en`, `zona_termo`), arrancando en el instante en que el Arduino
confirmó la orden con `OK`. Las pruebas comparan ese modelo con el sketch milisegundo a milisegundo.
Pausar, seguir o detener en la app manda la orden al Arduino, y si se desconecta o se cierra la app con una
secuencia en marcha, la app envía `SEQ OFF` antes. El semáforo térmico, en cambio, sigue funcionando solo.

## Escenas, CSV y alarmas

- **Escenas**: *Guardar escena* y *Cargar escena* guardan en un `.json` los tres LEDs, el periodo del sensor, el
  semáforo térmico y la secuencia elegida. Al cargar se valida todo; si algo está mal no se cambia nada. Después
  hay que pulsar *Aplicar* para enviarla.
- **Exportar CSV**: guarda cada lectura con fecha y hora (las fallidas quedan como «error de sensor»). Se
  conservan las últimas 100 000 lecturas. El archivo abre bien en Excel.
- **Alarmas**: avisan en la ventana (franja roja, registro y pitido del sistema) si la temperatura o la humedad
  superan su máximo, y avisan de nuevo cuando vuelven a la normalidad (con 1 unidad de histéresis). Una
  lectura fallida no apaga ni dispara una alarma.

## Decisiones de diseño (cambios respecto al borrador)

- **Aplicar espera `OK`/`ERR` de cada orden** antes de enviar la siguiente (reintenta una vez si no hay
  respuesta). Una configuración solo se da por aplicada cuando el Arduino la confirmó.
- **Semáforo térmico con histéresis de 1 °C**: sube de zona al instante y baja solo si la temperatura cae
  1 °C por debajo del umbral. El DHT11 tiene ±2 °C de error y resolución de 1 °C; sin histéresis parpadearía.
- **Prioridad entre TERMO y los LEDs**: la última orden manda. Una orden `LED` cancela el semáforo y deja
  los LEDs apagados salvo el ordenado. En la ventana, al activar el semáforo los paneles de LED se
  desactivan; al desactivarlo, Aplicar manda `TERMO OFF` y reenvía los tres LEDs. Si el sensor falla
  (`DATA ERR`), el semáforo conserva la última zona.
- **Respiración con corrección gamma** (brillo × x²): una rampa lineal de PWM se ve poco natural.
- **Línea de más de 63 caracteres**: se descarta y se responde `ERR linea larga`.
- **Reinicio al conectar**: abrir el puerto reinicia el UNO, por eso la app olvida lo aplicado y reenvía todo.
  Por la misma razón "recuperar el estado al conectar" con `STATUS` no aporta nada en un UNO.

## Limitaciones conocidas

- **No se ha probado con la placa real.** El sketch se compila y prueba contra un Arduino simulado en C++
  (más de 50 pruebas, incluida la comparación con el modelo de la app); la lógica de la ventana se probó con un
  Tkinter de mentira y los widgets se dibujaron con un lienzo de prueba para revisar su aspecto
  (`docs/vista_previa_widgets.png`). **La ventana Tkinter real nunca se ha abierto**: puede haber detalles de
  diseño por ajustar (tipografías, espacios, colores del desplegable de puertos).
- **Lectura del DHT11**: la librería desactiva las interrupciones unos 4–5 ms y bloquea ~25 ms. Una orden que
  llegue justo entonces podría perder algún carácter; por eso la app espera confirmación y reintenta.
  Si lo ves en la placa real, avísame o sube a 115200 baudios y mide.
- **LEDs virtuales**: aparecen siempre, también con la placa real, calculados desde lo que el Arduino confirmó.
  Si alguien cambia los LEDs sin pasar por la app (por ejemplo desde el Monitor Serie), el espejo no se entera.
- **Tkinter no dibuja sombras suaves ni transparencias**: el brillo de los LEDs usa anillos concéntricos y el
  área de la gráfica, franjas de un color mezclado con el fondo.

## Pruebas

```bash
python -m pytest tests -q       # el test del sketch necesita g++
```

## Extras pendientes

Ninguno de los extras del documento queda pendiente. Ideas para más adelante: secuencias definidas por el
usuario, alarmas con mínimo, y sonido o parpadeo en el Arduino cuando salta una alarma.
