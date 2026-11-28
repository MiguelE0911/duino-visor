// Placa simulada para el modo demo: responde igual que el sketch control_leds.ino.
//   - PlacaSimulada: la lógica, pura (el tiempo se pasa en ms). tests/firmware/test_sketch.py comprueba que
//     responde lo mismo que el sketch compilado.
//   - TransporteDemo: la misma interfaz que TransporteBle (transporte.js), con la placa simulada detrás.
import { COLORES, SECUENCIAS, VEL_MAX, VEL_MIN } from "./catalogo.js";
import { SecuenciaLocal, ledsDeZona, zonaTermo } from "./automatismos.js";
import { Rearmador, trozos } from "./lineas.js";

const MAX_LINEA = 63;
const MAX_TOKENS = 6;
const numero = (s) => (s !== undefined && /^-?\d+$/.test(s) ? Number.parseInt(s, 10) : null);

export class PlacaSimulada {
  constructor() {
    this.leds = Object.fromEntries(COLORES.map((c) => [c, { modo: "OFF", brillo: 0, on: 0, off: 0, periodo: 0, t0: 0 }]));
    this.periodoDht = 2000;
    this.ultimoDht = 0;
    this.termoActivo = false;
    this.termo = [22, 28];
    this.zona = -1;
    this.seq = new SecuenciaLocal();
  }

  // Temperatura y humedad que «mide»: varían despacio, en enteros como el DHT11.
  lectura(ahora) {
    const s = ahora / 1000;
    return [Math.round(25 + 5 * Math.sin(s / 25)), Math.round(55 + 10 * Math.cos(s / 40))];
  }

  // Una línea de texto -> las líneas que responde.
  procesar(texto, ahora) {
    if (texto.length > MAX_LINEA) return ["ERR linea larga"];
    this._sincronizarSeq(ahora); // el sketch avanza la animación en cada vuelta de loop()
    const tok = texto.toUpperCase().split(/[ \t]+/).filter(Boolean).slice(0, MAX_TOKENS);
    if (tok.length === 0) return [];
    switch (tok[0]) {
      case "PING": return ["PONG OAC-LEDS 1"];
      case "LED": return this._led(tok, ahora);
      case "DHT": {
        const a = tok.length === 2 ? numero(tok[1]) : null;
        if (a === null || a < 1000 || a > 3600000) return ["ERR periodo 1000-3600000 ms"];
        this.periodoDht = a;
        return ["OK DHT"];
      }
      case "TERMO": return this._termo(tok);
      case "SEQ": return this._seq(tok, ahora);
      case "STATUS": return this._status(ahora);
      default: return ["ERR comando"];
    }
  }

  // Lo que hace leerSensor() del sketch: las líneas DATA que tocan en este instante.
  tick(ahora) {
    this._sincronizarSeq(ahora);
    if (ahora - this.ultimoDht < this.periodoDht) return [];
    this.ultimoDht = ahora;
    const [t, h] = this.lectura(ahora);
    if (this.termoActivo) this._evaluarTermo(t, ahora);
    return [`DATA T=${t.toFixed(1)} H=${h.toFixed(1)}`];
  }

  _apagarTodos() { for (const l of Object.values(this.leds)) l.modo = "OFF"; }

  _cancelarAutomatismos() {
    if (this.termoActivo || this.seq.activa) {
      this.termoActivo = false;
      this.zona = -1;
      this.seq.detener();
      this._apagarTodos();
    }
  }

  _led(tok, ahora) {
    if (tok.length < 3) return ["ERR faltan argumentos"];
    const l = tok[1].length === 1 ? this.leds[tok[1]] : undefined;
    if (!l) return [`ERR led ${COLORES.join(" ")}`];
    const n = tok.length;
    const brillo = numero(tok[3]);
    const brilloMal = brillo === null || brillo < 0 || brillo > 255;
    switch (tok[2]) {
      case "OFF":
        if (n !== 3) return ["ERR argumentos"];
        this._cancelarAutomatismos();
        l.modo = "OFF";
        break;
      case "ON":
        if (n !== 4) return ["ERR uso LED c ON brillo"];
        if (brilloMal) return ["ERR brillo 0-255"];
        this._cancelarAutomatismos();
        Object.assign(l, { modo: "ON", brillo });
        break;
      case "BLINK": {
        if (n !== 6) return ["ERR uso LED c BLINK brillo on off"];
        if (brilloMal) return ["ERR brillo 0-255"];
        const on = numero(tok[4]), off = numero(tok[5]);
        if (on === null || off === null || on < 20 || off < 20 || on > 60000 || off > 60000) return ["ERR tiempo 20-60000 ms"];
        this._cancelarAutomatismos();
        Object.assign(l, { modo: "BLINK", brillo, on, off, t0: ahora });
        break;
      }
      case "FADE": {
        if (n !== 5) return ["ERR uso LED c FADE brillo periodo"];
        if (brilloMal) return ["ERR brillo 0-255"];
        const periodo = numero(tok[4]);
        if (periodo === null || periodo < 200 || periodo > 60000) return ["ERR periodo 200-60000 ms"];
        this._cancelarAutomatismos();
        Object.assign(l, { modo: "FADE", brillo, periodo, t0: ahora });
        break;
      }
      default:
        return ["ERR modo"];
    }
    return [`OK LED ${tok[1]}`];
  }

