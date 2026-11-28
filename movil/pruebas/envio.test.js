import assert from "node:assert/strict";
import { test } from "node:test";

import { Envio, confirmacionDe } from "../js/envio.js";

// Temporizador manual: las esperas solo vencen cuando la prueba lo dice.
function relojFalso() {
  const pendientes = new Map();
  let id = 0;
  return {
    poner(f) { pendientes.set(++id, f); return id; },
    quitar(i) { pendientes.delete(i); },
    vencer() { const fs = [...pendientes.values()]; pendientes.clear(); fs.forEach((f) => f()); },
    get cuantos() { return pendientes.size; },
  };
}

function preparar(opciones = {}) {
  const enviadas = [];
  const reloj = relojFalso();
  const envio = new Envio(async (orden) => { enviadas.push(orden); }, { temporizador: reloj, ...opciones });
  return { envio, enviadas, reloj };
}

const tic = () => new Promise((r) => setImmediate(r));

test("qué respuesta confirma cada orden", () => {
  assert.equal(confirmacionDe("LED R ON 9"), "LED R");
  assert.equal(confirmacionDe("seq vial 150"), "SEQ");
  assert.equal(confirmacionDe("STATUS"), "STATUS");
  assert.equal(confirmacionDe("PING"), null);
});

test("una orden a la vez: la segunda sale cuando llega el OK de la primera", async () => {
  const { envio, enviadas } = preparar();
  const a = envio.enviar("LED R ON 9");
  const b = envio.enviar("DHT 1000");
  await tic();
  assert.deepEqual(enviadas, ["LED R ON 9"]);
  assert.equal(envio.recibir("DATA T=24.0 H=50.0"), false);  // las lecturas no son respuestas
  assert.equal(envio.recibir("OK DHT"), false);              // no es la confirmación de esta orden
  assert.equal(envio.recibir("OK LED R"), true);
  assert.equal((await a).respuesta.texto, "LED R");
  await tic();
  assert.deepEqual(enviadas, ["LED R ON 9", "DHT 1000"]);
  envio.recibir("OK DHT");
  await b;
  assert.equal(envio.ocupado, false);
});

test("PING se confirma con PONG y STATUS junta las líneas STATE", async () => {
  const { envio } = preparar();
  const ping = envio.enviar("PING");
  await tic();
  envio.recibir("PONG OAC-LEDS 1");
  assert.equal((await ping).respuesta.tipo, "PONG");
  const status = envio.enviar("STATUS");
  await tic();
  ["STATE R ON 9 0 0 0", "STATE SEQ OFF", "OK STATUS"].forEach((l) => envio.recibir(l));
  assert.deepEqual((await status).estados, ["R ON 9 0 0 0", "SEQ OFF"]);
});

test("un ERR rechaza la orden con un mensaje claro y sigue con la siguiente", async () => {
  const { envio, enviadas } = preparar();
  const a = envio.enviar("LED R ON 300");
  const b = envio.enviar("PING");
  await tic();
  envio.recibir("ERR brillo 0-255");
  await assert.rejects(a, (e) => e.codigo === "ERR" && /brillo 0-255/.test(e.message));
  await tic();
  assert.equal(enviadas.at(-1), "PING");
  envio.recibir("PONG OAC-LEDS 1");
  await b;
});

test("sin respuesta reintenta una vez y luego falla", async () => {
  const { envio, enviadas, reloj } = preparar();
  const a = envio.enviar("PING");
  await tic();
  reloj.vencer();
  await tic();
  assert.deepEqual(enviadas, ["PING", "PING"]);
  reloj.vencer();
  await assert.rejects(a, (e) => e.codigo === "SIN_RESPUESTA");
  assert.equal(reloj.cuantos, 0);
});

test("si falla la escritura, la orden falla sin esperar", async () => {
  const reloj = relojFalso();
  const envio = new Envio(async () => { throw new Error("GATT desconectado"); }, { temporizador: reloj });
  await assert.rejects(envio.enviar("PING"), (e) => e.codigo === "ESCRITURA" && /GATT/.test(e.message));
  assert.equal(reloj.cuantos, 0);
});

test("al perder la conexión se cancela todo lo pendiente", async () => {
  const { envio, reloj } = preparar();
  const a = envio.enviar("PING");
  const b = envio.enviar("STATUS");
  await tic();
  envio.cancelarTodo();
  await assert.rejects(a, (e) => e.codigo === "CANCELADO");
  await assert.rejects(b, (e) => e.codigo === "CANCELADO");
  assert.equal(envio.ocupado, false);
  assert.equal(reloj.cuantos, 0);
});
