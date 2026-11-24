# Control de Arduino en tiempo real con Python (DuinoVisor)

## Resumen

Proponemos una app de escritorio en Python (Tkinter + pyserial) que detecta sola el Arduino, deja configurar cada LED (apagado, encendido con brillo, intermitente, respiración) y lo envía todo al pulsar **Aplicar**, mientras muestra temperatura y humedad del DHT11 en vivo. El Arduino ejecuta un sketch no bloqueante que interpreta comandos de texto por el puerto serie.

Objetivos que cubre, ligados a la asignatura:

- **Comunicación PC ↔ microcontrolador** por UART (USB-serie), con un protocolo propio de comandos.
- **E/S del microcontrolador**: salidas PWM para el brillo (`analogWrite`, 0–255) y entrada digital de un sensor con protocolo de un solo hilo (DHT11).
- **Tiempo real sin bloqueo**: el Arduino nunca usa `delay()`; todo se planifica con `millis()`, así los tres LEDs, el sensor y los comandos funcionan a la vez.
- **Concurrencia en la PC**: un hilo lee el puerto serie y la interfaz nunca se congela.

El código base está listo y probado: el sketch, la app y un modo demo que simula el Arduino para trabajar sin la placa.

## Arquitectura

Dos programas que se hablan por el cable USB, que el Arduino expone como un puerto serie (COM3 en Windows, /dev/ttyACM0 o /dev/ttyUSB0 en Linux).

[embedded content: arquitectura · 3 módulos Python, 3 tareas en el Arduino]

- **PC (Python 3.10 o superior)**: Tkinter para la interfaz (viene con Python, no hay que instalar nada) y **pyserial** para el puerto. La interfaz nunca lee el puerto directamente: un hilo lo lee y deja cada línea en una cola, y la interfaz la vacía cada 50 ms con `after()`. Así nunca se congela.
- **Arduino UNO**: un sketch que en cada vuelta de `loop()` hace tres tareas cortas: leer los bytes que llegaron, recalcular el brillo de cada LED y, si ya tocó, leer el DHT11.
- **Autodetección**: la app lista los puertos con `serial.tools.list_ports`, prueba primero los que tienen un fabricante USB típico de Arduino (oficial, CH340 de los clones, FTDI, CP210x) y se queda con el que responde `PONG OAC-LEDS` a la orden `PING`. Esto evita confundirlo con otro dispositivo serie.

Tkinter frente a PySide: elegimos Tkinter porque no requiere instalación y alcanza para sliders, botones y una gráfica en un Canvas. PySide6 da una interfaz más moderna, pero suma una dependencia pesada y más curva de aprendizaje.

## Esquema de conexiones

Cada LED va en un pin con PWM (en el UNO: 3, 5, 6, 9, 10, 11) a través de una resistencia de 220 Ω, y el DHT11 en el pin digital 2. Todo comparte la tierra (GND) del Arduino.

| Componente | Pin del Arduino | Conexión | Resistencia |
| --- | --- | --- | --- |
| LED rojo | 9 (PWM) | pin → resistencia → pata larga (ánodo); pata corta (cátodo) → GND | 220 Ω en serie |
| LED verde | 10 (PWM) | igual que el rojo | 220 Ω en serie |
| LED amarillo | 11 (PWM) | igual que el rojo | 220 Ω en serie |
| DHT11, pata VCC | 5V | directo | — |
| DHT11, pata DATA | 2 | directo | 10 kΩ entre DATA y 5V (pull-up) |
| DHT11, pata GND | GND | directo | — |
- **Por qué 220 Ω**: con 5 V y unos 2 V de caída en el LED quedan (5 − 2) / 220 ≈ 14 mA, por debajo de los 20 mA recomendados por pin.
- **Si el DHT11 viene en módulo** (placa pequeña de 3 patas), la resistencia de 10 kΩ ya está incluida. Si es el sensor suelto de 4 patas, la tercera pata no se conecta.
- **Cómo funciona el brillo**: `analogWrite(pin, 128)` no da 2,5 V. El pin alterna 5 V y 0 V unas 490 veces por segundo (980 en los pines 5 y 6) y queda encendido el 50 % del tiempo; el ojo lo promedia como brillo medio. Es un buen tema para la exposición de la materia.

