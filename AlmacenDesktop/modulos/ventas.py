"""
Panel Principal del Punto de Venta (POS).
Reemplaza el ventas.py original.

Responsabilidad única: construir y coordinar la UI.
Toda lógica de negocio delegada a Carrito, ProductoRepository y VentaRepository.
"""
from __future__ import annotations

import customtkinter as ctk
from tkinter import ttk, messagebox

from modulos.carrito import Carrito
from repositories.producto_repo import ProductoRepository
from repositories.venta_repo import VentaRepository
from modulos.dialogs.seleccion_dialog import DialogSeleccion
from modulos.dialogs.cobro_dialog import VentanaCobro, VentanaComprobante

# ══════════════════════════════════════════════════════════════════════════════
# PALETA – Dark Professional
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
    "danger_h":  "#dc2626",
    "warning":   "#f59e0b",
    "text":      "#f1f5f9",
    "text_dim":  "#94a3b8",
    "muted":     "#64748b",
    "border":    "#2d3348",
}

FONT = {
    "h1":    ("Segoe UI Black",    26),
    "h2":    ("Segoe UI Semibold", 15),
    "h3":    ("Segoe UI Semibold", 13),
    "body":  ("Segoe UI",          13),
    "small": ("Segoe UI",          11),
    "mono":  ("Consolas",          13),
    "total": ("Segoe UI Black",    38),
    "badge": ("Segoe UI Semibold", 11),
}


def _treeview_style(name: str, row_height: int = 40):
    """Aplica el tema oscuro a un ttk.Treeview."""
    s = ttk.Style()
    s.theme_use("clam")
    s.configure(name,
                background=C["card"], foreground=C["text"],
                fieldbackground=C["card"], borderwidth=0,
                rowheight=row_height, font=("Segoe UI", 12))
    s.configure(f"{name}.Heading",
                background=C["surface"], foreground=C["muted"],
                font=("Segoe UI Semibold", 11),
                borderwidth=0, relief="flat")
    s.map(name, background=[("selected", C["primary"])])


# ══════════════════════════════════════════════════════════════════════════════
# PANEL POS
# ══════════════════════════════════════════════════════════════════════════════

