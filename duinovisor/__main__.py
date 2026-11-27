"""Arranque de DuinoVisor.

    python -m duinovisor          # busca la placa y se conecta sola
    python -m duinovisor --demo   # usa un Arduino simulado (no hace falta la placa)
"""
import argparse
import sys


def activar_ppp_reales() -> None:
    """En Windows con escalado (125 %, 150 %...) evita que el sistema estire la ventana y la vea borrosa.
    La app luego dibuja todo al tamaño correcto con ui.tema.ESCALA."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="duinovisor", description="DuinoVisor: control de LEDs y lectura del DHT11")
    ap.add_argument("--demo", action="store_true", help="usar el Arduino simulado en lugar de la placa")
    args = ap.parse_args(argv)
    activar_ppp_reales()
    try:
        from duinovisor.ui.app import App
    except ImportError as e:
        if "tkinter" in str(e):
            print("Falta Tkinter. En Ubuntu/Debian:  sudo apt install python3-tk", file=sys.stderr)
            return 1
        raise
    App(demo=args.demo).mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
