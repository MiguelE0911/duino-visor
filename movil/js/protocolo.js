// Protocolo de texto de DuinoVisor (el mismo por serie y por BLE): armar órdenes y leer respuestas.
// Espejo de duinovisor/dominio/protocolo.py y leds.py. Puro: sin Bluetooth ni pantalla.
import {
  BRILLO_MAX, COLORES, MAX_DHT_MS, MAX_MS, MIN_BLINK_MS, MIN_DHT_MS, MIN_FADE_MS, MODOS, NOMBRES_MODO,
  NOMBRES_RITMO, PONG, RITMOS, SECUENCIAS, VEL_MAX, VEL_MIN, ledPorId,
} from "./catalogo.js";

// Configuración de un LED, con los mismos campos que LedConfig de Python.
export function ledConfig(color, cambios = {}) {
  return { color, modo: "OFF", brillo: 255, on_ms: 500, off_ms: 500, periodo_ms: 2000, ...cambios };
}

export function errores(cfg) {
  const e = [];
  const entre = (v, a, b) => Number.isInteger(v) && v >= a && v <= b;
  if (!COLORES.includes(cfg.color)) e.push(`color inválido: ${cfg.color}`);
  if (!MODOS.includes(cfg.modo)) return [...e, `modo inválido: ${cfg.modo}`];
  if (cfg.modo !== "OFF" && !entre(cfg.brillo, 0, BRILLO_MAX)) e.push(`el brillo debe estar entre 0 y ${BRILLO_MAX}`);
  if (cfg.modo === "BLINK") {
    if (!entre(cfg.on_ms, MIN_BLINK_MS, MAX_MS)) e.push(`el tiempo encendido debe estar entre ${MIN_BLINK_MS} y ${MAX_MS} ms`);
    if (!entre(cfg.off_ms, MIN_BLINK_MS, MAX_MS)) e.push(`el tiempo apagado debe estar entre ${MIN_BLINK_MS} y ${MAX_MS} ms`);
  }
  if (cfg.modo === "FADE" && !entre(cfg.periodo_ms, MIN_FADE_MS, MAX_MS)) {
    e.push(`el periodo debe estar entre ${MIN_FADE_MS} y ${MAX_MS} ms`);
  }
  return e;
}

// ---------------------------------------------------------------- órdenes
export function comandoLed(cfg) {
  const e = errores(cfg);
  if (e.length) throw new Error(e.join("; "));
  if (cfg.modo === "OFF") return `LED ${cfg.color} OFF`;
  if (cfg.modo === "ON") return `LED ${cfg.color} ON ${cfg.brillo}`;
  if (cfg.modo === "BLINK") return `LED ${cfg.color} BLINK ${cfg.brillo} ${cfg.on_ms} ${cfg.off_ms}`;
  return `LED ${cfg.color} FADE ${cfg.brillo} ${cfg.periodo_ms}`;
}

export function comandoDht(periodoMs) {
  if (!Number.isInteger(periodoMs) || periodoMs < MIN_DHT_MS || periodoMs > MAX_DHT_MS) {
    throw new Error(`el periodo del sensor debe estar entre ${MIN_DHT_MS} y ${MAX_DHT_MS} ms`);
  }
  return `DHT ${periodoMs}`;
}

export function comandoTermo(termo) {
  if (termo == null) return "TERMO OFF";
  const [tmin, tmax] = termo;
  if (!(Number.isInteger(tmin) && Number.isInteger(tmax)) || tmin >= tmax) {
    throw new Error("la temperatura mínima debe ser menor que la máxima");
  }
  return `TERMO ${tmin} ${tmax}`;
}

export function comandoSeq(nombre, vel = 100) {
  if (!(nombre in SECUENCIAS)) throw new Error(`secuencia desconocida: ${nombre}`);
  if (!Number.isInteger(vel) || vel < VEL_MIN || vel > VEL_MAX) {
    throw new Error(`la velocidad debe estar entre ${VEL_MIN} y ${VEL_MAX} %`);
  }
  return vel === 100 ? `SEQ ${nombre}` : `SEQ ${nombre} ${vel}`;
}

// ---------------------------------------------------------------- respuestas
// {tipo: PONG | DATA | DATA_ERR | OK | ERR | STATE | OTRO, texto, temperatura?, humedad?}
export function interpretar(linea) {
  linea = linea.trim();
  if (linea.startsWith(PONG)) return { tipo: "PONG", texto: linea };
  if (linea === "DATA ERR") return { tipo: "DATA_ERR", texto: linea };
  if (linea.startsWith("DATA ")) {
    const campos = Object.fromEntries(linea.slice(5).split(/\s+/).map((p) => p.split("=")));
    const t = Number.parseFloat(campos.T), h = Number.parseFloat(campos.H);
    if (Number.isFinite(t) && Number.isFinite(h)) return { tipo: "DATA", texto: linea, temperatura: t, humedad: h };
    return { tipo: "OTRO", texto: linea };
  }
  if (linea === "OK" || linea.startsWith("OK ")) return { tipo: "OK", texto: linea.slice(3) };
  if (linea === "ERR" || linea.startsWith("ERR ")) return { tipo: "ERR", texto: linea.slice(4) };
  if (linea.startsWith("STATE ")) return { tipo: "STATE", texto: linea.slice(6) };
  return { tipo: "OTRO", texto: linea };
}

