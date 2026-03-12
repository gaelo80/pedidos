# BodegaDesktop/modulos/pedidos.py
import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
import requests
import threading
import json
from urllib.parse import urljoin

# Colores
C = {
    'bg_dark': '#1a1a2e',
    'bg_light': '#eaeaea',
    'primary': '#2196F3',
    'success': '#4CAF50',
    'warning': '#FF9800',
    'error': '#F44336',
    'text': '#ffffff',
    'text_dark': '#000000',
}


class PanelPedidos(ctk.CTkFrame):
    """Panel para listar y filtrar pedidos pendientes"""

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.pedidos_data = []
        self.pedidos_mostrados = []

        self._crear_ui()
        self.on_mostrar()

    def _crear_ui(self):
        """Crear interfaz del panel"""

        # Header
        header = ctk.CTkFrame(self, fg_color=C['primary'], height=50)
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)

        titulo = ctk.CTkLabel(header, text="📋 Pedidos Pendientes", font=("Arial", 16, "bold"), text_color=C['text'])
        titulo.pack(side="left", padx=20, pady=10)

        btn_actualizar = ctk.CTkButton(
            header,
            text="🔄 Actualizar",
            command=lambda: threading.Thread(target=self.on_mostrar, daemon=True).start(),
            width=100,
            fg_color=C['success']
        )
        btn_actualizar.pack(side="right", padx=10, pady=10)

        # Filtros
        filtro_frame = ctk.CTkFrame(self, fg_color=C['bg_light'] if self._is_light_mode() else C['bg_dark'])
        filtro_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(filtro_frame, text="Buscar cliente:").pack(side="left", padx=5)
        self._entry_cliente = ctk.CTkEntry(filtro_frame, width=200, placeholder_text="Ingresa nombre")
        self._entry_cliente.pack(side="left", padx=5)
        self._entry_cliente.bind("<KeyRelease>", lambda e: self._filtrar())

        ctk.CTkLabel(filtro_frame, text="Estado:").pack(side="left", padx=20)
        self._combo_estado = ctk.CTkComboBox(
            filtro_frame,
            values=["Todos", "APROBADO_ADMIN", "PROCESANDO", "LISTO_BODEGA_DIRECTO"],
            width=150,
            command=lambda v: self._filtrar()
        )
        self._combo_estado.set("Todos")
        self._combo_estado.pack(side="left", padx=5)

        # Content area con Treeview
        content_frame = ctk.CTkFrame(self)
        content_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Crear tabla (usando labels, ya que CTk no tiene Treeview nativo)
        self._tabla_frame = ctk.CTkScrollableFrame(content_frame)
        self._tabla_frame.pack(fill="both", expand=True)

        # Status bar
        self._status_frame = ctk.CTkFrame(self, fg_color=C['warning'], height=30)
        self._status_frame.pack(fill="x", padx=0, pady=0)
        self._status_frame.pack_propagate(False)

        self._lbl_status = ctk.CTkLabel(
            self._status_frame,
            text="Cargando pedidos...",
            text_color=C['text_dark'],
            font=("Arial", 10)
        )
        self._lbl_status.pack(pady=5)

    def _is_light_mode(self):
        """Detecta si la app está en modo light"""
        return ctk.get_appearance_mode() == "light"

    def on_mostrar(self):
        """Se llama cuando el panel se muestra"""
        self._cargar_pedidos()

    def _cargar_pedidos(self):
        """Carga la lista de pedidos del API"""
        try:
            url_api = self.controller.api_url
            # Asegurar que la URL sea correcta
            url_api = url_api.rstrip('/')
            if not url_api.endswith('/api'):
                url_api = url_api + '/api'

            url = f"{url_api}/bodega/pedidos/"

            headers = {'Authorization': f'Bearer {self.controller.token}'}
            response = requests.get(url, headers=headers, timeout=10, verify=False)

            if response.status_code == 200:
                self.pedidos_data = response.json()
                self._mostrar_tabla()
                self._lbl_status.configure(text=f"✅ {len(self.pedidos_data)} pedidos cargados", text_color=C['text_dark'])
            else:
                self._lbl_status.configure(text="❌ Error al cargar pedidos", text_color=C['error'])

        except requests.exceptions.Timeout:
            self._lbl_status.configure(text="❌ Timeout - Servidor no responde", text_color=C['error'])
        except requests.exceptions.ConnectionError:
            self._lbl_status.configure(text="❌ Sin conexión", text_color=C['error'])
        except Exception as e:
            self._lbl_status.configure(text=f"❌ Error: {str(e)[:50]}", text_color=C['error'])

    def _mostrar_tabla(self):
        """Muestra la tabla de pedidos"""
        # Limpiar tabla
        for widget in self._tabla_frame.winfo_children():
            widget.destroy()

        # Header
        header_frame = ctk.CTkFrame(self._tabla_frame, fg_color=C['primary'], height=30)
        header_frame.pack(fill="x", pady=5, padx=5)
        header_frame.pack_propagate(False)

        headers = ["#", "Cliente", "Fecha", "Estado", "Items", "Acción"]
        col_widths = [60, 250, 150, 150, 80, 150]

        for i, (header, width) in enumerate(zip(headers, col_widths)):
            lbl = ctk.CTkLabel(
                header_frame,
                text=header,
                text_color=C['text'],
                font=("Arial", 10, "bold"),
                width=width
            )
            lbl.pack(side="left", padx=5, pady=5)

        # Filas
        for pedido in self.pedidos_data:
            row_frame = ctk.CTkFrame(
                self._tabla_frame,
                fg_color=C['bg_dark'] if self._is_light_mode() else "#2a2a3e",
                height=40
            )
            row_frame.pack(fill="x", pady=3, padx=5)
            row_frame.pack_propagate(False)

            # Columnas
            num_pedido = ctk.CTkLabel(row_frame, text=str(pedido.get('numero_pedido', 'N/A')), width=60)
            num_pedido.pack(side="left", padx=5, pady=5)

            cliente = ctk.CTkLabel(row_frame, text=str(pedido.get('cliente_nombre', ''))[:30], width=250)
            cliente.pack(side="left", padx=5, pady=5)

            fecha = ctk.CTkLabel(row_frame, text=str(pedido.get('fecha_hora', ''))[:10], width=150)
            fecha.pack(side="left", padx=5, pady=5)

            estado_color = self._get_estado_color(pedido.get('estado', ''))
            estado = ctk.CTkLabel(
                row_frame,
                text=pedido.get('estado_display', '')[:20],
                text_color=estado_color,
                width=150
            )
            estado.pack(side="left", padx=5, pady=5)

            items = ctk.CTkLabel(row_frame, text=str(pedido.get('total_items', 0)), width=80)
            items.pack(side="left", padx=5, pady=5)

            btn_despacho = ctk.CTkButton(
                row_frame,
                text="🚀 Despachar",
                command=lambda p_id=pedido['id']: self._abrir_despacho(p_id),
                width=100,
                fg_color=C['success'],
                font=("Arial", 9)
            )
            btn_despacho.pack(side="left", padx=5, pady=5)

    def _get_estado_color(self, estado):
        """Retorna color según el estado"""
        if estado == 'APROBADO_ADMIN':
            return C['success']
        elif estado == 'PROCESANDO':
            return C['warning']
        elif estado == 'LISTO_BODEGA_DIRECTO':
            return C['primary']
        return C['text']

    def _filtrar(self):
        """Filtra la tabla"""
        # Implementar filtros básicos
        cliente_filter = self._entry_cliente.get().lower()
        estado_filter = self._combo_estado.get()

        self.pedidos_mostrados = [
            p for p in self.pedidos_data
            if (cliente_filter == '' or cliente_filter in p.get('cliente_nombre', '').lower())
            and (estado_filter == 'Todos' or p.get('estado') == estado_filter)
        ]

        self.pedidos_data = self.pedidos_mostrados
        self._mostrar_tabla()

    def _abrir_despacho(self, pedido_id):
        """Abre el panel de despacho para un pedido"""
        # Setear el pedido actual en el controlador
        self.controller.pedido_actual_id = pedido_id

        # Cambiar a panel de despacho
        self.controller.cambiar_modulo('despacho')

        # Llamar on_mostrar para cargar el pedido
        self.controller.paneles['despacho'].on_mostrar()
