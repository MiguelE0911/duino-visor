/*
 * control_leds.ino  -  DuinoVisor
 *
 * 3 LEDs con PWM (pines 3, 5, 6, tabla `leds[]`) + sensor DHT11 (pin 2).
 * Placa: Arduino 101 (en la 101 solo 3, 5, 6 y 9 tienen PWM; en un UNO también valen).
 * Protocolo de texto por puerto serie a 9600 baudios, una orden por línea.
 * NUNCA se usa delay(): todo se planifica con millis().
 *
 * Librerías (Gestor de librerías del IDE):
 *   - DHT sensor library (Adafruit)
 *   - Adafruit Unified Sensor
 */
#include <Arduino.h>
#include <DHT.h>

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

// ---- búfer de entrada ----
char    linea[MAX_LINEA + 1];
uint8_t largo = 0;
bool    desbordada = false;

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

void ordenSeq(char **tok, uint8_t n, uint32_t ahora) {
  if (n < 2 || n > 3) { Serial.println("ERR uso SEQ nombre [vel] | OFF | PAUSA | SEGUIR"); return; }
  if (strcmp(tok[1], "OFF") == 0) {
    if (seqDef != NULL) { seqDef = NULL; seqPausa = false; apagarTodos(); }
    Serial.println("OK SEQ");
  } else if (strcmp(tok[1], "PAUSA") == 0) {
    if (seqDef == NULL) { Serial.println("ERR sin secuencia"); return; }
    if (!seqPausa) {
      uint32_t dur = durPaso(), t = ahora - seqInicioPaso;
      seqRestante = (t >= dur) ? 0 : dur - t;
      seqPausa = true;
    }
    Serial.println("OK SEQ");
  } else if (strcmp(tok[1], "SEGUIR") == 0) {
    if (seqDef == NULL) { Serial.println("ERR sin secuencia"); return; }
    if (seqPausa) {
      seqInicioPaso = ahora - (durPaso() - seqRestante);
      seqPausa = false;
    }
    Serial.println("OK SEQ");
  } else {
    const DefSeq *def = NULL;
    for (uint8_t i = 0; i < N_SECUENCIAS; i++) if (strcmp(tok[1], SECUENCIAS[i].nombre) == 0) def = &SECUENCIAS[i];
    if (def == NULL) {                                       // ERR secuencia VIAL FANTASTICO ALERTA
      Serial.print("ERR secuencia");
      for (uint8_t i = 0; i < N_SECUENCIAS; i++) { Serial.print(' '); Serial.print(SECUENCIAS[i].nombre); }
      Serial.println();
      return;
    }
    long vel = 100;
    if (n == 3 && (!numero(tok[2], vel) || vel < 25 || vel > 400)) { Serial.println("ERR velocidad 25-400"); return; }
    termoActivo = false; zona = -1;
    seqDef = def; seqPaso = 0; seqVel = (uint16_t)vel; seqPausa = false; seqInicioPaso = ahora;
    aplicarPasoSeq();
    Serial.println("OK SEQ");
  }
}

