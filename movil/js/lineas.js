// Texto <-> paquetes BLE. Puro: sin Bluetooth ni pantalla.
//   - trozos(): una orden pasa a bytes terminados en "\n", partidos en paquetes de 20 bytes.
//   - Rearmador: junta los paquetes que notifica la placa y entrega líneas completas.
import { BLE } from "./catalogo.js";

const codificador = new TextEncoder();

export function trozos(orden, max = BLE.trozo) {
  const bytes = codificador.encode(orden.replace(/[\r\n]+$/, "") + "\n");
  const salida = [];
  for (let i = 0; i < bytes.length; i += max) salida.push(bytes.slice(i, i + max));
  return salida;
}

export class Rearmador {
  constructor(alLinea, maximo = 256) {
    this.alLinea = alLinea;
    this.maximo = maximo; // por si llega basura sin "\n": no crecer sin límite
    this.resto = "";
    this.decodificador = new TextDecoder();
  }

  // Acepta un DataView, un ArrayBuffer, un Uint8Array o un texto.
  agregar(datos) {
    let texto;
    if (typeof datos === "string") texto = datos;
    else {
      const bytes = datos instanceof DataView
        ? new Uint8Array(datos.buffer, datos.byteOffset, datos.byteLength)
        : new Uint8Array(datos.buffer ?? datos, datos.byteOffset ?? 0, datos.byteLength);
      texto = this.decodificador.decode(bytes, { stream: true });
    }
    const partes = (this.resto + texto).split("\n");
    this.resto = partes.pop();
    if (this.resto.length > this.maximo) this.resto = "";
    for (const p of partes) {
      const linea = p.replace(/\r/g, "").trim();
      if (linea) this.alLinea(linea);
    }
  }

  vaciar() {
    this.resto = "";
    this.decodificador = new TextDecoder();
  }
}
