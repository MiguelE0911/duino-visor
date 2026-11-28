import assert from "node:assert/strict";
import { test } from "node:test";

import { COLORES } from "../js/catalogo.js";
import {
  brilloEn, comandoDht, comandoLed, comandoSeq, comandoTermo, errores, interpretar, ledConfig, leerStatus,
  resumenLed, ritmoDe,
} from "../js/protocolo.js";

const c = COLORES[0];

test("órdenes de LED", () => {
  assert.equal(comandoLed(ledConfig(c)), `LED ${c} OFF`);
  assert.equal(comandoLed(ledConfig(c, { modo: "ON", brillo: 128 })), `LED ${c} ON 128`);
  assert.equal(comandoLed(ledConfig(c, { modo: "BLINK", brillo: 9, on_ms: 100, off_ms: 300 })), `LED ${c} BLINK 9 100 300`);
  assert.equal(comandoLed(ledConfig(c, { modo: "FADE", brillo: 200, periodo_ms: 2000 })), `LED ${c} FADE 200 2000`);
});

test("valores fuera de rango no generan orden", () => {
  assert.throws(() => comandoLed(ledConfig(c, { modo: "ON", brillo: 300 })), /brillo/);
  assert.throws(() => comandoLed(ledConfig(c, { modo: "BLINK", on_ms: 10 })), /encendido/);
  assert.throws(() => comandoLed(ledConfig(c, { modo: "FADE", periodo_ms: 100 })), /periodo/);
  assert.throws(() => comandoLed(ledConfig("X", { modo: "ON" })), /color/);
  assert.deepEqual(errores(ledConfig(c, { modo: "OFF", brillo: 999 })), []); // apagado: el brillo no importa
});

test("órdenes del sensor, semáforo térmico y animaciones", () => {
  assert.equal(comandoDht(1000), "DHT 1000");
  assert.throws(() => comandoDht(500));
  assert.equal(comandoTermo([22, 28]), "TERMO 22 28");
  assert.equal(comandoTermo(null), "TERMO OFF");
  assert.throws(() => comandoTermo([28, 22]));
  assert.equal(comandoSeq("VIAL"), "SEQ VIAL");
  assert.equal(comandoSeq("VIAL", 150), "SEQ VIAL 150");
  assert.throws(() => comandoSeq("FOO"));
  assert.throws(() => comandoSeq("VIAL", 10));
});

test("interpretar respuestas", () => {
  assert.equal(interpretar("PONG OAC-LEDS 1").tipo, "PONG");
  assert.deepEqual(interpretar("DATA T=24.5 H=51.0"), { tipo: "DATA", texto: "DATA T=24.5 H=51.0", temperatura: 24.5, humedad: 51 });
  assert.equal(interpretar("DATA ERR").tipo, "DATA_ERR");
  assert.equal(interpretar("DATA T=x").tipo, "OTRO");
  assert.deepEqual(interpretar("OK LED R"), { tipo: "OK", texto: "LED R" });
  assert.deepEqual(interpretar("ERR brillo 0-255"), { tipo: "ERR", texto: "brillo 0-255" });
  assert.deepEqual(interpretar("STATE SEQ OFF"), { tipo: "STATE", texto: "SEQ OFF" });
});

test("leer STATUS", () => {
  const estados = COLORES.map((x, i) => (i === 0 ? `${x} BLINK 200 100 300 0` : `${x} OFF 0 0 0 0`));
  let r = leerStatus([...estados, "SEQ OFF"]);
  assert.deepEqual(Object.keys(r.leds), COLORES);
  assert.deepEqual(r.leds[c], ledConfig(c, { modo: "BLINK", brillo: 200, on_ms: 100, off_ms: 300, periodo_ms: 0 }));
  assert.equal(r.seq, null);
  r = leerStatus(["SEQ VIAL 150 PAUSA"]);
  assert.deepEqual(r.seq, { nombre: "VIAL", vel: 150, pausada: true });
});

test("brillo en cada instante, igual que el sketch", () => {
  const blink = ledConfig(c, { modo: "BLINK", brillo: 255, on_ms: 500, off_ms: 250 });
  assert.deepEqual([0, 499, 500, 749, 750].map((t) => brilloEn(blink, t)), [255, 255, 0, 0, 255]);
  const fade = ledConfig(c, { modo: "FADE", brillo: 200, periodo_ms: 2000 });
  assert.equal(brilloEn(fade, 0), 0);
  assert.equal(brilloEn(fade, 1000), 200);
  assert.equal(brilloEn(fade, 500), 50);                     // (0.5)^2 * 200: corrección gamma
});

test("resumen para la pantalla", () => {
  assert.equal(resumenLed(ledConfig(c)), "Apagada");
  assert.equal(resumenLed(ledConfig(c, { modo: "ON", brillo: 128 })), "Encendida · 50 %");
  assert.equal(resumenLed(ledConfig(c, { modo: "BLINK", on_ms: 500, off_ms: 500 })), "Parpadea · normal");
  assert.equal(resumenLed(ledConfig(c, { modo: "FADE", periodo_ms: 3000 })), "Respira · a medida");
  assert.equal(ritmoDe(ledConfig(c, { modo: "FADE", periodo_ms: 4000 })), "lento");
});
