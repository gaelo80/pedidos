# main.py
import json
import os
import sqlite3
import threading
import time
from tkinter import messagebox

import customtkinter as ctk
import requests
from PIL import Image

# Desactivar advertencias de SSL (para certificados auto-firmados)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from database import inicializar_db, DB_PATH
from modulos.ventas import PanelPOS
from modulos.inventario import PanelInventario
from modulos.informes import PanelInformes
from modulos.devoluciones import PanelDevoluciones
from modulos.configuracion import PanelConfiguracion

# Configuración de API - Usar variable de entorno o valor por defecto
import os
API_BASE_URL = os.getenv('ALMACEN_API_URL', "http://127.0.0.1:8000/api")

# ══════════════════════════════════════════════════════════════════════════════
# PALETA
# ══════════════════════════════════════════════════════════════════════════════
C = {
    "bg":        "#0f1117",
    "surface":   "#1a1d27",
    "card":      "#20243a",
    "primary":   "#3b82f6",
    "primary_h": "#2563eb",
    "success":   "#10b981",
    "danger":    "#ef4444",
    "warning":   "#f59e0b",
    "text":      "#f1f5f9",
    "text_dim":  "#94a3b8",
    "muted":     "#64748b",
    "border":    "#2d3348",
}

FONT = {
    "h1":    ("Segoe UI Black",    28),
    "h2":    ("Segoe UI Semibold", 16),
    "body":  ("Segoe UI",          13),
    "small": ("Segoe UI",          11),
    "brand": ("Segoe UI Black",    38),
    "sub":   ("Segoe UI",          14),
}

MODULE_BUTTONS = [
    ("Punto de Venta",  "ventas.png",       "ventas",        "#10b981", "#059669"),
    ("Inventario",      "inventario.png",   "inventario",    "#3b82f6", "#2563eb"),
    ("Devoluciones",    "devoluciones.png", "devoluciones",  "#f97316", "#ea580c"),
    ("Informes / Caja", "reportes.png",     "informes",      "#8b5cf6", "#7c3aed"),
    ("Configuración",   "config.png",       "configuracion", "#64748b", "#475569"),
]


# ══════════════════════════════════════════════════════════════════════════════
# APP PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

