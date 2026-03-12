# BodegaDesktop/main.py
import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
from PIL import Image
import threading
import sqlite3
import requests
import json
import logging
import os
import sys
from urllib.parse import urljoin

from database import inicializar_db, obtener_configuracion, guardar_configuracion

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Desactivar advertencias SSL
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Importar módulos
from modulos.pedidos import PanelPedidos
from modulos.despacho import PanelDespacho
from modulos.configuracion import PanelConfiguracion


class AppBodega(ctk.CTk):
    """Aplicación principal para despacho de bodega"""

    def __init__(self):
        super().__init__()

        # Inicializar BD local
        inicializar_db()

        # Configuración general
        self.title("Bodega - Despacho de Pedidos")
        self.geometry("1400x800")
        self.minsize(1000, 600)

        # Variables de estado
        self.token = None
        self.usuario_actual = None
        self.empresa_id = None
        self.api_url = None

        # Colores
        self.C = {
            'bg_dark': '#1a1a2e',
            'bg_light': '#eaeaea',
            'primary': '#2196F3',
            'success': '#4CAF50',
            'warning': '#FF9800',
            'error': '#F44336',
            'text': '#ffffff',
            'text_dark': '#000000',
        }

        # Crear pantalla de login
        self._crear_login()

    def _crear_login(self):
        """Crear interfaz de login"""
        self._container = ctk.CTkFrame(self)
        self._container.pack(side="top", fill="both", expand=True)
        self._container.grid_rowconfigure(0, weight=1)
        self._container.grid_columnconfigure(0, weight=1)

        self._pantalla_login = ctk.CTkFrame(self._container, fg_color=self.C['bg_dark'])
        self._pantalla_login.grid(row=0, column=0, sticky="nsew")
        self._pantalla_login.grid_rowconfigure(0, weight=1)
        self._pantalla_login.grid_columnconfigure(0, weight=1)

        # Panel login
        panel_login = ctk.CTkFrame(self._pantalla_login, fg_color=self.C['bg_dark'])
        panel_login.place(relx=0.5, rely=0.5, anchor="center")

        # Logo/Título
        titulo = ctk.CTkLabel(
            panel_login,
            text="BODEGA DESPACHO",
            font=("Arial", 32, "bold"),
            text_color=self.C['primary']
        )
        titulo.pack(pady=(0, 20))

        # Usuario
        ctk.CTkLabel(panel_login, text="Usuario:", text_color=self.C['text']).pack(pady=(10, 0))
        self._entry_usuario = ctk.CTkEntry(panel_login, width=300, placeholder_text="usuario")
        self._entry_usuario.pack(pady=5)

        # Contraseña
        ctk.CTkLabel(panel_login, text="Contraseña:", text_color=self.C['text']).pack(pady=(10, 0))
        self._entry_password = ctk.CTkEntry(panel_login, width=300, placeholder_text="contraseña", show="•")
        self._entry_password.pack(pady=5)

        # Status
        self._lbl_status = ctk.CTkLabel(panel_login, text="", text_color=self.C['error'])
        self._lbl_status.pack(pady=10)

        # Botones
        btn_frame = ctk.CTkFrame(panel_login, fg_color="transparent")
        btn_frame.pack(pady=20)

        btn_ingresar = ctk.CTkButton(
            btn_frame,
            text="INGRESAR",
            command=lambda: threading.Thread(target=self._ejecutar_login, daemon=True).start(),
            width=150,
            height=40,
            fg_color=self.C['success'],
            text_color=self.C['text']
        )
        btn_ingresar.pack(side="left", padx=10)

        btn_config = ctk.CTkButton(
            btn_frame,
            text="⚙️ Configurar Servidor",
            command=self._dialogo_configurar_servidor,
            width=150,
            height=40,
            fg_color=self.C['primary'],
            text_color=self.C['text']
        )
        btn_config.pack(side="left", padx=10)

        btn_probar = ctk.CTkButton(
            btn_frame,
            text="🧪 Probar Conexión",
            command=lambda: threading.Thread(target=self._probar_conexion, daemon=True).start(),
            width=150,
            height=40,
            fg_color=self.C['warning'],
            text_color=self.C['text_dark']
        )
        btn_probar.pack(side="left", padx=10)

        # Hacer focus después de que el evento se procese completamente
        try:
            self.after(100, lambda: self._entry_usuario.focus())
        except:
            pass  # Ignorar errores de focus

    def _probar_conexion(self):
        """Prueba la conexión sin autenticación"""
        try:
            url_api = obtener_configuracion('api_url') or 'http://127.0.0.1:8000/api'
            # Asegurar que la URL sea correcta
            url_api = url_api.rstrip('/')
            if not url_api.endswith('/api'):
                url_api = url_api + '/api'

            url_token = f"{url_api}/token/"

            # POST con credenciales dummy para probar conexión
            response = requests.post(
                url_token,
                json={"username": "test", "password": "test"},
                timeout=4,
                verify=False
            )
            # Esperamos 400/401 como prueba de que el servidor responde
            if response.status_code in [400, 401]:
                self._lbl_status.configure(text="✅ Servidor respondiendo correctamente", text_color=self.C['success'])
            else:
                self._lbl_status.configure(text="⚠️ Respuesta inesperada del servidor", text_color=self.C['warning'])
        except requests.exceptions.Timeout:
            self._lbl_status.configure(text="❌ Timeout - Servidor no responde", text_color=self.C['error'])
        except requests.exceptions.ConnectionError:
            self._lbl_status.configure(text="❌ Sin conexión de red", text_color=self.C['error'])
        except Exception as e:
            self._lbl_status.configure(text=f"❌ Error: {str(e)[:40]}", text_color=self.C['error'])

    def _dialogo_configurar_servidor(self):
        """Diálogo para configurar URL del servidor"""
        url_actual = obtener_configuracion('api_url') or 'http://127.0.0.1:8000/api'

        dialog = ctk.CTkToplevel(self)
        dialog.title("Configurar Servidor")
        dialog.geometry("500x200")
        dialog.resizable(False, False)

        ctk.CTkLabel(dialog, text="URL del API:", font=("Arial", 12)).pack(pady=10)
        entry_url = ctk.CTkEntry(dialog, width=400)
        entry_url.insert(0, url_actual)
        entry_url.pack(pady=5, padx=20)

        def guardar():
            try:
                nueva_url = entry_url.get().strip()
                if nueva_url:
                    guardar_configuracion('api_url', nueva_url)
                    self.api_url = nueva_url
                    dialog.destroy()
                    CTkMessagebox(title="✅ Configurado", message="URL guardada correctamente")
            except Exception as e:
                CTkMessagebox(title="Error", message=f"Error: {str(e)}")

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=20)

        ctk.CTkButton(btn_frame, text="Guardar", command=guardar, width=100).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Cancelar", command=dialog.destroy, width=100).pack(side="left", padx=5)

    def _ejecutar_login(self):
        """Ejecuta el login con validación JWT"""
        usuario = self._entry_usuario.get().strip()
        password = self._entry_password.get().strip()

        if not usuario or not password:
            self._lbl_status.configure(text="❌ Ingresa usuario y contraseña", text_color=self.C['error'])
            return

        try:
            # Obtener URL del servidor
            api_url = obtener_configuracion('api_url') or 'http://127.0.0.1:8000/api'
            # Asegurar que la URL sea correcta
            api_url = api_url.rstrip('/')
            if not api_url.endswith('/api'):
                api_url = api_url + '/api'

            url_token = f"{api_url}/token/"

            # Intentar login
            response = requests.post(
                url_token,
                json={"username": usuario, "password": password},
                timeout=5,
                verify=False
            )

            if response.status_code == 200:
                data = response.json()
                self.token = data.get('access')
                self.usuario_actual = usuario
                self.api_url = api_url

                # Guardar URL
                guardar_configuracion('api_url', api_url)

                self._lbl_status.configure(text="✅ Login exitoso", text_color=self.C['success'])
                self.after(500, self._mostrar_dashboard)
            else:
                self._lbl_status.configure(text="❌ Credenciales inválidas", text_color=self.C['error'])
                self._entry_password.delete(0, "end")

        except requests.exceptions.Timeout:
            self._lbl_status.configure(text="❌ Timeout - Verifica conexión", text_color=self.C['error'])
        except requests.exceptions.ConnectionError:
            self._lbl_status.configure(text="❌ Sin conexión - Configura servidor", text_color=self.C['error'])
        except Exception as e:
            self._lbl_status.configure(text=f"❌ Error: {str(e)[:40]}", text_color=self.C['error'])

    def _mostrar_dashboard(self):
        """Muestra el dashboard después del login"""
        self._pantalla_login.destroy()
        self._crear_dashboard()

    def _crear_dashboard(self):
        """Crear interfaz principal después del login"""
        # Frame principal
        self._container = ctk.CTkFrame(self)
        self._container.pack(side="top", fill="both", expand=True)
        self._container.grid_rowconfigure(0, weight=0)
        self._container.grid_rowconfigure(1, weight=1)
        self._container.grid_columnconfigure(0, weight=1)

        # Top bar con navegación
        topbar = ctk.CTkFrame(self._container, fg_color=self.C['primary'], height=60)
        topbar.grid(row=0, column=0, sticky="ew")
        topbar.pack_propagate(False)

        # Título
        titulo = ctk.CTkLabel(
            topbar,
            text=f"👤 {self.usuario_actual} - Bodega Despacho",
            font=("Arial", 14, "bold"),
            text_color=self.C['text']
        )
        titulo.pack(side="left", padx=20, pady=10)

        # Botones topbar
        btn_frame = ctk.CTkFrame(topbar, fg_color="transparent")
        btn_frame.pack(side="right", padx=20, pady=10)

        ctk.CTkButton(
            btn_frame,
            text="Pedidos",
            command=lambda: self.cambiar_modulo('pedidos'),
            width=100,
            fg_color=self.C['success']
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="Configuración",
            command=lambda: self.cambiar_modulo('configuracion'),
            width=100,
            fg_color=self.C['primary']
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="Cerrar Sesión",
            command=self._cerrar_sesion,
            width=100,
            fg_color=self.C['error']
        ).pack(side="left", padx=5)

        # Content frame
        self._content = ctk.CTkFrame(self._container)
        self._content.grid(row=1, column=0, sticky="nsew")

        # Crear paneles
        self.paneles = {}
        self.paneles['pedidos'] = PanelPedidos(self._content, self)
        self.paneles['despacho'] = PanelDespacho(self._content, self)
        self.paneles['configuracion'] = PanelConfiguracion(self._content, self)

        # Mostrar panel de pedidos
        self.cambiar_modulo('pedidos')

    def cambiar_modulo(self, nombre_modulo):
        """Cambia entre módulos"""
        for nombre, panel in self.paneles.items():
            if nombre != nombre_modulo:
                panel.pack_forget()

        if nombre_modulo in self.paneles:
            panel = self.paneles[nombre_modulo]
            panel.pack(fill="both", expand=True)

            # Llamar al hook de recarga
            if hasattr(panel, 'on_mostrar'):
                panel.on_mostrar()

    def _cerrar_sesion(self):
        """Cierra la sesión y vuelve al login"""
        self.token = None
        self.usuario_actual = None
        self.empresa_id = None

        # Limpiar paneles
        if hasattr(self, 'paneles'):
            for panel in self.paneles.values():
                panel.destroy()

        # Limpiar content
        if hasattr(self, '_content'):
            self._content.destroy()

        # Limpiar container
        if hasattr(self, '_container'):
            self._container.destroy()

        # Volver a login
        self._crear_login()


if __name__ == "__main__":
    app = AppBodega()
    app.mainloop()
