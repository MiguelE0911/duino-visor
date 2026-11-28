// Puente para las pruebas de Python (tests/firmware/):
//   node puente.js catalogo    imprime el catálogo de la app en JSON
//   node puente.js responder   lee órdenes por stdin y escribe las respuestas de la placa simulada ("< línea")
import * as catalogo from "../../js/catalogo.js";
import { PlacaSimulada } from "../../js/simulador.js";

const modo = process.argv[2];
if (modo === "catalogo") {
  const { ledPorId, ...datos } = catalogo;
  process.stdout.write(JSON.stringify(datos));
} else if (modo === "responder") {
  let entrada = "";
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (d) => { entrada += d; });
  process.stdin.on("end", () => {
    const placa = new PlacaSimulada();
    const salida = [];
    for (const orden of entrada.split(/\r?\n/)) {
      if (orden) for (const r of placa.procesar(orden, 0)) salida.push(`< ${r}`);
    }
    process.stdout.write(salida.join("\n") + "\n");
  });
} else {
  process.stderr.write("uso: node puente.js catalogo | responder\n");
  process.exit(2);
}
