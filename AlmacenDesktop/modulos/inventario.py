"""
Panel de Control de Inventario.
Muestra KPIs, tabla filtrable y exportación CSV.
"""
from __future__ import annotations

import csv
from datetime import datetime
from tkinter import ttk, messagebox, filedialog

import customtkinter as ctk

from repositories.producto_repo import ProductoRepository


class SimpleVar:
    """Variable simple compatible con CTkSegmentedButton sin necesidad de tkinter.StringVar"""
    def __init__(self, value=""):
        self.value = value
        self._trace_callbacks = []

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        # Ejecutar callbacks registrados
        for callback in self._trace_callbacks:
            callback(None, None, None)

    def trace_add(self, mode, callback):
        """Agregar un callback de traza (compatible con tkinter)"""
        if mode == "write":
            self._trace_callbacks.append(callback)
        return f"trace_{id(callback)}"

    def trace_remove(self, mode, cbname):
        """Remover un callback de traza"""
        pass  # Simplificado para este caso

# ══════════════════════════════════════════════════════════════════════════════
# PALETA – Dark Professional (consistente con ventas y devoluciones)
# ══════════════════════════════════════════════════════════════════════════════
C = {
    "bg":        "#0f1117",
    "surface":   "#1a1d27",
    "card":      "#20243a",
    "card_alt":  "#252a3f",
    "primary":   "#3b82f6",
    "primary_h": "#2563eb",
    "success":   "#10b981",
    "success_h": "#059669",
    "danger":    "#ef4444",
    "warning":   "#f59e0b",
    "text":      "#f1f5f9",
    "text_dim":  "#94a3b8",
    "muted":     "#64748b",
    "border":    "#2d3348",
}

FONT = {
    "h1":    ("Segoe UI Black",    24),
    "h2":    ("Segoe UI Semibold", 15),
    "h3":    ("Segoe UI Semibold", 13),
    "body":  ("Segoe UI",          13),
    "small": ("Segoe UI",          11),
    "kpi":   ("Segoe UI Black",    30),
    "kpi_s": ("Segoe UI Black",    22),
}


def _treeview_style():
    s = ttk.Style()
    s.theme_use("clam")
    s.configure("Inv.Treeview",
                background=C["card"], foreground=C["text"],
                fieldbackground=C["card"], borderwidth=0,
                rowheight=40, font=("Segoe UI", 12))
    s.configure("Inv.Treeview.Heading",
                background=C["surface"], foreground=C["muted"],
                font=("Segoe UI Semibold", 11),
                borderwidth=0, relief="flat")
    s.map("Inv.Treeview", background=[("selected", C["primary"])])


# ══════════════════════════════════════════════════════════════════════════════
# PANEL INVENTARIO
# ══════════════════════════════════════════════════════════════════════════════

