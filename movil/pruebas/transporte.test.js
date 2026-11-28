// Mensajes reales de Chrome al pedir un dispositivo Bluetooth, y qué entiende la persona.
import assert from "node:assert/strict";
import { test } from "node:test";

import { explicarErrorBluetooth } from "../js/transporte.js";

const error = (name, message) => Object.assign(new Error(message), { name });

test("cerrar la lista sin elegir no es un error", () => {
  assert.equal(explicarErrorBluetooth(error("NotFoundError", "User cancelled the requestDevice() chooser.")), null);
});

test("NotFoundError también puede ser Bluetooth apagado: se explica, no se calla", () => {
  const e = explicarErrorBluetooth(error("NotFoundError", "Bluetooth adapter not available."));
  assert.match(e.message, /Bluetooth del celular está apagado/);
  assert.equal(e.detalle, "NotFoundError: Bluetooth adapter not available.");
});

test("permiso bloqueado", () => {
  for (const e of [error("NotFoundError", "Bluetooth permission has been blocked."), error("NotAllowedError", "Permission denied.")]) {
    assert.match(explicarErrorBluetooth(e).message, /permiso/);
  }
});

test("ubicación apagada en Android", () => {
  assert.match(explicarErrorBluetooth(error("NotFoundError", "Location services are turned off.")).message, /Ubicación/);
});

test("sin toque del usuario se pide tocar otra vez, aunque el texto diga «permission»", () => {
  const e = error("SecurityError", "Must be handling a user gesture to show a permission request.");
  assert.match(explicarErrorBluetooth(e).message, /otra vez/);
});

test("Bluetooth desactivado en el navegador y errores desconocidos", () => {
  assert.match(explicarErrorBluetooth(error("NotFoundError", "Web Bluetooth API globally disabled.")).message, /desactivado/);
  const raro = explicarErrorBluetooth(error("NetworkError", "algo raro"));
  assert.match(raro.message, /No se pudo/);
  assert.equal(raro.detalle, "NetworkError: algo raro");
});
