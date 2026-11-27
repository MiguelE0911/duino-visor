// Mínimo "Arduino falso" para compilar el sketch en la PC y probarlo.
#pragma once
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <cstdio>
#include <cmath>
#include <string>
#include <deque>
using std::isnan;

#define OUTPUT 1
#define INPUT 0

extern uint32_t shim_millis;
extern void shim_pwm_log(uint8_t pin, int val);
inline uint32_t millis() { return shim_millis; }
inline void pinMode(uint8_t, uint8_t) {}
inline void analogWrite(uint8_t pin, int val) { shim_pwm_log(pin, val); }

struct SerialShim {
  std::deque<char> rx;
  std::string linea;
  void begin(long) {}
  int available() { return (int)rx.size(); }
  int read() { if (rx.empty()) return -1; char c = rx.front(); rx.pop_front(); return (unsigned char)c; }
  void feed(const std::string &s) { for (char c : s) rx.push_back(c); }
  void print(const char *s) { linea += s; }
  void print(char c) { linea += c; }
  void print(unsigned char v) { linea += std::to_string((int)v); }
  void print(int v) { linea += std::to_string(v); }
  void print(unsigned int v) { linea += std::to_string(v); }
  void print(long v) { linea += std::to_string(v); }
  void print(unsigned long v) { linea += std::to_string(v); }
  void print(double v, int d = 2) { char b[32]; snprintf(b, sizeof b, "%.*f", d, v); linea += b; }
  template <class T> void println(T v) { print(v); flushLinea(); }
  void println(double v, int d) { print(v, d); flushLinea(); }
  void flushLinea() { printf("< %s\n", linea.c_str()); linea.clear(); }
};
extern SerialShim Serial;
