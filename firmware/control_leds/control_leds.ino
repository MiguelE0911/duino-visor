/*
 * control_leds.ino  -  DuinoVisor
 *
 * 3 LEDs con PWM (pines 3, 5, 6, tabla `leds[]`) + sensor DHT11 (pin 2).
 * Placa: Arduino 101 (en la 101 solo 3, 5, 6 y 9 tienen PWM; en un UNO también valen).
 * Protocolo de texto, una orden por línea, por dos canales a la vez:
 *   - puerto serie a 9600 baudios (programa de escritorio);
 *   - Bluetooth LE, solo en el 101 (aplicación del celular): servicio con los UUID del
 *     «Nordic UART Service»; el celular escribe las órdenes en RX y recibe las respuestas
 *     por notificaciones de TX, en trozos de hasta 20 bytes. Cada línea termina en '\n'.
 * Las órdenes y respuestas son idénticas por ambos canales. Cada orden se responde por el
 * canal que la envió; las lecturas del sensor (DATA) salen por los dos.
 * NUNCA se usa delay(): todo se planifica con millis().
 *
 * Librerías (Gestor de librerías del IDE):
 *   - DHT sensor library (Adafruit)
 *   - Adafruit Unified Sensor
 *   - CurieBLE (viene con el paquete de placas «Intel Curie Boards»)
 */
#include <Arduino.h>
#include <DHT.h>

#if defined(ARDUINO_ARCH_ARC32)      // Arduino 101: tiene Bluetooth LE
#define CON_BLE
#include <CurieBLE.h>
#endif

#define PIN_DHT      2
#define MAX_LINEA    63      // más largo que esto se descarta
#define MAX_TOKENS   6
#define HISTERESIS   1.0f    // grados que hay que bajar para cambiar de zona (TERMO)

DHT dht(PIN_DHT, DHT11);

enum Modo : uint8_t { M_OFF, M_ON, M_BLINK, M_FADE };

struct Led {
  char          id;           // 'R', 'G' o 'Y'
  uint8_t       pin;          // pin con PWM
  Modo          modo;
  uint8_t       brillo;       // 0-255
  uint16_t      onMs;         // BLINK
  uint16_t      offMs;        // BLINK
  uint16_t      periodo;      // FADE
  uint32_t ultimoCambio; // BLINK: último cambio de fase; FADE: inicio del ciclo
  bool          fase;         // BLINK: true = encendido
  int16_t       pwm;          // último valor escrito (-1 = ninguno)
};

// La lista de LEDs. Agregar uno es añadir una línea aquí (en un pin con PWM) y su entrada en
// LEDS de duinovisor/dominio/placa.py, en el mismo orden. Las secuencias que no lo nombran lo dejan apagado.
Led leds[] = {
  { 'R',  3, M_OFF, 0, 0, 0, 0, 0, false, -1 },
  { 'G',  5, M_OFF, 0, 0, 0, 0, 0, false, -1 },
  { 'Y',  6, M_OFF, 0, 0, 0, 0, 0, false, -1 },
};
#define LARGO(tabla) (sizeof(tabla) / sizeof((tabla)[0]))
const uint8_t N_LEDS = LARGO(leds);

// ---- estado del sensor y del semáforo térmico ----
uint32_t periodoDht  = 2000;
uint32_t ultimoDht   = 0;
bool          termoActivo = false;
float         termoMin = 22, termoMax = 28;
int8_t        zona = -1;           // 0 verde, 1 amarillo, 2 rojo intermitente

// Semáforo térmico: qué LED se enciende en cada zona (0 fresco, 1 templado, 2 calor); el resto se apaga.
// Misma tabla que LUZ_DE_ZONA en duinovisor/dominio/termometro.py.
struct DefZona { char led; Modo modo; };
const DefZona ZONAS_TERMO[] = { {'G', M_ON}, {'Y', M_ON}, {'R', M_BLINK} };

