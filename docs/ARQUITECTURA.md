# Arquitectura de DuinoVisor

## Capas

```
ui  ──►  hardware  ──►  dominio
 │                        ▲
 └──►  almacenamiento  ───┘
```

| Capa | Puede importar | No puede usar | Qué contiene |
| --- | --- | --- | --- |
| `dominio` | solo `dominio` | Tkinter, `serial`, archivos, hilos | Reglas puras: qué es un LED válido, qué orden se envía, cómo se comporta el Arduino en cada milisegundo |
| `hardware` | `dominio` | Tkinter | Hablar con la placa (real o simulada) |
| `almacenamiento` | `dominio` | Tkinter, `serial` | Leer y escribir archivos del usuario |
| `ui` | todas | — | La ventana |

`tests/test_arquitectura.py` comprueba estas reglas leyendo los `import` de cada módulo. Si falla, la
dependencia va al revés: mueve el código a la capa correcta en lugar de añadir una excepción.

## Catálogo de componentes

`dominio/placa.py` es la **única lista** de lo que hay conectado: `LEDS` (letra, nombre, pin, color real y
posición en el semáforo) y el sensor `DHT`. Nada más en Python escribe las letras R/G/Y por su cuenta:
`leds.COLORES`, los nombres de la ventana, el orden del semáforo, los colores del tema, los pines de la
protoboard, el simulador y las escenas se derivan de ella. Las tablas de datos que nombran LEDs concretos
(los pasos de `secuencias.SECUENCIAS` y `termometro.LUZ_DE_ZONA`) usan su letra, y lo que no nombran queda
apagado.

El `firmware/` (sketch) es la otra mitad del contrato: `dominio/protocolo.py`, `secuencias.py`,
`termometro.py`, `leds.brillo_en` y `placa.py` deben coincidir con él (`leds[]`, `PIN_DHT`, `ZONAS_TERMO` y las
tablas `SEQ_*`, cuyas columnas siguen el orden de `leds[]`). `tests/firmware/test_contrato.py` compara esas
tablas leyendo el `.ino`, sin compilar; `tests/firmware/test_sketch.py` lo compila con g++ y compara su salida
con el dominio milisegundo a milisegundo.

## La ventana: `App` y sus mixins

`ui/app.py` define `App`, que hereda de un mixin por cada responsabilidad. Todos comparten `self`
(las variables de Tk, `enlace`, `aplicado`, ...), así que cada módulo se lee por separado pero funcionan
como una sola clase.

| Módulo | Responsabilidad |
| --- | --- |
| `app.py` | Crea el estado y las variables, arma la ventana, `al_cambiar`, el bucle `_ciclo` y `_recibir` |
| `vistas/cabecera.py` | Título, estado de conexión, pestañas, «Aplicar» y menú |
| `vistas/luces.py` | Semáforo o protoboard, editor del LED elegido y animaciones |
| `vistas/clima.py` | Medidor y barras o termómetro y gota, avisos, semáforo térmico, gráfica y franja de alarma |
| `vistas/detalles.py` | Registro de comunicación |
| `vistas/configuracion.py` | Pestaña Configuración (conexión, sensor, apariencia, cada ajuste con su explicación), preferencias y cambio de tema (reconstruye la ventana) |
| `vistas/acerca.py` | Ventana «Acerca de» |
| `controladores/conexion.py` | Buscar la placa, conectar y desconectar (en hilos, vía `cola_ui`) |
| `controladores/envio.py` | Leer la ventana, armar los pasos y enviarlos uno a uno esperando OK/ERR |
| `controladores/cambios.py` | Qué muestra la barra de cambios sin aplicar (base, envío, aplicado, fallo) |
| `controladores/espejo.py` | Lo que el Arduino está haciendo, calculado desde lo confirmado, y la ficha del componente elegido |
| `fichas.py` | Textos de las fichas de la protoboard (sin Tkinter; se prueban solos) |
| `widgets/protoboard.py` | El lienzo de la protoboard: zoom, arrastre, teclado, paso del ratón, barra de herramientas y animación |
| `widgets/dibujo_placa.py` | Cómo se dibuja cada pieza (placa, protoboard, cables, resistencias, LEDs, DHT11) |
| `widgets/ficha.py` | La tarjeta flotante de la ficha |
| `widgets/geometria.py` | Cuentas sin Tkinter: curvas de los cables, degradados, encaje, zoom y vista previa |
| `widgets/raster.py` | Pintar con Pillow: adaptador con la API del Canvas, mesa, LEDs con resplandor y cables resaltados |
| `widgets/avisos.py` | El aviso flotante de cambios sin aplicar (una ventanita sin bordes que sigue a la principal) |
| `controladores/secuencias.py` | Iniciar, pausar, seguir y detener animaciones |
| `controladores/archivos.py` | Escenas y CSV (diálogos de archivo) |
| `controladores/sensor.py` | Historial de lecturas y alarmas |

