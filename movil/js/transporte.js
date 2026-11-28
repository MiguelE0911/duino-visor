// Conexión con la placa por Web Bluetooth. Es el ÚNICO módulo que toca Bluetooth: si algún día se hace una
// app nativa (p. ej. con Capacitor), solo hay que cambiar este archivo.
//
// Interfaz (la misma que TransporteDemo en simulador.js):
//   t.alLinea = (linea) => {}            cada línea completa que envía la placa
//   t.alEstado = (estado, detalle) => {}  "buscando" | "conectando" | "conectado" | "reconectando" | "desconectado"
//   await t.conectar()                    abre el selector de dispositivos (debe llamarse desde un toque)
//   await t.escribir(orden)               envía una orden (sin "\n"; se añade aquí)
//   t.desconectar()
//   t.conectado, t.nombre
import { BLE } from "./catalogo.js";
import { Rearmador, trozos } from "./lineas.js";

const ESPERAS_RECONEXION_MS = [1000, 2000, 4000, 8000, 15000]; // la última se repite

// Por qué no se puede usar Bluetooth aquí, o null si se puede.
export function motivoSinBluetooth() {
  if (typeof window !== "undefined" && !window.isSecureContext) {
    return "Esta página debe abrirse desde una dirección segura (https:// o localhost) para usar Bluetooth.";
  }
  if (typeof navigator === "undefined" || !navigator.bluetooth) {
    return "Este navegador no puede usar Bluetooth. Ábrela en Chrome o Edge (Android o PC). En iPhone, usa el navegador Bluefy.";
  }
  return null;
}

// Traduce un error de Web Bluetooth a algo que se entienda y se pueda arreglar.
// Devuelve null si el usuario solo cerró la lista sin elegir. Ojo: Chrome usa NotFoundError tanto para eso como
// para «Bluetooth apagado» o «sin permiso», así que hay que mirar el mensaje.
export function explicarErrorBluetooth(e) {
  const nombre = e?.name ?? "Error";
  const texto = String(e?.message ?? e ?? "");
  const detalle = `${nombre}: ${texto}`;
  const es = (re) => re.test(texto);
  if (nombre === "NotFoundError" && es(/cancel/i)) return null;
  let mensaje;
  if (es(/gesture/i)) {
    mensaje = "El navegador no abrió la búsqueda. Toca «Buscar placa» otra vez.";
  } else if (es(/adapter|not available|unavailable|powered|turned off/i) && !es(/location/i)) {
    mensaje = "El Bluetooth del celular está apagado o no está disponible. Enciéndelo y vuelve a tocar «Buscar placa».";
  } else if (es(/location/i)) {
    mensaje = "Android pide tener la Ubicación encendida para buscar dispositivos Bluetooth. Actívala y vuelve a intentar.";
  } else if (nombre === "NotAllowedError" || nombre === "SecurityError" || es(/permission|blocked|denied/i)) {
    mensaje = "Chrome no tiene permiso para usar Bluetooth. En Ajustes → Aplicaciones → Chrome → Permisos, permite "
      + "«Dispositivos cercanos» (y «Ubicación» si aparece). Después recarga esta página.";
  } else if (es(/globally disabled|disabled/i)) {
    mensaje = "Este navegador tiene el Bluetooth desactivado. Prueba con Chrome actualizado.";
  } else {
    mensaje = "No se pudo abrir la búsqueda de Bluetooth.";
  }
  const error = new Error(mensaje);
  error.detalle = detalle;
  return error;
}

export class TransporteBle {
  constructor() {
    this.alLinea = () => {};
    this.alEstado = () => {};
    this.dispositivo = null;
    this.rx = null;
    this.tx = null;
    this.manual = false; // true si la desconexión la pidió el usuario: no reconectar
    this.intento = 0;
    this.temporizador = null;
    this.colaEscritura = Promise.resolve();
    this.rearmador = new Rearmador((l) => this.alLinea(l));
    this._alDesconectarse = () => this._perdida();
    this._alNotificar = (e) => this.rearmador.agregar(e.target.value);
  }

