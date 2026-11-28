// La placa simulada se compara con el sketch compilado en tests/firmware/test_sketch.py; aquí van los casos
// que dependen del tiempo (animaciones, sensor, semáforo térmico) y el transporte de demostración.
import assert from "node:assert/strict";
import { test } from "node:test";

import { COLORES, LUZ_DE_ZONA, SECUENCIAS } from "../js/catalogo.js";
import { Envio } from "../js/envio.js";
import { leerStatus } from "../js/protocolo.js";
import { PlacaSimulada, TransporteDemo } from "../js/simulador.js";

const estadoDe = (placa, t) => leerStatus(placa.procesar("STATUS", t).filter((l) => l.startsWith("STATE ")).map((l) => l.slice(6)));

test("el sensor manda DATA con el periodo pedido", () => {
  const p = new PlacaSimulada();
  p.procesar("DHT 1000", 0);
  const datos = [];
  for (let t = 0; t <= 3000; t += 10) datos.push(...p.tick(t));
  assert.equal(datos.length, 3);
  assert.match(datos[0], /^DATA T=\d+\.0 H=\d+\.0$/);
});

test("una animación cambia los LEDs con el tiempo y se ve en STATUS", () => {
  const p = new PlacaSimulada();
  assert.deepEqual(p.procesar("SEQ VIAL", 0), ["OK SEQ"]);
  const encendidos = (t) => Object.entries(estadoDe(p, t).leds).filter(([, l]) => l.modo === "ON").map(([c]) => c);
  const [[ms0, paso0], [, paso1]] = SECUENCIAS.VIAL;
  assert.deepEqual(encendidos(100), Object.keys(paso0));
  assert.deepEqual(encendidos(ms0 + 100), Object.keys(paso1));
  assert.deepEqual(estadoDe(p, 5100).seq, { nombre: "VIAL", vel: 100, pausada: false });
});

test("el semáforo térmico enciende el LED de la zona", () => {
  const p = new PlacaSimulada();
  p.lectura = () => [30, 50];                                 // hace calor
  p.procesar("TERMO 22 28", 0);
  p.tick(5000);
  const leds = estadoDe(p, 5000).leds;
  const calor = LUZ_DE_ZONA[2];
  assert.equal(leds[calor.color].modo, calor.modo);
  assert.equal(COLORES.filter((c) => leds[c].modo !== "OFF").length, 1);
});

test("el transporte de demostración responde por el mismo camino que el Bluetooth", async () => {
  const t = new TransporteDemo({ retardoMs: 1 });
  const estados = [];
  t.alEstado = (e) => estados.push(e);
  const envio = new Envio((o) => t.escribir(o));
  t.alLinea = (l) => envio.recibir(l);
  await t.conectar();
  const { respuesta } = await envio.enviar("PING");
  assert.equal(respuesta.tipo, "PONG");
  const { estados: lineas } = await envio.enviar("STATUS");
  assert.equal(lineas.length, COLORES.length + 1);
  await assert.rejects(envio.enviar(`LED ${COLORES[0]} ON 300`), /brillo 0-255/);
  t.desconectar();
  assert.deepEqual(estados, ["conectando", "conectado", "desconectado"]);
});
