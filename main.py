"""DuinoVisor: control de Arduino en tiempo real.

    python main.py          # busca la placa y se conecta sola
    python main.py --demo   # usa un Arduino simulado (no hace falta la placa)
"""
import argparse
import sys


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="DuinoVisor: control de LEDs y lectura del DHT11")
    ap.add_argument("--demo", action="store_true", help="usar el Arduino simulado en lugar de la placa")
    args = ap.parse_args(argv)
    try:
        from gui import App
    except ImportError as e:
        if "tkinter" in str(e):
            print("Falta Tkinter. En Ubuntu/Debian:  sudo apt install python3-tk", file=sys.stderr)
            return 1
        raise
    App(demo=args.demo).mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
