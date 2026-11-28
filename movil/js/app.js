// Arranque y pantalla de la app del celular. Une el transporte (Bluetooth o demo), el envío con confirmación
// y lo que se muestra. La lógica que no necesita la pantalla está en los otros módulos, con sus pruebas.
import { LEDS, NOMBRES_SEQ } from "./catalogo.js";
import { SecuenciaLocal } from "./automatismos.js";
import { Envio } from "./envio.js";
import { brilloEn, interpretar, leerStatus, resumenLed } from "./protocolo.js";
import { TransporteDemo } from "./simulador.js";
import { TransporteBle, motivoSinBluetooth } from "./transporte.js";

const CADA_CUANTO_STATUS_MS = 5000;
const MAX_REGISTRO = 80;

const $ = (id) => document.getElementById(id);

const app = {
  transporte: null,
  envio: null,
  esDemo: false,
  leds: {},            // lo último que dijo STATUS
  seq: new SecuenciaLocal(),
  statusEn: 0,         // performance.now() de ese STATUS
  lectura: null,       // {temperatura, humedad, en}
  pantalla: "luces",
};

// ---------------------------------------------------------------- conexión
const TEXTO_ESTADO = {
  desconectado: "Sin conexión",
  buscando: "Buscando…",
  conectando: "Conectando…",
  conectado: "Conectada",
  reconectando: "Reconectando…",
};

function conectar(transporte, esDemo) {
  if (app.transporte) {
    app.transporte.alEstado = () => {};
    app.transporte.desconectar();
  }
  app.transporte = transporte;
  app.esDemo = esDemo;
  app.envio = new Envio((orden) => {
    registrar("→ " + orden, "tx");
    return transporte.escribir(orden);
  });
  transporte.alLinea = alLinea;
  transporte.alEstado = alEstado;
  // conectar() abre el selector de Bluetooth: tiene que ocurrir dentro del toque, sin esperas antes.
  transporte.conectar().catch((e) => mostrarMensaje(e.message ?? String(e), true));
}

function alEstado(estado, detalle) {
  const pastilla = $("pastilla");
  pastilla.dataset.estado = estado;
  $("pastilla-texto").textContent = estado === "conectado" && app.esDemo ? "Demostración" : TEXTO_ESTADO[estado];
  $("det-conexion").textContent = TEXTO_ESTADO[estado] + (app.esDemo ? " (sin placa)" : " (Bluetooth)");
  $("det-placa").textContent = app.transporte?.nombre ?? "—";

  $("aviso-reconexion").hidden = estado !== "reconectando";
  if (estado === "reconectando") {
    app.envio?.cancelarTodo();
    const seg = Math.round((detalle?.esperaMs ?? 0) / 1000);
    $("aviso-reconexion-texto").textContent = `Intento ${detalle?.intento ?? 1}: volveré a probar en ${seg} s. Acerca el celular a la placa.`;
  }
  if (estado === "conectado") {
    mostrarConectado(true);
    comprobarPlaca();
  }
  if (estado === "desconectado") {
    app.envio?.cancelarTodo();
    mostrarConectado(false);
  }
  const ocupado = estado === "buscando" || estado === "conectando";
  $("btn-buscar").disabled = ocupado || motivoSinBluetooth() !== null;
  $("btn-demo").disabled = ocupado;
}

// Al conectar: ¿es nuestra placa? Luego, qué tiene encendido.
async function comprobarPlaca() {
  try {
    await app.envio.enviar("PING");
    await leerEstado();
  } catch (e) {
    if (e.codigo === "CANCELADO") return;
    mostrarMensaje("La placa no contesta como se esperaba. Comprueba que tenga cargado el programa control_leds.ino.", true);
  }
}

async function leerEstado() {
  const { estados } = await app.envio.enviar("STATUS");
  const { leds, seq } = leerStatus(estados);
  app.leds = leds;
  app.statusEn = performance.now();
  if (seq) {
    app.seq.iniciar(seq.nombre, seq.vel, 0);
    if (seq.pausada) app.seq.pausar(0);
  } else {
    app.seq.detener();
  }
  pintarLuces();
}

// Orden escrita en «Mostrar detalles». Después se vuelve a leer el estado para que se vea el cambio.
async function enviarAMano(texto) {
  const orden = texto.trim().toUpperCase();
  if (!orden || !app.transporte?.conectado) return;
  $("orden").value = "";
  try {
    await app.envio.enviar(orden);
    if (orden !== "STATUS") await leerEstado();
  } catch (e) {
    if (e.codigo !== "CANCELADO") mostrarMensaje(e.message, true);
  }
}

// Cada línea que manda la placa: si no es la respuesta a una orden, puede ser una lectura del sensor.
function alLinea(linea) {
  const m = interpretar(linea);
  registrar("← " + linea, m.tipo === "ERR" || m.tipo === "DATA_ERR" ? "err" : "");
  if (app.envio?.recibir(linea)) return;
  if (m.tipo === "DATA") {
    app.lectura = { temperatura: m.temperatura, humedad: m.humedad, en: Date.now() };
    pintarClima();
  } else if (m.tipo === "DATA_ERR") {
    $("clima-hora").textContent = "El sensor no respondió en la última lectura.";
  }
}

