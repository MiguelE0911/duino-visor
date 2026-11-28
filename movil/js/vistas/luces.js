// Pantalla «Luces»: una tarjeta por LED (interruptor, modo, brillo y ritmo) y la tarjeta «Todas a la vez»
// (encender o apagar todas y las animaciones). Solo crea y pinta elementos: lo que pasa al tocar lo decide
// app.js con las funciones puras de luces.js.
import { LEDS, NOMBRES_RITMO, NOMBRES_SEQ, SECUENCIAS, VEL_MAX, VEL_MIN, ledPorId } from "../catalogo.js";
import { conBrillo, conModo, conRitmo, estaEncendida } from "../luces.js";
import { porcentaje, resumenLed, ritmoDe } from "../protocolo.js";

const MODOS_EDITOR = [["ON", "Fija"], ["BLINK", "Parpadea"], ["FADE", "Respira"]];

const crear = (etiqueta, atributos = {}, ...hijos) => {
  const el = document.createElement(etiqueta);
  for (const [k, v] of Object.entries(atributos)) {
    if (k === "texto") el.textContent = v;
    else if (k === "clase") el.className = v;
    else el.setAttribute(k, v);
  }
  el.append(...hijos);
  return el;
};

function segmentado(etiqueta, opciones, alElegir) {
  const grupo = crear("div", { clase: "segmentado", role: "radiogroup", "aria-label": etiqueta });
  for (const [valor, texto] of opciones) {
    const b = crear("button", { type: "button", role: "radio", "aria-checked": "false", "data-valor": valor, texto });
    b.addEventListener("click", () => alElegir(valor));
    grupo.append(b);
  }
  return grupo;
}

function marcar(grupo, valor) {
  for (const b of grupo.querySelectorAll("[role=radio]")) b.setAttribute("aria-checked", String(b.dataset.valor === valor));
}

function textoVelocidad(vel) {
  return vel === 100 ? "Normal" : `${vel} %`;
}

function pintarVelocidad(barra, salida, vel) {
  barra.value = String(vel);
  salida.textContent = textoVelocidad(vel);
  barra.style.setProperty("--relleno", `${((vel - VEL_MIN) / (VEL_MAX - VEL_MIN)) * 100}%`);
}