// ---- secuencias (SEQ): la app tiene la misma tabla para espejarlas ----
// Cada paso fija el brillo de cada LED durante `ms` milisegundos. Las columnas de `brillo` siguen el
// orden de leds[] (aquí R, G, Y); las que falten valen 0, así que un LED nuevo queda apagado.
struct PasoSeq { uint8_t brillo[N_LEDS]; uint16_t ms; };
const PasoSeq SEQ_VIAL[]    = { {{0, 255, 0}, 5000}, {{0, 0, 255}, 1500}, {{255, 0, 0}, 5000} };
const PasoSeq SEQ_FANT[]    = { {{255, 0, 0}, 150}, {{0, 0, 255}, 150}, {{0, 255, 0}, 150}, {{0, 0, 255}, 150} };
const PasoSeq SEQ_ALERTA[]  = { {{0, 0, 255}, 500}, {{0, 0, 0}, 500} };
struct DefSeq { const char *nombre; const PasoSeq *pasos; uint8_t n; };
const DefSeq SECUENCIAS[] = {
  { "VIAL",       SEQ_VIAL,   LARGO(SEQ_VIAL) },
  { "FANTASTICO", SEQ_FANT,   LARGO(SEQ_FANT) },
  { "ALERTA",     SEQ_ALERTA, LARGO(SEQ_ALERTA) },
};
const uint8_t N_SECUENCIAS = LARGO(SECUENCIAS);
const DefSeq *seqDef = NULL;        // NULL = ninguna secuencia activa
uint8_t  seqPaso = 0;
uint16_t seqVel = 100;              // % de velocidad (25-400)
bool     seqPausa = false;
uint32_t seqInicioPaso = 0;
uint32_t seqRestante = 0;           // ms que le faltaban al paso al pausar

// ---- búferes de entrada: uno por canal, para no mezclar órdenes a medias ----
struct Entrada {
  char    linea[MAX_LINEA + 1];
  uint8_t largo;
  bool    desbordada;
};
Entrada entradaSerie = { {0}, 0, false };

// ======================================================================
// Utilidades
// ======================================================================
bool numero(const char *s, long &out) {
  if (s == NULL || *s == '\0') return false;
  const char *p = s;
  if (*p == '-') p++;
  if (*p == '\0') return false;
  for (const char *q = p; *q; q++) if (*q < '0' || *q > '9') return false;
  out = atol(s);
  return true;
}

Led *ledPorId(char id) {
  for (uint8_t i = 0; i < N_LEDS; i++) if (leds[i].id == id) return &leds[i];
  return NULL;
}

Led *buscarLed(const char *s) {
  if (s == NULL || s[0] == '\0' || s[1] != '\0') return NULL;
  return ledPorId(s[0]);
}

const char *nombreModo(Modo m) {
  switch (m) {
    case M_ON:    return "ON";
    case M_BLINK: return "BLINK";
    case M_FADE:  return "FADE";
    default:      return "OFF";
  }
}

void apagarTodos() {
  for (uint8_t i = 0; i < N_LEDS; i++) leds[i].modo = M_OFF;
}

// Una orden manual de LED cancela el semáforo térmico y las secuencias y deja
// todo apagado, para que no queden LEDs encendidos por detrás.
void cancelarAutomatismos() {
  if (termoActivo || seqDef != NULL) {
    termoActivo = false; zona = -1;
    seqDef = NULL; seqPausa = false;
    apagarTodos();
  }
}

// ======================================================================
// Semáforo térmico: el Arduino decide, así funciona aunque la app se cierre
// ======================================================================
void aplicarZona(int8_t z, uint32_t ahora) {
  apagarTodos();
  if (z < 0 || z >= (int8_t)LARGO(ZONAS_TERMO)) return;
  Led *l = ledPorId(ZONAS_TERMO[z].led);
  if (l == NULL) return;
  l->modo = ZONAS_TERMO[z].modo;
  l->brillo = 255;
  if (l->modo == M_BLINK) {                                  // intermitente: 250 ms y 250 ms
    l->onMs = 250; l->offMs = 250;
    l->fase = true; l->ultimoCambio = ahora;
  }
}

