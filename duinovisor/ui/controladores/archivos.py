"""Guardar y cargar escenas y exportar las lecturas a CSV."""
from __future__ import annotations

from datetime import datetime
from tkinter import filedialog, messagebox

from duinovisor.almacenamiento import escenas
from duinovisor.almacenamiento.exportar import escribir_csv


class ArchivosMixin:
    """Menú de archivos."""

    def guardar_escena(self):
        try:
            leds, dht, termo = self._leds_ui(), *self.leer_ui()[1:]
        except ValueError as e:
            messagebox.showwarning("Escena", f"No se guardó nada.\n\n{e}")
            return
        ruta = filedialog.asksaveasfilename(title="Guardar escena", defaultextension=".json",
                                            initialfile="escena.json", filetypes=[("Escena de DuinoVisor", "*.json")])
        if not ruta:
            return
        try:
            escenas.guardar(ruta, leds, dht, termo, self._seleccion_seq())
        except OSError as e:
            messagebox.showerror("Escena", f"No se pudo guardar el archivo: {e}")
            return
        self.log(f"Escena guardada en {ruta}", "info")

    def cargar_escena(self):
        ruta = filedialog.askopenfilename(title="Cargar escena", filetypes=[("Escena de DuinoVisor", "*.json")])
        if not ruta:
            return
        try:
            leds, dht, termo, seq = escenas.cargar(ruta)
        except ValueError as e:
            messagebox.showwarning("Escena", f"No se cargó nada.\n\n{e}")
            return
        for c, cfg in leds.items():
            self.paneles[c].cargar(cfg)
        self.v_dht.set(str(dht))
        self.v_termo.set(termo is not None)
        if termo is not None:
            self.v_tmin.set(str(termo[0]))
            self.v_tmax.set(str(termo[1]))
        if seq is not None:
            self.v_seq.set(seq[0])
            self.v_vel.set(seq[1])
        self.log("Escena cargada. Pulsa Aplicar para enviarla.", "info")
        self.al_cambiar()

    def exportar_csv(self):
        if not self.lecturas:
            messagebox.showinfo("Exportar CSV", "Todavía no hay lecturas del sensor.")
            return
        ruta = filedialog.asksaveasfilename(title="Exportar lecturas", defaultextension=".csv",
                                            initialfile=f"lecturas_{datetime.now():%Y%m%d_%H%M%S}.csv",
                                            filetypes=[("CSV", "*.csv")])
        if not ruta:
            return
        try:
            n = escribir_csv(ruta, self.lecturas)
        except OSError as e:
            messagebox.showerror("Exportar CSV", f"No se pudo guardar el archivo: {e}")
            return
        self.log(f"{n} lecturas guardadas en {ruta}", "info")
