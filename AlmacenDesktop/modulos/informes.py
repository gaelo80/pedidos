"""
Panel de Informes y Cierre de Caja.
Arqueo por período, detalle de transacciones y reporte Z.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import webbrowser
from datetime import datetime
from tkinter import ttk, messagebox, filedialog
from typing import Optional

import customtkinter as ctk

from database import obtener_conexion

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
    "purple":    "#8b5cf6",
    "purple_h":  "#7c3aed",
    "text":      "#f1f5f9",
    "text_dim":  "#94a3b8",
    "muted":     "#64748b",
    "border":    "#2d3348",
    "wa":        "#25D366",
    "wa_h":      "#128C7E",
}

FONT = {
    "h1":    ("Segoe UI Black",    24),
    "h2":    ("Segoe UI Semibold", 15),
    "h3":    ("Segoe UI Semibold", 13),
    "body":  ("Segoe UI",          13),
    "small": ("Segoe UI",          11),
    "mono":  ("Consolas",          13),
    "kpi":   ("Segoe UI Black",    28),
    "kpi_s": ("Segoe UI Black",    20),
    "ticket":("Consolas",          13),
}

PERIODOS = ["Hoy", "Ayer", "Esta Semana", "Todo el Histórico"]


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
# PANEL INFORMES
# ══════════════════════════════════════════════════════════════════════════════

class PanelInformes(ctk.CTkFrame):

    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=C["bg"])
        self.controller  = controller
        self.datos_cierre: dict = {}

        _treeview_style("Inf.Treeview",  row_height=40)
        _treeview_style("Det.Treeview",  row_height=38)

        self._build_cabecera()
        self._build_filtros()
        self._build_tabs()

        self.generar_informe()

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

        ctk.CTkLabel(bar, text="INFORMES Y CIERRE DE CAJA",
                     font=FONT["h1"],
                     text_color=C["text"]).pack(side="left", padx=8)

        self._lbl_actualizado = ctk.CTkLabel(
            bar, text="",
            font=FONT["small"],
            text_color=C["muted"],
        )
        self._lbl_actualizado.pack(side="right", padx=18)

    # ── Barra de filtros ───────────────────────────────────────────────────────

    def _build_filtros(self):
        bar = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=12)
        bar.pack(fill="x", padx=12, pady=(10, 4))

        ctk.CTkLabel(bar, text="📅  PERÍODO:",
                     font=FONT["h3"],
                     text_color=C["muted"]).pack(side="left", padx=(16, 8), pady=12)

        self._seg_periodo = ctk.CTkSegmentedButton(
            bar,
            values=PERIODOS,
            selected_color=C["purple"],
            selected_hover_color=C["purple_h"],
            unselected_color=C["surface"],
            unselected_hover_color=C["card_alt"],
            text_color=C["text"],
            font=FONT["body"],
            height=38,
            command=lambda _: self.generar_informe(),
        )
        self._seg_periodo.set("Hoy")
        self._seg_periodo.pack(side="left", padx=8)

        ctk.CTkButton(
            bar, text="↺  Recargar", width=120, height=38,
            font=FONT["body"],
            fg_color=C["surface"], hover_color=C["primary"],
            border_width=1, border_color=C["border"],
            text_color=C["text"], corner_radius=8,
            command=self.generar_informe,
        ).pack(side="right", padx=16)

    # ── Pestañas ───────────────────────────────────────────────────────────────

    def _build_tabs(self):
        self._tabs = ctk.CTkTabview(
            self,
            fg_color=C["surface"],
            segmented_button_fg_color=C["card"],
            segmented_button_selected_color=C["purple"],
            segmented_button_selected_hover_color=C["purple_h"],
            segmented_button_unselected_color=C["card"],
            segmented_button_unselected_hover_color=C["card_alt"],
            text_color=C["text_dim"],
        )
        self._tabs.pack(fill="both", expand=True, padx=12, pady=(4, 12))

        self._tab_arqueo = self._tabs.add("  📊  Arqueo de Caja  ")
        self._tab_mov    = self._tabs.add("  🧾  Transacciones  ")

        self._build_tab_arqueo()
        self._build_tab_movimientos()

    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA 1 – ARQUEO
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_arqueo(self):
        body = ctk.CTkScrollableFrame(self._tab_arqueo, fg_color="transparent")
        body.pack(fill="both", expand=True)

        # ── Fila 1: métodos de pago ──
        row1 = ctk.CTkFrame(body, fg_color="transparent")
        row1.pack(fill="x", pady=(10, 6))

        self._kpi_efectivo = self._kpi(row1, "💵  Ventas Efectivo",    "$ 0", C["success"])
        self._kpi_tarjeta  = self._kpi(row1, "💳  Ventas Tarjeta",     "$ 0", C["primary"])
        self._kpi_transf   = self._kpi(row1, "📱  Transferencias",     "$ 0", C["purple"])

        # ── Fila 2: ajustes y caja ──
        row2 = ctk.CTkFrame(body, fg_color="transparent")
        row2.pack(fill="x", pady=6)

        self._kpi_excedentes = self._kpi(row2, "📈  Excedentes Cobrados", "$ 0", C["warning"])
        self._kpi_saldos     = self._kpi(row2, "📉  Dinero Devuelto",     "$ 0", C["danger"])
        self._kpi_caja       = self._kpi(row2, "💰  TOTAL NETO EN CAJA",  "$ 0", C["success"],
                                         grande=True)

        # ── Botón cierre ──
        ctk.CTkButton(
            body,
            text="🔒  REALIZAR CIERRE DE CAJA  (Reporte Z)",
            font=("Segoe UI Black", 18),
            height=64,
            fg_color=C["danger"],
            hover_color=C["danger_h"],
            text_color="white",
            corner_radius=12,
            command=self._abrir_cierre,
        ).pack(fill="x", padx=4, pady=24)

    def _kpi(self, parent, titulo: str, valor: str, color: str,
             grande: bool = False) -> ctk.CTkLabel:
        card = ctk.CTkFrame(parent, fg_color=C["card"],
                            corner_radius=14, border_width=1,
                            border_color=C["border"])
        card.pack(side="left", fill="both", expand=True, padx=5)

        ctk.CTkLabel(card, text=titulo,
                     font=FONT["h3"],
                     text_color=C["muted"]).pack(anchor="w", padx=18, pady=(16, 4))
        lbl = ctk.CTkLabel(card, text=valor,
                           font=FONT["kpi"] if grande else FONT["kpi_s"],
                           text_color=color)
        lbl.pack(anchor="w", padx=18, pady=(0, 16))
        return lbl

    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA 2 – TRANSACCIONES
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_movimientos(self):
        hint = ctk.CTkFrame(self._tab_mov, fg_color=C["card_alt"],
                            corner_radius=8, height=34)
        hint.pack(fill="x", padx=8, pady=(8, 4))
        hint.pack_propagate(False)
        ctk.CTkLabel(hint,
                     text="💡  Doble clic en cualquier fila para ver el detalle completo",
                     font=FONT["small"],
                     text_color=C["muted"]).pack(side="left", padx=14)

        frame = ctk.CTkFrame(self._tab_mov, fg_color=C["card"], corner_radius=12)
        frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        cols = ("_id", "_origen", "fecha", "tipo", "cliente",
                "metodo", "descripcion", "monto")
        self._tabla = ttk.Treeview(frame, columns=cols,
                                   show="headings", style="Inf.Treeview")

        self._tabla.heading("fecha",       text="FECHA")
        self._tabla.heading("tipo",        text="OPERACIÓN")
        self._tabla.heading("cliente",     text="CLIENTE / MOTIVO")
        self._tabla.heading("metodo",      text="MÉTODO")
        self._tabla.heading("descripcion", text="RESUMEN")
        self._tabla.heading("monto",       text="MONTO")

        self._tabla.column("_id",         width=0,   stretch=False)
        self._tabla.column("_origen",     width=0,   stretch=False)
        self._tabla.column("fecha",       width=150)
        self._tabla.column("tipo",        width=140, anchor="center")
        self._tabla.column("cliente",     width=160)
        self._tabla.column("metodo",      width=110, anchor="center")
        self._tabla.column("descripcion", width=250)
        self._tabla.column("monto",       width=120, anchor="e")

        self._tabla.tag_configure("ingreso", foreground="#4ade80")
        self._tabla.tag_configure("egreso",  foreground="#f87171")
        self._tabla.tag_configure("neutro",  foreground=C["muted"])

        sb = ctk.CTkScrollbar(frame, command=self._tabla.yview)
        self._tabla.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(0, 8), pady=8)
        self._tabla.pack(fill="both", expand=True, padx=(8, 0), pady=8)

        self._tabla.bind("<Double-1>", self._ver_detalle)

    # ══════════════════════════════════════════════════════════════════════════
    # LÓGICA DE DATOS
    # ══════════════════════════════════════════════════════════════════════════

    def _fecha_filtro(self) -> str:
        """Retorna prefijo de fecha para el WHERE, o '' para todo."""
        p = self._seg_periodo.get()
        if p == "Hoy":
            return datetime.now().strftime("%Y-%m-%d")
        if p == "Ayer":
            return time.strftime("%Y-%m-%d",
                                 time.localtime(time.time() - 86_400))
        if p == "Esta Semana":
            # Lunes de la semana actual
            hoy = datetime.now()
            lunes = hoy.replace(hour=0, minute=0, second=0,
                                microsecond=0)
            lunes = lunes.replace(day=hoy.day - hoy.weekday())
            return lunes.strftime("%Y-%m-%d")
        return ""  # Todo el histórico

    def generar_informe(self):
        for i in self._tabla.get_children():
            self._tabla.delete(i)

        fecha_filtro = self._fecha_filtro()
        totales = {"EFECTIVO": 0.0, "TARJETA": 0.0, "TRANSFERENCIA": 0.0}
        excedentes = 0.0
        saldos     = 0.0

        conn   = obtener_conexion()
        cursor = conn.cursor()

        # ── 1. Ventas POS ──────────────────────────────────────────────────────
        q_ventas = (
            "SELECT id_venta, fecha, total, metodo_pago, detalles "
            "FROM ventas_pendientes_sincronizar"
            + (" WHERE fecha LIKE ?" if fecha_filtro else "")
        )
        params = (f"{fecha_filtro}%",) if fecha_filtro else ()
        cursor.execute(q_ventas, params)

        for id_v, fecha, total, metodo, det_json in cursor.fetchall():
            metodo_k = self._normalizar_metodo(metodo)
            totales[metodo_k] += total

            cliente_nombre = "Consumidor Final"
            resumen        = "Venta POS"
            try:
                datos = json.loads(det_json)
                items  = datos.get("items", datos)
                cli    = datos.get("cliente", {})
                if cli and cli.get("nombre"):
                    cliente_nombre = cli["nombre"]
                resumen = f"Venta — {len(items)} ítem(s)"
            except Exception:
                pass

            self._tabla.insert("", "end",
                               values=(id_v, "VENTA", fecha, "Venta POS",
                                       cliente_nombre, metodo_k,
                                       resumen, f"+ $ {total:,.0f}"),
                               tags=("ingreso",))

        # ── 2. Devoluciones / Cambios ──────────────────────────────────────────
        q_dev = (
            "SELECT id_devolucion, fecha, tipo, detalles "
            "FROM devoluciones_pendientes"
            + (" WHERE fecha LIKE ?" if fecha_filtro else "")
        )
        cursor.execute(q_dev, params)

        for id_d, fecha, tipo_bd, det_json in cursor.fetchall():
            partes  = tipo_bd.split(" - ", 1)
            tipo_mov = partes[0].strip()
            cliente  = partes[1].strip() if len(partes) > 1 else "General"

            try:
                det = json.loads(det_json)
            except Exception:
                continue

            balance = 0.0
            for v in det.values():
                subt   = v.get("precio", 0) * v.get("cant", 1)
                accion = v.get("accion") or (
                    "SALE" if "VENTA" in tipo_bd else "ENTRA"
                )
                balance += subt if accion == "SALE" else -subt

            if "BODEGA" in tipo_bd:
                self._tabla.insert("", "end",
                                   values=(id_d, "DEVOLUCION", fecha,
                                           "Retorno Bodega", cliente,
                                           "N/A", f"Mov: {tipo_mov}", "$ 0"),
                                   tags=("neutro",))
                continue

            if balance > 0:
                excedentes      += balance
                totales["EFECTIVO"] += balance
                self._tabla.insert("", "end",
                                   values=(id_d, "DEVOLUCION", fecha,
                                           "Cambio (Cobro)", cliente,
                                           "EFECTIVO", f"Mov: {tipo_mov}",
                                           f"+ $ {balance:,.0f}"),
                                   tags=("ingreso",))
            elif balance < 0:
                saldos += abs(balance)
                self._tabla.insert("", "end",
                                   values=(id_d, "DEVOLUCION", fecha,
                                           "Dev / Nota", cliente,
                                           "EFECTIVO", f"Mov: {tipo_mov}",
                                           f"- $ {abs(balance):,.0f}"),
                                   tags=("egreso",))
            else:
                self._tabla.insert("", "end",
                                   values=(id_d, "DEVOLUCION", fecha,
                                           "Mano a Mano", cliente,
                                           "N/A", f"Mov: {tipo_mov}", "$ 0"),
                                   tags=("neutro",))

        conn.close()

        # ── Actualizar KPIs ────────────────────────────────────────────────────
        total_caja = totales["EFECTIVO"] - saldos
        self.datos_cierre = {
            "periodo":          self._seg_periodo.get(),
            "fecha_cierre":     datetime.now().strftime("%Y-%m-%d %H:%M"),
            "efectivo":         totales["EFECTIVO"],
            "tarjeta":          totales["TARJETA"],
            "transferencia":    totales["TRANSFERENCIA"],
            "excedentes":       excedentes,
            "saldos":           saldos,
            "total_caja_fisica": total_caja,
        }

        self._kpi_efectivo.configure(text=f"$ {totales['EFECTIVO']:,.0f}")
        self._kpi_tarjeta.configure( text=f"$ {totales['TARJETA']:,.0f}")
        self._kpi_transf.configure(  text=f"$ {totales['TRANSFERENCIA']:,.0f}")
        self._kpi_excedentes.configure(text=f"$ {excedentes:,.0f}")
        self._kpi_saldos.configure(    text=f"$ {saldos:,.0f}")
        self._kpi_caja.configure(
            text=f"$ {total_caja:,.0f}",
            text_color=C["danger"] if total_caja < 0 else C["success"],
        )
        self._lbl_actualizado.configure(
            text=f"↺ {datetime.now().strftime('%H:%M:%S')}"
        )

    @staticmethod
    def _normalizar_metodo(metodo: Optional[str]) -> str:
        if not metodo:
            return "EFECTIVO"
        m = metodo.upper()
        if "TARJETA" in m or "CRÉDITO" in m or "DEBITO" in m or "DÉBITO" in m:
            return "TARJETA"
        if "TRANSFER" in m or "NEQUI" in m or "DAVIPLATA" in m:
            return "TRANSFERENCIA"
        return "EFECTIVO"

    # ══════════════════════════════════════════════════════════════════════════
    # DETALLE DE TRANSACCIÓN (doble clic)
    # ══════════════════════════════════════════════════════════════════════════

    def _ver_detalle(self, _event=None):
        sel = self._tabla.selection()
        if not sel:
            return

        valores   = self._tabla.item(sel[0])["values"]
        id_bd     = valores[0]
        origen    = valores[1]
        fecha_mov = valores[2]

        conn   = obtener_conexion()
        cursor = conn.cursor()

        vent = ctk.CTkToplevel(self)
        vent.geometry("700x560")
        vent.configure(fg_color=C["bg"])
        vent.attributes("-topmost", True)
        vent.grab_set()
        vent.resizable(False, False)

        _treeview_style("Det.Treeview", row_height=38)

        if origen == "VENTA":
            vent.title(f"Venta #{id_bd}")
            cursor.execute(
                "SELECT detalles, total, metodo_pago "
                "FROM ventas_pendientes_sincronizar WHERE id_venta=?",
                (id_bd,)
            )
            res = cursor.fetchone()
            if not res:
                conn.close(); vent.destroy(); return

            det_json, total, metodo = res
            datos  = json.loads(det_json)
            items  = datos.get("items", datos)
            cli    = datos.get("cliente", {})

            # Cabecera
            hdr = ctk.CTkFrame(vent, fg_color=C["surface"],
                               corner_radius=0, height=80)
            hdr.pack(fill="x")
            ctk.CTkLabel(hdr, text=f"COMPROBANTE DE VENTA  #{id_bd}",
                         font=FONT["h2"],
                         text_color=C["text"]).pack(anchor="w", padx=20, pady=(14, 2))
            ctk.CTkLabel(hdr, text=fecha_mov,
                         font=FONT["small"],
                         text_color=C["muted"]).pack(anchor="w", padx=20)

            # Datos del cliente (si tiene FE)
            if cli and cli.get("nombre"):
                cf = ctk.CTkFrame(vent, fg_color=C["card_alt"], corner_radius=0)
                cf.pack(fill="x")
                info = (
                    f"  👤  {cli.get('nombre')}   |   Doc: {cli.get('documento', 'N/A')}"
                    f"   |   {cli.get('correo', '')}   |   {cli.get('telefono', '')}"
                )
                if cli.get("requiere_fe"):
                    info += "   ⚠️  Requiere Factura Electrónica DIAN"
                ctk.CTkLabel(cf, text=info, font=FONT["small"],
                             text_color=C["primary"]).pack(anchor="w", padx=4, pady=8)

            # Tabla de productos
            frame_t = ctk.CTkFrame(vent, fg_color=C["card"], corner_radius=0)
            frame_t.pack(fill="both", expand=True, padx=0, pady=0)

            cols = ("ref", "nombre", "precio", "cant", "subtotal")
            t = ttk.Treeview(frame_t, columns=cols,
                             show="headings", style="Det.Treeview", height=8)
            t.heading("ref",      text="CÓDIGO")
            t.heading("nombre",   text="DESCRIPCIÓN")
            t.heading("precio",   text="PRECIO U.")
            t.heading("cant",     text="CANT")
            t.heading("subtotal", text="SUBTOTAL")
            t.column("ref",      width=100)
            t.column("nombre",   width=260)
            t.column("precio",   width=110, anchor="e")
            t.column("cant",     width=70,  anchor="center")
            t.column("subtotal", width=120, anchor="e")
            t.pack(fill="both", expand=True, padx=8, pady=8)

            for ref, d in items.items():
                t.insert("", "end",
                         values=(ref, d["nombre"],
                                 f"$ {d.get('precio', 0):,.0f}",
                                 d.get("cant", 1),
                                 f"$ {d.get('subtotal', 0):,.0f}"))

            # Pie
            pie = ctk.CTkFrame(vent, fg_color=C["surface"],
                               corner_radius=0, height=60)
            pie.pack(fill="x", side="bottom")
            ctk.CTkLabel(pie, text=f"Método de pago:  {metodo}",
                         font=FONT["body"],
                         text_color=C["muted"]).pack(side="left", padx=20, pady=16)
            ctk.CTkLabel(pie, text=f"TOTAL  $ {total:,.0f}",
                         font=("Segoe UI Black", 22),
                         text_color=C["success"]).pack(side="right", padx=20)

        elif origen == "DEVOLUCION":
            vent.title(f"Movimiento #{id_bd}")
            cursor.execute(
                "SELECT detalles, tipo FROM devoluciones_pendientes WHERE id_devolucion=?",
                (id_bd,)
            )
            res = cursor.fetchone()
            if not res:
                conn.close(); vent.destroy(); return

            det_json, tipo_full = res
            det = json.loads(det_json)

            hdr = ctk.CTkFrame(vent, fg_color=C["surface"],
                               corner_radius=0, height=80)
            hdr.pack(fill="x")
            ctk.CTkLabel(hdr, text=f"MOVIMIENTO DE INVENTARIO  #{id_bd}",
                         font=FONT["h2"],
                         text_color=C["text"]).pack(anchor="w", padx=20, pady=(14, 2))
            ctk.CTkLabel(hdr, text=f"{fecha_mov}   —   {tipo_full}",
                         font=FONT["small"],
                         text_color=C["muted"]).pack(anchor="w", padx=20)

            frame_t = ctk.CTkFrame(vent, fg_color=C["card"], corner_radius=0)
            frame_t.pack(fill="both", expand=True)

            cols = ("flujo", "ref", "nombre", "precio", "cant", "subtotal")
            t = ttk.Treeview(frame_t, columns=cols,
                             show="headings", style="Det.Treeview", height=8)
            t.heading("flujo",    text="FLUJO")
            t.heading("ref",      text="CÓDIGO")
            t.heading("nombre",   text="DESCRIPCIÓN")
            t.heading("precio",   text="PRECIO U.")
            t.heading("cant",     text="CANT")
            t.heading("subtotal", text="SUBTOTAL")
            t.column("flujo",    width=90,  anchor="center")
            t.column("ref",      width=100)
            t.column("nombre",   width=220)
            t.column("precio",   width=110, anchor="e")
            t.column("cant",     width=70,  anchor="center")
            t.column("subtotal", width=120, anchor="e")
            t.tag_configure("ENTRA", foreground="#4ade80")
            t.tag_configure("SALE",  foreground="#f87171")
            t.pack(fill="both", expand=True, padx=8, pady=8)

            t_entra = 0.0
            t_sale  = 0.0
            for v in det.values():
                sub    = v.get("precio", 0) * v.get("cant", 1)
                accion = v.get("accion") or (
                    "SALE" if "VENTA" in tipo_full else "ENTRA"
                )
                flujo = "↓ ENTRA" if accion == "ENTRA" else "↑ SALE"
                t.insert("", "end",
                         values=(flujo, v.get("ref", ""), v.get("nombre", ""),
                                 f"$ {v.get('precio', 0):,.0f}",
                                 v.get("cant", 1),
                                 f"$ {sub:,.0f}"),
                         tags=(accion,))
                if accion == "ENTRA": t_entra += sub
                else:                 t_sale  += sub

            pie = ctk.CTkFrame(vent, fg_color=C["surface"],
                               corner_radius=0, height=60)
            pie.pack(fill="x", side="bottom")
            ctk.CTkLabel(pie, text=f"↓ Entró:  $ {t_entra:,.0f}",
                         font=FONT["h2"],
                         text_color=C["success"]).pack(side="left", padx=20, pady=16)
            ctk.CTkLabel(pie, text=f"↑ Salió:  $ {t_sale:,.0f}",
                         font=FONT["h2"],
                         text_color=C["danger"]).pack(side="right", padx=20)

        conn.close()
        ctk.CTkButton(vent, text="Cerrar",
                      font=FONT["body"], height=38, width=120,
                      fg_color=C["card"],
                      border_width=1, border_color=C["border"],
                      text_color=C["muted"],
                      corner_radius=8,
                      command=vent.destroy).pack(pady=10)

    # ══════════════════════════════════════════════════════════════════════════
    # CIERRE DE CAJA
    # ══════════════════════════════════════════════════════════════════════════

    def _abrir_cierre(self):
        self.generar_informe()
        d = self.datos_cierre

        ticket = (
            f"REPORTE DE CIERRE DE CAJA\n"
            f"{'─' * 38}\n"
            f"Período  :  {d['periodo']}\n"
            f"Fecha    :  {d['fecha_cierre']}\n"
            f"{'─' * 38}\n"
            f"Efectivo      $ {d['efectivo']:>14,.0f}\n"
            f"Tarjeta       $ {d['tarjeta']:>14,.0f}\n"
            f"Transferencia $ {d['transferencia']:>14,.0f}\n"
            f"{'─' * 38}\n"
            f"Excedentes    $ {d['excedentes']:>14,.0f}\n"
            f"Devuelto    - $ {d['saldos']:>14,.0f}\n"
            f"{'─' * 38}\n"
            f"TOTAL CAJA    $ {d['total_caja_fisica']:>14,.0f}\n"
        )

        vent = ctk.CTkToplevel(self)
        vent.title("Cierre de Caja")
        vent.geometry("460x620")
        vent.configure(fg_color=C["bg"])
        vent.attributes("-topmost", True)
        vent.grab_set()
        vent.resizable(False, False)

        # Banner
        banner = ctk.CTkFrame(vent, fg_color=C["danger"],
                              corner_radius=0, height=70)
        banner.pack(fill="x")
        ctk.CTkLabel(banner, text="🔒  CIERRE DE CAJA",
                     font=("Segoe UI Black", 20),
                     text_color="white").pack(expand=True)

        # Total destacado
        ctk.CTkLabel(vent,
                     text=f"$ {d['total_caja_fisica']:,.0f}",
                     font=("Segoe UI Black", 40),
                     text_color=C["success"] if d["total_caja_fisica"] >= 0
                     else C["danger"]).pack(pady=(16, 0))
        ctk.CTkLabel(vent, text="TOTAL NETO EN CAJA",
                     font=FONT["small"],
                     text_color=C["muted"]).pack()

        # Ticket
        frame_t = ctk.CTkFrame(vent, fg_color=C["card"], corner_radius=12)
        frame_t.pack(fill="both", expand=True, padx=20, pady=14)
        ctk.CTkLabel(frame_t, text=ticket,
                     font=FONT["ticket"],
                     text_color=C["text"],
                     justify="left").pack(anchor="w", padx=20, pady=16)

        # Botones
        ctk.CTkButton(
            vent, text="🟢  Enviar por WhatsApp al Administrador",
            font=("Segoe UI Semibold", 14), height=48,
            fg_color=C["wa"], hover_color=C["wa_h"],
            corner_radius=10,
            command=lambda: self._enviar_wa(ticket),
        ).pack(fill="x", padx=20, pady=(0, 6))

        ctk.CTkButton(
            vent, text="💾  Guardar copia en el PC (.txt)",
            font=("Segoe UI Semibold", 14), height=48,
            fg_color=C["primary"], hover_color=C["primary_h"],
            corner_radius=10,
            command=lambda: self._guardar_txt(ticket),
        ).pack(fill="x", padx=20, pady=(0, 6))

        ctk.CTkButton(
            vent, text="Cancelar",
            font=FONT["body"], height=38,
            fg_color="transparent",
            border_width=1, border_color=C["border"],
            text_color=C["muted"],
            corner_radius=10,
            command=vent.destroy,
        ).pack(fill="x", padx=20, pady=(0, 16))

    def _enviar_wa(self, ticket: str):
        tel_raw = ctk.CTkInputDialog(
            text="WhatsApp del administrador:\n(Ej: 57300000000)",
            title="Enviar Cierre",
        ).get_input()
        if not tel_raw:
            return
        tel = re.sub(r"\D", "", tel_raw)
        if len(tel) < 10:
            messagebox.showwarning("Número inválido",
                                   "El número debe tener al menos 10 dígitos.",
                                   parent=self)
            return
        msg = f"🚨 *CIERRE DE CAJA* 🚨\n\n```\n{ticket}\n```"
        webbrowser.open(f"https://wa.me/{tel}?text={urllib.parse.quote(msg)}")

    def _guardar_txt(self, ticket: str):
        fecha_str = datetime.now().strftime("%Y%m%d_%H%M")
        ruta = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile=f"Cierre_Caja_{fecha_str}.txt",
            title="Guardar Cierre de Caja",
            filetypes=[("Texto", "*.txt"), ("Todos los archivos", "*.*")],
        )
        if not ruta:
            return
        try:
            with open(ruta, "w", encoding="utf-8") as f:
                f.write("=== REPORTE DE CIERRE DE CAJA ===\n\n")
                f.write(ticket)
            messagebox.showinfo("Guardado", f"Archivo guardado en:\n{ruta}",
                                parent=self)
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo guardar:\n{exc}",
                                 parent=self)