// ¿La línea tiene una forma que la placa puede enviar? Si se pierde un trozo por el camino, dos respuestas se
// pegan («OK LED ROK LED G») o quedan cortadas: eso se cuenta como mensaje dañado.
export function lineaValida(linea) {
  const led = `[${COLORES.join("")}]`;
  const seq = Object.keys(SECUENCIAS).join("|");
  const formas = [
    String.raw`${PONG} \d+`,
    String.raw`DATA T=-?\d+\.\d H=-?\d+\.\d`, "DATA ERR",
    `OK(?: (?:LED ${led}|DHT|TERMO|SEQ|STATUS))?`,
    "ERR [ -~]*",
    String.raw`STATE ${led} (?:${MODOS.join("|")})(?: \d+){4}`,
    String.raw`STATE SEQ (?:OFF|(?:${seq}) \d+ (?:RUN|PAUSA))`,
  ];
  return new RegExp(`^(?:${formas.join("|")})$`).test(linea.trim());
}

// Lo que devuelve STATUS (las líneas STATE, sin la palabra STATE) -> {leds: {R: cfg, ...}, seq, completo}.
// seq es null o {nombre, vel, pausada}. Las líneas rotas se ignoran; `completo` es false si faltó algún LED o la
// línea SEQ (se perdió un trozo por el camino): entonces no hay que fiarse de lo que falta.
export function leerStatus(estados) {
  const leds = {};
  let seq = null;
  let haySeq = false;
  for (const texto of estados) {
    if (!lineaValida(`STATE ${texto.trim()}`)) continue;
    const p = texto.trim().split(/\s+/);
    if (p[0] === "SEQ") {
      haySeq = true;
      if (p[1] !== "OFF") seq = { nombre: p[1], vel: Number(p[2]), pausada: p[3] === "PAUSA" };
    } else {
      const [brillo, on_ms, off_ms, periodo_ms] = p.slice(2, 6).map(Number);
      leds[p[0]] = ledConfig(p[0], { modo: p[1], brillo, on_ms, off_ms, periodo_ms });
    }
  }
  return { leds, seq, completo: haySeq && COLORES.every((c) => c in leds) };
}

// ---------------------------------------------------------------- para mostrar
// PWM (0-255) que tiene el LED `ms` milisegundos después de recibir la orden. Igual que el sketch.
export function brilloEn(cfg, ms) {
  if (cfg.modo === "OFF") return 0;
  if (cfg.modo === "ON") return cfg.brillo;
  if (cfg.modo === "BLINK") return ms % (cfg.on_ms + cfg.off_ms) < cfg.on_ms ? cfg.brillo : 0;
  const pos = ms % cfg.periodo_ms;
  const mitad = Math.floor(cfg.periodo_ms / 2);
  const x = pos < mitad ? pos : cfg.periodo_ms - pos;
  return Math.min(cfg.brillo, Math.trunc(cfg.brillo * (x / mitad) ** 2 + 0.5));
}

// "lento" | "normal" | "rapido" | "" (si los milisegundos no son de ningún ritmo).
export function ritmoDe(cfg) {
  const tabla = RITMOS[cfg.modo];
  if (!tabla) return "";
  for (const [nombre, ms] of Object.entries(tabla)) {
    if (cfg.modo === "BLINK" ? cfg.on_ms === ms && cfg.off_ms === ms : cfg.periodo_ms === ms) return nombre;
  }
  return "";
}

export const porcentaje = (brillo) => Math.round((brillo * 100) / BRILLO_MAX);

// "Apagada", "Encendida · 50 %", "Parpadea · normal", "Respira · a medida".
export function resumenLed(cfg) {
  if (cfg.modo === "OFF") return NOMBRES_MODO.OFF;
  if (cfg.modo === "ON") return `${NOMBRES_MODO.ON} · ${porcentaje(cfg.brillo)} %`;
  const ritmo = NOMBRES_RITMO[ritmoDe(cfg)]?.toLowerCase() ?? "a medida";
  return `${NOMBRES_MODO[cfg.modo]} · ${ritmo}`;
}

export const nombreLed = (id) => ledPorId(id)?.nombre ?? id;
