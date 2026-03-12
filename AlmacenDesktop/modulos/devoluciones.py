"""
Panel de Gestión de Movimientos e Inventario.
Maneja Ventas manuales, Devoluciones y Cambios de prenda.
"""
from __future__ import annotations

import customtkinter as ctk
from tkinter import ttk, messagebox, StringVar

from repositories.producto_repo import ProductoRepository
from repositories.movimiento_repo import MovimientoRepository
from modulos.dialogs.seleccion_dialog import DialogSeleccion


class SimpleVar:
    """Variable simple compatible con CTkRadioButton sin necesidad de tkinter.StringVar"""
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
# PALETA – Dark Professional (consistente con ventas.py)
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
    "orange":    "#f97316",
    "orange_h":  "#ea580c",
    "text":      "#f1f5f9",
    "text_dim":  "#94a3b8",
    "muted":     "#64748b",
    "border":    "#2d3348",
    "entra_bg":  "#052e16",
    "sale_bg":   "#450a0a",
}

FONT = {
    "h1":    ("Segoe UI Black",    24),
    "h2":    ("Segoe UI Semibold", 15),
    "h3":    ("Segoe UI Semibold", 13),
    "body":  ("Segoe UI",          13),
    "small": ("Segoe UI",          11),
    "mono":  ("Consolas",          13),
    "total": ("Segoe UI Black",    32),
}

# Tipos de movimiento
TIPOS = {
    "VENTA":      {"label": "Venta Manual / Salida",         "color": C["danger"],  "accion_auto": "SALE"},
    "DEVOLUCION": {"label": "Entrada por Devolución",        "color": C["success"], "accion_auto": "ENTRA"},
    "CAMBIO":     {"label": "Cambio de Prenda (Mano a Mano)","color": C["orange"],  "accion_auto": None},
}


def _treeview_style(name: str, row_height: int = 40):
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
# PANEL DEVOLUCIONES
# ══════════════════════════════════════════════════════════════════════════════