class PanelPOS(ctk.CTkFrame):

    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=C["bg"])
        self.controller = controller
        self.carrito    = Carrito()

        _treeview_style("POS.Treeview",  row_height=42)
        _treeview_style("Stock.Treeview", row_height=38)
        _treeview_style("Hist.Treeview",  row_height=38)

        self._build_cabecera()
        self._build_tabs()

    # ── Cabecera ───────────────────────────────────────────────────────────────

    def _build_cabecera(self):
        bar = ctk.CTkFrame(self, fg_color=C["surface"],
                           height=62, corner_radius=0)
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

        ctk.CTkLabel(bar, text="PUNTO DE VENTA",
                     font=FONT["h1"],
                     text_color=C["text"]).pack(side="left", padx=8)

        self._lbl_badge = ctk.CTkLabel(
            bar,
            text="Carrito vacío",
            font=FONT["badge"],
            text_color=C["muted"],
            fg_color=C["card"],
            corner_radius=6,
            padx=10, pady=4,
        )
        self._lbl_badge.pack(side="right", padx=18)

    # ── Pestañas ───────────────────────────────────────────────────────────────

    def _build_tabs(self):
        self._tabs = ctk.CTkTabview(
            self,
            fg_color=C["surface"],
            segmented_button_fg_color=C["card"],
            segmented_button_selected_color=C["primary"],
            segmented_button_selected_hover_color=C["primary_h"],
            segmented_button_unselected_color=C["card"],
            segmented_button_unselected_hover_color=C["card_alt"],
            text_color=C["text_dim"],
        )
        self._tabs.pack(fill="both", expand=True, padx=12, pady=(6, 12))

        self._tab_venta = self._tabs.add("  🛒  Nueva Venta  ")
        self._tab_stock = self._tabs.add("  📦  Stock  ")
        self._tab_hist  = self._tabs.add("  📜  Historial  ")

        self._build_tab_venta()
        self._build_tab_stock()
        self._build_tab_hist()

        # Auto-recarga al cambiar de pestaña
        self._tabs.configure(command=self._on_tab_cambio)

    def _on_tab_cambio(self, nombre_tab: str = ""):
        nombre = self._tabs.get()
        if "Stock" in nombre:
            self._cargar_stock()
        elif "Historial" in nombre:
            self._cargar_historial()

    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA 1 – NUEVA VENTA
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_venta(self):
        wrapper = ctk.CTkFrame(self._tab_venta, fg_color="transparent")
        wrapper.pack(fill="both", expand=True)
        self._build_panel_busqueda(wrapper)
        self._build_panel_carrito(wrapper)

    def _build_panel_busqueda(self, parent):
        panel = ctk.CTkFrame(parent, width=300,
                             fg_color=C["card"], corner_radius=14)
        panel.pack(side="left", fill="y", padx=(0, 8), pady=4)
        panel.pack_propagate(False)

        ctk.CTkLabel(panel, text="BUSCAR PRODUCTO",
                     font=FONT["h3"],
                     text_color=C["muted"]).pack(anchor="w", padx=20, pady=(20, 6))

        self._entry_busqueda = ctk.CTkEntry(
            panel,
            placeholder_text="🔍  Código o nombre...",
            height=48, font=("Segoe UI", 15),
            fg_color=C["surface"],
            border_color=C["border"],
            text_color=C["text"],
            placeholder_text_color=C["muted"],
            corner_radius=10,
        )
        self._entry_busqueda.pack(padx=16, fill="x")
        self._entry_busqueda.bind("<Return>", self._on_buscar)
        self._entry_busqueda.focus()

        ctk.CTkLabel(panel, text="Presiona Enter o escanea el código",
                     font=FONT["small"],
                     text_color=C["muted"]).pack(pady=(6, 0))

        self._lbl_status = ctk.CTkLabel(
            panel, text="",
            font=FONT["body"],
            text_color=C["success"],
            wraplength=260, justify="center",
        )
        self._lbl_status.pack(pady=8, padx=16)

        ctk.CTkFrame(panel, height=1, fg_color=C["border"]).pack(fill="x", padx=16, pady=8)

        ctk.CTkLabel(panel, text="ACCIONES",
                     font=FONT["h3"],
                     text_color=C["muted"]).pack(anchor="w", padx=20, pady=(6, 10))

        def _btn(text, hover):
            return ctk.CTkButton(
                panel, text=text, font=FONT["body"], height=40,
                fg_color=C["surface"], hover_color=hover,
                text_color=C["text"],
                border_width=1, border_color=C["border"],
                corner_radius=8,
            )

        b_editar   = _btn("✏  Editar Cantidad",    C["primary"])
        b_quitar   = _btn("🗑  Quitar Seleccionado", C["warning"])
        b_vaciar   = _btn("🧹  Vaciar Carrito",      C["danger"])

        b_editar.configure(command=self._editar_item)
        b_quitar.configure(command=self._eliminar_item)
        b_vaciar.configure(command=self._vaciar_carrito)

        for b in (b_editar, b_quitar, b_vaciar):
            b.pack(fill="x", padx=16, pady=3)

    def _build_panel_carrito(self, parent):
        panel = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=14)
        panel.pack(side="right", fill="both", expand=True, pady=4)

        ctk.CTkLabel(panel, text="CARRITO DE COMPRA",
                     font=FONT["h3"],
                     text_color=C["muted"]).pack(anchor="w", padx=20, pady=(20, 8))

        cols = ("_id", "ref", "nombre", "precio", "cant", "subtotal")
        self._tabla_carrito = ttk.Treeview(panel, columns=cols,
                                           show="headings", style="POS.Treeview")
        self._tabla_carrito.heading("ref",      text="CÓDIGO")
        self._tabla_carrito.heading("nombre",   text="DESCRIPCIÓN")
        self._tabla_carrito.heading("precio",   text="P. UNIT")
        self._tabla_carrito.heading("cant",     text="CANT")
        self._tabla_carrito.heading("subtotal", text="SUBTOTAL")
        self._tabla_carrito.column("_id",      width=0,   stretch=False)
        self._tabla_carrito.column("ref",      width=100)
        self._tabla_carrito.column("nombre",   width=260)
        self._tabla_carrito.column("precio",   width=110, anchor="e")
        self._tabla_carrito.column("cant",     width=70,  anchor="center")
        self._tabla_carrito.column("subtotal", width=120, anchor="e")

        sb = ctk.CTkScrollbar(panel, command=self._tabla_carrito.yview)
        self._tabla_carrito.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(0, 8), pady=(0, 8))
        self._tabla_carrito.pack(fill="both", expand=True, padx=(12, 0))
        self._tabla_carrito.bind("<Double-1>", lambda _e: self._editar_item())

        # Footer con total y botón cobrar
        footer = ctk.CTkFrame(panel, fg_color=C["surface"],
                              corner_radius=12, height=80)
        footer.pack(fill="x", padx=12, pady=12)
        footer.pack_propagate(False)

        col_total = ctk.CTkFrame(footer, fg_color="transparent")
        col_total.pack(side="left", padx=20)
        ctk.CTkLabel(col_total, text="TOTAL",
                     font=FONT["small"],
                     text_color=C["muted"]).pack(anchor="w")
        self._lbl_total = ctk.CTkLabel(col_total,
                                       text="$ 0",
                                       font=FONT["total"],
                                       text_color=C["success"])
        self._lbl_total.pack()

        ctk.CTkButton(
            footer,
            text="COBRAR  →",
            font=("Segoe UI Black", 18),
            height=54, width=210,
            fg_color=C["success"],
            hover_color=C["success_h"],
            text_color="white",
            corner_radius=10,
            command=self._abrir_cobro,
        ).pack(side="right", padx=20)

    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA 2 – STOCK
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_stock(self):
        top = ctk.CTkFrame(self._tab_stock, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=10)

        self._entry_stock = ctk.CTkEntry(
            top,
            placeholder_text="🔍  Buscar por nombre o código...",
            width=340, height=40,
            fg_color=C["card"], border_color=C["border"],
            text_color=C["text"], placeholder_text_color=C["muted"],
            font=FONT["body"],
        )
        self._entry_stock.pack(side="left", padx=(0, 8))
        self._entry_stock.bind("<KeyRelease>", lambda _: self._cargar_stock())

        ctk.CTkButton(
            top, text="↺  Refrescar", width=120, height=40,
            font=FONT["body"],
            fg_color=C["card"], hover_color=C["primary"],
            border_width=1, border_color=C["border"],
            text_color=C["text"], corner_radius=8,
            command=self._cargar_stock,
        ).pack(side="left")

        frame = ctk.CTkFrame(self._tab_stock, fg_color=C["card"], corner_radius=12)
        frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        cols = ("ref", "nombre", "precio", "stock")
        self._tabla_stock = ttk.Treeview(frame, columns=cols,
                                         show="headings", style="Stock.Treeview")
        self._tabla_stock.heading("ref",    text="CÓDIGO")
        self._tabla_stock.heading("nombre", text="DESCRIPCIÓN")
        self._tabla_stock.heading("precio", text="PRECIO DETAL")
        self._tabla_stock.heading("stock",  text="STOCK")
        self._tabla_stock.column("ref",    width=120)
        self._tabla_stock.column("nombre", width=340)
        self._tabla_stock.column("precio", width=130, anchor="e")
        self._tabla_stock.column("stock",  width=90,  anchor="center")
        self._tabla_stock.pack(fill="both", expand=True, padx=6, pady=6)

    def _cargar_stock(self):
        for i in self._tabla_stock.get_children():
            self._tabla_stock.delete(i)
        termino = self._entry_stock.get().strip()
        for p in ProductoRepository.listar(termino):
            tag = "bajo" if p[4] <= 3 else "ok"
            self._tabla_stock.insert("", "end",
                                     values=(p[1], p[2], f"$ {p[3]:,.0f}", p[4]),
                                     tags=(tag,))
        self._tabla_stock.tag_configure("bajo", foreground="#c0392b")
        self._tabla_stock.tag_configure("ok",   foreground="#000000")

    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA 3 – HISTORIAL
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_hist(self):
        top = ctk.CTkFrame(self._tab_hist, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=10)

        ctk.CTkLabel(top, text="Ventas registradas en este dispositivo",
                     font=FONT["body"],
                     text_color=C["muted"]).pack(side="left")

        ctk.CTkButton(
            top, text="↺  Refrescar", width=120, height=38,
            font=FONT["body"],
            fg_color=C["card"], hover_color=C["primary"],
            border_width=1, border_color=C["border"],
            text_color=C["text"], corner_radius=8,
            command=self._cargar_historial,
        ).pack(side="right")

        frame = ctk.CTkFrame(self._tab_hist, fg_color=C["card"], corner_radius=12)
        frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        cols = ("id", "fecha", "total", "metodo")
        self._tabla_hist = ttk.Treeview(frame, columns=cols,
                                        show="headings", style="Hist.Treeview")
        self._tabla_hist.heading("id",     text="# VENTA")
        self._tabla_hist.heading("fecha",  text="FECHA")
        self._tabla_hist.heading("total",  text="TOTAL")
        self._tabla_hist.heading("metodo", text="MÉTODO")
        self._tabla_hist.column("id",     width=80,  anchor="center")
        self._tabla_hist.column("fecha",  width=180)
        self._tabla_hist.column("total",  width=140, anchor="e")
        self._tabla_hist.column("metodo", width=180)
        self._tabla_hist.pack(fill="both", expand=True, padx=6, pady=6)

    def _cargar_historial(self):
        for i in self._tabla_hist.get_children():
            self._tabla_hist.delete(i)
        for fila in VentaRepository.historial():
            self._tabla_hist.insert("", "end",
                                    values=(fila[0], fila[1],
                                            f"$ {fila[2]:,.0f}", fila[3]))

    # ══════════════════════════════════════════════════════════════════════════
    # LÓGICA DEL CARRITO
    # ══════════════════════════════════════════════════════════════════════════

    def _on_buscar(self, _event=None):
        termino = self._entry_busqueda.get().strip()
        if not termino:
            return
        resultados = ProductoRepository.buscar(termino)
        if not resultados:
            self._set_status("No encontrado", error=True)
            return
        if len(resultados) == 1:
            self._agregar_al_carrito(resultados[0])
            self._entry_busqueda.delete(0, "end")
        else:
            DialogSeleccion(self, resultados,
                            on_seleccion=self._on_producto_seleccionado)

    def _on_producto_seleccionado(self, producto):
        self._agregar_al_carrito(producto)
        self._entry_busqueda.delete(0, "end")
        self._entry_busqueda.focus()

    def _agregar_al_carrito(self, producto):
        id_p, ref, nombre, precio, stock = producto
        msg = self.carrito.agregar(id_p, ref, nombre, precio, stock)
        self._set_status(msg, error=msg.startswith("⚠"))
        self._refrescar_tabla()

    def _refrescar_tabla(self):
        for i in self._tabla_carrito.get_children():
            self._tabla_carrito.delete(i)
        for ref, item in self.carrito.items.items():
            self._tabla_carrito.insert(
                "", "end", iid=ref,
                values=(item.id_producto, ref, item.nombre,
                        f"$ {item.precio:,.0f}", item.cantidad,
                        f"$ {item.subtotal:,.0f}"),
            )
        total = self.carrito.total
        self._lbl_total.configure(text=f"$ {total:,.0f}")

        n = self.carrito.cantidad_lineas
        if n == 0:
            self._lbl_badge.configure(text="Carrito vacío",
                                      text_color=C["muted"])
        else:
            self._lbl_badge.configure(
                text=f"🛒  {n} {'línea' if n == 1 else 'líneas'}  ·  $ {total:,.0f}",
                text_color=C["success"],
            )

    def _editar_item(self):
        sel = self._tabla_carrito.selection()
        if not sel:
            return
        ref  = sel[0]
        item = self.carrito.items.get(ref)
        if not item:
            return

        vent = ctk.CTkToplevel(self)
        vent.title("Editar cantidad")
        vent.geometry("340x220")
        vent.configure(fg_color=C["bg"])
        vent.attributes("-topmost", True)
        vent.grab_set()
        vent.resizable(False, False)

        ctk.CTkLabel(vent, text=item.nombre, font=FONT["h2"],
                     text_color=C["text"],
                     wraplength=300).pack(pady=(24, 4))
        ctk.CTkLabel(vent, text=f"Stock disponible: {item.stock_max}",
                     font=FONT["small"],
                     text_color=C["muted"]).pack()

        entry = ctk.CTkEntry(vent, font=("Segoe UI Black", 28),
                             justify="center", height=52,
                             fg_color=C["card"], border_color=C["border"],
                             text_color=C["text"])
        entry.insert(0, str(item.cantidad))
        entry.pack(padx=40, fill="x", pady=14)
        entry.focus()
        entry.select_range(0, "end")

        def guardar(_event=None):
            try:
                nueva = int(entry.get())
            except ValueError:
                return
            err = self.carrito.actualizar_cantidad(ref, nueva)
            if err:
                messagebox.showwarning("Error", err, parent=vent)
                return
            self._refrescar_tabla()
            vent.destroy()

        entry.bind("<Return>", guardar)
        ctk.CTkButton(vent, text="Guardar", font=FONT["body"], height=38,
                      fg_color=C["primary"], hover_color=C["primary_h"],
                      corner_radius=8, command=guardar).pack(padx=40, fill="x")

    def _eliminar_item(self):
        sel = self._tabla_carrito.selection()
        if sel:
            self.carrito.eliminar(sel[0])
            self._refrescar_tabla()
            self._entry_busqueda.focus()

    def _vaciar_carrito(self):
        if not self.carrito.vacio:
            if messagebox.askyesno("Confirmar", "¿Vaciar todo el carrito?",
                                   parent=self):
                self.carrito.vaciar()
                self._refrescar_tabla()
                self._set_status("Carrito vaciado")

    # ── Cobro ──────────────────────────────────────────────────────────────────

    def _abrir_cobro(self):
        if self.carrito.vacio:
            messagebox.showwarning("Carrito vacío",
                                   "Agrega productos antes de cobrar.",
                                   parent=self)
            return
        VentanaCobro(self, self.carrito, on_exito=self._post_venta)

    def _post_venta(self, datos: dict, total: float, metodo: str):
        self.carrito.vaciar()
        self._refrescar_tabla()
        self._set_status("✓ Venta registrada correctamente")
        self._entry_busqueda.focus()
        VentanaComprobante(self, datos, total, metodo)

    # ── Helper ─────────────────────────────────────────────────────────────────

    def _set_status(self, msg: str, error: bool = False):
        self._lbl_status.configure(
            text=msg,
            text_color=C["danger"] if error else C["success"],
        )