// acciones: { cambiar(cfg), vistaPrevia(id, cfg|null), alternar(id), todas(encender),
//             animacion(nombre, vel), pausar(), seguir(), detener() }
// estado (en pintar): { cfg: {id: cfg}, enviando: {id: bool}, seq: {nombre, vel, pausada} | null }
export function crearVistaLuces(contenedor, acciones) {
  let estado = { cfg: {}, enviando: {}, seq: null };
  let arrastrando = null; // id del LED cuyo brillo se está moviendo (no se pisa con lo que llega de la placa)
  let velArrastrando = false;
  const tarjetas = {};

  // ---------- una tarjeta por LED, de arriba abajo como en el semáforo
  const lista = crear("ul", { clase: "lista-luces" });
  for (const led of [...LEDS].sort((a, b) => a.fila - b.fila)) {
    const id = led.id;
    const cfgDe = () => estado.cfg[id];
    const bombilla = crear("span", { clase: "bombilla", "aria-hidden": "true" });
    bombilla.style.setProperty("--color", led.color);
    const resumen = crear("span", { clase: "luz-resumen", texto: "—" });
    const abrir = crear("button", { type: "button", clase: "luz-abrir", "aria-expanded": "false", "aria-controls": `editor-${id}` },
      bombilla,
      crear("span", { clase: "luz-textos" }, crear("span", { clase: "luz-nombre", texto: led.luz }), resumen),
      crear("span", { clase: "chevron", "aria-hidden": "true" }));
    const interruptor = crear("button", { type: "button", clase: "interruptor", role: "switch", "aria-checked": "false",
      "aria-label": `Encender ${led.luz.toLowerCase()}` }, crear("span", { clase: "perilla" }));
    interruptor.style.setProperty("--color", led.color);
    interruptor.addEventListener("click", () => acciones.alternar(id));

    const modos = segmentado("Modo", MODOS_EDITOR, (modo) => acciones.cambiar(conModo(cfgDe(), modo)));
    const salidaBrillo = crear("output", { for: `brillo-${id}`, texto: "—" });
    const brillo = crear("input", { type: "range", id: `brillo-${id}`, min: "1", max: "255", step: "1", value: "255" });
    brillo.style.setProperty("--color", led.color);
    brillo.addEventListener("input", () => {
      arrastrando = id;
      const cfg = conBrillo(cfgDe(), Number(brillo.value));
      salidaBrillo.textContent = `${porcentaje(cfg.brillo)} %`;
      brillo.style.setProperty("--relleno", `${(cfg.brillo / 255) * 100}%`);
      acciones.vistaPrevia(id, cfg);
    });
    brillo.addEventListener("change", () => {
      arrastrando = null;
      acciones.vistaPrevia(id, null);
      acciones.cambiar(conBrillo(cfgDe(), Number(brillo.value)));
    });
    const ritmos = segmentado("Ritmo", Object.entries(NOMBRES_RITMO), (r) => acciones.cambiar(conRitmo(cfgDe(), r)));
    const campoRitmo = crear("div", { clase: "campo" }, crear("span", { clase: "campo-titulo", texto: "Ritmo" }), ritmos);
    const avisoSeq = crear("p", { clase: "nota", texto: "Si la cambias, se detiene la animación." });

    const editor = crear("div", { clase: "luz-editor", id: `editor-${id}`, hidden: "" },
      crear("div", { clase: "campo" }, crear("span", { clase: "campo-titulo", texto: "Modo" }), modos),
      crear("div", { clase: "campo" },
        crear("label", { clase: "campo-titulo", for: `brillo-${id}` }, "Brillo ", salidaBrillo), brillo),
      campoRitmo, avisoSeq);
    abrir.addEventListener("click", () => {
      const abrirla = editor.hidden;
      for (const t of Object.values(tarjetas)) { t.editor.hidden = true; t.abrir.setAttribute("aria-expanded", "false"); }
      editor.hidden = !abrirla;
      abrir.setAttribute("aria-expanded", String(abrirla));
    });

    const li = crear("li", { clase: "tarjeta luz", "data-id": id },
      crear("div", { clase: "luz-cabecera" }, abrir, interruptor), editor);
    lista.append(li);
    tarjetas[id] = { li, bombilla, resumen, abrir, interruptor, modos, brillo, salidaBrillo, ritmos, campoRitmo, avisoSeq, editor };
  }

  // ---------- todas a la vez
  const btnTodasOn = crear("button", { type: "button", clase: "boton boton-secundario", texto: "Encender todas" });
  const btnTodasOff = crear("button", { type: "button", clase: "boton boton-secundario", texto: "Apagar todas" });
  btnTodasOn.addEventListener("click", () => acciones.todas(true));
  btnTodasOff.addEventListener("click", () => acciones.todas(false));

  const velocidad = crear("input", { type: "range", id: "velocidad", min: String(VEL_MIN), max: String(VEL_MAX), step: "25", value: "100" });
  const salidaVel = crear("output", { for: "velocidad", texto: "Normal" });
  pintarVelocidad(velocidad, salidaVel, 100);
  velocidad.addEventListener("input", () => {
    velArrastrando = true;
    pintarVelocidad(velocidad, salidaVel, Number(velocidad.value));
  });
  velocidad.addEventListener("change", () => {
    velArrastrando = false;
    if (estado.seq) acciones.animacion(estado.seq.nombre, Number(velocidad.value));
  });

  const botonesSeq = {};
  const grupoSeq = crear("div", { clase: "animaciones" });
  for (const nombre of Object.keys(SECUENCIAS)) {
    const usados = [...new Set(SECUENCIAS[nombre].flatMap(([, b]) => Object.keys(b)))];
    const puntos = crear("span", { clase: "puntos", "aria-hidden": "true" },
      ...usados.map((c) => { const p = crear("span"); p.style.background = ledPorId(c)?.color ?? "#888"; return p; }));
    const b = crear("button", { type: "button", clase: "animacion", "aria-pressed": "false" }, puntos,
      crear("span", { texto: NOMBRES_SEQ[nombre] ?? nombre }));
    b.addEventListener("click", () => acciones.animacion(nombre, Number(velocidad.value)));
    botonesSeq[nombre] = b;
    grupoSeq.append(b);
  }
  const btnPausa = crear("button", { type: "button", clase: "boton boton-secundario", texto: "Pausar" });
  const btnDetener = crear("button", { type: "button", clase: "boton boton-secundario", texto: "Detener" });
  btnPausa.addEventListener("click", () => (estado.seq?.pausada ? acciones.seguir() : acciones.pausar()));
  btnDetener.addEventListener("click", () => acciones.detener());
  const controlesSeq = crear("div", { clase: "fila-botones" }, btnPausa, btnDetener);

  const conjunto = crear("section", { clase: "tarjeta conjunto", "aria-labelledby": "titulo-conjunto" },
    crear("h3", { id: "titulo-conjunto", texto: "Todas a la vez" }),
    crear("div", { clase: "fila-botones" }, btnTodasOn, btnTodasOff),
    crear("h4", { texto: "Animaciones" }),
    grupoSeq,
    crear("div", { clase: "campo" },
      crear("label", { clase: "campo-titulo", for: "velocidad" }, "Velocidad ", salidaVel),
      velocidad,
      crear("div", { clase: "extremos", "aria-hidden": "true" }, crear("span", { texto: "Más lenta" }), crear("span", { texto: "Más rápida" }))),
    controlesSeq);

  contenedor.append(lista, conjunto);

  return {
    pintar(nuevo) {
      estado = nuevo;
      const seq = estado.seq;
      for (const [id, t] of Object.entries(tarjetas)) {
        const cfg = estado.cfg[id];
        if (!cfg) continue;
        const on = estaEncendida(cfg);
        t.interruptor.setAttribute("aria-checked", String(on));
        t.interruptor.setAttribute("aria-label", `${on ? "Apagar" : "Encender"} ${ledPorId(id).luz.toLowerCase()}`);
        t.resumen.textContent = estado.enviando[id] ? "Enviando…" : seq ? "La controla la animación" : resumenLed(cfg);
        t.li.classList.toggle("enviando", Boolean(estado.enviando[id]));
        marcar(t.modos, seq || !on ? "" : cfg.modo);
        if (arrastrando !== id) {
          t.brillo.value = String(Math.max(1, cfg.brillo));
          t.salidaBrillo.textContent = `${porcentaje(cfg.brillo)} %`;
          t.brillo.style.setProperty("--relleno", `${(Math.max(1, cfg.brillo) / 255) * 100}%`);
        }
        t.campoRitmo.hidden = !(cfg.modo === "BLINK" || cfg.modo === "FADE");
        marcar(t.ritmos, ritmoDe(cfg));
        t.avisoSeq.hidden = !seq;
      }
      for (const [nombre, b] of Object.entries(botonesSeq)) b.setAttribute("aria-pressed", String(seq?.nombre === nombre));
      if (seq && !velArrastrando) pintarVelocidad(velocidad, salidaVel, seq.vel);
      controlesSeq.hidden = !seq;
      btnPausa.textContent = seq?.pausada ? "Seguir" : "Pausar";
    },

    // niveles: {id: 0..1} del brillo de cada bombilla en este instante
    animar(niveles) {
      for (const [id, t] of Object.entries(tarjetas)) t.bombilla.style.setProperty("--nivel", (niveles[id] ?? 0).toFixed(3));
    },
  };
}
