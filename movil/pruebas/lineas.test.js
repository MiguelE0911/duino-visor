import assert from "node:assert/strict";
import { test } from "node:test";

import { BLE } from "../js/catalogo.js";
import { Rearmador, trozos } from "../js/lineas.js";

const texto = (bytes) => new TextDecoder().decode(bytes);

test("una orden corta va en un solo trozo terminado en salto de línea", () => {
  const t = trozos("PING");
  assert.equal(t.length, 1);
  assert.equal(texto(t[0]), "PING\n");
});

test("una orden larga se parte en trozos de 20 bytes", () => {
  const orden = "LED Y BLINK 255 500 250";               // 23 + "\n" = 24 bytes
  const t = trozos(orden);
  assert.deepEqual(t.map((x) => x.length), [BLE.trozo, 4]);
  assert.equal(t.map(texto).join(""), orden + "\n");
});

test("no se duplica el salto de línea si la orden ya lo trae", () => {
  assert.equal(texto(trozos("PING\n")[0]), "PING\n");
});

test("el rearmador junta líneas partidas en varios trozos", () => {
  const lineas = [];
  const r = new Rearmador((l) => lineas.push(l));
  for (const t of trozos("STATE SEQ FANTASTICO 100 RUN")) r.agregar(t);
  r.agregar(new TextEncoder().encode("OK STA"));
  assert.deepEqual(lineas, ["STATE SEQ FANTASTICO 100 RUN"]);
  r.agregar(new TextEncoder().encode("TUS\r\nDATA T=24.0 H=51.0\n"));
  assert.deepEqual(lineas, ["STATE SEQ FANTASTICO 100 RUN", "OK STATUS", "DATA T=24.0 H=51.0"]);
});

test("el rearmador acepta DataView como los eventos de Web Bluetooth", () => {
  const lineas = [];
  const r = new Rearmador((l) => lineas.push(l));
  const bytes = new TextEncoder().encode("xxPONG OAC-LEDS 1\n");
  r.agregar(new DataView(bytes.buffer, 2));
  assert.deepEqual(lineas, ["PONG OAC-LEDS 1"]);
});

test("el rearmador descarta basura sin fin de línea y sigue funcionando", () => {
  const lineas = [];
  const r = new Rearmador((l) => lineas.push(l), 10);
  r.agregar("A".repeat(50));
  r.agregar("\nOK SEQ\n");
  assert.deepEqual(lineas, ["OK SEQ"]);
});
