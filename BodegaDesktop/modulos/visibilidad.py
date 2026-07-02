import customtkinter as ctk
from tkinter import ttk, messagebox
import requests

class PanelVisibilidad(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="#0f1117")
        self.controller = controller
        
        # Estilo de la tabla
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("Vis.Treeview", background="#20243a", foreground="#f1f5f9", fieldbackground="#20243a", rowheight=40, borderwidth=0)
        s.configure("Vis.Treeview.Heading", background="#1a1d27", foreground="#94a3b8", font=("Segoe UI Semibold", 11), borderwidth=0)
        s.map("Vis.Treeview", background=[("selected", "#3b82f6")])

        self._build_ui()

    def _build_ui(self):
        # --- Barra Superior ---
        top_bar = ctk.CTkFrame(self, fg_color="#1a1d27", height=60, corner_radius=0)
        top_bar.pack(fill="x")
        ctk.CTkLabel(top_bar, text="VISIBILIDAD DE PRODUCTOS EN TIENDAS", font=("Segoe UI Black", 20), text_color="#f1f5f9").pack(side="left", padx=20, pady=15)
        
        # --- Buscador y Botones ---
        tools = ctk.CTkFrame(self, fg_color="transparent")
        tools.pack(fill="x", padx=20, pady=15)
        
        self.entry_buscar = ctk.CTkEntry(tools, placeholder_text="🔍 Buscar producto...", width=300, height=40, fg_color="#1a1d27", border_color="#2d3348")
        self.entry_buscar.pack(side="left", padx=(0, 10))
        self.entry_buscar.bind("<KeyRelease>", self._filtrar_local)
        
        ctk.CTkButton(tools, text="↻ Recargar Datos", height=40, fg_color="#20243a", border_width=1, border_color="#2d3348", command=self.cargar_datos).pack(side="left")
        
        self.btn_toggle = ctk.CTkButton(tools, text="👁️ Ocultar/Mostrar Seleccionado", height=40, fg_color="#f59e0b", hover_color="#d97706", command=self._toggle_visibilidad)
        self.btn_toggle.pack(side="right")

        # --- Tabla ---
        frame_tabla = ctk.CTkFrame(self, fg_color="#20243a", corner_radius=10)
        frame_tabla.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        cols = ("id", "ref", "nombre", "stock", "estado")
        self.tabla = ttk.Treeview(frame_tabla, columns=cols, show="headings", style="Vis.Treeview")
        self.tabla.heading("ref", text="CÓDIGO")
        self.tabla.heading("nombre", text="DESCRIPCIÓN")
        self.tabla.heading("stock", text="STOCK")
        self.tabla.heading("estado", text="VISIBLE EN TIENDAS")
        
        self.tabla.column("id", width=0, stretch=False) # Columna oculta
        self.tabla.column("ref", width=120)
        self.tabla.column("nombre", width=350)
        self.tabla.column("stock", width=100, anchor="center")
        self.tabla.column("estado", width=150, anchor="center")
        
        self.tabla.tag_configure("oculto", foreground="#ef4444") # Rojo
        self.tabla.tag_configure("visible", foreground="#10b981") # Verde
        
        sb = ctk.CTkScrollbar(frame_tabla, command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", pady=5)
        self.tabla.pack(fill="both", expand=True, padx=5, pady=5)

        self.productos_memoria = [] # Caché para buscador rápido

    def cargar_datos(self):
        for i in self.tabla.get_children():
            self.tabla.delete(i)
            
        headers = {"Authorization": f"Bearer {self.controller.token}"}
        try:
            # Reutilizamos el endpoint que acabamos de modificar
            res = requests.get(f"{self.controller.API_BASE_URL}/almacen/inventario/", headers=headers, timeout=5, verify=False)
            if res.status_code == 200:
                self.productos_memoria = res.json()
                self._renderizar_tabla(self.productos_memoria)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el inventario:\n{e}")

    def _renderizar_tabla(self, datos):
        for i in self.tabla.get_children():
            self.tabla.delete(i)
            
        for p in datos:
            estado_texto = "❌ OCULTO" if p['oculto_para_standar'] else "✅ VISIBLE"
            tag = "oculto" if p['oculto_para_standar'] else "visible"
            self.tabla.insert("", "end", values=(p['id'], p['codigo_barras'], p['nombre'], p['stock_actual'], estado_texto), tags=(tag,))

    def _filtrar_local(self, event=None):
        termino = self.entry_buscar.get().lower()
        filtrados = [p for p in self.productos_memoria if termino in p['nombre'].lower() or termino in p['codigo_barras'].lower()]
        self._renderizar_tabla(filtrados)

    def _toggle_visibilidad(self):
        seleccion = self.tabla.selection()
        if not seleccion:
            messagebox.showwarning("Atención", "Selecciona un producto de la lista primero.")
            return
            
        valores = self.tabla.item(seleccion[0])['values']
        item_id = valores[0]
        estado_actual_oculto = "OCULTO" in valores[4]
        nuevo_estado = not estado_actual_oculto # Invertimos el estado
        
        headers = {"Authorization": f"Bearer {self.controller.token}"}
        try:
            # Enviamos el PATCH a Django
            res = requests.patch(
                f"{self.controller.API_BASE_URL}/almacen/inventario/{item_id}/", 
                json={"oculto_para_standar": nuevo_estado}, 
                headers=headers, verify=False
            )
            
            if res.status_code == 200:
                # Actualizamos la memoria y la tabla sin hacer otra petición pesada
                for p in self.productos_memoria:
                    if p['id'] == item_id:
                        p['oculto_para_standar'] = nuevo_estado
                        break
                self._filtrar_local()
            else:
                messagebox.showerror("Error", "No se pudo actualizar el estado en el servidor.")
        except Exception as e:
            messagebox.showerror("Error", f"Fallo de conexión:\n{e}")