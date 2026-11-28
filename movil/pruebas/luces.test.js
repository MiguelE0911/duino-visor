import assert from "node:assert/strict";
import { test } from "node:test";

import { COLORES, RITMOS } from "../js/catalogo.js";
import { apagar, conBrillo, conModo, conRitmo, encender, mismaLuz, ordenesTodas } from "../js/luces.js";
import { comandoLed, ledConfig, leerStatus, ritmoDe } from "../js/protocolo.js";

const c = COLORES[0];
// Como llega de STATUS: los campos que el modo no usa valen 0.
const deStatus = (texto) => leerStatus([`${c} ${texto}`]).leds[c];

test("pasar de fija a parpadea o respira pone un ritmo válido", () => {
  const fija = deStatus("ON 128 0 0 0");
  const parpadea = conModo(fija, "BLINK");
  assert.equal(ritmoDe(parpadea), "normal");
  assert.equal(parpadea.brillo, 128);
  assert.equal(comandoLed(parpadea), `LED ${c} BLINK 128 ${RITMOS.BLINK.normal} ${RITMOS.BLINK.normal}`);
  assert.equal(ritmoDe(conModo(fija, "FADE")), "normal");
});

test("cambiar de modo conserva los tiempos si ya eran válidos", () => {
  const lenta = deStatus("BLINK 200 1000 1000 4000");
  assert.equal(ritmoDe(conModo(lenta, "FADE")), "lento");     // el periodo 4000 ya estaba
});

test("elegir un modo con brillo 0 la enciende al máximo", () => {
  assert.equal(conModo(deStatus("OFF 0 0 0 0"), "ON").brillo, 255);
});

test("mover el brillo de una luz apagada la enciende fija", () => {
  const cfg = conBrillo(deStatus("OFF 0 0 0 0"), 64.4);
  assert.equal(comandoLed(cfg), `LED ${c} ON 64`);
  assert.equal(conBrillo(cfg, 999).brillo, 255);
});

test("el ritmo cambia los milisegundos del modo actual", () => {
  const cfg = conRitmo(conModo(ledConfig(c), "BLINK"), "rapido");
  assert.equal(cfg.on_ms, RITMOS.BLINK.rapido);
  assert.equal(conRitmo(conModo(ledConfig(c), "FADE"), "lento").periodo_ms, RITMOS.FADE.lento);
  const fija = conModo(ledConfig(c), "ON");
  assert.deepEqual(conRitmo(fija, "lento"), fija);              // una luz fija no tiene ritmo
});

test("el interruptor vuelve a encenderla como estaba", () => {
  const recordada = deStatus("FADE 90 0 0 1000");
  const apagada = apagar(recordada);
  assert.equal(comandoLed(apagada), `LED ${c} OFF`);
  assert.equal(comandoLed(encender(apagada, recordada)), `LED ${c} FADE 90 1000`);
  assert.equal(comandoLed(encender(deStatus("OFF 0 0 0 0"))), `LED ${c} ON 255`);   // sin recuerdo: fija al máximo
  assert.deepEqual(encender(recordada), recordada);             // ya encendida: no cambia
});

test("todas a la vez", () => {
  const leds = Object.fromEntries(COLORES.map((x) => [x, ledConfig(x)]));
  const recordados = { [c]: ledConfig(c, { modo: "BLINK", brillo: 50, on_ms: 200, off_ms: 200 }) };
  const encender = ordenesTodas(true, leds, recordados).map((o) => o.orden);
  assert.equal(encender.length, COLORES.length);
  assert.equal(encender[0], `LED ${c} BLINK 50 200 200`);
  assert.ok(encender.slice(1).every((o) => / ON 255$/.test(o)));
  assert.deepEqual(ordenesTodas(false, leds).map((o) => o.orden), COLORES.map((x) => `LED ${x} OFF`));
});

test("misma luz: se compara lo que hace, no los campos que el modo no usa", () => {
  const pedida = conModo(ledConfig(c), "ON");                    // on_ms 500, off_ms 500, periodo 2000
  assert.ok(mismaLuz(pedida, deStatus("ON 255 0 0 0")));          // STATUS trae 0 en esos campos
  assert.ok(!mismaLuz(pedida, deStatus("ON 128 0 0 0")));
  assert.ok(mismaLuz(apagar(pedida), deStatus("OFF 7 0 0 0")));   // apagada: el brillo no importa
  assert.ok(!mismaLuz(pedida, undefined));
});

test("tras una orden de animación confirmada se sabe cómo quedó la placa, igual que con STATUS", async () => {
  const { trasOrdenSeq } = await import("../js/luces.js");
  const { PlacaSimulada } = await import("../js/simulador.js");
  const { SECUENCIAS } = await import("../js/catalogo.js");
  const placa = new PlacaSimulada();
  const leer = () => leerStatus(placa.procesar("STATUS", 0).filter((l) => l.startsWith("STATE ")).map((l) => l.slice(6)));
  let estado = { leds: leer().leds, seq: null };
  const ordenes = [`LED ${c} BLINK 9 100 300`, ...Object.keys(SECUENCIAS).map((s) => `SEQ ${s} 150`), "SEQ PAUSA",
    "SEQ SEGUIR", "SEQ OFF", "SEQ OFF", "SEQ VIAL", "SEQ OFF"];
  for (const orden of ordenes) {
    assert.deepEqual(placa.procesar(orden, 0).at(-1).slice(0, 2), "OK", orden);
    if (orden.startsWith("SEQ")) estado = trasOrdenSeq(estado, orden);
    else estado = leer();
    const real = leer();                                     // con el tiempo detenido en 0: el primer paso
    assert.deepEqual(estado.seq, real.seq, orden);
    for (const x of COLORES) assert.ok(mismaLuz(estado.leds[x], real.leds[x]), `${orden} ${x}`);
  }
});

test("desde el celular no se aceleran las animaciones", async () => {
  const { VELOCIDADES_MOVIL, VEL_MIN } = await import("../js/catalogo.js");
  const { comandoSeq } = await import("../js/protocolo.js");
  assert.ok(VELOCIDADES_MOVIL.length > 0);
  for (const [vel, texto] of VELOCIDADES_MOVIL) {
    assert.ok(vel >= VEL_MIN && vel <= 100, `${texto}: ${vel}`);
    assert.doesNotThrow(() => comandoSeq("VIAL", vel));       // el sketch la acepta
  }
});