void evaluarTermo(float t, uint32_t ahora) {
  int8_t bruta = (t < termoMin) ? 0 : (t < termoMax ? 1 : 2);
  int8_t nueva = zona;
  if (zona < 0 || bruta > zona) {
    nueva = bruta;                       // subir de zona es inmediato
  } else if (bruta < zona) {
    float umbral = (zona == 2) ? termoMax : termoMin;
    if (t < umbral - HISTERESIS) nueva = bruta;   // bajar exige histéresis
  }
  if (nueva != zona) {
    zona = nueva;
    aplicarZona(zona, ahora);
  }
}

// ======================================================================
// Secuencias
// ======================================================================
void fijarLed(Led &l, uint8_t b) {
  l.modo = b ? M_ON : M_OFF;
  l.brillo = b;
}

uint32_t durPaso() {
  uint32_t d = (uint32_t)seqDef->pasos[seqPaso].ms * 100UL / seqVel;
  return d < 20 ? 20 : d;
}

void aplicarPasoSeq() {
  const PasoSeq &p = seqDef->pasos[seqPaso];
  for (uint8_t i = 0; i < N_LEDS; i++) fijarLed(leds[i], p.brillo[i]);
}

void actualizarSecuencia(uint32_t ahora) {
  if (seqDef == NULL || seqPausa) return;
  uint32_t dur = durPaso();
  bool cambio = false;
  while (ahora - seqInicioPaso >= dur) {     // los pasos caen en sumas exactas: no se acumula error
    seqInicioPaso += dur;
    seqPaso = (seqPaso + 1) % seqDef->n;
    dur = durPaso();
    cambio = true;
  }
  if (cambio) aplicarPasoSeq();
}

void ordenSeq(char **tok, uint8_t n, uint32_t ahora, Print &out) {
  if (n < 2 || n > 3) { out.println("ERR uso SEQ nombre [vel] | OFF | PAUSA | SEGUIR"); return; }
  if (strcmp(tok[1], "OFF") == 0) {
    if (seqDef != NULL) { seqDef = NULL; seqPausa = false; apagarTodos(); }
    out.println("OK SEQ");
  } else if (strcmp(tok[1], "PAUSA") == 0) {
    if (seqDef == NULL) { out.println("ERR sin secuencia"); return; }
    if (!seqPausa) {
      uint32_t dur = durPaso(), t = ahora - seqInicioPaso;
      seqRestante = (t >= dur) ? 0 : dur - t;
      seqPausa = true;
    }
    out.println("OK SEQ");
  } else if (strcmp(tok[1], "SEGUIR") == 0) {
    if (seqDef == NULL) { out.println("ERR sin secuencia"); return; }
    if (seqPausa) {
      seqInicioPaso = ahora - (durPaso() - seqRestante);
      seqPausa = false;
    }
    out.println("OK SEQ");
  } else {
    const DefSeq *def = NULL;
    for (uint8_t i = 0; i < N_SECUENCIAS; i++) if (strcmp(tok[1], SECUENCIAS[i].nombre) == 0) def = &SECUENCIAS[i];
    if (def == NULL) {                                       // ERR secuencia VIAL FANTASTICO ALERTA
      out.print("ERR secuencia");
      for (uint8_t i = 0; i < N_SECUENCIAS; i++) { out.print(' '); out.print(SECUENCIAS[i].nombre); }
      out.println();
      return;
    }
    long vel = 100;
    if (n == 3 && (!numero(tok[2], vel) || vel < 25 || vel > 400)) { out.println("ERR velocidad 25-400"); return; }
    termoActivo = false; zona = -1;
    seqDef = def; seqPaso = 0; seqVel = (uint16_t)vel; seqPausa = false; seqInicioPaso = ahora;
    aplicarPasoSeq();
    out.println("OK SEQ");
  }
}

