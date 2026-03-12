"""
Diálogo de selección de producto cuando hay múltiples coincidencias.
"""
from typing import Callable, List
import customtkinter as ctk
from tkinter import ttk

from repositories.producto_repo import ProductoRow

C = {
    "bg":      "#0f1117",
    "surface": "#1a1d27",
    "card":    "#20243a",
    "primary": "#3b82f6",
    "text":    "#f1f5f9",
    "muted":   "#64748b",
    "border":  "#2d3348",
}


class DialogSeleccion(ctk.CTkToplevel):
    """
    Ventana modal para elegir entre varios productos.
    Llama a on_seleccion(producto) con la fila elegida.
    """

    def __init__(self, parent, productos: List[ProductoRow],
                 on_seleccion: Callable):
        super().__init__(parent)
        self.productos = productos
        self.on_seleccion = on_seleccion

        self.title("Seleccionar Producto")
        self.geometry("700x420")
        self.configure(fg_color=C["bg"])
        self.attributes("-topmost", True)
        self.grab_set()
        self.resizable(False, False)

        self._build()

    def _build(self):
        # Cabecera
        hdr = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0, height=56)
        hdr.pack(fill="x")
        ctk.CTkLabel(
            hdr,
            text="Múltiples productos encontrados — elige uno",
            font=("Segoe UI Semibold", 14),
            text_color=C["text"],
        ).pack(side="left", padx=20, pady=16)

        # Estilo tabla
        s = ttk.Style()
        s.configure("Sel.Treeview",
                    background=C["card"], foreground=C["text"],
                    fieldbackground=C["card"], borderwidth=0,
                    rowheight=40, font=("Segoe UI", 12))
        s.configure("Sel.Treeview.Heading",
                    background=C["surface"], foreground=C["muted"],
                    font=("Segoe UI Semibold", 11), borderwidth=0, relief="flat")
        s.map("Sel.Treeview", background=[("selected", C["primary"])])

        frame = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=12)
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        cols = ("ref", "nombre", "stock", "precio")
        self.tabla = ttk.Treeview(frame, columns=cols,
                                  show="headings", style="Sel.Treeview")
        self.tabla.heading("ref",    text="CÓDIGO")
        self.tabla.heading("nombre", text="DESCRIPCIÓN")
        self.tabla.heading("stock",  text="STOCK")
        self.tabla.heading("precio", text="PRECIO")
        self.tabla.column("ref",    width=130)
        self.tabla.column("nombre", width=310)
        self.tabla.column("stock",  width=90,  anchor="center")
        self.tabla.column("precio", width=120, anchor="e")
        self.tabla.pack(fill="both", expand=True, padx=4, pady=4)

        for p in self.productos:
            self.tabla.insert("", "end", iid=p[0],
                              values=(p[1], p[2], p[4], f"$ {p[3]:,.0f}"))

        self.tabla.bind("<Double-1>", self._confirmar)

        # Pie
        pie = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0, height=56)
        pie.pack(fill="x", side="bottom")
        ctk.CTkLabel(pie, text="Doble clic para agregar al carrito",
                     font=("Segoe UI", 12),
                     text_color=C["muted"]).pack(side="left", padx=20)
        ctk.CTkButton(
            pie, text="Cancelar", width=100,
            fg_color="transparent", border_width=1,
            border_color=C["border"], text_color=C["muted"],
            command=self.destroy,
        ).pack(side="right", padx=16, pady=10)

    def _confirmar(self, _event=None):
        sel = self.tabla.selection()
        if not sel:
            return
        p_id = int(sel[0])
        prod = next(p for p in self.productos if p[0] == p_id)
        self.on_seleccion(prod)
        self.destroy()