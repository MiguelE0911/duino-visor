// Driver: compila el .ino tal cual y lo maneja por stdin.
//   > texto      envía una línea por el "puerto serie"
//   t N          avanza N ms (llama a loop() cada ms)
//   dht T H|nan  fija lo que lee el sensor
//   start N      fija millis() inicial (para probar el desborde)
//   pwm          muestra el último PWM de cada pin
#include "Arduino.h"
#include "DHT.h"
#include <iostream>
#include <sstream>
#include <map>

uint32_t shim_millis = 0;
float shim_dht_t = 24.0f, shim_dht_h = 50.0f;
SerialShim Serial;
static std::map<int,int> ultimo;
void shim_pwm_log(uint8_t pin, int val) { printf("@%u P%d=%d\n", shim_millis, pin, val); ultimo[pin] = val; }

#include "../../firmware/control_leds/control_leds.ino"

int main() {
  setup();
  std::string l;
  while (std::getline(std::cin, l)) {
    if (l.empty()) continue;
    if (l[0] == '>') { Serial.feed(l.substr(2) + "\n"); loop(); }
    else if (l.rfind("t ", 0) == 0) { long n = atol(l.c_str() + 2); for (long i = 0; i < n; i++) { shim_millis++; loop(); } }
    else if (l.rfind("start ", 0) == 0) { shim_millis = (uint32_t)strtoul(l.c_str() + 6, 0, 10); ultimoDht = shim_millis; }
    else if (l.rfind("dht ", 0) == 0) {
      std::istringstream s(l.substr(4)); std::string a, b; s >> a >> b;
      if (a == "nan") { shim_dht_t = shim_dht_h = NAN; } else { shim_dht_t = atof(a.c_str()); shim_dht_h = atof(b.c_str()); }
    }
    else if (l == "pwm") { printf("PWM 3=%d 5=%d 6=%d\n", ultimo[3], ultimo[5], ultimo[6]); }
  }
  return 0;
}