  _termo(tok) {
    const a = numero(tok[1]), b = numero(tok[2]);
    if (tok.length === 2 && tok[1] === "OFF") {
      this.termoActivo = false;
    } else if (tok.length === 3 && a !== null && b !== null && a < b) {
      this.termo = [a, b];
      this.termoActivo = true;
    } else {
      return ["ERR uso TERMO tmin tmax (tmin<tmax) | TERMO OFF"];
    }
    this.zona = -1;
    this.seq.detener();
    this._apagarTodos();
    return ["OK TERMO"];
  }

  _seq(tok, ahora) {
    if (tok.length < 2 || tok.length > 3) return ["ERR uso SEQ nombre [vel] | OFF | PAUSA | SEGUIR"];
    const accion = tok[1];
    if (accion === "OFF") {
      if (this.seq.activa) {
        this.seq.detener();
        this._apagarTodos();
      }
      return ["OK SEQ"];
    }
    if (accion === "PAUSA" || accion === "SEGUIR") {
      if (!this.seq.activa) return ["ERR sin secuencia"];
      if (accion === "PAUSA") this.seq.pausar(ahora); else this.seq.seguir(ahora);
      return ["OK SEQ"];
    }
    if (!(accion in SECUENCIAS)) return [`ERR secuencia ${Object.keys(SECUENCIAS).join(" ")}`];
    let vel = 100;
    if (tok.length === 3) {
      vel = numero(tok[2]);
      if (vel === null || vel < VEL_MIN || vel > VEL_MAX) return ["ERR velocidad 25-400"];
    }
    this.termoActivo = false;
    this.zona = -1;
    this.seq.iniciar(accion, vel, ahora);
    this._sincronizarSeq(ahora); // como aplicarPasoSeq(): el primer paso se ve enseguida
    return ["OK SEQ"];
  }

  _sincronizarSeq(ahora) {
    const b = this.seq.brillos(ahora);
    if (b) for (const [c, v] of Object.entries(b)) Object.assign(this.leds[c], { modo: v ? "ON" : "OFF", brillo: v });
  }

  _status(ahora) {
    this._sincronizarSeq(ahora);
    const filas = Object.entries(this.leds).map(([c, l]) => `STATE ${c} ${l.modo} ${l.brillo} ${l.on} ${l.off} ${l.periodo}`);
    filas.push(this.seq.activa
      ? `STATE SEQ ${this.seq.nombre} ${this.seq.vel} ${this.seq.pausada ? "PAUSA" : "RUN"}`
      : "STATE SEQ OFF");
    return [...filas, "OK STATUS"];
  }

  _evaluarTermo(t, ahora) {
    const nueva = zonaTermo(t, this.zona, ...this.termo);
    if (nueva === this.zona) return;
    this.zona = nueva;
    for (const [c, cfg] of Object.entries(ledsDeZona(nueva))) {
      const l = this.leds[c];
      l.modo = cfg.modo;
      if (cfg.modo === "OFF") continue;
      l.brillo = cfg.brillo;
      if (cfg.modo === "BLINK") Object.assign(l, { on: cfg.on_ms, off: cfg.off_ms, t0: ahora });
    }
  }
}

// Transporte de mentira: misma interfaz que TransporteBle. Las respuestas pasan por los mismos trozos de
// 20 bytes y el mismo Rearmador que por Bluetooth, con un pequeño retraso.
export class TransporteDemo {
  constructor({ retardoMs = 40 } = {}) {
    this.nombre = "Placa de demostración";
    this.alLinea = () => {};
    this.alEstado = () => {};
    this.retardoMs = retardoMs;
    this.placa = null;
    this.reloj = null;
    this.t0 = 0;
    this.entrada = "";
  }

  get conectado() { return this.placa !== null; }

  ahora() { return Date.now() - this.t0; }

  async conectar() {
    this.alEstado("conectando");
    await new Promise((r) => setTimeout(r, 300));
    this.placa = new PlacaSimulada();
    this.t0 = Date.now();
    this.rearmador = new Rearmador((l) => this.alLinea(l));
    this.reloj = setInterval(() => this._notificar(this.placa.tick(this.ahora())), 100);
    this.alEstado("conectado");
  }

  async escribir(orden) {
    if (!this.placa) throw new Error("no hay conexión");
    for (const trozo of trozos(orden)) {
      this.entrada += new TextDecoder().decode(trozo);
      let i;
      while ((i = this.entrada.indexOf("\n")) >= 0) {
        const linea = this.entrada.slice(0, i).replace(/\r/g, "");
        this.entrada = this.entrada.slice(i + 1);
        const respuestas = this.placa.procesar(linea, this.ahora());
        setTimeout(() => this._notificar(respuestas), this.retardoMs);
      }
    }
  }

  _notificar(lineas) {
    if (!this.placa) return;
    for (const l of lineas) for (const t of trozos(l)) this.rearmador.agregar(t);
  }

  desconectar() {
    clearInterval(this.reloj);
    this.placa = null;
    this.entrada = "";
    this.alEstado("desconectado");
  }
}