// ---------------------------------------------------------------- pantalla
function mostrarConectado(si) {
  $("pantalla-conexion").hidden = si;
  $("pestanas").hidden = !si;
  $("detalles").hidden = !si;
  irA(si ? app.pantalla : null);
  if (!si) {
    app.leds = {};
    app.seq.detener();
    app.lectura = null;
    pintarClima();
  }
}

function irA(pantalla) {
  if (pantalla) app.pantalla = pantalla;
  for (const nombre of ["luces", "clima"]) $(`pantalla-${nombre}`).hidden = pantalla !== nombre;
  for (const b of document.querySelectorAll(".pestana")) {
    if (b.dataset.pantalla === pantalla) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  }
}

function crearLuces() {
  const lista = $("lista-luces");
  lista.replaceChildren();
  for (const led of [...LEDS].sort((a, b) => a.fila - b.fila)) {
    const li = document.createElement("li");
    li.className = "tarjeta luz";
    li.innerHTML = `<span class="bombilla" aria-hidden="true"></span><div><h3></h3><p>—</p></div>`;
    li.querySelector(".bombilla").style.setProperty("--color", led.color);
    li.querySelector("h3").textContent = led.luz;
    li.dataset.id = led.id;
    lista.append(li);
  }
}

function pintarLuces() {
  const seq = app.seq.activa ? app.seq.nombre : null;
  $("animacion-actual").hidden = !seq;
  if (seq) $("animacion-actual").textContent = `Animación: ${NOMBRES_SEQ[seq] ?? seq}${app.seq.pausada ? " (en pausa)" : ""}`;
  for (const li of document.querySelectorAll(".luz")) {
    const cfg = app.leds[li.dataset.id];
    li.querySelector("p").textContent = seq ? "La controla la animación" : cfg ? resumenLed(cfg) : "—";
  }
}

// Brillo de cada bombilla en este instante (calculado a partir del último STATUS).
function animarLuces() {
  if (app.pantalla === "luces" && app.transporte?.conectado) {
    const t = performance.now() - app.statusEn;
    const brillos = app.seq.brillos(t);
    for (const li of document.querySelectorAll(".luz")) {
      const cfg = app.leds[li.dataset.id];
      const b = brillos ? brillos[li.dataset.id] : cfg ? brilloEn(cfg, t) : 0;
      li.querySelector(".bombilla").style.setProperty("--nivel", (b / 255).toFixed(3));
    }
  }
  requestAnimationFrame(animarLuces);
}

function pintarClima() {
  const l = app.lectura;
  $("temperatura").textContent = l ? l.temperatura.toFixed(1).replace(".", ",") : "--";
  $("humedad").textContent = l ? Math.round(l.humedad) : "--";
  if (!l) {
    $("clima-hora").textContent = "Esperando la primera lectura del sensor…";
    return;
  }
  const seg = Math.round((Date.now() - l.en) / 1000);
  $("clima-hora").textContent = seg < 2 ? "Actualizado ahora mismo" : `Actualizado hace ${seg} s`;
}

function registrar(texto, clase = "") {
  const ol = $("registro");
  const li = document.createElement("li");
  li.textContent = texto;
  if (clase) li.className = clase;
  ol.append(li);
  while (ol.children.length > MAX_REGISTRO) ol.firstChild.remove();
  ol.scrollTop = ol.scrollHeight;
}

let temporizadorMensaje = null;
function mostrarMensaje(texto, error = false) {
  const m = $("mensaje");
  m.textContent = texto;
  m.classList.toggle("error", error);
  m.hidden = false;
  clearTimeout(temporizadorMensaje);
  temporizadorMensaje = setTimeout(() => { m.hidden = true; }, error ? 7000 : 3500);
}

// ---------------------------------------------------------------- arranque
function iniciar() {
  crearLuces();
  const motivo = motivoSinBluetooth();
  if (motivo) {
    $("sin-bluetooth").textContent = motivo;
    $("sin-bluetooth").hidden = false;
    $("btn-buscar").disabled = true;
  }
  $("btn-buscar").addEventListener("click", () => conectar(new TransporteBle(), false));
  $("btn-demo").addEventListener("click", () => conectar(new TransporteDemo(), true));
  $("btn-desconectar").addEventListener("click", () => app.transporte?.desconectar());
  $("btn-dejar").addEventListener("click", () => app.transporte?.desconectar());
  for (const b of document.querySelectorAll(".pestana")) b.addEventListener("click", () => irA(b.dataset.pantalla));
  $("mensaje").addEventListener("click", () => { $("mensaje").hidden = true; });
  $("form-orden").addEventListener("submit", (e) => {
    e.preventDefault();
    enviarAMano($("orden").value);
  });

  // Otra app (el escritorio) puede cambiar la placa: se vuelve a leer su estado cada pocos segundos.
  setInterval(() => {
    if (app.transporte?.conectado && !app.envio.ocupado && document.visibilityState === "visible") {
      leerEstado().catch(() => {});
    }
  }, CADA_CUANTO_STATUS_MS);
  setInterval(() => { if (app.lectura) pintarClima(); }, 1000);
  requestAnimationFrame(animarLuces);
}

iniciar();