// ======================================================================
// Procesamiento de órdenes
// ======================================================================
// Ejecuta una orden y responde por `out`, el canal que la envió (serie o BLE).
void procesarComando(char *texto, Print &out) {
  for (char *c = texto; *c; c++) if (*c >= 'a' && *c <= 'z') *c -= 32;   // a mayúsculas

  char *tok[MAX_TOKENS];
  uint8_t n = 0;
  for (char *p = strtok(texto, " \t"); p != NULL && n < MAX_TOKENS; p = strtok(NULL, " \t")) tok[n++] = p;
  if (n == 0) return;                                    // línea vacía: se ignora

  uint32_t ahora = millis();
  long a, b, c;

  if (strcmp(tok[0], "PING") == 0) {
    out.println("PONG OAC-LEDS 1");

  } else if (strcmp(tok[0], "LED") == 0) {
    if (n < 3)                      { out.println("ERR faltan argumentos"); return; }
    Led *l = buscarLed(tok[1]);
    if (l == NULL) {                                         // ERR led R G Y
      out.print("ERR led");
      for (uint8_t i = 0; i < N_LEDS; i++) { out.print(' '); out.print(leds[i].id); }
      out.println();
      return;
    }

    if (strcmp(tok[2], "OFF") == 0) {
      if (n != 3)                   { out.println("ERR argumentos"); return; }
      cancelarAutomatismos();
      l->modo = M_OFF;

    } else if (strcmp(tok[2], "ON") == 0) {
      if (n != 4)                   { out.println("ERR uso LED c ON brillo"); return; }
      if (!numero(tok[3], a) || a < 0 || a > 255) { out.println("ERR brillo 0-255"); return; }
      cancelarAutomatismos();
      l->modo = M_ON; l->brillo = (uint8_t)a;

    } else if (strcmp(tok[2], "BLINK") == 0) {
      if (n != 6)                   { out.println("ERR uso LED c BLINK brillo on off"); return; }
      if (!numero(tok[3], a) || a < 0 || a > 255) { out.println("ERR brillo 0-255"); return; }
      if (!numero(tok[4], b) || !numero(tok[5], c) || b < 20 || c < 20 || b > 60000 || c > 60000) {
        out.println("ERR tiempo 20-60000 ms"); return;
      }
      cancelarAutomatismos();
      l->modo = M_BLINK; l->brillo = (uint8_t)a;
      l->onMs = (uint16_t)b; l->offMs = (uint16_t)c;
      l->fase = true; l->ultimoCambio = ahora;

    } else if (strcmp(tok[2], "FADE") == 0) {
      if (n != 5)                   { out.println("ERR uso LED c FADE brillo periodo"); return; }
      if (!numero(tok[3], a) || a < 0 || a > 255) { out.println("ERR brillo 0-255"); return; }
      if (!numero(tok[4], b) || b < 200 || b > 60000) { out.println("ERR periodo 200-60000 ms"); return; }
      cancelarAutomatismos();
      l->modo = M_FADE; l->brillo = (uint8_t)a;
      l->periodo = (uint16_t)b; l->ultimoCambio = ahora;

    } else {
      out.println("ERR modo"); return;
    }
    out.print("OK LED "); out.println(l->id);

  } else if (strcmp(tok[0], "DHT") == 0) {
    if (n != 2 || !numero(tok[1], a) || a < 1000 || a > 3600000L) {
      out.println("ERR periodo 1000-3600000 ms"); return;     // 1000 ms: límite del DHT11
    }
    periodoDht = (uint32_t)a;
    out.println("OK DHT");

  } else if (strcmp(tok[0], "TERMO") == 0) {
    if (n == 2 && strcmp(tok[1], "OFF") == 0) {
      termoActivo = false; zona = -1; seqDef = NULL; seqPausa = false; apagarTodos();
      out.println("OK TERMO");
    } else if (n == 3 && numero(tok[1], a) && numero(tok[2], b) && a < b) {
      termoMin = (float)a; termoMax = (float)b;
      termoActivo = true; zona = -1; seqDef = NULL; seqPausa = false; apagarTodos();   // se enciende con la próxima lectura
      out.println("OK TERMO");
    } else {
      out.println("ERR uso TERMO tmin tmax (tmin<tmax) | TERMO OFF");
    }

  } else if (strcmp(tok[0], "SEQ") == 0) {
    ordenSeq(tok, n, ahora, out);

  } else if (strcmp(tok[0], "STATUS") == 0) {
    for (uint8_t i = 0; i < N_LEDS; i++) {
      out.print("STATE "); out.print(leds[i].id); out.print(' ');
      out.print(nombreModo(leds[i].modo)); out.print(' ');
      out.print(leds[i].brillo); out.print(' ');
      out.print(leds[i].onMs); out.print(' ');
      out.print(leds[i].offMs); out.print(' ');
      out.println(leds[i].periodo);
    }
    if (seqDef == NULL) {
      out.println("STATE SEQ OFF");
    } else {
      out.print("STATE SEQ "); out.print(seqDef->nombre); out.print(' ');
      out.print(seqVel); out.print(' '); out.println(seqPausa ? "PAUSA" : "RUN");
    }
    out.println("OK STATUS");

  } else {
    out.println("ERR comando");
  }
}

