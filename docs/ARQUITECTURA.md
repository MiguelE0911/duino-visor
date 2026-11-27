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

El `firmware/` (sketch) es la otra mitad del contrato: `dominio/protocolo.py`, `secuencias.py`,
`termometro.py`, `leds.brillo_en` y `placa.py` deben coincidir con él. `tests/firmware/` lo compila con g++
y compara su salida con el dominio milisegundo a milisegundo.

## La ventana: `App` y sus mixins

`ui/app.py` define `App`, que hereda de un mixin por cada responsabilidad. Todos comparten `self`
(las variables de Tk, `enlace`, `aplicado`, ...), así que cada módulo se lee por separado pero funcionan
como una sola clase.

| Módulo | Responsabilidad |
| --- | --- |
| `app.py` | Crea el estado y las variables, arma la ventana, `al_cambiar`, el bucle `_ciclo` y `_recibir` |
| `vistas/cabecera.py` | Título, estado de conexión, pestañas, «Aplicar» y menú |
| `vistas/luces.py` | Semáforo o protoboard, editor del LED elegido y animaciones |
| `vistas/clima.py` | Medidor, humedad, avisos, semáforo térmico, gráfica y franja de alarma |
| `vistas/detalles.py` | Puerto, botón de conexión y registro de comunicación |
| `vistas/ajustes.py` | Ventana de ajustes y cambio de tema (reconstruye la ventana) |
| `controladores/conexion.py` | Buscar la placa, conectar y desconectar (en hilos, vía `cola_ui`) |
| `controladores/envio.py` | Leer la ventana, armar los pasos y enviarlos uno a uno esperando OK/ERR |
| `controladores/espejo.py` | Lo que el Arduino está haciendo, calculado desde lo confirmado |
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
| Una animación nueva | `SECUENCIAS` y `NOMBRES_SEQ` en `dominio/secuencias.py` y la misma tabla en el sketch. La ventana la muestra sola |
| Un modo de LED nuevo | `MODOS`, `errores` y `brillo_en` en `dominio/leds.py`; `comando_led` en `dominio/protocolo.py`; el sketch; el simulador; la etiqueta en `ui/constantes.MODOS` y sus controles en `vistas/luces.py` |
| Una orden nueva del protocolo | Función `comando_*` / `Paso` en `dominio/protocolo.py` (y `confirmar` si cambia el estado), el sketch y el simulador |
| Un sensor nuevo | Su lectura en `dominio/protocolo.interpretar`, su pin en `dominio/placa.py`, el simulador, y una vista o tarjeta en `ui/vistas/` |
| Una pestaña o panel nuevo | Un mixin en `ui/vistas/` (y otro en `ui/controladores/` si tiene lógica), añadido a la lista de bases de `App` |
| Un widget nuevo | En el módulo de su familia dentro de `ui/widgets/` (o uno nuevo), heredando de `base.Lienzo` |
| Un formato de archivo nuevo | Un módulo en `almacenamiento/` y su acción en `ui/controladores/archivos.py` |
| Una capa nueva | Su carpeta en `duinovisor/`, sus reglas en `PERMITIDAS` de `tests/test_arquitectura.py` y en esta página |

Cada cambio en `dominio/` lleva su prueba en `tests/dominio/`, y si toca el contrato con la placa, también
en `tests/firmware/`.