## Protocolo serial

Texto plano, una orden por línea terminada en salto de línea, a 9600 baudios. Es legible, así se puede probar a mano desde el Monitor Serie del IDE de Arduino antes de tener la app. El Arduino responde `OK` o `ERR <motivo>` a cada orden.

| Orden (PC → Arduino) | Ejemplo | Qué hace |
| --- | --- | --- |
| `PING` | `PING` | Responde `PONG OAC-LEDS 1`; la app lo usa para reconocer la placa |
| `LED <c> OFF` | `LED R OFF` | Apaga el LED (c = R, G o Y) |
| `LED <c> ON <brillo>` | `LED G ON 128` | Encendido fijo, brillo 0–255 |
| `LED <c> BLINK <brillo> <on_ms> <off_ms>` | `LED Y BLINK 255 500 250` | Intermitente: 500 ms encendido, 250 ms apagado (mínimo 20 ms) |
| `LED <c> FADE <brillo> <periodo_ms>` | `LED R FADE 200 2000` | “Respiración”: sube y baja en 2 s (mínimo 200 ms) |
| `DHT <periodo_ms>` | `DHT 2000` | Cada cuánto se lee y envía el sensor (mínimo 1000 ms, límite del DHT11) |
| `TERMO <t_min> <t_max>` / `TERMO OFF` | `TERMO 22 28` | Semáforo térmico (ver extras) |
| `STATUS` | `STATUS` | Una línea `STATE` por LED con su configuración actual |

| Mensaje (Arduino → PC) | Ejemplo | Cuándo |
| --- | --- | --- |
| `DATA T=<°C> H=<%>` | `DATA T=24.5 H=51.0` | Cada periodo del DHT |
| `DATA ERR` | `DATA ERR` | El sensor no respondió (cable flojo, sin pull-up) |
| `OK <orden>` | `OK LED R` | Orden aceptada |
| `ERR <motivo>` | `ERR brillo 0-255` | Orden rechazada; la app la muestra en el registro |
| `STATE …` | `STATE G BLINK 200 100 300 2000` | Respuesta a `STATUS` |

El Arduino acepta minúsculas (las pasa a mayúsculas) y descarta líneas de más de 63 caracteres.

## Sketch Arduino no bloqueante

El sketch nunca llama a `delay()`: si lo hiciera, un LED intermitente de 500 ms congelaría la lectura de órdenes y los demás LEDs durante medio segundo. En su lugar, `loop()` se repite miles de veces por segundo y en cada vuelta hace tres tareas cortas:

1. `leerSerie()`: lee los bytes que haya en el búfer del puerto (sin esperar) y los acumula; al llegar el salto de línea llama a `procesarComando()`, que separa las palabras con `strtok` y actualiza el estado.
2. `actualizarLeds(ahora)`: para cada LED calcula el brillo de este instante según su modo y hace `analogWrite`.
    - BLINK: si `ahora - ultimoCambio >= onMs` (u `offMs`), invierte la fase. La resta sin signo sigue funcionando cuando `millis()` se desborda a los 49 días.
    - FADE: onda triangular, brillo proporcional a la posición dentro del periodo.
3. `leerSensor(ahora)`: si pasaron `periodoDht` ms, lee el DHT11 y envía `DATA`. Es el único paso “lento” (unos 25 ms), aceptable para LEDs.

Cada LED es un `struct Led` con pin, modo, brillo, tiempos y su último cambio, guardado en un arreglo. Agregar un cuarto LED es añadir una línea al arreglo.

Librerías: **DHT sensor library** de Adafruit y su dependencia **Adafruit Unified Sensor**, instaladas desde el Gestor de librerías del IDE.

Archivo: control_leds.ino. Lo compilamos contra una simulación de Arduino en la PC y comprobamos las respuestas a cada orden, los tiempos del intermitente, la respiración y el semáforo térmico; falta probarlo en la placa real.

## Módulos de la app Python

Cada archivo tiene una sola responsabilidad, así pueden trabajar en paralelo sin pisarse.

