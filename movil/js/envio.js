// Envío con confirmación: una orden a la vez; cada una espera su OK / ERR (o PONG) antes de la siguiente,
// con un reintento si la placa no contesta. Como ui/controladores/envio.py del escritorio.
// Las órdenes con la misma `clave` (p. ej. la misma luz) que aún esperan turno se reemplazan por la más nueva:
// tocar rápido no llena la fila con órdenes que ya no importan.
// Puro: recibe la función que escribe y un temporizador, así se prueba sin Bluetooth.
import { interpretar } from "./protocolo.js";

const temporizadorReal = { poner: (f, ms) => setTimeout(f, ms), quitar: (id) => clearTimeout(id) };

// Qué texto de OK confirma cada orden: "LED R ON 9" -> "LED R"; "SEQ VIAL" -> "SEQ"; PING -> PONG.
export function confirmacionDe(orden) {
  const p = orden.trim().toUpperCase().split(/\s+/);
  if (p[0] === "PING") return null; // la confirma PONG
  return p[0] === "LED" ? `LED ${p[1] ?? ""}` : p[0];
}

export class ErrorEnvio extends Error {
  constructor(mensaje, codigo, orden) {
    super(mensaje);
    this.codigo = codigo; // "ERR" (la placa lo rechazó), "SIN_RESPUESTA", "ESCRITURA", "CANCELADO", "REEMPLAZADO"
    this.orden = orden;
  }
}

export class Envio {
  constructor(escribir, { esperaMs = 1500, reintentos = 1, temporizador = temporizadorReal, alPerder = () => {} } = {}) {
    this.escribir = escribir;
    this.alPerder = alPerder; // se llama con la orden cada vez que su respuesta no llega a tiempo
    this.perdidas = 0;
    this.esperaMs = esperaMs;
    this.reintentos = reintentos;
    this.temporizador = temporizador;
    this.cola = [];
    this.actual = null;
  }

  get ocupado() {
    return this.actual !== null || this.cola.length > 0;
  }

  // Devuelve una promesa con {respuesta, estados}; `estados` son las líneas STATE (para STATUS).
  // Si ya hay en la fila (sin enviar) una orden con la misma clave, la nueva ocupa su lugar y la vieja falla
  // con el código REEMPLAZADO.
  enviar(orden, { clave = null } = {}) {
    return new Promise((resolver, rechazar) => {
      const item = { orden, clave, resolver, rechazar, intentos: 0, estados: [], espera: null };
      const i = clave === null ? -1 : this.cola.findIndex((x) => x.clave === clave);
      if (i >= 0) {
        const viejo = this.cola[i];
        this.cola[i] = item;
        viejo.rechazar(new ErrorEnvio(`«${viejo.orden}» se reemplazó por «${orden}»`, "REEMPLAZADO", viejo.orden));
      } else {
        this.cola.push(item);
      }
      this._siguiente();
    });
  }

  // Cada línea que llega de la placa pasa por aquí. Devuelve true si era la respuesta esperada.
  recibir(linea) {
    const item = this.actual;
    if (!item) return false;
    const m = interpretar(linea);
    if (m.tipo === "STATE") {
      item.estados.push(m.texto);
      return true;
    }
    const esperado = confirmacionDe(item.orden);
    if ((m.tipo === "PONG" && esperado === null) || (m.tipo === "OK" && m.texto === esperado)) {
      this._terminar(item, () => item.resolver({ respuesta: m, estados: item.estados }));
      return true;
    }
    if (m.tipo === "ERR") {
      const error = new ErrorEnvio(`La placa no aceptó «${item.orden}»: ${m.texto}`, "ERR", item.orden);
      this._terminar(item, () => item.rechazar(error));
      return true;
    }
    return false;
  }

  // Al desconectarse: todo lo pendiente falla.
  cancelarTodo(motivo = "Se perdió la conexión") {
    const todos = [...(this.actual ? [this.actual] : []), ...this.cola];
    if (this.actual?.espera != null) this.temporizador.quitar(this.actual.espera);
    this.actual = null;
    this.cola = [];
    for (const item of todos) item.rechazar(new ErrorEnvio(motivo, "CANCELADO", item.orden));
  }

  _siguiente() {
    if (this.actual || this.cola.length === 0) return;
    this.actual = this.cola.shift();
    this._mandar(this.actual);
  }

  async _mandar(item) {
    item.estados = [];
    item.espera = this.temporizador.poner(() => this._sinRespuesta(item), this.esperaMs);
    try {
      await this.escribir(item.orden);
    } catch (e) {
      if (this.actual !== item) return;
      const error = new ErrorEnvio(`No se pudo enviar «${item.orden}»: ${e?.message ?? e}`, "ESCRITURA", item.orden);
      this._terminar(item, () => item.rechazar(error));
    }
  }

  _sinRespuesta(item) {
    if (this.actual !== item) return;
    item.espera = null;
    this.perdidas += 1;
    this.alPerder(item.orden);
    if (item.intentos < this.reintentos) {
      item.intentos += 1;
      this._mandar(item);
      return;
    }
    const error = new ErrorEnvio(`La placa no respondió a «${item.orden}».`, "SIN_RESPUESTA", item.orden);
    this._terminar(item, () => item.rechazar(error));
  }

  _terminar(item, avisar) {
    if (item.espera != null) this.temporizador.quitar(item.espera);
    item.espera = null;
    this.actual = null;
    avisar();
    this._siguiente();
  }
}
