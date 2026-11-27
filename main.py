"""Atajo para arrancar DuinoVisor sin instalarlo: equivale a `python -m duinovisor`.

    python main.py          # busca la placa y se conecta sola
    python main.py --demo   # usa un Arduino simulado (no hace falta la placa)
"""
import sys

from duinovisor.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
