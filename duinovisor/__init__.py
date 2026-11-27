"""DuinoVisor: control de un Arduino (LEDs y un sensor DHT11) en tiempo real desde el PC.

Capas, de dentro hacia fuera (cada una solo importa de las anteriores):

    dominio         reglas puras: protocolo, LEDs, secuencias, termómetro, alarmas
    hardware        enlace serie y Arduino simulado
    almacenamiento  escenas, CSV y preferencias
    ui              ventana Tkinter: tema, widgets, vistas y controladores

Ver docs/ARQUITECTURA.md.
"""

__version__ = "1.0.0"
