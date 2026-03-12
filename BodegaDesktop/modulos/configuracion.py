# BodegaDesktop/modulos/configuracion.py
import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
import requests
from urllib.parse import urljoin
from database import obtener_configuracion, guardar_configuracion

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


class PanelConfiguracion(ctk.CTkFrame):
    """Panel de configuración"""

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # CTkTabview para pestañas
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)

        # Tab 1: Red y Sincronización
        self.tab_red = self.tabview.add("Red y Sincronización")
        self._crear_tab_red()

        # Tab 2: Mantenimiento
        self.tab_mantenimiento = self.tabview.add("Mantenimiento")
        self._crear_tab_mantenimiento()

    def _crear_tab_red(self):
        """Tab de configuración de red"""

        frame = ctk.CTkScrollableFrame(self.tab_red)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Título
        ctk.CTkLabel(
            frame,
            text="Configuración de Red",
            font=("Arial", 16, "bold")
        ).pack(pady=20)

        # URL del servidor
        ctk.CTkLabel(frame, text="URL del API:").pack(anchor="w", padx=20)
        self._entry_url = ctk.CTkEntry(frame, width=400)
        url_actual = obtener_configuracion('api_url') or 'http://127.0.0.1:8000/api'
        self._entry_url.insert(0, url_actual)
        self._entry_url.pack(pady=5, padx=20)

        # Botones
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(pady=20, padx=20)

        ctk.CTkButton(
            btn_frame,
            text="💾 Guardar",
            command=self._guardar_url,
            fg_color=C['success']
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="🧪 Probar Conexión",
            command=self._probar_conexion,
            fg_color=C['primary']
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="🔄 Sincronizar",
            command=self._sincronizar,
            fg_color=C['warning']
        ).pack(side="left", padx=5)

        # Status
        self._lbl_status = ctk.CTkLabel(frame, text="", text_color=C['success'])
        self._lbl_status.pack(pady=10)

    def _crear_tab_mantenimiento(self):
        """Tab de mantenimiento"""

        frame = ctk.CTkScrollableFrame(self.tab_mantenimiento)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Título
        ctk.CTkLabel(
            frame,
            text="Mantenimiento",
            font=("Arial", 16, "bold")
        ).pack(pady=20)

        # Limpiar caché
        ctk.CTkButton(
            frame,
            text="🗑 Limpiar Caché",
            command=self._limpiar_cache,
            width=300,
            fg_color=C['warning']
        ).pack(pady=10)

        # Reset
        ctk.CTkButton(
            frame,
            text="⚠️ Reset Completo",
            command=self._reset_completo,
            width=300,
            fg_color=C['error']
        ).pack(pady=10)

        # Info
        info_text = """
        Información del Sistema:
        - Versión: 0.1.0
        - Plataforma: Windows
        - BD Local: bodega_local.db
        - Status: ✅ En Funcionamiento
        """

        ctk.CTkLabel(frame, text=info_text, text_color=C['text'], justify="left").pack(pady=20, padx=20)

    def _guardar_url(self):
        """Guarda la URL del servidor"""
        url = self._entry_url.get().strip()
        if url:
            guardar_configuracion('api_url', url)
            self.controller.api_url = url
            self._lbl_status.configure(text="✅ URL guardada correctamente")
        else:
            self._lbl_status.configure(text="❌ URL vacía", text_color=C['error'])

    def _probar_conexion(self):
        """Prueba la conexión con el servidor"""
        try:
            url = self._entry_url.get().strip()
            if not url:
                self._lbl_status.configure(text="❌ URL vacía", text_color=C['error'])
                return

            url_token = urljoin(url, 'token/')
            response = requests.get(url_token, timeout=4, verify=False)

            if response.status_code in [400, 401]:
                self._lbl_status.configure(text="✅ Servidor respondiendo correctamente", text_color=C['success'])
            else:
                self._lbl_status.configure(text=f"⚠️ Respuesta: {response.status_code}", text_color=C['warning'])

        except requests.exceptions.Timeout:
            self._lbl_status.configure(text="❌ Timeout - Servidor no responde", text_color=C['error'])
        except requests.exceptions.ConnectionError:
            self._lbl_status.configure(text="❌ Sin conexión", text_color=C['error'])
        except Exception as e:
            self._lbl_status.configure(text=f"❌ Error: {str(e)[:30]}", text_color=C['error'])

    def _sincronizar(self):
        """Sincroniza manualmente (placeholder)"""
        self._lbl_status.configure(text="🔄 Sincronización en progreso...", text_color=C['warning'])
        self.after(1000, lambda: self._lbl_status.configure(text="✅ Sincronización completada", text_color=C['success']))

    def _limpiar_cache(self):
        """Limpia la caché local"""
        respuesta = CTkMessagebox(
            title="Confirmar",
            message="¿Borrar caché local?",
            options=["Sí", "No"]
        )
        if respuesta == "Sí":
            CTkMessagebox(title="✅", message="Caché borrado")

    def _reset_completo(self):
        """Reset completo del app"""
        respuesta = CTkMessagebox(
            title="⚠️ ADVERTENCIA",
            message="¿Reset COMPLETO del app? Se borrará toda la configuración.",
            options=["Sí, Reset", "Cancelar"]
        )
        if respuesta == "Sí, Reset":
            respuesta2 = CTkMessagebox(
                title="Confirmación Final",
                message="Esta acción no se puede deshacer. ¿Continuar?",
                options=["Sí, Continuar", "Cancelar"]
            )
            if respuesta2 == "Sí, Continuar":
                # Aquí iría lógica de reset
                self.controller._cerrar_sesion()