// ======================================================================
// Entrada de texto: junta caracteres hasta '\n' (igual para serie y BLE)
// ======================================================================
void recibirCaracter(Entrada &e, char c, Print &canal) {
  if (c == '\r') return;
  if (c == '\n') {
    if (e.desbordada) {
      canal.println("ERR linea larga");
    } else {
      e.linea[e.largo] = '\0';
      procesarComando(e.linea, canal);
    }
    e.largo = 0; e.desbordada = false;
  } else if (e.largo < MAX_LINEA) {
    e.linea[e.largo++] = c;
  } else {
    e.desbordada = true;            // se descarta hasta el salto de línea
  }
}

// ======================================================================
// Bluetooth LE (solo Arduino 101)
// ======================================================================
#ifdef CON_BLE
// UUID del «Nordic UART Service»: muchas apps de prueba (nRF Connect, Serial Bluetooth Terminal)
// lo reconocen como un puerto serie, así se puede probar la placa sin la app de DuinoVisor.
#define NOMBRE_BLE    "DuinoVisor"
#define UUID_SERVICIO "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
#define UUID_RX       "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"   // el celular escribe órdenes
#define UUID_TX       "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"   // la placa notifica respuestas
#define BLE_TROZO     20       // bytes por paquete BLE
// Ritmo de las notificaciones. La radio del 101 DESCARTA EN SILENCIO las que no caben en su cola (CurieBLE
// dice «enviado» siempre), así que se manda como mucho un trozo por intervalo de conexión, que el enlace
// saca seguro. El intervalo lo elige el celular; se mide al conectar y cada segundo.
#define BLE_PAUSA_MIN_MS      15     // nunca más seguido que esto
#define BLE_PAUSA_INICIAL_MS  50     // hasta conocer el intervalo real (Android suele usar 30-50 ms)
#define BLE_REVISAR_MS        1000   // cada cuánto se vuelve a leer el intervalo
#define BLE_INTERVALO_MIN_MS  15     // intervalo que se le pide al celular, para no ir lento
#define BLE_INTERVALO_MAX_MS  30

BLEService        bleServicio(UUID_SERVICIO);
BLECharacteristic bleRx(UUID_RX, BLEWrite | BLEWriteWithoutResponse, BLE_TROZO);
BLECharacteristic bleTx(UUID_TX, BLENotify, BLE_TROZO);

// Cola circular de bytes; N debe ser potencia de 2. Un solo productor y un solo consumidor.
template <uint16_t N>
struct Cola {
  static_assert((N & (N - 1)) == 0, "N debe ser potencia de 2");
  uint8_t datos[N];
  volatile uint16_t ini = 0, fin = 0;      // ini: próximo a sacar; fin: próximo hueco
  uint16_t usados() const { return (uint16_t)(fin - ini); }
  uint16_t libres() const { return N - usados(); }
  bool meter(uint8_t c) {
    if (libres() == 0) return false;
    datos[fin & (N - 1)] = c;
    fin = fin + 1;
    return true;
  }
  uint8_t mirar(uint16_t i) const { return datos[(ini + i) & (N - 1)]; }
  void descartar(uint16_t n) { ini = ini + n; }
  void vaciar() { ini = fin; }
};