// ======================================================================
// Procesamiento de órdenes
// ======================================================================
void procesarComando(char *texto) {
  for (char *c = texto; *c; c++) if (*c >= 'a' && *c <= 'z') *c -= 32;   // a mayúsculas

  char *tok[MAX_TOKENS];
  uint8_t n = 0;
  for (char *p = strtok(texto, " \t"); p != NULL && n < MAX_TOKENS; p = strtok(NULL, " \t")) tok[n++] = p;
  if (n == 0) return;                                    // línea vacía: se ignora

  uint32_t ahora = millis();
  long a, b, c;

  if (strcmp(tok[0], "PING") == 0) {
    Serial.println("PONG OAC-LEDS 1");

  } else if (strcmp(tok[0], "LED") == 0) {
    if (n < 3)                      { Serial.println("ERR faltan argumentos"); return; }
    Led *l = buscarLed(tok[1]);
    if (l == NULL) {                                         // ERR led R G Y
      Serial.print("ERR led");
      for (uint8_t i = 0; i < N_LEDS; i++) { Serial.print(' '); Serial.print(leds[i].id); }
      Serial.println();
      return;
    }

    if (strcmp(tok[2], "OFF") == 0) {
      if (n != 3)                   { Serial.println("ERR argumentos"); return; }
      cancelarAutomatismos();
      l->modo = M_OFF;

    } else if (strcmp(tok[2], "ON") == 0) {
      if (n != 4)                   { Serial.println("ERR uso LED c ON brillo"); return; }
      if (!numero(tok[3], a) || a < 0 || a > 255) { Serial.println("ERR brillo 0-255"); return; }
      cancelarAutomatismos();
      l->modo = M_ON; l->brillo = (uint8_t)a;

    } else if (strcmp(tok[2], "BLINK") == 0) {
      if (n != 6)                   { Serial.println("ERR uso LED c BLINK brillo on off"); return; }
      if (!numero(tok[3], a) || a < 0 || a > 255) { Serial.println("ERR brillo 0-255"); return; }
      if (!numero(tok[4], b) || !numero(tok[5], c) || b < 20 || c < 20 || b > 60000 || c > 60000) {
        Serial.println("ERR tiempo 20-60000 ms"); return;
      }
      cancelarAutomatismos();
      l->modo = M_BLINK; l->brillo = (uint8_t)a;
      l->onMs = (uint16_t)b; l->offMs = (uint16_t)c;
      l->fase = true; l->ultimoCambio = ahora;

    } else if (strcmp(tok[2], "FADE") == 0) {
      if (n != 5)                   { Serial.println("ERR uso LED c FADE brillo periodo"); return; }
      if (!numero(tok[3], a) || a < 0 || a > 255) { Serial.println("ERR brillo 0-255"); return; }
      if (!numero(tok[4], b) || b < 200 || b > 60000) { Serial.println("ERR periodo 200-60000 ms"); return; }
      cancelarAutomatismos();
      l->modo = M_FADE; l->brillo = (uint8_t)a;
      l->periodo = (uint16_t)b; l->ultimoCambio = ahora;

    } else {
      Serial.println("ERR modo"); return;
    }
    Serial.print("OK LED "); Serial.println(l->id);

  } else if (strcmp(tok[0], "DHT") == 0) {
    if (n != 2 || !numero(tok[1], a) || a < 1000 || a > 3600000L) {
      Serial.println("ERR periodo 1000-3600000 ms"); return;     // 1000 ms: límite del DHT11
    }
    periodoDht = (uint32_t)a;
    Serial.println("OK DHT");

  } else if (strcmp(tok[0], "TERMO") == 0) {
    if (n == 2 && strcmp(tok[1], "OFF") == 0) {
      termoActivo = false; zona = -1; seqDef = NULL; seqPausa = false; apagarTodos();
      Serial.println("OK TERMO");
    } else if (n == 3 && numero(tok[1], a) && numero(tok[2], b) && a < b) {
      termoMin = (float)a; termoMax = (float)b;
      termoActivo = true; zona = -1; seqDef = NULL; seqPausa = false; apagarTodos();   // se enciende con la próxima lectura
      Serial.println("OK TERMO");
    } else {
      Serial.println("ERR uso TERMO tmin tmax (tmin<tmax) | TERMO OFF");
    }

  } else if (strcmp(tok[0], "SEQ") == 0) {
    ordenSeq(tok, n, ahora);

  } else if (strcmp(tok[0], "STATUS") == 0) {
    for (uint8_t i = 0; i < N_LEDS; i++) {
      Serial.print("STATE "); Serial.print(leds[i].id); Serial.print(' ');
      Serial.print(nombreModo(leds[i].modo)); Serial.print(' ');
      Serial.print(leds[i].brillo); Serial.print(' ');
      Serial.print(leds[i].onMs); Serial.print(' ');
      Serial.print(leds[i].offMs); Serial.print(' ');
      Serial.println(leds[i].periodo);
    }
    if (seqDef == NULL) {
      Serial.println("STATE SEQ OFF");
    } else {
      Serial.print("STATE SEQ "); Serial.print(seqDef->nombre); Serial.print(' ');
      Serial.print(seqVel); Serial.print(' '); Serial.println(seqPausa ? "PAUSA" : "RUN");
    }
    Serial.println("OK STATUS");

  } else {
    Serial.println("ERR comando");
  }
}

// ======================================================================
// Las tres tareas de cada vuelta de loop()
// ======================================================================
void leerSerie() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      if (desbordada) {
        Serial.println("ERR linea larga");
      } else {
        linea[largo] = '\0';
        procesarComando(linea);
      }
      largo = 0; desbordada = false;
    } else if (largo < MAX_LINEA) {
      linea[largo++] = c;
    } else {
      desbordada = true;            // se descarta hasta el salto de línea
    }
  }
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

void leerSensor(uint32_t ahora) {
  if (ahora - ultimoDht < periodoDht) return;
  ultimoDht = ahora;
  // Esta es la única parte "lenta" (~25 ms). La librería desactiva las
  // interrupciones unos ms mientras lee los bits.
  float h = dht.readHumidity();
  float t = dht.readTemperature();
  if (isnan(h) || isnan(t)) {
    Serial.println("DATA ERR");
    return;                                  // en TERMO se conserva la última zona
  }
  Serial.print("DATA T="); Serial.print(t, 1);
  Serial.print(" H=");     Serial.println(h, 1);
  if (termoActivo) evaluarTermo(t, ahora);
}

void setup() {
  Serial.begin(9600);
  dht.begin();
  for (uint8_t i = 0; i < N_LEDS; i++) {
    pinMode(leds[i].pin, OUTPUT);
    analogWrite(leds[i].pin, 0);
    leds[i].pwm = 0;
  }
}

void loop() {
  uint32_t ahora = millis();
  leerSerie();
  actualizarSecuencia(ahora);
  actualizarLeds(ahora);
  leerSensor(ahora);
}