Regla práctica: si un método crea widgets va en `vistas/`; si decide qué hacer, en `controladores/`; si
la decisión no necesita la ventana para nada, en `dominio/`.

## Recorrido de una orden

1. El usuario cambia algo → una variable de Tk → `App.al_cambiar` marca «cambios sin aplicar».
2. «Aplicar» → `EnvioMixin.aplicar` → `dominio.protocolo.plan` calcula los pasos.
3. Cada paso sale por `hardware.enlace.Enlace` y espera respuesta (`SIN_RESPUESTA_MS`, un reintento).
4. `App._recibir` interpreta la línea con `dominio.protocolo.interpretar`; con `OK`,
   `EspejoMixin._confirmado` actualiza `aplicado` y el espejo.
5. `App._ciclo` pinta el semáforo, la protoboard y los chips con `EspejoMixin._brillos_espejo`.

## Dónde va cada cosa al ampliar

| Quiero añadir… | Pasos |
| --- | --- |
| Un LED nuevo | Una entrada en `LEDS` de `dominio/placa.py`, la misma línea en `leds[]` del sketch (pin con PWM) y en `LEDS` de `movil/js/catalogo.js`. El resto se adapta solo; ver «Añadir un LED» en el README |
| Una animación nueva | `SECUENCIAS` y `NOMBRES_SEQ` en `dominio/secuencias.py` (pasos `(ms, {LED: brillo})`), la misma tabla en el sketch (una columna por LED, en el orden de `leds[]`) y en `movil/js/catalogo.js`. La ventana, el celular y los simuladores la muestran solos |
| Un modo de LED nuevo | `MODOS`, `errores` y `brillo_en` en `dominio/leds.py`; `comando_led` en `dominio/protocolo.py`; el sketch; el simulador; la etiqueta en `ui/constantes.MODOS` y sus controles en `vistas/luces.py` |
| Una orden nueva del protocolo | Función `comando_*` / `Paso` en `dominio/protocolo.py` (y `confirmar` si cambia el estado), el sketch y el simulador |
| Un sensor nuevo | Su lectura en `dominio/protocolo.interpretar`, su `Sensor` en `SENSORES` de `dominio/placa.py` (con su `descripcion` para la ficha), el simulador, su dibujo en `widgets/protoboard.py` con la etiqueta `sel_<id>`, y una vista o tarjeta en `ui/vistas/` |
| Un ajuste nuevo | Su fila con `_fila_ajuste` (título, explicación y control) en `vistas/configuracion.py`; si se recuerda, su clave y valor por defecto en `almacenamiento/preferencias.POR_DEFECTO` |
| Una pestaña o panel nuevo | Un mixin en `ui/vistas/` (y otro en `ui/controladores/` si tiene lógica), añadido a la lista de bases de `App` |
| Un widget nuevo | En el módulo de su familia dentro de `ui/widgets/` (o uno nuevo), heredando de `base.Lienzo` |
| Un formato de archivo nuevo | Un módulo en `almacenamiento/` y su acción en `ui/controladores/archivos.py` |
| Una capa nueva | Su carpeta en `duinovisor/`, sus reglas en `PERMITIDAS` de `tests/test_arquitectura.py` y en esta página |

Cada cambio en `dominio/` lleva su prueba en `tests/dominio/`, y si toca el contrato con la placa, también
en `tests/firmware/`.

## Dibujar con Tkinter sin que se trabe

