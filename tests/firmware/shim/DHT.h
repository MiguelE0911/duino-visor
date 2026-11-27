#pragma once
#include <Arduino.h>
#define DHT11 11
extern float shim_dht_t, shim_dht_h;
struct DHT {
  DHT(uint8_t, uint8_t) {}
  void begin() {}
  float readTemperature() { return shim_dht_t; }
  float readHumidity() { return shim_dht_h; }
};
