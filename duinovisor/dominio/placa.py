"""Cableado de la placa. Debe coincidir con firmware/control_leds/control_leds.ino (PIN_DHT y la tabla `leds[]`)."""

PINES = {"R": 3, "G": 5, "Y": 6}      # pines PWM de cada LED
PIN_DHT = 2
RESISTENCIA_LED = "220 Ω"
