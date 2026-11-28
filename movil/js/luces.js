// Qué configuración resulta de cada gesto sobre una luz (interruptor, modo, brillo, ritmo) y las órdenes de
// «todas a la vez». Puro: sin pantalla ni Bluetooth.
import { COLORES, MAX_MS, MIN_BLINK_MS, MIN_FADE_MS, RITMOS, SECUENCIAS } from "./catalogo.js";
import { comandoLed, ledConfig } from "./protocolo.js";

export const BRILLO_AL_ENCENDER = 255;

// ¿Los tiempos de este modo son válidos? (STATUS devuelve 0 en los campos que el modo no usa).
function tiemposValidos(cfg) {
  const ok = (v, min) => Number.isInteger(v) && v >= min && v <= MAX_MS;
  if (cfg.modo === "BLINK") return ok(cfg.on_ms, MIN_BLINK_MS) && ok(cfg.off_ms, MIN_BLINK_MS);
  if (cfg.modo === "FADE") return ok(cfg.periodo_ms, MIN_FADE_MS);
  return true;
}

// Con el ritmo «normal» si los tiempos del modo no sirven.
function completar(cfg) {
  if (tiemposValidos(cfg)) return cfg;
  return conRitmo(cfg, "normal");
}

export function conModo(cfg, modo) {
  const brillo = cfg.brillo > 0 ? cfg.brillo : BRILLO_AL_ENCENDER;
  return completar({ ...cfg, modo, brillo });
}

export function conBrillo(cfg, brillo) {
  const b = Math.max(0, Math.min(255, Math.round(brillo)));
  return completar({ ...cfg, brillo: b, modo: cfg.modo === "OFF" ? "ON" : cfg.modo });
}

export function conRitmo(cfg, ritmo) {
  const ms = RITMOS[cfg.modo]?.[ritmo];
  if (ms === undefined) return cfg;
  return cfg.modo === "BLINK" ? { ...cfg, on_ms: ms, off_ms: ms } : { ...cfg, periodo_ms: ms };
}

export const apagar = (cfg) => ({ ...cfg, modo: "OFF" });

// Al encender con el interruptor vuelve como estaba la última vez que se vio encendida (si se sabe).
export function encender(cfg, recordado) {
  if (cfg.modo !== "OFF") return cfg;
  const base = recordado && recordado.modo !== "OFF" ? { ...recordado, color: cfg.color } : { ...cfg, modo: "ON" };
  return conModo(base, base.modo);
}

export const estaEncendida = (cfg) => cfg.modo !== "OFF";

// ¿Hacen lo mismo? Se compara la orden que generan: STATUS deja valores viejos en los campos que el modo no usa.
export function mismaLuz(a, b) {
  if (!a || !b) return false;
  try {
    return comandoLed(a) === comandoLed(b);
  } catch {
    return false;
  }
}

// «Encender todas»: cada una como la recordaba (o fija al máximo). «Apagar todas»: LED x OFF de cada una.
export function ordenesTodas(encendidas, leds, recordados = {}) {
  return COLORES.map((c) => {
    const actual = leds[c] ?? ledConfig(c);
    const cfg = encendidas ? encender(apagar(actual), recordados[c]) : apagar(actual);
    return { cfg, orden: comandoLed(cfg) };
  });
}

// Cómo queda la placa cuando confirma (OK SEQ) una orden de animación, sin preguntarle con STATUS.
// Igual que ordenSeq() del sketch: al empezar, cada luz toma el brillo del primer paso; al detener, se apagan todas.
// estado: {leds: {id: cfg}, seq: {nombre, vel, pausada} | null}
export function trasOrdenSeq(estado, orden) {
  const [, accion, velTexto] = orden.trim().toUpperCase().split(/\s+/);
  const { leds, seq } = estado;
  if (accion === "PAUSA" || accion === "SEGUIR") {
    return { leds, seq: seq ? { ...seq, pausada: accion === "PAUSA" } : null };
  }
  if (accion === "OFF") {
    if (!seq) return { leds, seq: null };
    return { leds: Object.fromEntries(COLORES.map((c) => [c, apagar(leds[c] ?? ledConfig(c))])), seq: null };
  }
  const [, primero] = SECUENCIAS[accion][0];
  const nuevos = Object.fromEntries(COLORES.map((c) => {
    const b = primero[c] ?? 0;
    return [c, { ...(leds[c] ?? ledConfig(c)), modo: b ? "ON" : "OFF", brillo: b }];
  }));
  return { leds: nuevos, seq: { nombre: accion, vel: velTexto ? Number(velTexto) : 100, pausada: false } };
}
