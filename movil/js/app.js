// Arranque y pantalla de la app del celular. Une el transporte (Bluetooth o demo), el envío con confirmación
// y lo que se muestra. La lógica que no necesita la pantalla está en los otros módulos, con sus pruebas.
import { LEDS, NOMBRES_SEQ } from "./catalogo.js";
import { SecuenciaLocal } from "./automatismos.js";
import { Envio } from "./envio.js";
import { apagar, encender, estaEncendida, ordenesTodas } from "./luces.js";
import { brilloEn, comandoLed, comandoSeq, interpretar, ledConfig, leerStatus } from "./protocolo.js";
import { TransporteDemo } from "./simulador.js";
import { TransporteBle, motivoSinBluetooth } from "./transporte.js";
import { crearVistaLuces } from "./vistas/luces.js";

const CADA_CUANTO_STATUS_MS = 5000;
const MAX_REGISTRO = 80;

const $ = (id) => document.getElementById(id);

const app = {
  transporte: null,
  envio: null,
  esDemo: false,
  leds: {},            // lo que la placa confirmó (STATUS u OK de una orden)
  t0: {},              // performance.now() en que cada LED empezó su configuración actual (para animarla)
  recordados: {},      // última configuración encendida de cada LED (el interruptor la recupera)
  pendiente: {},       // id -> {cfg, n}: enviado y esperando OK
  previa: {},          // id -> cfg mientras se arrastra el brillo
  contador: 0,
  seq: new SecuenciaLocal(),   // copia local de la animación, para dibujarla
  seqInfo: null,       // {nombre, vel, pausada} según STATUS
  lectura: null,       // {temperatura, humedad, en}
  pantalla: "luces",
  vista: null,
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
  mostrarErrorConexion(null);
  // conectar() abre el selector de Bluetooth: tiene que ocurrir dentro del toque, sin esperas antes.
  transporte.conectar().catch((e) => mostrarErrorConexion(e));
}

// El problema queda escrito en la tarjeta de conexión (con el detalle técnico debajo) hasta el próximo intento.
function mostrarErrorConexion(e) {
  $("error-conexion").hidden = !e;
  if (!e) return;
  $("error-conexion-texto").textContent = e.message ?? String(e);
  $("error-conexion-detalle").textContent = e.detalle ? `Detalle técnico: ${e.detalle}` : "";
}

// ¿Está encendido el Bluetooth? Se avisa antes de tocar el botón (no todos los navegadores lo saben).
async function vigilarBluetooth() {
  const bt = navigator.bluetooth;
  if (!bt?.getAvailability) return;
  const pintar = (si) => {
    if (motivoSinBluetooth()) return;
    $("sin-bluetooth").hidden = si;
    $("sin-bluetooth").textContent = "El Bluetooth del celular parece apagado. Enciéndelo para buscar la placa.";
  };
  try {
    pintar(await bt.getAvailability());
    bt.addEventListener("availabilitychanged", (ev) => pintar(ev.value));
  } catch { /* sin información: no se avisa */ }
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
  const ahora = performance.now();
  for (const [id, cfg] of Object.entries(leds)) {
    if (JSON.stringify(app.leds[id]) !== JSON.stringify(cfg)) app.t0[id] = ahora;
    if (!seq && estaEncendida(cfg)) app.recordados[id] = cfg;
  }
  app.leds = leds;
  if (seq) {
    if (!app.seq.activa || app.seq.nombre !== seq.nombre || app.seq.vel !== seq.vel) app.seq.iniciar(seq.nombre, seq.vel, ahora);
    if (seq.pausada) app.seq.pausar(ahora); else app.seq.seguir(ahora);
  } else {
    app.seq.detener();
  }
  app.seqInfo = seq;
  pintarLuces();
}

// Después de una orden: se vuelve a leer la placa (otras luces pueden haber cambiado, p. ej. al cortar una
// animación). Si quedan órdenes en cola, lo hará la última.
async function refrescar() {
  if (app.envio && app.transporte?.conectado && !app.envio.ocupado) {
    try { await leerEstado(); } catch { /* el próximo STATUS periódico lo arregla */ }
  } else {
    pintarLuces();
  }
}

function avisarFallo(e) {
  if (e?.codigo !== "CANCELADO") mostrarMensaje(e?.message ?? String(e), true);
}