Cola<128> bleEntrada;     // lo que escribe el celular (lo llena bleAlEscribir)
Cola<256> bleSalida;      // respuestas pendientes de notificar (la vacía bleAtender)
Entrada   entradaBle = { {0}, 0, false };
bool      bleConectado = false;
uint32_t  bleUltimoEnvio = 0;
uint32_t  blePausa = BLE_PAUSA_INICIAL_MS;   // separación entre notificaciones (≈ intervalo de conexión)
uint32_t  bleRevisado = 0;                   // última vez que se leyó el intervalo
uint8_t   bleMediciones = 0;                 // lecturas del intervalo en esta conexión

// OJO: BLE.connected() no sirve aquí; BLE es la propia placa y siempre da false. Lo que cuenta es si el
// celular (el «central») sigue conectado; bleAtender lo consulta una vez por vuelta y lo guarda en bleConectado.
bool bleActivo() { return bleConectado && bleTx.subscribed(); }

// Lo que se imprime aquí va al celular. Junta cada línea y la pasa entera a la cola; si no cabe,
// la descarta entera, así nunca llega media línea.
class SalidaBle : public Print {
 public:
  using Print::write;
  size_t write(uint8_t c) override {
    if (c == '\r') return 1;
    if (largo < sizeof(linea)) linea[largo++] = c; else desbordada = true;
    if (c == '\n') {
      if (!desbordada && bleActivo() && bleSalida.libres() >= largo) {
        for (uint8_t i = 0; i < largo; i++) bleSalida.meter(linea[i]);
      }
      largo = 0; desbordada = false;
    }
    return 1;
  }
 private:
  uint8_t linea[MAX_LINEA + 1];
  uint8_t largo = 0;
  bool    desbordada = false;
};
SalidaBle salidaBle;

// La pila BLE llama aquí con cada trozo que escribe el celular. Solo copia: se procesa en loop().
void bleAlEscribir(BLEDevice, BLECharacteristic caracteristica) {
  const uint8_t *v = caracteristica.value();
  int n = caracteristica.valueLength();
  for (int i = 0; i < n; i++) if (!bleEntrada.meter(v[i])) break;
}

void bleIniciar() {
  BLE.begin();
  BLE.setLocalName(NOMBRE_BLE);
  BLE.setAdvertisedService(bleServicio);
  bleServicio.addCharacteristic(bleRx);
  bleServicio.addCharacteristic(bleTx);
  BLE.addService(bleServicio);
  bleRx.setEventHandler(BLEWritten, bleAlEscribir);
  BLE.advertise();
}

// Lee el intervalo de conexión y ajusta blePausa. En la segunda lectura (ya pasada la conexión inicial)
// le pide al celular un intervalo corto; puede aceptarlo o no, por eso se sigue midiendo.
void bleMedirIntervalo(uint32_t ahora) {
  bleRevisado = ahora;
  BLEDevice central = BLE.central();
  if (bleMediciones == 1) central.setConnectionInterval(BLE_INTERVALO_MIN_MS, BLE_INTERVALO_MAX_MS);
  if (bleMediciones < 255) bleMediciones++;
  int intervalo = central.getConnectionInterval();
  if (intervalo >= 7 && intervalo <= 4000) {
    uint32_t pausa = (uint32_t)intervalo + 1;
    blePausa = pausa > BLE_PAUSA_MIN_MS ? pausa : BLE_PAUSA_MIN_MS;
  }
}