class AppAlmacen(ctk.CTk):

    def __init__(self):
        super().__init__()

        # Registrar esta ventana como root de tkinter para que
        # StringVar/BooleanVar funcionen sin pasar master explícito
        import tkinter
        tkinter._default_root = self

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.title("Sieslo ERP — Almacén")
        self.geometry("1280x800")
        self.minsize(1024, 720)
        self._centrar_ventana(1280, 800)
        self.configure(fg_color=C["bg"])

        # Estado de sesión
        self.token:           str | None = None
        self.usuario_actual:  str        = "Invitado"
        self.API_BASE_URL:    str        = API_BASE_URL

        inicializar_db()
        self._cargar_iconos()

        # Contenedor raíz
        self._container = ctk.CTkFrame(self, fg_color="transparent")
        self._container.pack(fill="both", expand=True)

        self._pantalla_login     = self._crear_login()
        self._pantalla_principal = self._crear_principal()

        self._mostrar_login()

    # ── Utilidades ─────────────────────────────────────────────────────────────

    def _centrar_ventana(self, w: int, h: int):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x  = (sw - w) // 2
        y  = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _cargar_iconos(self):
        base = os.path.join(os.path.dirname(os.path.realpath(__file__)), "assets")

        def _img(name, size=(60, 60)):
            path = os.path.join(base, name)
            if os.path.exists(path):
                img = Image.open(path)
                return ctk.CTkImage(light_image=img, dark_image=img, size=size)
            return None

        self._iconos = {nombre: _img(archivo)
                        for _, archivo, nombre, *_ in MODULE_BUTTONS}

    # ══════════════════════════════════════════════════════════════════════════
    # PANTALLA DE LOGIN
    # ══════════════════════════════════════════════════════════════════════════

    def _crear_login(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self._container, fg_color=C["bg"])

        # Fondo con gradiente visual usando un frame oscuro a la izquierda
        left = ctk.CTkFrame(frame, fg_color=C["surface"], width=460,
                            corner_radius=0)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        # Marca
        brand = ctk.CTkFrame(left, fg_color="transparent")
        brand.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(brand, text="Sieslo",
                     font=FONT["brand"],
                     text_color=C["primary"]).pack()
        ctk.CTkLabel(brand, text="Sistema de Gestión de Almacén",
                     font=FONT["sub"],
                     text_color=C["muted"]).pack(pady=(4, 0))

        ctk.CTkFrame(brand, height=1, fg_color=C["border"],
                     width=300).pack(pady=32)

        ctk.CTkLabel(brand, text="Desarrollado por el equipo Sieslo",
                     font=FONT["small"],
                     text_color=C["muted"]).pack()

        # Panel de login (derecha)
        right = ctk.CTkFrame(frame, fg_color=C["bg"])
        right.pack(side="right", fill="both", expand=True)

        box = ctk.CTkFrame(right, fg_color="transparent", width=380)
        box.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(box, text="Bienvenido",
                     font=FONT["h1"],
                     text_color=C["text"]).pack(anchor="w")
        ctk.CTkLabel(box, text="Ingresa tus credenciales para continuar",
                     font=FONT["small"],
                     text_color=C["muted"]).pack(anchor="w", pady=(4, 32))

        # Usuario
        ctk.CTkLabel(box, text="USUARIO",
                     font=("Segoe UI Semibold", 11),
                     text_color=C["muted"]).pack(anchor="w")
        self._entry_user = ctk.CTkEntry(
            box,
            placeholder_text="tu_usuario",
            height=46, width=380,
            font=("Segoe UI", 14),
            fg_color=C["card"],
            border_color=C["border"],
            text_color=C["text"],
            placeholder_text_color=C["muted"],
            corner_radius=8,
        )
        self._entry_user.pack(pady=(4, 16), fill="x")

        # Contraseña
        ctk.CTkLabel(box, text="CONTRASEÑA",
                     font=("Segoe UI Semibold", 11),
                     text_color=C["muted"]).pack(anchor="w")
        self._entry_pass = ctk.CTkEntry(
            box,
            placeholder_text="••••••••",
            show="•",
            height=46, width=380,
            font=("Segoe UI", 14),
            fg_color=C["card"],
            border_color=C["border"],
            text_color=C["text"],
            placeholder_text_color=C["muted"],
            corner_radius=8,
        )
        self._entry_pass.pack(pady=(4, 8), fill="x")
        # Enter en cualquier campo ejecuta login
        self._entry_user.bind("<Return>", lambda _: self._entry_pass.focus())
        self._entry_pass.bind("<Return>", lambda _: self._ejecutar_login())

        # Mensaje de error
        self._lbl_login_msg = ctk.CTkLabel(
            box, text="",
            font=FONT["small"],
            text_color=C["danger"],
            height=20,
        )
        self._lbl_login_msg.pack(anchor="w", pady=(0, 12))

        # Botón ingresar
        self._btn_login = ctk.CTkButton(
            box,
            text="INGRESAR",
            font=("Segoe UI Black", 15),
            height=50, width=380,
            fg_color=C["primary"],
            hover_color=C["primary_h"],
            corner_radius=8,
            command=self._ejecutar_login,
        )
        self._btn_login.pack(fill="x")

        # Botones de configuración (sin autenticación)
        botones_frame = ctk.CTkFrame(box, fg_color="transparent")
        botones_frame.pack(fill="x", pady=(12, 0))

        ctk.CTkButton(
            botones_frame,
            text="⚙️  Configurar Servidor",
            font=FONT["body"],
            height=40,
            fg_color=C["surface"],
            hover_color="#2d3348",
            text_color=C["text_dim"],
            border_width=1,
            border_color=C["border"],
            corner_radius=8,
            command=self._dialogo_configurar_servidor,
        ).pack(side="left", fill="both", expand=True, padx=(0, 6))

        ctk.CTkButton(
            botones_frame,
            text="🧪 Probar",
            font=FONT["body"],
            height=40,
            fg_color=C["surface"],
            hover_color="#2d3348",
            text_color=C["text_dim"],
            border_width=1,
            border_color=C["border"],
            corner_radius=8,
            command=self._probar_conexion_login,
        ).pack(side="left", fill="both", expand=True, padx=(6, 0))

        ctk.CTkLabel(box,
                     text="Usa Configurar Servidor para cambiar URL sin loguearte.",
                     font=FONT["small"],
                     text_color=C["muted"]).pack(pady=(16, 0))

        return frame

    def _ejecutar_login(self):
        usr = self._entry_user.get().strip()
        pwd = self._entry_pass.get()

        if not usr or not pwd:
            self._lbl_login_msg.configure(text="Completa usuario y contraseña.")
            return

        self._btn_login.configure(text="Conectando...", state="disabled")
        self._lbl_login_msg.configure(text="", text_color=C["warning"])
        self.update()

        # Cargar URL desde BD (importante: no usar la variable global)
        import sqlite3
        try:
            conn = sqlite3.connect("almacen_local.db")
            cursor = conn.cursor()
            cursor.execute("SELECT valor FROM configuracion WHERE clave='api_url'")
            resultado = cursor.fetchone()
            api_url = resultado[0] if resultado else API_BASE_URL
            conn.close()
        except:
            api_url = API_BASE_URL

        try:
            res = requests.post(
                f"{api_url}/token/",
                json={"username": usr, "password": pwd},
                timeout=5,
            )

            # Validar que el servidor respondió
            if res.status_code == 200:
                # Credenciales válidas
                self.token          = res.json().get("access")
                self.usuario_actual = usr.capitalize()
                self._btn_login.configure(text="INGRESAR", state="normal")
                self._mostrar_dashboard()
                threading.Thread(target=self._loop_sync,
                                 daemon=True).start()

            elif res.status_code == 401:
                # Credenciales inválidas (RECHAZAR siempre)
                self._lbl_login_msg.configure(
                    text="Usuario o contraseña incorrectos.",
                    text_color=C["danger"])
                self._btn_login.configure(text="INGRESAR", state="normal")
                self._entry_pass.delete(0, "end")
                self._entry_pass.focus()

            else:
                # Otro error del servidor
                self._lbl_login_msg.configure(
                    text=f"Error del servidor (HTTP {res.status_code}).",
                    text_color=C["danger"])
                self._btn_login.configure(text="INGRESAR", state="normal")

        except requests.exceptions.Timeout:
            # Servidor no responde - Ofrecer modo offline
            self._lbl_login_msg.configure(
                text="Timeout: Servidor no responde. Reintenta o intenta más tarde.",
                text_color=C["danger"])
            self._btn_login.configure(text="INGRESAR", state="normal")

        except requests.exceptions.ConnectionError as e:
            # No hay conexión de red - Intentar sin verificar SSL
            try:
                res = requests.post(
                    f"{api_url}/token/",
                    json={"username": usr, "password": pwd},
                    timeout=5,
                    verify=False  # Desactivar verificación SSL (fallback)
                )

                if res.status_code == 200:
                    self.token          = res.json().get("access")
                    self.usuario_actual = usr.capitalize()
                    self._btn_login.configure(text="INGRESAR", state="normal")
                    self._mostrar_dashboard()
                    threading.Thread(target=self._loop_sync,
                                     daemon=True).start()
                else:
                    self._lbl_login_msg.configure(
                        text="Usuario o contraseña incorrectos.",
                        text_color=C["danger"])
                    self._btn_login.configure(text="INGRESAR", state="normal")

            except Exception:
                self._lbl_login_msg.configure(
                    text="Sin conexión: Verifica URL, red e internet.",
                    text_color=C["danger"])
                self._btn_login.configure(text="INGRESAR", state="normal")

        except Exception as e:
            # Error inesperado
            self._lbl_login_msg.configure(
                text=f"Error inesperado: {str(e)[:40]}",
                text_color=C["danger"])
            self._btn_login.configure(text="INGRESAR", state="normal")

    def _probar_conexion_login(self):
        """Prueba conexión al servidor sin necesidad de credenciales."""
        import sqlite3

        # Cargar URL
        try:
            conn = sqlite3.connect("almacen_local.db")
            cursor = conn.cursor()
            cursor.execute("SELECT valor FROM configuracion WHERE clave='api_url'")
            resultado = cursor.fetchone()
            url = resultado[0] if resultado else None
            conn.close()
        except:
            url = None

        if not url:
            messagebox.showwarning(
                "URL No Configurada",
                "Primero debes configurar la URL del servidor.\n\n"
                "Click en '⚙️ Configurar Servidor'"
            )
            return

        # Probar conexión
        try:
            res = requests.get(f"{url}/almacen/inventario/", timeout=4)
            if res.status_code < 500:
                messagebox.showinfo(
                    "Conexión Exitosa ✓",
                    f"Servidor respondiendo correctamente\n"
                    f"URL: {url}\n"
                    f"HTTP {res.status_code}\n\n"
                    f"Ahora puedes ingresar con tus credenciales."
                )
            else:
                messagebox.showwarning(
                    "Error del Servidor",
                    f"El servidor respondió con error:\n"
                    f"HTTP {res.status_code}\n\n"
                    f"Verifica que Django esté corriendo."
                )
        except requests.exceptions.Timeout:
            messagebox.showerror(
                "Timeout",
                f"El servidor no responde (timeout 4s).\n\n"
                f"Verifica:\n"
                f"• URL correcta: {url}\n"
                f"• Conexión a internet\n"
                f"• Que el servidor esté en línea"
            )
        except requests.exceptions.ConnectionError:
            messagebox.showerror(
                "Sin Conexión",
                f"No se puede conectar al servidor:\n\n"
                f"URL: {url}\n\n"
                f"Verifica:\n"
                f"• URL correcta\n"
                f"• Conexión a internet\n"
                f"• Firewall/proxy del almacén"
            )
        except Exception as e:
            messagebox.showerror(
                "Error",
                f"Error al conectar:\n{str(e)[:60]}"
            )

    def _dialogo_configurar_servidor(self):
        """Abre un diálogo para cambiar URL sin autenticación."""
        from tkinter import simpledialog
        import sqlite3

        # Cargar URL actual
        try:
            conn = sqlite3.connect("almacen_local.db")
            cursor = conn.cursor()
            cursor.execute("SELECT valor FROM configuracion WHERE clave='api_url'")
            resultado = cursor.fetchone()
            url_actual = resultado[0] if resultado else "http://127.0.0.1:8000/api"
            conn.close()
        except:
            url_actual = "http://127.0.0.1:8000/api"

        # Pedir nueva URL
        nueva_url = simpledialog.askstring(
            "Configurar Servidor",
            "Ingresa la URL del servidor API:\n(Ej: https://tu-dominio.com/api)",
            initialvalue=url_actual
        )

        if nueva_url and nueva_url.strip():
            nueva_url = nueva_url.strip()
            if not (nueva_url.startswith("http://") or nueva_url.startswith("https://")):
                messagebox.showwarning(
                    "URL Inválida",
                    "La URL debe comenzar con http:// o https://"
                )
                return

            # Guardar en BD
            try:
                conn = sqlite3.connect("almacen_local.db")
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS configuracion (
                        id INTEGER PRIMARY KEY,
                        clave TEXT UNIQUE,
                        valor TEXT
                    )
                """)
                cursor.execute(
                    "INSERT OR REPLACE INTO configuracion (clave, valor) VALUES (?, ?)",
                    ("api_url", nueva_url)
                )
                conn.commit()
                conn.close()

                # Actualizar en memoria
                self.API_BASE_URL = nueva_url

                messagebox.showinfo(
                    "Éxito",
                    f"URL guardada:\n{nueva_url}\n\nAhora puedes ingresar con tus credenciales."
                )
            except Exception as e:
                messagebox.showerror("Error", f"Error al guardar: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # PANTALLA PRINCIPAL
    # ══════════════════════════════════════════════════════════════════════════

    def _crear_principal(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self._container, fg_color=C["bg"])

        # TopBar
        topbar = ctk.CTkFrame(frame, height=54,
                              fg_color=C["surface"], corner_radius=0)
        topbar.pack(side="top", fill="x")
        topbar.pack_propagate(False)

        ctk.CTkLabel(topbar, text="Sieslo  ERP",
                     font=("Segoe UI Black", 18),
                     text_color=C["primary"]).pack(side="left", padx=20)

        ctk.CTkFrame(topbar, width=1, fg_color=C["border"]).pack(
            side="left", fill="y", pady=10)

        ctk.CTkLabel(topbar, text="Módulo de Almacén",
                     font=FONT["body"],
                     text_color=C["muted"]).pack(side="left", padx=16)

        # Indicador online/offline + usuario
        self._lbl_usuario = ctk.CTkLabel(
            topbar, text="",
            font=("Segoe UI Semibold", 13),
            text_color=C["muted"],
        )
        self._lbl_usuario.pack(side="right", padx=20)

        # Área de contenido
        self._content = ctk.CTkFrame(frame, fg_color="transparent")
        self._content.pack(fill="both", expand=True)

        # Crear todos los paneles
        self.paneles = {
            "dashboard":    self._crear_dashboard(),
            "ventas":       PanelPOS(self._content, self),
            "inventario":   PanelInventario(self._content, self),
            "informes":     PanelInformes(self._content, self),
            "devoluciones": PanelDevoluciones(self._content, self),
            "configuracion":PanelConfiguracion(self._content, self),
        }

        return frame

    def _crear_dashboard(self) -> ctk.CTkFrame:
        dash = ctk.CTkFrame(self._content, fg_color=C["bg"])

        # Saludo
        header = ctk.CTkFrame(dash, fg_color="transparent")
        header.pack(pady=(50, 10))
        ctk.CTkLabel(header, text="¿Qué deseas hacer hoy?",
                     font=FONT["h1"],
                     text_color=C["text"]).pack()
        ctk.CTkLabel(header, text="Selecciona un módulo para comenzar",
                     font=FONT["sub"],
                     text_color=C["muted"]).pack(pady=(6, 0))

        # Grid de botones
        grid = ctk.CTkFrame(dash, fg_color="transparent")
        grid.pack(expand=True, pady=20)

        for idx, (texto, _, modulo, color, hover) in enumerate(MODULE_BUTTONS):
            row, col = divmod(idx, 3)
            icono    = self._iconos.get(modulo)

            card = ctk.CTkButton(
                grid,
                text=texto,
                image=icono,
                compound="top",
                width=210, height=200,
                font=("Segoe UI Semibold", 14),
                fg_color=C["card"],
                hover_color=color,
                border_width=1,
                border_color=C["border"],
                text_color=C["text_dim"],
                corner_radius=16,
                command=lambda m=modulo: self.cambiar_modulo(m),
            )
            card.grid(row=row, column=col, padx=12, pady=12)

            # Franja de color en la parte superior de cada card
            accent = ctk.CTkFrame(card, height=4, fg_color=color,
                                  corner_radius=0)
            # No se puede superponer fácilmente en CTkButton, pero el hover lo compensa

        return dash

    # ── Navegación ─────────────────────────────────────────────────────────────

    def _mostrar_login(self):
        self._pantalla_principal.pack_forget()
        self._pantalla_login.pack(fill="both", expand=True)
        self._entry_user.focus()

    def _mostrar_dashboard(self):
        self._pantalla_login.pack_forget()
        self._lbl_usuario.configure(
            text=f"👤  {self.usuario_actual}")
        self._pantalla_principal.pack(fill="both", expand=True)
        self.cambiar_modulo("dashboard")

    def cambiar_modulo(self, nombre_modulo: str):
        for panel in self.paneles.values():
            panel.pack_forget()

        panel = self.paneles[nombre_modulo]
        panel.pack(fill="both", expand=True)

        # Auto-recarga por módulo
        if nombre_modulo == "ventas":
            panel._entry_busqueda.focus()
        elif nombre_modulo == "inventario":
            panel.cargar_datos()
        elif nombre_modulo == "informes":
            panel.generar_informe()
        elif nombre_modulo == "devoluciones":
            panel.cargar_historial()

    # ══════════════════════════════════════════════════════════════════════════
    # SINCRONIZACIÓN
    # ══════════════════════════════════════════════════════════════════════════

    def sincronizar_catalogo(self):
        """Descarga el catálogo desde Django y actualiza SQLite."""
        if not self.token:
            messagebox.showwarning("Sin sesión",
                                   "Inicia sesión para sincronizar.")
            return
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            res = requests.get(
                f"{API_BASE_URL}/almacen/inventario/",
                headers=headers, timeout=10)

            if res.status_code == 200:
                productos = res.json()
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                for p in productos:
                    cursor.execute(
                        "INSERT OR REPLACE INTO productos_local "
                        "(id_producto, codigo_barras, nombre, precio_detal, stock_local) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (p["id"], p["codigo_barras"], p["nombre"],
                         p["precio_detal"], p["stock_actual"])
                    )
                conn.commit()
                conn.close()
                messagebox.showinfo(
                    "Sincronización exitosa",
                    f"{len(productos)} productos actualizados.")
            else:
                messagebox.showerror(
                    "Error del servidor",
                    f"Código HTTP: {res.status_code}")
        except Exception as exc:
            messagebox.showerror("Sin conexión",
                                 f"No se pudo sincronizar:\n{exc}")

    def _loop_sync(self):
        """Bucle silencioso cada 60 s."""
        while True:
            if self.token:
                self._sync_silenciosa()
            time.sleep(60)

    def _sync_silenciosa(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            # Descargar catálogo
            res = requests.get(
                f"{API_BASE_URL}/almacen/inventario/",
                headers=headers, timeout=10)

            if res.status_code == 200:
                productos = res.json()
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                for p in productos:
                    cursor.execute(
                        "INSERT OR REPLACE INTO productos_local "
                        "(id_producto, codigo_barras, nombre, precio_detal, stock_local) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (p["id"], p["codigo_barras"], p["nombre"],
                         p["precio_detal"], p["stock_actual"])
                    )
                conn.commit()
                conn.close()

            # Subir ventas pendientes (estructura preparada)
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id_venta, fecha, total, metodo_pago, detalles "
                "FROM ventas_pendientes_sincronizar "
                "WHERE estado_sincronizacion = 0"
            )
            pendientes = cursor.fetchall()
            conn.close()

            # POST a Django por cada venta pendiente
            for id_venta, fecha, total, metodo_pago, detalles_json in pendientes:
                try:
                    import json
                    detalles = json.loads(detalles_json)

                    # Convertir detalles a formato esperado por Django
                    detalles_lista = []
                    for item_id, item_data in detalles.items():
                        detalles_lista.append({
                            "producto": item_data.get("id_producto"),
                            "cantidad": item_data.get("cant"),
                            "precio_unitario": item_data.get("precio"),
                            "subtotal": item_data.get("subtotal"),
                        })

                    payload = {
                        "consecutivo_local": f"ALM-{id_venta}",
                        "fecha_venta": fecha,
                        "total_venta": total,
                        "metodo_pago": metodo_pago,
                        "detalles": detalles_lista,
                    }

                    res = requests.post(
                        f"{API_BASE_URL}/almacen/facturas/",
                        json=payload,
                        headers=headers,
                        timeout=10
                    )

                    if res.status_code == 201:
                        # Marcar como sincronizado
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE ventas_pendientes_sincronizar "
                            "SET estado_sincronizacion = 1 "
                            "WHERE id_venta = ?",
                            (id_venta,)
                        )
                        conn.commit()
                        conn.close()
                except Exception:
                    # Si falla una venta, continuar con la siguiente
                    pass

            self.after(0, lambda: self._lbl_usuario.configure(
                text=f"🟢  {self.usuario_actual}",
                text_color=C["success"]))

        except Exception:
            self.after(0, lambda: self._lbl_usuario.configure(
                text=f"🔴  {self.usuario_actual}  (sin conexión)",
                text_color=C["danger"]))


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = AppAlmacen()
    app.mainloop()