Tk repinta de una vez **el rectángulo que abarca todo lo que cambió** desde el último repintado. Si en un
fotograma cambian un LED a la izquierda y la ficha abajo a la derecha, se repinta casi todo el lienzo, y el coste
crece con el número de elementos (con ~2000 elementos vectoriales, ~55 ms: más que el ciclo de 50 ms).

Por eso la vista protoboard tiene dos capas:

- **Lo fijo es una imagen** pintada con Pillow (`widgets/raster.py`): mesa, placa, protoboard, cables y
  resistencias. `LienzoImagen` imita la parte de la API del Canvas que usa `dibujo_placa`, así las mismas funciones
  dibujan en la imagen o, si no hay Pillow, en el lienzo. Se pinta al doble de tamaño y se reduce (antialiasing);
  las letras se escriben después, ya reducida. Con la imagen, repintar todo cuesta ~5 ms.
- **Lo vivo son pocos elementos**: los LEDs (una imagen por nivel de brillo, en caché), anillos, halos, la barra de
  herramientas y la ficha. Se cambian con `itemconfigure`, sin redibujar la escena.

Reglas: no hacer `tag_raise`/`tag_lower` de capas grandes en cada fotograma; con zoom o desplazamiento, redibujar
solo la escena (`_redibujar_escena`); y para algo que dependa de lo que hay bajo el ratón, buscarlo por geometría
(`_componente_en`) y no por las etiquetas de los elementos, que en la imagen no existen. Para medir, pon la pantalla
al 125 % o 150 %: es donde se nota.

## La app del celular (`movil/`)

Una página web con **Web Bluetooth** (HTML, CSS y JavaScript sin framework ni compilación) que habla con la
placa por BLE con **las mismas órdenes de texto** que el escritorio. No comparte código con Python, pero sí el
contrato: `tests/firmware/` comprueba que sus tablas y su placa simulada coinciden con el sketch.

```
app.js ──► envio.js ──► protocolo.js ──► catalogo.js
   │                         ▲
   ├──► transporte.js ──► lineas.js          (Bluetooth: el único módulo que lo toca)
   └──► simulador.js  ──► automatismos.js    (modo demo, con la misma interfaz que transporte.js)
```

| Módulo | Qué hace | ¿Toca el navegador? |
| --- | --- | --- |
| `catalogo.js` | LEDs, UUID BLE, límites, animaciones, zonas del semáforo térmico y ritmos (espejo de `dominio/` y del sketch) | No |
| `protocolo.js` | Armar órdenes, interpretar respuestas, leer `STATUS`, brillo en cada instante, textos de resumen | No |
| `automatismos.js` | Animaciones (`SecuenciaLocal`) y zonas del semáforo térmico | No |
| `lineas.js` | Partir una orden en paquetes de 20 bytes y rearmar las líneas que llegan | No |
| `envio.js` | Una orden a la vez, espera su `OK`/`ERR`/`PONG`, un reintento; recoge las líneas `STATE` | No |
| `simulador.js` | `PlacaSimulada` (responde como el sketch) y `TransporteDemo` | No |
| `transporte.js` | Web Bluetooth: elegir la placa, notificaciones, escribir en trozos, reconectar con esperas crecientes | Sí |
| `app.js` | La pantalla: conexión, luces, clima, detalles y órdenes a mano | Sí |

- **Transporte intercambiable:** `TransporteBle` y `TransporteDemo` tienen la misma interfaz (`conectar`,
  `escribir`, `desconectar`, `alLinea`, `alEstado`). Para una app nativa bastaría otro transporte.
- **Al conectar** se envía `PING` (¿es nuestra placa?) y `STATUS`; luego `STATUS` cada 5 s mientras la página
  está visible, porque el escritorio puede cambiar la placa por USB. La app **no** reinicia la placa al
  conectarse (a diferencia del escritorio, que envía `TERMO OFF`).
- **Pruebas:** `cd movil && node --test` (módulos sin navegador). `tests/firmware/test_contrato.py` compara
  `catalogo.js` con `dominio/` y los UUID con el sketch, y `test_sketch.py` envía las mismas órdenes al sketch
  compilado y a `PlacaSimulada` (con `movil/pruebas/herramientas/puente.js`). Necesitan `node`; sin él se omiten.