| Archivo | Responsabilidad | Depende de |
| --- | --- | --- |
| `main.py` | Arranque; `--demo` usa el Arduino simulado | gui |
| `gui.py` | Ventana Tkinter: un panel por LED, sensor, botón Aplicar, registro | protocol, arduino_link, grafica |
| `protocol.py` | `LedConfig`, construir y validar órdenes, interpretar líneas, calcular cambios | nada (funciones puras) |
| `arduino_link.py` | Listar puertos, autodetectar, hilo lector con cola, enviar | pyserial, protocol |
| `grafica.py` | Gráfica en vivo de temperatura y humedad sobre un Canvas | tkinter |
| `simulador.py` | Arduino falso que imita el sketch, para trabajar sin la placa | protocol |
| `tests/test_protocol.py` | Pruebas con pytest del protocolo (8 pruebas, pasan) | protocol |

**Flujo del botón Aplicar**

1. Al mover cualquier control, la app solo muestra “Hay cambios sin aplicar”; no envía nada.
2. Al pulsar **Aplicar**, cada panel genera su `LedConfig` y se valida (brillo 0–255, tiempos mínimos). Si algo es inválido, aparece un aviso y no se envía nada.
3. `protocol.cambios()` compara con la última configuración aplicada y devuelve solo las órdenes de los LEDs que cambiaron.
4. Se envían por el puerto y quedan en el registro con `→`; las respuestas `OK`/`ERR` aparecen con `←`.
5. Al reconectar, la app olvida lo aplicado y el siguiente Aplicar reenvía todo, porque el Arduino se reinicia al abrir el puerto.

**Autodetección**: al abrir la app se busca la placa en un hilo aparte (abrir el puerto reinicia el Arduino y tarda unos 2 s por puerto). Si la encuentra, se conecta sola; si no, se puede elegir el puerto a mano y pulsar Conectar.

## Funciones extra

Las dos primeras ya están en el código base; el resto son ideas para sumar puntos si sobra tiempo.

| Extra | Estado | Idea |
| --- | --- | --- |
| Gráfica en vivo | Incluida | Últimas 60 lecturas de temperatura (rojo) y humedad (azul) en la ventana |
| Semáforo térmico | Incluido | `TERMO 22 28`: verde bajo 22 °C, amarillo entre 22 y 28 °C, rojo intermitente desde 28 °C. Lo decide el Arduino, así funciona aunque la app se cierre |
| Guardar y cargar escenas | Por hacer | Guardar la configuración de los 3 LEDs en un `.json` y cargarla con un clic |
| Exportar lecturas a CSV | Por hacer | Guardar cada `DATA` con fecha y hora para analizarlas en Excel |
| Secuencias | Por hacer | Semáforo vial o “auto fantástico”: una orden nueva `SEQ` en el sketch |
| Alarma por humedad | Por hacer | Aviso en la app cuando la humedad pase un umbral |
| Recuperar estado al conectar | Por hacer | Enviar `STATUS` al conectar y cargar los paneles con lo que tiene el Arduino |

## Plan de trabajo y cómo ejecutar

Se reparte por el cable: una persona se encarga de todo lo que corre en el Arduino y la otra de la app. El protocolo es el contrato entre ambas, así cada una puede avanzar sola (el modo `--demo` y el Monitor Serie sirven para probar sin la otra parte).

| Etapa | Persona A: Arduino y hardware | Persona B: app Python | Juntas |
| --- | --- | --- | --- |
| 1. Base | Armar el circuito; cargar el sketch y probar las órdenes a mano en el Monitor Serie | Instalar pyserial; correr `python main.py --demo` y las pruebas | Acordar el protocolo (esta tabla) |
| 2. Integración | Revisar `DATA ERR`, pull-up y tiempos mínimos | Probar la autodetección en Windows y Linux con la placa real | Primera prueba completa con Aplicar |
| 3. Extras | Orden `SEQ` o mejoras al semáforo térmico | Escenas en `.json`, exportar CSV, `STATUS` al conectar | Elegir 2 extras |
| 4. Entrega | Foto o diagrama del circuito (Fritzing o Tinkercad) | Capturas de la app | Informe, demo en vivo, explicación de PWM, UART y `millis()` |