class PanelInventario(ctk.CTkFrame):

    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=C["bg"])
        self.controller = controller

        _treeview_style()

        self._build_cabecera()
        self._build_kpis()
        self._build_toolbar()
        self._build_tabla()

        self.cargar_datos()

    # ── Cabecera ───────────────────────────────────────────────────────────────

    def _build_cabecera(self):
        bar = ctk.CTkFrame(self, fg_color=C["surface"], height=62, corner_radius=0)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        ctk.CTkButton(
            bar, text="← Menú",
            font=FONT["body"], width=100, height=36,
            fg_color=C["card"], hover_color=C["danger"],
            text_color=C["text_dim"],
            border_width=1, border_color=C["border"],
            corner_radius=8,
            command=lambda: self.controller.cambiar_modulo("dashboard"),
        ).pack(side="left", padx=18, pady=13)

        ctk.CTkLabel(bar, text="CONTROL DE INVENTARIO",
                     font=FONT["h1"],
                     text_color=C["text"]).pack(side="left", padx=8)

        # Timestamp último refresco
        self._lbl_actualizado = ctk.CTkLabel(
            bar, text="",
            font=FONT["small"],
            text_color=C["muted"],
        )
        self._lbl_actualizado.pack(side="right", padx=18)

    # ── KPIs ───────────────────────────────────────────────────────────────────

    def _build_kpis(self):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(14, 6))

        def _kpi(parent, titulo, valor_inicial, color, icon):
            card = ctk.CTkFrame(parent, fg_color=C["card"],
                                corner_radius=14, border_width=1,
                                border_color=C["border"])
            card.pack(side="left", fill="x", expand=True, padx=5)

            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=18, pady=(16, 4))
            ctk.CTkLabel(top, text=icon, font=("Segoe UI", 20)).pack(side="left")
            ctk.CTkLabel(top, text=titulo, font=FONT["h3"],
                         text_color=C["muted"]).pack(side="left", padx=10)

            lbl = ctk.CTkLabel(card, text=valor_inicial,
                               font=FONT["kpi"], text_color=color)
            lbl.pack(anchor="w", padx=18, pady=(0, 16))
            return lbl

        self._kpi_refs   = _kpi(row, "Total Referencias",   "0",   C["primary"], "📦")
        self._kpi_valor  = _kpi(row, "Valor Total (Detal)", "$ 0", C["success"], "💰")
        self._kpi_agot   = _kpi(row, "Agotados",            "0",   C["danger"],  "❌")
        self._kpi_bajo   = _kpi(row, "Stock Bajo (≤ 3)",    "0",   C["warning"], "⚠️")

    # ── Toolbar ────────────────────────────────────────────────────────────────

    def _build_toolbar(self):
        bar = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=12)
        bar.pack(fill="x", padx=12, pady=6)

        ctk.CTkLabel(bar, text="🔍", font=("Segoe UI", 16),
                     text_color=C["muted"]).pack(side="left", padx=(16, 4), pady=12)

        self._entry_buscar = ctk.CTkEntry(
            bar,
            placeholder_text="Buscar por código o nombre...",
            width=320, height=38,
            fg_color=C["surface"],
            border_color=C["border"],
            text_color=C["text"],
            placeholder_text_color=C["muted"],
            font=FONT["body"],
        )
        self._entry_buscar.pack(side="left", padx=(0, 10), pady=12)
        self._entry_buscar.bind("<KeyRelease>", lambda _: self.cargar_datos())

        ctk.CTkButton(
            bar, text="↺  Recargar", width=120, height=38,
            font=FONT["body"],
            fg_color=C["surface"], hover_color=C["primary"],
            border_width=1, border_color=C["border"],
            text_color=C["text"], corner_radius=8,
            command=self.cargar_datos,
        ).pack(side="left", padx=4)

        # Filtro rápido de estado
        self._filtro_var = SimpleVar(value="Todos")
        self._seg_filtro = ctk.CTkSegmentedButton(
            bar,
            values=["Todos", "Agotados", "Stock Bajo"],
            variable=self._filtro_var,
            selected_color=C["primary"],
            selected_hover_color=C["primary_h"],
            unselected_color=C["surface"],
            unselected_hover_color=C["card_alt"],
            text_color=C["text"],
            font=FONT["small"],
            height=36,
            command=lambda _: self.cargar_datos(),
        )
        self._seg_filtro.pack(side="left", padx=10)

        ctk.CTkButton(
            bar, text="📥  Exportar CSV", width=140, height=38,
            font=FONT["body"],
            fg_color=C["success"], hover_color=C["success_h"],
            text_color="white", corner_radius=8,
            command=self._exportar_csv,
        ).pack(side="right", padx=16)

    # ── Tabla ──────────────────────────────────────────────────────────────────

    def _build_tabla(self):
        frame = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=14)
        frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        cols = ("ref", "nombre", "precio", "stock", "estado")
        self._tabla = ttk.Treeview(frame, columns=cols,
                                   show="headings", style="Inv.Treeview")

        self._tabla.heading("ref",     text="CÓDIGO / REF",
                            command=lambda: self._ordenar("ref"))
        self._tabla.heading("nombre",  text="DESCRIPCIÓN",
                            command=lambda: self._ordenar("nombre"))
        self._tabla.heading("precio",  text="PRECIO DETAL",
                            command=lambda: self._ordenar("precio"))
        self._tabla.heading("stock",   text="STOCK FÍSICO",
                            command=lambda: self._ordenar("stock"))
        self._tabla.heading("estado",  text="ESTADO")

        self._tabla.column("ref",    width=160)
        self._tabla.column("nombre", width=380)
        self._tabla.column("precio", width=130, anchor="e")
        self._tabla.column("stock",  width=110, anchor="center")
        self._tabla.column("estado", width=130, anchor="center")

        self._tabla.tag_configure("agotado", foreground="#f87171")
        self._tabla.tag_configure("bajo",    foreground="#fbbf24")
        self._tabla.tag_configure("ok",      foreground="#000000")

        sb = ctk.CTkScrollbar(frame, command=self._tabla.yview)
        self._tabla.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(0, 8), pady=8)
        self._tabla.pack(fill="both", expand=True, padx=(8, 0), pady=8)

        # Variables de ordenamiento
        self._orden_col = None
        self._orden_asc = True

    # ══════════════════════════════════════════════════════════════════════════
    # LÓGICA
    # ══════════════════════════════════════════════════════════════════════════

    def cargar_datos(self, _event=None):
        for i in self._tabla.get_children():
            self._tabla.delete(i)

        termino  = self._entry_buscar.get().strip()
        filtro   = self._filtro_var.get()
        productos = ProductoRepository.listar(termino, limite=2000)

        total_refs  = 0
        valor_total = 0.0
        agotados    = 0
        bajo_stock  = 0

        for p in productos:
            _, ref, nombre, precio, stock = p
            valor_total += precio * stock
            total_refs  += 1

            if stock <= 0:
                estado = "❌  Agotado"
                tag    = "agotado"
                agotados += 1
            elif stock <= 3:
                estado = "⚠️  Stock Bajo"
                tag    = "bajo"
                bajo_stock += 1
            else:
                estado = "✓  Disponible"
                tag    = "ok"

            # Aplicar filtro rápido
            if filtro == "Agotados"   and tag != "agotado": continue
            if filtro == "Stock Bajo" and tag != "bajo":    continue

            self._tabla.insert("", "end",
                               values=(ref, nombre, f"$ {precio:,.0f}", stock, estado),
                               tags=(tag,))

        # KPIs
        self._kpi_refs.configure(text=str(total_refs))
        self._kpi_valor.configure(
            text=f"$ {valor_total:,.0f}" if valor_total < 1_000_000
            else f"$ {valor_total/1_000_000:.1f}M"
        )
        self._kpi_agot.configure(text=str(agotados))
        self._kpi_bajo.configure(text=str(bajo_stock))

        self._lbl_actualizado.configure(
            text=f"Actualizado: {datetime.now().strftime('%H:%M:%S')}"
        )

    def _ordenar(self, col: str):
        """Ordena la tabla al hacer clic en el encabezado."""
        filas = [(self._tabla.set(k, col), k)
                 for k in self._tabla.get_children("")]

        # Intentar orden numérico si aplica
        def _clave(x):
            v = x[0].replace("$", "").replace(",", "").replace(".", "").strip()
            try:
                return float(v)
            except ValueError:
                return v.lower()

        if self._orden_col == col:
            self._orden_asc = not self._orden_asc
        else:
            self._orden_asc = True
        self._orden_col = col

        filas.sort(key=_clave, reverse=not self._orden_asc)
        for idx, (_, k) in enumerate(filas):
            self._tabla.move(k, "", idx)

    def _exportar_csv(self):
        items = self._tabla.get_children()
        if not items:
            messagebox.showwarning("Sin datos", "No hay datos visibles para exportar.",
                                   parent=self)
            return

        fecha_str = datetime.now().strftime("%Y%m%d_%H%M")
        ruta = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=f"Inventario_{fecha_str}.csv",
            title="Guardar reporte de inventario",
            filetypes=[("CSV para Excel", "*.csv"), ("Todos los archivos", "*.*")],
        )
        if not ruta:
            return

        try:
            with open(ruta, mode="w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(["Referencia", "Descripción", "Precio", "Stock", "Estado"])
                for i in items:
                    writer.writerow(self._tabla.item(i)["values"])
            messagebox.showinfo("Exportado", f"Archivo guardado en:\n{ruta}", parent=self)
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo guardar:\n{exc}", parent=self)