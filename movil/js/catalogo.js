// Catálogo de la placa para la app del celular: espejo de duinovisor/dominio/placa.py (LEDs),
// de secuencias.py y termometro.py (tablas de datos) y de los UUID BLE del sketch.
// tests/firmware/test_contrato.py comprueba que todo coincide. Si añades un LED, cámbialo también aquí.

// En el mismo orden que `leds[]` del sketch (es el orden de STATUS).
export const LEDS = [
  { id: "R", nombre: "Rojo", luz: "Luz roja", color: "#e5533d", fila: 0 },
  { id: "G", nombre: "Verde", luz: "Luz verde", color: "#4fbf5f", fila: 2 },
  { id: "Y", nombre: "Amarillo", luz: "Luz amarilla", color: "#f2c14e", fila: 1 },
];
export const COLORES = LEDS.map((l) => l.id);
export const ledPorId = (id) => LEDS.find((l) => l.id === id);

// Bluetooth LE: los UUID del «Nordic UART Service» (en minúsculas, como los pide Web Bluetooth).
export const BLE = {
  nombre: "DuinoVisor",
  servicio: "6e400001-b5a3-f393-e0a9-e50e24dcca9e",
  rx: "6e400002-b5a3-f393-e0a9-e50e24dcca9e", // el celular escribe órdenes
  tx: "6e400003-b5a3-f393-e0a9-e50e24dcca9e", // la placa notifica respuestas
  trozo: 20, // bytes por paquete
};

// Límites del protocolo (iguales que el sketch y dominio/leds.py, protocolo.py, secuencias.py).
export const MODOS = ["OFF", "ON", "BLINK", "FADE"];
export const BRILLO_MAX = 255;
export const MIN_BLINK_MS = 20;
export const MIN_FADE_MS = 200;
export const MAX_MS = 60000;
export const MIN_DHT_MS = 1000;
export const MAX_DHT_MS = 3600000;
export const VEL_MIN = 25;
export const VEL_MAX = 400;
export const MIN_PASO_MS = 20;
export const PONG = "PONG OAC-LEDS";

// Animaciones: cada paso es [ms, {LED: brillo}]; los LEDs que no nombra quedan apagados.
export const SECUENCIAS = {
  VIAL: [[5000, { G: 255 }], [1500, { Y: 255 }], [5000, { R: 255 }]],
  FANTASTICO: [[150, { R: 255 }], [150, { Y: 255 }], [150, { G: 255 }], [150, { Y: 255 }]],
  ALERTA: [[500, { Y: 255 }], [500, {}]],
};
export const NOMBRES_SEQ = { VIAL: "Semáforo vial", FANTASTICO: "Auto fantástico", ALERTA: "Alerta amarilla" };

// Semáforo térmico: qué LED se enciende en cada zona (0 fresco, 1 templado, 2 calor).
export const HISTERESIS_TERMO = 1.0;
export const LUZ_DE_ZONA = [
  { color: "G", modo: "ON", brillo: 255 },
  { color: "Y", modo: "ON", brillo: 255 },
  { color: "R", modo: "BLINK", brillo: 255, on_ms: 250, off_ms: 250 },
];

// Lo que se elige en la pantalla en vez de milisegundos (igual que ui/constantes.py del escritorio).
export const RITMOS = {
  BLINK: { lento: 1000, normal: 500, rapido: 200 },
  FADE: { lento: 4000, normal: 2000, rapido: 1000 },
};
export const NOMBRES_MODO = { OFF: "Apagada", ON: "Encendida", BLINK: "Parpadea", FADE: "Respira" };
export const NOMBRES_RITMO = { lento: "Lento", normal: "Normal", rapido: "Rápido" };
