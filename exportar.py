"""Exportar las lecturas del DHT11 a CSV (se abre bien en Excel)."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

ENCABEZADO = ("fecha_hora", "temperatura_c", "humedad_pct", "estado")
Lectura = tuple[datetime, Optional[float], Optional[float]]


def escribir_csv(ruta, lecturas: Iterable[Lectura]) -> int:
    """Escribe las lecturas y devuelve cuántas filas guardó. Una lectura sin valores es un error del sensor."""
    n = 0
    # utf-8-sig: así Excel reconoce bien los acentos
    with Path(ruta).open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(ENCABEZADO)
        for momento, t, h in lecturas:
            ok = t is not None and h is not None
            w.writerow([momento.strftime("%Y-%m-%d %H:%M:%S"),
                        f"{t:.1f}" if ok else "", f"{h:.1f}" if ok else "",
                        "ok" if ok else "error de sensor"])
            n += 1
    return n
