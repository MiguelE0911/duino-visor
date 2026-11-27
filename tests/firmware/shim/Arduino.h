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
#define DEC 10

extern uint32_t shim_millis;
extern void shim_pwm_log(uint8_t pin, int val);
inline uint32_t millis() { return shim_millis; }
inline void pinMode(uint8_t, uint8_t) {}
inline void analogWrite(uint8_t pin, int val) { shim_pwm_log(pin, val); }

// Como la clase Print del núcleo: todo print() termina en write(), y println() añade "\r\n".
struct Print {
  virtual ~Print() {}
  virtual size_t write(uint8_t c) = 0;
  size_t print(const char *s) { size_t n = 0; while (*s) n += write((uint8_t)*s++); return n; }
  size_t print(char c) { return write((uint8_t)c); }
  size_t print(unsigned char v, int = DEC) { return print(std::to_string((int)v).c_str()); }
  size_t print(int v, int = DEC) { return print(std::to_string(v).c_str()); }
  size_t print(unsigned int v, int = DEC) { return print(std::to_string(v).c_str()); }
  size_t print(long v, int = DEC) { return print(std::to_string(v).c_str()); }
  size_t print(unsigned long v, int = DEC) { return print(std::to_string(v).c_str()); }
  size_t print(double v, int d = 2) { char b[32]; snprintf(b, sizeof b, "%.*f", d, v); return print(b); }
  size_t println() { return print("\r\n"); }
  template <class T> size_t println(T v) { size_t n = print(v); return n + println(); }
  size_t println(double v, int d) { size_t n = print(v, d); return n + println(); }
};

// El puerto serie: lo que se escribe sale por stdout como "< línea".
struct SerialShim : Print {
  std::deque<char> rx;
  std::string linea;
  void begin(long) {}
  int available() { return (int)rx.size(); }
  int read() { if (rx.empty()) return -1; char c = rx.front(); rx.pop_front(); return (unsigned char)c; }
  void feed(const std::string &s) { for (char c : s) rx.push_back(c); }
  size_t write(uint8_t c) override {
    if (c == '\n') { printf("< %s\n", linea.c_str()); linea.clear(); }
    else if (c != '\r') linea += (char)c;
    return 1;
  }
};
extern SerialShim Serial;