void bleAtender(uint32_t ahora) {
  BLE.poll();
  bool conectado = BLE.central().connected();
  if (conectado != bleConectado) {
    // Cada conexión empieza limpia: sin órdenes a medias ni respuestas para el celular anterior.
    bleConectado = conectado;
    bleEntrada.vaciar(); bleSalida.vaciar();
    entradaBle.largo = 0; entradaBle.desbordada = false;
    blePausa = BLE_PAUSA_INICIAL_MS; bleMediciones = 0;
    if (conectado) bleMedirIntervalo(ahora);
    else BLE.advertise();                                // volver a estar visible para reconectar
  }
  if (conectado && ahora - bleRevisado >= BLE_REVISAR_MS) bleMedirIntervalo(ahora);
  while (bleEntrada.usados() > 0) {
    char c = (char)bleEntrada.mirar(0);
    bleEntrada.descartar(1);
    recibirCaracter(entradaBle, c, salidaBle);
  }
  if (bleSalida.usados() == 0 || ahora - bleUltimoEnvio < blePausa) return;
  if (!bleActivo()) { bleSalida.vaciar(); return; }
  uint8_t trozo[BLE_TROZO];
  uint16_t n = bleSalida.usados() < BLE_TROZO ? bleSalida.usados() : BLE_TROZO;
  for (uint16_t i = 0; i < n; i++) trozo[i] = bleSalida.mirar(i);
  if (bleTx.writeValue(trozo, n)) bleSalida.descartar(n);   // si falla, se reintenta en la próxima pausa
  bleUltimoEnvio = ahora;
}
#else
void bleIniciar() {}
void bleAtender(uint32_t) {}
#endif

// ======================================================================
// Las tareas de cada vuelta de loop()
// ======================================================================
void leerSerie() {
  while (Serial.available() > 0) recibirCaracter(entradaSerie, (char)Serial.read(), Serial);
}

void actualizarLeds(uint32_t ahora) {
  for (uint8_t i = 0; i < N_LEDS; i++) {
    Led &l = leds[i];
    int16_t v = 0;
    switch (l.modo) {
      case M_OFF:
        v = 0;
        break;
      case M_ON:
        v = l.brillo;
        break;
      case M_BLINK: {
        uint32_t dur = l.fase ? l.onMs : l.offMs;
        if (ahora - l.ultimoCambio >= dur) {      // resta sin signo: segura al desbordar millis()
          l.fase = !l.fase;
          l.ultimoCambio = ahora;
        }
        v = l.fase ? l.brillo : 0;
        break;
      }
      case M_FADE: {
        while (ahora - l.ultimoCambio >= l.periodo) l.ultimoCambio += l.periodo;
        uint32_t pos = ahora - l.ultimoCambio;           // 0 .. periodo-1
        uint32_t mitad = l.periodo / 2;
        uint32_t x = (pos < mitad) ? pos : (l.periodo - pos);   // onda triangular
        float f = (float)x / (float)mitad;                    // 0..1
        v = (int16_t)(l.brillo * f * f + 0.5f);               // f*f: corrección gamma
        if (v > l.brillo) v = l.brillo;                       // con periodo impar f puede pasar de 1
        break;
      }
    }
    if (v != l.pwm) {
      analogWrite(l.pin, v);
      l.pwm = v;
    }
  }
}

void informarLectura(Print &out, bool ok, float t, float h) {
  if (!ok) { out.println("DATA ERR"); return; }
  out.print("DATA T="); out.print(t, 1);
  out.print(" H=");     out.println(h, 1);
}

void leerSensor(uint32_t ahora) {
  if (ahora - ultimoDht < periodoDht) return;
  ultimoDht = ahora;
  // Esta es la única parte "lenta" (~25 ms). La librería desactiva las
  // interrupciones unos ms mientras lee los bits.
  float h = dht.readHumidity();
  float t = dht.readTemperature();
  bool ok = !(isnan(h) || isnan(t));
  informarLectura(Serial, ok, t, h);                         // la lectura va por todos los canales
#ifdef CON_BLE
  informarLectura(salidaBle, ok, t, h);
#endif
  if (ok && termoActivo) evaluarTermo(t, ahora);            // si falla, TERMO conserva la última zona
}

void setup() {
  Serial.begin(9600);
  dht.begin();
  for (uint8_t i = 0; i < N_LEDS; i++) {
    pinMode(leds[i].pin, OUTPUT);
    analogWrite(leds[i].pin, 0);
    leds[i].pwm = 0;
  }
  bleIniciar();
}

void loop() {
  uint32_t ahora = millis();
  leerSerie();
  bleAtender(ahora);
  actualizarSecuencia(ahora);
  actualizarLeds(ahora);
  leerSensor(ahora);
}
