// Lo que la placa hace sola: animaciones (SEQ) y semáforo térmico (TERMO).
// Espejo de duinovisor/dominio/secuencias.py y termometro.py. Puro: tiempos en ms.
import { COLORES, HISTERESIS_TERMO, LUZ_DE_ZONA, MIN_PASO_MS, SECUENCIAS, VEL_MAX, VEL_MIN } from "./catalogo.js";
import { ledConfig } from "./protocolo.js";

export const duracionPaso = (ms, vel) => Math.max(MIN_PASO_MS, Math.floor((ms * 100) / vel));

// Copia local de la animación que corre en la placa.
export class SecuenciaLocal {
  constructor() {
    this.nombre = null;
    this.vel = 100;
    this.inicio = 0;
    this.congelado = null;
  }

  get activa() { return this.nombre !== null; }
  get pausada() { return this.activa && this.congelado !== null; }

  iniciar(nombre, vel, t) {
    if (!(nombre in SECUENCIAS)) throw new Error(`secuencia desconocida: ${nombre}`);
    if (vel < VEL_MIN || vel > VEL_MAX) throw new Error(`la velocidad debe estar entre ${VEL_MIN} y ${VEL_MAX} %`);
    Object.assign(this, { nombre, vel, inicio: t, congelado: null });
  }

  pausar(t) { if (this.activa && !this.pausada) this.congelado = t - this.inicio; }

  seguir(t) {
    if (this.pausada) {
      this.inicio = t - this.congelado;
      this.congelado = null;
    }
  }

  detener() {
    this.nombre = null;
    this.congelado = null;
  }

  paso(t) {
    const duraciones = SECUENCIAS[this.nombre].map(([ms]) => duracionPaso(ms, this.vel));
    const total = duraciones.reduce((a, b) => a + b, 0);
    const e = (this.congelado ?? t - this.inicio) % total;
    let acumulado = 0;
    for (let i = 0; i < duraciones.length; i++) {
      acumulado += duraciones[i];
      if (e < acumulado) return i;
    }
    return duraciones.length - 1;
  }

  // {LED: brillo} del paso actual, o null si no hay animación.
  brillos(t) {
    if (!this.activa) return null;
    const [, brillos] = SECUENCIAS[this.nombre][this.paso(t)];
    return Object.fromEntries(COLORES.map((c) => [c, brillos[c] ?? 0]));
  }
}

// Zona del semáforo térmico: 0 verde, 1 amarillo, 2 rojo intermitente. Subir es inmediato; bajar exige histéresis.
export function zonaTermo(t, zona, tmin, tmax, histeresis = HISTERESIS_TERMO) {
  const bruta = t < tmin ? 0 : t < tmax ? 1 : 2;
  if (zona < 0 || bruta > zona) return bruta;
  if (bruta < zona) {
    const umbral = zona === 2 ? tmax : tmin;
    if (t < umbral - histeresis) return bruta;
  }
  return zona;
}

// Configuración de cada LED en una zona del semáforo térmico.
export function ledsDeZona(zona) {
  const salida = Object.fromEntries(COLORES.map((c) => [c, ledConfig(c)]));
  const luz = LUZ_DE_ZONA[zona];
  if (luz) salida[luz.color] = ledConfig(luz.color, luz);
  return salida;
}
