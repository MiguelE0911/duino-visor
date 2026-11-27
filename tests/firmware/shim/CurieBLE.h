// CurieBLE falso: lo justo para compilar el sketch y probar el canal BLE en la PC.
//   - El driver escribe en una característica con shim_ble_escribir() (llama al manejador BLEWritten,
//     como hace la pila real en cada escritura del celular).
//   - Cada notificación se imprime rearmada por líneas como "b< línea". Si un trozo pasa de 20 bytes
//     el programa termina con error: es el límite real de un paquete BLE.
#pragma once
#include <Arduino.h>

#define BLE_MAX_ATTR_DATA_LEN 20
typedef uint8_t byte;
enum BLEProperty { BLEWriteWithoutResponse = 0x04, BLEWrite = 0x08, BLENotify = 0x10 };
enum BLECharacteristicEvent { BLEWritten = 0 };

extern bool shim_ble_conectado, shim_ble_suscrito;
extern int shim_ble_anuncios;

// Un dispositivo BLE. Como en la librería real, BLE (la propia placa) responde connected() == false
// siempre; solo el central (el celular, BLE.central()) dice si hay conexión.
struct BLEDevice {
  bool esCentral = false;
  bool connected() const { return esCentral && shim_ble_conectado; }
};
struct BLECharacteristic;
typedef void (*BLECharacteristicEventHandler)(BLEDevice, BLECharacteristic);

struct BLECharacteristic {
  const char *uuid = "";
  unsigned char props = 0;
  unsigned short tam = 0;
  uint8_t valor[BLE_MAX_ATTR_DATA_LEN] = {};
  int largo = 0;
  BLECharacteristicEventHandler alEscribir = nullptr;
  std::string linea;
  BLECharacteristic() {}
  BLECharacteristic(const char *u, unsigned char p, unsigned short t) : uuid(u), props(p), tam(t) {}
  void setEventHandler(BLECharacteristicEvent, BLECharacteristicEventHandler h) { alEscribir = h; }
  const byte *value() const { return valor; }
  int valueLength() const { return largo; }
  bool subscribed() { return shim_ble_suscrito; }
  bool writeValue(const byte v[], int n) {               // notificación hacia el celular
    if (n > BLE_MAX_ATTR_DATA_LEN) { printf("ERROR trozo de %d bytes\n", n); exit(3); }
    for (int i = 0; i < n; i++) {
      if (v[i] == '\n') { printf("b< %s\n", linea.c_str()); linea.clear(); }
      else linea += (char)v[i];
    }
    printf("@%u NOTIF %d\n", shim_millis, n);
    return true;
  }
  // Lo que hace la pila cuando el celular escribe un trozo.
  void recibir(const std::string &trozo) {
    largo = (int)trozo.size();
    memcpy(valor, trozo.data(), trozo.size());
    if (alEscribir) alEscribir(BLEDevice(), *this);
  }
};

struct BLEService {
  const char *uuid;
  explicit BLEService(const char *u) : uuid(u) {}
  void addCharacteristic(BLECharacteristic &) {}
};

struct BLELocal : BLEDevice {
  BLEDevice central() const { BLEDevice c; c.esCentral = true; return c; }
  bool begin() { return true; }
  void setLocalName(const char *) {}
  void setAdvertisedService(const BLEService &) {}
  int addService(BLEService &) { return 0; }
  int advertise() { shim_ble_anuncios++; printf("@%u ANUNCIO\n", shim_millis); return 0; }
  void poll() {}
};
extern BLELocal BLE;