// ---------------------------------------------------------------- acciones de la pantalla Luces
const visible = (id) => app.previa[id] ?? app.pendiente[id]?.cfg ?? app.leds[id] ?? ledConfig(id);

async function cambiarLed(cfg) {
  if (!app.transporte?.conectado) return;
  const id = cfg.color;
  let orden;
  try {
    orden = comandoLed(cfg);
  } catch (e) {
    mostrarMensaje(e.message, true);
    return;
  }
  const n = ++app.contador;
  app.pendiente[id] = { cfg, n };
  app.t0[id] = performance.now();
  pintarLuces();
  try {
    await app.envio.enviar(orden);
    app.leds[id] = cfg;                      // confirmado; una orden de LED corta animación y semáforo térmico
    if (estaEncendida(cfg)) app.recordados[id] = cfg;
    app.seq.detener();
    app.seqInfo = null;
  } catch (e) {
    avisarFallo(e);
  } finally {
    if (app.pendiente[id]?.n === n) delete app.pendiente[id];
    await refrescar();
  }
}

async function ordenAnimacion(orden) {
  if (!app.transporte?.conectado) return;
  try {
    await app.envio.enviar(orden);
  } catch (e) {
    avisarFallo(e);
  } finally {
    await refrescar();
  }
}

const accionesLuces = {
  cambiar: cambiarLed,
  vistaPrevia(id, cfg) {
    if (cfg) app.previa[id] = cfg; else delete app.previa[id];
  },
  alternar(id) {
    const cfg = visible(id);
    cambiarLed(estaEncendida(cfg) ? apagar(cfg) : encender(cfg, app.recordados[id]));
  },
  todas(encendidas) {
    if (!encendidas && app.seqInfo) {
      ordenAnimacion("SEQ OFF");               // detener la animación ya las deja apagadas
      return;
    }
    const actuales = Object.fromEntries(LEDS.map((l) => [l.id, visible(l.id)]));
    for (const { cfg } of ordenesTodas(encendidas, actuales, app.recordados)) {
      // Una luz que ya está así no se toca (reiniciaría su parpadeo), salvo que haya que cortar una animación.
      if (app.seqInfo || JSON.stringify(cfg) !== JSON.stringify(actuales[cfg.color])) cambiarLed(cfg);
    }
  },
  animacion: (nombre, vel) => ordenAnimacion(comandoSeq(nombre, vel)),
  pausar: () => ordenAnimacion("SEQ PAUSA"),
  seguir: () => ordenAnimacion("SEQ SEGUIR"),
  detener: () => ordenAnimacion("SEQ OFF"),
};

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
    Object.assign(app, { leds: {}, pendiente: {}, previa: {}, seqInfo: null });
    app.seq.detener();
    pintarLuces();
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

function pintarLuces() {
  const seq = app.seqInfo;
  $("animacion-actual").hidden = !seq;
  if (seq) $("animacion-actual").textContent = `Animación: ${NOMBRES_SEQ[seq.nombre] ?? seq.nombre}${seq.pausada ? " (en pausa)" : ""}`;
  const cfg = {}, enviando = {};
  for (const { id } of LEDS) {
    cfg[id] = visible(id);
    enviando[id] = Boolean(app.pendiente[id]);
  }
  app.vista.pintar({ cfg, enviando, seq });
}

// Brillo de cada bombilla en este instante, calculado desde lo confirmado (o lo que se está enviando).
function animarLuces() {
  if (app.pantalla === "luces" && app.transporte?.conectado) {
    const ahora = performance.now();
    const brillos = app.seq.brillos(ahora);
    const niveles = {};
    for (const { id } of LEDS) {
      const propio = app.previa[id] ?? app.pendiente[id]?.cfg;
      const b = !propio && brillos ? brillos[id] : brilloEn(visible(id), ahora - (app.t0[id] ?? ahora));
      niveles[id] = b / 255;
    }
    app.vista.animar(niveles);
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
  app.vista = crearVistaLuces($("vista-luces"), accionesLuces);
  pintarLuces();
  const motivo = motivoSinBluetooth();
  if (motivo) {
    $("sin-bluetooth").textContent = motivo;
    $("sin-bluetooth").hidden = false;
    $("btn-buscar").disabled = true;
  } else {
    vigilarBluetooth();
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
