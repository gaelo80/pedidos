# BodegaDesktop/modulos/despacho.py
import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
import requests
import threading
import json
import webbrowser
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# Función auxiliar
def normalizar_url_api(url_api):
    """Asegura que la URL sea correcta"""
    url_api = url_api.rstrip('/')
    if not url_api.endswith('/api'):
        url_api = url_api + '/api'
    return url_api

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


class PanelDespacho(ctk.CTkFrame):
    """Panel para escanear y despachar pedidos"""

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.pedido_data = None
        self.cantidades_borrador = {}  # {detalle_id: cantidad}
        self.codigos_barras_map = {}   # {codigo_barras: detalle_info}
        self.escaneos_recientes = []

        self._crear_ui()

    def _crear_ui(self):
        """Crear interfaz del panel de despacho"""

        # Top bar
        topbar = ctk.CTkFrame(self, fg_color=C['primary'], height=50)
        topbar.pack(fill="x", padx=0, pady=0)
        topbar.pack_propagate(False)

        self._lbl_titulo = ctk.CTkLabel(topbar, text="Cargando...", font=("Arial", 14, "bold"), text_color=C['text'])
        self._lbl_titulo.pack(side="left", padx=20, pady=10)

        btn_volver = ctk.CTkButton(
            topbar,
            text="← Volver",
            command=self._volver_a_lista,
            width=100,
            fg_color=C['error']
        )
        btn_volver.pack(side="right", padx=10, pady=10)

        btn_comprobante = ctk.CTkButton(
            topbar,
            text="🖨 Ver Comprobante",
            command=self._abrir_comprobante,
            width=120,
            fg_color=C['warning']
        )
        btn_comprobante.pack(side="right", padx=5, pady=10)

        # Contenido principal
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Sección izquierda: Items + scanner
        left_frame = ctk.CTkFrame(main_frame)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # Scanner
        scanner_frame = ctk.CTkFrame(left_frame, fg_color=C['warning'])
        scanner_frame.pack(fill="x", padx=0, pady=5)

        ctk.CTkLabel(scanner_frame, text="📦 ESCANEAR CÓDIGO:", text_color=C['text_dark']).pack(side="left", padx=10, pady=5)
        self._entry_scanner = ctk.CTkEntry(
            scanner_frame,
            width=300,
            placeholder_text="Coloca el escáner aquí y presiona Enter",
            border_color=C['success']
        )
        self._entry_scanner.pack(side="left", padx=5, pady=5)
        self._entry_scanner.bind("<Return>", lambda e: self._procesar_escaneo())

        # Items list
        items_frame = ctk.CTkFrame(left_frame, fg_color=C['bg_dark'] if self._is_light() else "#2a2a3e")
        items_frame.pack(fill="both", expand=True, padx=0, pady=10)

        ctk.CTkLabel(items_frame, text="Items del Pedido", font=("Arial", 12, "bold")).pack(padx=10, pady=5)

        self._items_scroll = ctk.CTkScrollableFrame(items_frame)
        self._items_scroll.pack(fill="both", expand=True, padx=5, pady=5)

        # Sección derecha: Progreso + Últimos escaneos
        right_frame = ctk.CTkFrame(main_frame)
        right_frame.pack(side="right", fill="both", expand=False, padx=10, width=300)

        # Progreso
        progreso_frame = ctk.CTkFrame(right_frame)
        progreso_frame.pack(fill="x", padx=0, pady=10)

        ctk.CTkLabel(progreso_frame, text="📊 PROGRESO", font=("Arial", 12, "bold")).pack(padx=10, pady=5)

        self._lbl_total_pedido = ctk.CTkLabel(progreso_frame, text="Pedido: 0 prendas")
        self._lbl_total_pedido.pack(padx=10, pady=2)

        self._lbl_despachado = ctk.CTkLabel(progreso_frame, text="Despachado: 0 prendas", text_color=C['success'])
        self._lbl_despachado.pack(padx=10, pady=2)

        self._lbl_pendiente = ctk.CTkLabel(progreso_frame, text="Pendiente: 0 prendas", text_color=C['warning'])
        self._lbl_pendiente.pack(padx=10, pady=2)

        # Barra de progreso
        self._progress_bar = ctk.CTkProgressBar(progreso_frame, fg_color=C['error'])
        self._progress_bar.set(0)
        self._progress_bar.pack(padx=10, pady=5, fill="x")

        # Escaneos recientes
        escaneos_frame = ctk.CTkFrame(right_frame)
        escaneos_frame.pack(fill="both", expand=True, padx=0, pady=10)

        ctk.CTkLabel(escaneos_frame, text="Últimos Escaneos", font=("Arial", 12, "bold")).pack(padx=10, pady=5)

        self._escaneos_scroll = ctk.CTkScrollableFrame(escaneos_frame)
        self._escaneos_scroll.pack(fill="both", expand=True, padx=5, pady=5)

        # Footer con botones
        footer_frame = ctk.CTkFrame(self)
        footer_frame.pack(fill="x", padx=10, pady=10)

        btn_enviar = ctk.CTkButton(
            footer_frame,
            text="✅ Enviar Despacho",
            command=lambda: threading.Thread(target=self._enviar_despacho, daemon=True).start(),
            width=150,
            fg_color=C['success'],
            font=("Arial", 12, "bold")
        )
        btn_enviar.pack(side="left", padx=5)

        btn_incompleto = ctk.CTkButton(
            footer_frame,
            text="⚠️ Finalizar Incompleto",
            command=lambda: threading.Thread(target=self._finalizar_incompleto, daemon=True).start(),
            width=150,
            fg_color=C['warning']
        )
        btn_incompleto.pack(side="left", padx=5)

        btn_cancelar = ctk.CTkButton(
            footer_frame,
            text="❌ Cancelar Pedido",
            command=lambda: threading.Thread(target=self._cancelar_pedido, daemon=True).start(),
            width=150,
            fg_color=C['error']
        )
        btn_cancelar.pack(side="left", padx=5)

    def _is_light(self):
        return ctk.get_appearance_mode() == "light"

    def on_mostrar(self):
        """Se llama cuando el panel se muestra"""
        if hasattr(self.controller, 'pedido_actual_id'):
            self._cargar_pedido(self.controller.pedido_actual_id)
        try:
            self.after(100, lambda: self._entry_scanner.focus())
        except:
            pass  # Ignorar errores de focus

    def _cargar_pedido(self, pedido_id):
        """Carga los datos del pedido"""
        try:
            url_api = normalizar_url_api(self.controller.api_url)
            url = f"{url_api}/bodega/pedidos/{pedido_id}/"

            headers = {'Authorization': f'Bearer {self.controller.token}'}
            response = requests.get(url, headers=headers, timeout=10, verify=False)

            if response.status_code == 200:
                self.pedido_data = response.json()
                self.cantidades_borrador = {}
                self.codigos_barras_map = {}

                # Construir mapa de códigos de barras
                for detalle in self.pedido_data.get('detalles', []):
                    codigo = detalle.get('codigo_barras', '')
                    if codigo:
                        self.codigos_barras_map[codigo] = {
                            'id': detalle['id'],
                            'referencia': detalle['producto_referencia'],
                            'nombre': detalle['producto_nombre'],
                            'color': detalle['producto_color'],
                            'talla': detalle['producto_talla'],
                            'cantidad': detalle['cantidad'],
                            'cantidad_verificada': detalle.get('cantidad_verificada', 0) or 0,
                        }

                self._actualizar_ui()
            else:
                CTkMessagebox(title="Error", message="No se pudo cargar el pedido")
                self._volver_a_lista()

        except Exception as e:
            CTkMessagebox(title="Error", message=f"Error al cargar pedido: {str(e)}")

    def _actualizar_ui(self):
        """Actualiza la interfaz con datos del pedido"""
        if not self.pedido_data:
            return

        # Titulo
        numero = self.pedido_data.get('numero_pedido', 'N/A')
        cliente = self.pedido_data.get('cliente_nombre', 'N/A')
        estado = self.pedido_data.get('estado_display', 'N/A')
        self._lbl_titulo.configure(text=f"Pedido #{numero} - {cliente} ({estado})")

        # Limpiar items
        for widget in self._items_scroll.winfo_children():
            widget.destroy()

        # Agrupar items por referencia/color
        items_agrupados = defaultdict(list)
        for detalle in self.pedido_data.get('detalles', []):
            clave = (detalle['producto_referencia'], detalle['producto_color'])
            items_agrupados[clave].append(detalle)

        # Mostrar items agrupados
        total_pedido = 0
        total_despachado = 0

        for (referencia, color), detalles in items_agrupados.items():
            # Frame por referencia/color
            ref_frame = ctk.CTkFrame(self._items_scroll, fg_color=C['primary'])
            ref_frame.pack(fill="x", padx=5, pady=5)

            titulo_ref = f"{referencia} - {color or 'Sin color'}"
            ctk.CTkLabel(ref_frame, text=titulo_ref, text_color=C['text'], font=("Arial", 10, "bold")).pack(padx=10, pady=5)

            # Tallas dentro de la referencia
            for detalle in detalles:
                talla = detalle.get('producto_talla', '')
                cantidad = detalle['cantidad']
                cantidad_verificada = self.cantidades_borrador.get(detalle['id'], detalle.get('cantidad_verificada', 0))

                total_pedido += cantidad
                total_despachado += cantidad_verificada

                # Frame talla
                talla_frame = ctk.CTkFrame(self._items_scroll, fg_color="transparent")
                talla_frame.pack(fill="x", padx=20, pady=2)

                estado_color = C['success'] if cantidad_verificada >= cantidad else C['warning']
                texto_talla = f"T{talla}: {cantidad_verificada}/{cantidad}"

                ctk.CTkLabel(
                    talla_frame,
                    text=texto_talla,
                    text_color=estado_color,
                    font=("Arial", 9)
                ).pack(side="left")

        # Actualizar progreso
        total_pendiente = total_pedido - total_despachado
        self._lbl_total_pedido.configure(text=f"Pedido: {total_pedido} prendas")
        self._lbl_despachado.configure(text=f"Despachado: {total_despachado} prendas")
        self._lbl_pendiente.configure(text=f"Pendiente: {total_pendiente} prendas")

        if total_pedido > 0:
            self._progress_bar.set(total_despachado / total_pedido)

    def _procesar_escaneo(self):
        """Procesa el código escaneado"""
        codigo = self._entry_scanner.get().strip()
        self._entry_scanner.delete(0, "end")

        if not codigo:
            return

        # Buscar en el mapa
        detalle_info = self.codigos_barras_map.get(codigo)

        if not detalle_info:
            self._agregar_escaneo(f"❌ No encontrado: {codigo}", C['error'])
            return

        detalle_id = detalle_info['id']
        cantidad_actual = self.cantidades_borrador.get(detalle_id, 0)
        cantidad_maxima = detalle_info['cantidad']

        # Validar cantidad
        if cantidad_actual >= cantidad_maxima:
            self._agregar_escaneo(f"⚠️ {detalle_info['referencia']} T{detalle_info['talla']} completado", C['warning'])
            return

        # Incrementar cantidad
        self.cantidades_borrador[detalle_id] = cantidad_actual + 1

        # Guardar en API (background)
        threading.Thread(
            target=self._guardar_borrador_api,
            args=(detalle_id, self.cantidades_borrador[detalle_id]),
            daemon=True
        ).start()

        # Feedback
        nueva_cantidad = self.cantidades_borrador[detalle_id]
        self._agregar_escaneo(
            f"✅ {detalle_info['referencia']} T{detalle_info['talla']} ({nueva_cantidad}/{cantidad_maxima})",
            C['success']
        )

        # Actualizar UI
        self._actualizar_ui()

    def _guardar_borrador_api(self, detalle_id, cantidad):
        """Guarda el borrador en el API"""
        try:
            url_api = normalizar_url_api(self.controller.api_url)
            pedido_id = self.pedido_data['id']
            url = f"{url_api}/bodega/pedidos/{pedido_id}/guardar-borrador/"

            headers = {'Authorization': f'Bearer {self.controller.token}'}
            data = {'detalles': [{'id': detalle_id, 'cantidad': cantidad}]}

            requests.post(url, json=data, headers=headers, timeout=5, verify=False)
        except Exception as e:
            logger.error(f"Error guardando borrador: {e}")

    def _agregar_escaneo(self, mensaje, color):
        """Agrega un escaneo reciente a la lista"""
        # Limpiar escaneos previos
        for widget in self._escaneos_scroll.winfo_children():
            widget.destroy()

        # Agregar nuevo
        self.escaneos_recientes.insert(0, (mensaje, color))
        if len(self.escaneos_recientes) > 10:
            self.escaneos_recientes = self.escaneos_recientes[:10]

        for msg, col in self.escaneos_recientes:
            lbl = ctk.CTkLabel(self._escaneos_scroll, text=msg, text_color=col, font=("Arial", 9))
            lbl.pack(padx=5, pady=2, fill="x")

    def _enviar_despacho(self):
        """Envía el despacho confirmado"""
        if not self.pedido_data or not self.cantidades_borrador:
            CTkMessagebox(title="Error", message="No hay cantidades para despachar")
            return

        try:
            respuesta = CTkMessagebox(
                title="Confirmar Despacho",
                message="¿Confirmar envío de despacho?",
                options=["Sí", "No"]
            )

            if respuesta != "Sí":
                return

            url_api = normalizar_url_api(self.controller.api_url)
            pedido_id = self.pedido_data['id']
            url = f"{url_api}/bodega/pedidos/{pedido_id}/enviar-despacho/"

            headers = {'Authorization': f'Bearer {self.controller.token}'}
            response = requests.post(url, json={}, headers=headers, timeout=10, verify=False)

            if response.status_code == 200:
                data = response.json()
                comprobante_url = data.get('comprobante_url', '')

                CTkMessagebox(title="✅ Éxito", message="Despacho enviado correctamente")

                # Abrir comprobante en navegador
                if comprobante_url:
                    webbrowser.open(comprobante_url)

                # Volver a lista
                self.after(500, self._volver_a_lista)
            else:
                CTkMessagebox(title="Error", message=f"Error: {response.text[:100]}")

        except Exception as e:
            CTkMessagebox(title="Error", message=f"Error al enviar: {str(e)}")

    def _finalizar_incompleto(self):
        """Marca como enviado incompleto"""
        try:
            respuesta = CTkMessagebox(
                title="Confirmar",
                message="¿Finalizar pedido como INCOMPLETO?\nSe devolverá el stock pendiente.",
                options=["Sí", "No"]
            )

            if respuesta != "Sí":
                return

            url_api = normalizar_url_api(self.controller.api_url)
            pedido_id = self.pedido_data['id']
            url = f"{url_api}/bodega/pedidos/{pedido_id}/finalizar-incompleto/"

            headers = {'Authorization': f'Bearer {self.controller.token}'}
            response = requests.post(url, json={}, headers=headers, timeout=10, verify=False)

            if response.status_code == 200:
                CTkMessagebox(title="✅ Éxito", message="Pedido marcado como INCOMPLETO")
                self.after(500, self._volver_a_lista)
            else:
                CTkMessagebox(title="Error", message=f"Error: {response.text[:100]}")

        except Exception as e:
            CTkMessagebox(title="Error", message=f"Error: {str(e)}")

    def _cancelar_pedido(self):
        """Cancela el pedido completamente"""
        try:
            respuesta = CTkMessagebox(
                title="⚠️ ADVERTENCIA",
                message="¿Cancelar pedido completamente?\nSe devolverá TODO el stock.",
                options=["Sí, Cancelar", "No"]
            )

            if respuesta != "Sí, Cancelar":
                return

            url_api = normalizar_url_api(self.controller.api_url)
            pedido_id = self.pedido_data['id']
            url = f"{url_api}/bodega/pedidos/{pedido_id}/cancelar/"

            headers = {'Authorization': f'Bearer {self.controller.token}'}
            response = requests.post(url, json={}, headers=headers, timeout=10, verify=False)

            if response.status_code == 200:
                CTkMessagebox(title="✅ Cancelado", message="Pedido cancelado correctamente")
                self.after(500, self._volver_a_lista)
            else:
                CTkMessagebox(title="Error", message=f"Error: {response.text[:100]}")

        except Exception as e:
            CTkMessagebox(title="Error", message=f"Error: {str(e)}")

    def _abrir_comprobante(self):
        """Abre el comprobante en navegador"""
        CTkMessagebox(title="Info", message="Comprobante disponible después de enviar despacho")

    def _volver_a_lista(self):
        """Vuelve a la lista de pedidos"""
        self.controller.cambiar_modulo('pedidos')