class PanelDevoluciones(ctk.CTkFrame):

    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=C["bg"])
        self.controller  = controller
        self._items: dict = {}

        _treeview_style("Mov.Treeview",  row_height=42)
        _treeview_style("Hist.Treeview", row_height=38)

        self._build_cabecera()
        self._build_tabs()

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

        ctk.CTkLabel(bar, text="MOVIMIENTOS E INVENTARIO",
                     font=FONT["h1"],
                     text_color=C["text"]).pack(side="left", padx=8)

        # Badge de tipo activo
        self._lbl_tipo_badge = ctk.CTkLabel(
            bar, text="● VENTA",
            font=("Segoe UI Semibold", 12),
            text_color=C["danger"],
            fg_color=C["card"],
            corner_radius=6, padx=12, pady=4,
        )
        self._lbl_tipo_badge.pack(side="right", padx=18)

    # ── Pestañas ───────────────────────────────────────────────────────────────

    def _build_tabs(self):
        self._tabs = ctk.CTkTabview(
            self,
            fg_color=C["surface"],
            segmented_button_fg_color=C["card"],
            segmented_button_selected_color=C["orange"],
            segmented_button_selected_hover_color=C["orange_h"],
            segmented_button_unselected_color=C["card"],
            segmented_button_unselected_hover_color=C["card_alt"],
            text_color=C["text_dim"],
        )
        self._tabs.pack(fill="both", expand=True, padx=12, pady=(6, 12))

        self._tab_op   = self._tabs.add("  🔄  Nueva Operación  ")
        self._tab_hist = self._tabs.add("  📜  Historial  ")

        self._build_tab_operacion()
        self._build_tab_historial()

        self._tabs.configure(command=self._on_tab_cambio)

    def _on_tab_cambio(self, _=None):
        if "Historial" in self._tabs.get():
            self.cargar_historial()

    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA 1 – NUEVA OPERACIÓN
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_operacion(self):
        wrapper = ctk.CTkFrame(self._tab_op, fg_color="transparent")
        wrapper.pack(fill="both", expand=True)
        self._build_panel_controles(wrapper)
        self._build_panel_lista(wrapper)

    # ── Panel izquierdo ────────────────────────────────────────────────────────

    def _build_panel_controles(self, parent):
        panel = ctk.CTkFrame(parent, width=320,
                             fg_color=C["card"], corner_radius=14)
        panel.pack(side="left", fill="y", padx=(0, 8), pady=4)
        panel.pack_propagate(False)

        # ── 1. Tipo de movimiento ──
        ctk.CTkLabel(panel, text="TIPO DE MOVIMIENTO",
                     font=FONT["h3"],
                     text_color=C["muted"]).pack(anchor="w", padx=20, pady=(20, 10))

        self._tipo_var = SimpleVar(value="VENTA")

        for tipo, info in TIPOS.items():
            btn = ctk.CTkRadioButton(
                panel,
                text=info["label"],
                variable=self._tipo_var,
                value=tipo,
                font=FONT["body"],
                text_color=C["text"],
                fg_color=info["color"],
                hover_color=info["color"],
                border_color=C["border"],
                command=self._on_tipo_cambio,
            )
            btn.pack(anchor="w", padx=20, pady=5)

        # Panel dirección (solo visible en CAMBIO)
        self._panel_dir = ctk.CTkFrame(panel, fg_color=C["surface"], corner_radius=10)

        ctk.CTkLabel(self._panel_dir, text="¿QUÉ ESTÁS HACIENDO AHORA?",
                     font=("Segoe UI Semibold", 11),
                     text_color=C["muted"]).pack(anchor="w", padx=14, pady=(12, 6))

        self._accion_var = SimpleVar(value="ENTRA")

        dir_row = ctk.CTkFrame(self._panel_dir, fg_color="transparent")
        dir_row.pack(fill="x", padx=14, pady=(0, 12))

        ctk.CTkRadioButton(
            dir_row, text="⬇  Recibo prenda",
            variable=self._accion_var, value="ENTRA",
            font=FONT["body"], text_color=C["success"],
            fg_color=C["success"], hover_color=C["success"],
            border_color=C["border"],
        ).pack(side="left", padx=(0, 16))

        ctk.CTkRadioButton(
            dir_row, text="⬆  Entrego nueva",
            variable=self._accion_var, value="SALE",
            font=FONT["body"], text_color=C["danger"],
            fg_color=C["danger"], hover_color=C["danger"],
            border_color=C["border"],
        ).pack(side="left")

        # Separador
        ctk.CTkFrame(panel, height=1, fg_color=C["border"]).pack(fill="x", padx=16, pady=10)

        # ── 2. Cliente / Motivo ──
        ctk.CTkLabel(panel, text="CLIENTE / MOTIVO",
                     font=FONT["h3"],
                     text_color=C["muted"]).pack(anchor="w", padx=20, pady=(4, 6))

        self._entry_cliente = ctk.CTkEntry(
            panel,
            placeholder_text="Nombre o motivo...",
            height=40, font=FONT["body"],
            fg_color=C["surface"],
            border_color=C["border"],
            text_color=C["text"],
            placeholder_text_color=C["muted"],
            corner_radius=8,
        )
        self._entry_cliente.pack(fill="x", padx=16, pady=(0, 10))

        # ── 3. Buscar producto ──
        ctk.CTkLabel(panel, text="BUSCAR PRODUCTO",
                     font=FONT["h3"],
                     text_color=C["muted"]).pack(anchor="w", padx=20, pady=(4, 6))

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
        self._entry_busqueda.pack(fill="x", padx=16)
        self._entry_busqueda.bind("<Return>", self._on_buscar)

        self._lbl_status = ctk.CTkLabel(
            panel, text="",
            font=FONT["small"],
            text_color=C["success"],
            wraplength=270, justify="center",
        )
        self._lbl_status.pack(pady=6)

        # Separador
        ctk.CTkFrame(panel, height=1, fg_color=C["border"]).pack(fill="x", padx=16, pady=4)

        # Botón limpiar
        ctk.CTkButton(
            panel, text="🧹  Limpiar Lista",
            font=FONT["body"], height=38,
            fg_color=C["surface"], hover_color=C["danger"],
            text_color=C["text_dim"],
            border_width=1, border_color=C["border"],
            corner_radius=8,
            command=self._limpiar,
        ).pack(fill="x", padx=16, pady=4)

        # Botón finalizar (fijo abajo)
        self._btn_procesar = ctk.CTkButton(
            panel,
            text="✓  FINALIZAR REGISTRO",
            font=("Segoe UI Black", 15),
            height=52,
            fg_color=C["orange"],
            hover_color=C["orange_h"],
            text_color="white",
            corner_radius=10,
            command=self._procesar,
        )
        self._btn_procesar.pack(side="bottom", fill="x", padx=16, pady=16)

    # ── Panel derecho: lista de items ─────────────────────────────────────────

    def _build_panel_lista(self, parent):
        panel = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=14)
        panel.pack(side="right", fill="both", expand=True, pady=4)

        ctk.CTkLabel(panel, text="ITEMS DEL MOVIMIENTO",
                     font=FONT["h3"],
                     text_color=C["muted"]).pack(anchor="w", padx=20, pady=(20, 8))

        cols = ("flujo", "ref", "nombre", "precio", "cant", "subtotal")
        self._tabla = ttk.Treeview(panel, columns=cols,
                                   show="headings", style="Mov.Treeview")

        self._tabla.heading("flujo",    text="FLUJO")
        self._tabla.heading("ref",      text="CÓDIGO")
        self._tabla.heading("nombre",   text="DESCRIPCIÓN")
        self._tabla.heading("precio",   text="PRECIO U.")
        self._tabla.heading("cant",     text="CANT")
        self._tabla.heading("subtotal", text="SUBTOTAL")

        self._tabla.column("flujo",    width=90,  anchor="center")
        self._tabla.column("ref",      width=100)
        self._tabla.column("nombre",   width=260)
        self._tabla.column("precio",   width=110, anchor="e")
        self._tabla.column("cant",     width=60,  anchor="center")
        self._tabla.column("subtotal", width=120, anchor="e")

        # Tags de color por flujo
        self._tabla.tag_configure("ENTRA", foreground="#4ade80")   # verde
        self._tabla.tag_configure("SALE",  foreground="#f87171")   # rojo

        sb = ctk.CTkScrollbar(panel, command=self._tabla.yview)
        self._tabla.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(0, 8), pady=(0, 8))
        self._tabla.pack(fill="both", expand=True, padx=(12, 0))

        # Footer balance
        footer = ctk.CTkFrame(panel, fg_color=C["surface"],
                              corner_radius=12, height=80)
        footer.pack(fill="x", padx=12, pady=12)
        footer.pack_propagate(False)

        col_bal = ctk.CTkFrame(footer, fg_color="transparent")
        col_bal.pack(side="left", padx=20)
        ctk.CTkLabel(col_bal, text="BALANCE",
                     font=FONT["small"],
                     text_color=C["muted"]).pack(anchor="w")
        self._lbl_balance = ctk.CTkLabel(col_bal,
                                         text="$ 0",
                                         font=FONT["total"],
                                         text_color=C["text"])
        self._lbl_balance.pack()

        self._lbl_balance_desc = ctk.CTkLabel(
            footer, text="",
            font=FONT["small"],
            text_color=C["muted"],
        )
        self._lbl_balance_desc.pack(side="right", padx=20)

    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA 2 – HISTORIAL
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_historial(self):
        top = ctk.CTkFrame(self._tab_hist, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=10)

        ctk.CTkLabel(top, text="Movimientos registrados en este dispositivo",
                     font=FONT["body"],
                     text_color=C["muted"]).pack(side="left")

        ctk.CTkButton(
            top, text="↺  Refrescar", width=120, height=38,
            font=FONT["body"],
            fg_color=C["card"], hover_color=C["primary"],
            border_width=1, border_color=C["border"],
            text_color=C["text"], corner_radius=8,
            command=self.cargar_historial,
        ).pack(side="right")

        frame = ctk.CTkFrame(self._tab_hist, fg_color=C["card"], corner_radius=12)
        frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        cols = ("id", "fecha", "tipo", "cliente", "resumen")
        self._tabla_hist = ttk.Treeview(frame, columns=cols,
                                        show="headings", style="Hist.Treeview")
        self._tabla_hist.heading("id",      text="#")
        self._tabla_hist.heading("fecha",   text="FECHA")
        self._tabla_hist.heading("tipo",    text="TIPO")
        self._tabla_hist.heading("cliente", text="CLIENTE / MOTIVO")
        self._tabla_hist.heading("resumen", text="DETALLE")

        self._tabla_hist.column("id",      width=60,  anchor="center")
        self._tabla_hist.column("fecha",   width=160)
        self._tabla_hist.column("tipo",    width=110)
        self._tabla_hist.column("cliente", width=160)
        self._tabla_hist.column("resumen", width=420)

        self._tabla_hist.tag_configure("VENTA",      foreground="#f87171")
        self._tabla_hist.tag_configure("DEVOLUCION", foreground="#4ade80")
        self._tabla_hist.tag_configure("CAMBIO",     foreground="#fbbf24")

        self._tabla_hist.pack(fill="both", expand=True, padx=6, pady=6)

    def cargar_historial(self):
        for i in self._tabla_hist.get_children():
            self._tabla_hist.delete(i)
        for f in MovimientoRepository.historial():
            import json as _json
            det = _json.loads(f[3])
            resumen = "  |  ".join(
                f"{'↓' if v.get('accion') == 'ENTRA' else '↑'} "
                f"{v.get('cant', 1)}× {v.get('nombre', '')[:18]}"
                for v in det.values()
            )
            partes  = f[2].split(" - ", 1)
            tipo    = partes[0].strip()
            cliente = partes[1].strip() if len(partes) > 1 else "N/A"
            tag     = tipo if tipo in ("VENTA", "DEVOLUCION", "CAMBIO") else ""
            self._tabla_hist.insert("", "end",
                                    values=(f[0], f[1], tipo, cliente, resumen),
                                    tags=(tag,))

    # ══════════════════════════════════════════════════════════════════════════
    # LÓGICA DE OPERACIÓN
    # ══════════════════════════════════════════════════════════════════════════

    def _on_tipo_cambio(self):
        tipo = self._tipo_var.get()
        info = TIPOS[tipo]

        # Mostrar/ocultar panel de dirección
        if tipo == "CAMBIO":
            self._panel_dir.pack(fill="x", padx=16, pady=(0, 8),
                                 after=list(self._panel_dir.master.children.values())[2])
        else:
            self._panel_dir.pack_forget()

        # Actualizar badge
        self._lbl_tipo_badge.configure(
            text=f"●  {tipo}",
            text_color=info["color"],
        )
        self._limpiar()

    def _on_buscar(self, _event=None):
        termino = self._entry_busqueda.get().strip()
        if not termino:
            return
        resultados = ProductoRepository.buscar(termino)
        if not resultados:
            self._set_status("No encontrado", error=True)
            return
        if len(resultados) == 1:
            self._agregar_item(resultados[0])
            self._entry_busqueda.delete(0, "end")
        else:
            DialogSeleccion(self, resultados,
                            on_seleccion=self._on_producto_seleccionado)

    def _on_producto_seleccionado(self, producto):
        self._agregar_item(producto)
        self._entry_busqueda.delete(0, "end")
        self._entry_busqueda.focus()

    def _agregar_item(self, producto):
        id_p, ref, nombre, precio, stock = producto
        tipo = self._tipo_var.get()

        # Determinar dirección
        accion = (self._accion_var.get()
                  if tipo == "CAMBIO"
                  else TIPOS[tipo]["accion_auto"])

        # Validar stock disponible si sale
        if accion == "SALE" and stock <= 0:
            messagebox.showwarning("Sin stock",
                                   f"No hay existencias de:\n{nombre}", parent=self)
            return

        clave = f"{ref}_{accion}"
        if clave in self._items:
            self._items[clave]["cant"] += 1
        else:
            self._items[clave] = {
                "id": id_p, "ref": ref, "nombre": nombre,
                "precio": precio, "cant": 1, "accion": accion,
            }

        self._refrescar_tabla()
        self._set_status(f"✓ {'[↓ ENTRA]' if accion == 'ENTRA' else '[↑ SALE]'}  {nombre}")

    def _refrescar_tabla(self):
        for i in self._tabla.get_children():
            self._tabla.delete(i)

        balance = 0.0
        for v in self._items.values():
            subt = v["precio"] * v["cant"]
            balance += subt if v["accion"] == "SALE" else -subt
            flujo = "↓ ENTRA" if v["accion"] == "ENTRA" else "↑ SALE"
            self._tabla.insert("", "end",
                               values=(flujo, v["ref"], v["nombre"],
                                       f"$ {v['precio']:,.0f}", v["cant"],
                                       f"$ {subt:,.0f}"),
                               tags=(v["accion"],))

        # Actualizar balance
        self._lbl_balance.configure(text=f"$ {abs(balance):,.0f}")
        if balance > 0:
            self._lbl_balance.configure(text_color=C["danger"])
            self._lbl_balance_desc.configure(
                text="Cliente debe pagar diferencia", text_color=C["danger"])
        elif balance < 0:
            self._lbl_balance.configure(text_color=C["success"])
            self._lbl_balance_desc.configure(
                text="Saldo a favor del cliente", text_color=C["success"])
        else:
            self._lbl_balance.configure(text_color=C["text"])
            self._lbl_balance_desc.configure(text="Sin diferencia", text_color=C["muted"])

    def _limpiar(self):
        self._items.clear()
        for i in self._tabla.get_children():
            self._tabla.delete(i)
        self._lbl_balance.configure(text="$ 0", text_color=C["text"])
        self._lbl_balance_desc.configure(text="")
        self._lbl_status.configure(text="")

    def _procesar(self):
        if not self._items:
            messagebox.showwarning("Lista vacía",
                                   "Agrega al menos un producto.", parent=self)
            return

        cliente = self._entry_cliente.get().strip() or "General"
        tipo    = self._tipo_var.get()

        if not messagebox.askyesno(
            "Confirmar",
            f"¿Aplicar este movimiento ({tipo}) al inventario local?",
            parent=self,
        ):
            return

        try:
            MovimientoRepository.guardar(tipo, cliente, self._items)
            messagebox.showinfo("Éxito",
                                "Movimiento registrado y stock actualizado.",
                                parent=self)
            self._entry_cliente.delete(0, "end")
            self._entry_busqueda.delete(0, "end")
            self._limpiar()
            self._entry_busqueda.focus()
        except Exception as exc:
            messagebox.showerror("Error",
                                 f"No se pudo guardar el movimiento:\n{exc}",
                                 parent=self)

    # ── Helper ─────────────────────────────────────────────────────────────────

    def _set_status(self, msg: str, error: bool = False):
        self._lbl_status.configure(
            text=msg,
            text_color=C["danger"] if error else C["success"],
        )