  get conectado() { return this.rx !== null; }
  get nombre() { return this.dispositivo?.name || BLE.nombre; }

  async conectar() {
    const motivo = motivoSinBluetooth();
    if (motivo) throw new Error(motivo);
    this.manual = false;
    this.alEstado("buscando");
    let dispositivo;
    try {
      dispositivo = await navigator.bluetooth.requestDevice({
        filters: [{ name: BLE.nombre }, { services: [BLE.servicio] }],
        optionalServices: [BLE.servicio],
      });
    } catch (e) {
      this.alEstado("desconectado");
      const explicado = explicarErrorBluetooth(e);
      if (explicado === null) return false; // el usuario cerró la lista sin elegir
      throw explicado;
    }
    if (this.dispositivo && this.dispositivo !== dispositivo) this._soltar();
    this.dispositivo = dispositivo;
    dispositivo.addEventListener("gattserverdisconnected", this._alDesconectarse);
    this.alEstado("conectando");
    try {
      await this._abrir();
    } catch (e) {
      this._limpiarConexion();
      this.alEstado("desconectado");
      const error = new Error(`Se encontró ${this.nombre}, pero no se pudo conectar. Acerca el celular a la placa y vuelve a intentar.`);
      error.detalle = `${e?.name ?? "Error"}: ${e?.message ?? e}`;
      throw error;
    }
    return true;
  }

  async _abrir() {
    const servidor = await this.dispositivo.gatt.connect();
    const servicio = await servidor.getPrimaryService(BLE.servicio);
    const rx = await servicio.getCharacteristic(BLE.rx);
    const tx = await servicio.getCharacteristic(BLE.tx);
    this.rearmador.vaciar();
    tx.addEventListener("characteristicvaluechanged", this._alNotificar);
    await tx.startNotifications();
    this.tx = tx;
    this.rx = rx;
    this.intento = 0;
    this.colaEscritura = Promise.resolve();
    this.alEstado("conectado");
  }

  // Las escrituras van de una en una (Web Bluetooth no admite dos a la vez), en trozos de 20 bytes.
  escribir(orden) {
    const tarea = this.colaEscritura.then(async () => {
      if (!this.rx) throw new Error("no hay conexión");
      for (const trozo of trozos(orden)) {
        if (this.rx.writeValueWithResponse) await this.rx.writeValueWithResponse(trozo);
        else await this.rx.writeValue(trozo);
      }
    });
    this.colaEscritura = tarea.catch(() => {});
    return tarea;
  }

  desconectar() {
    this.manual = true;
    clearTimeout(this.temporizador);
    if (this.dispositivo?.gatt?.connected) this.dispositivo.gatt.disconnect(); // dispara _perdida()
    else {
      this._limpiarConexion();
      this.alEstado("desconectado");
    }
  }

  _perdida() {
    this._limpiarConexion();
    if (this.manual || !this.dispositivo) {
      this.alEstado("desconectado");
      return;
    }
    this._reintentar();
  }

  _reintentar() {
    const espera = ESPERAS_RECONEXION_MS[Math.min(this.intento, ESPERAS_RECONEXION_MS.length - 1)];
    this.intento += 1;
    this.alEstado("reconectando", { intento: this.intento, esperaMs: espera });
    clearTimeout(this.temporizador);
    this.temporizador = setTimeout(async () => {
      if (this.manual) return;
      try {
        await this._abrir();
      } catch {
        this._limpiarConexion();
        if (!this.manual) this._reintentar();
      }
    }, espera);
  }

  _limpiarConexion() {
    if (this.tx) this.tx.removeEventListener("characteristicvaluechanged", this._alNotificar);
    this.tx = null;
    this.rx = null;
  }

  _soltar() {
    this.dispositivo?.removeEventListener("gattserverdisconnected", this._alDesconectarse);
    this.dispositivo = null;
  }
}
