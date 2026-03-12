"""
Panel de Configuración del Sistema.
General, Red/Sincronización y Mantenimiento de BD.
"""
from __future__ import annotations

from contextlib import contextmanager
from tkinter import messagebox, StringVar

import customtkinter as ctk
import requests

from database import obtener_conexion


class SimpleVar:
    """Variable simple compatible con CTkSegmentedButton sin necesidad de tkinter.StringVar"""
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
    "danger_bg": "#1a0505",
}

FONT = {
    "h1":    ("Segoe UI Black",    24),
    "h2":    ("Segoe UI Semibold", 16),
    "h3":    ("Segoe UI Semibold", 13),
    "body":  ("Segoe UI",          13),
    "small": ("Segoe UI",          11),
}


@contextmanager
def _db():
    conn = obtener_conexion()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _seccion(parent, titulo: str) -> ctk.CTkFrame:
    """Crea un bloque de sección con título y card."""
    ctk.CTkLabel(parent, text=titulo,
                 font=FONT["h2"],
                 text_color=C["text"]).pack(anchor="w", padx=4, pady=(20, 8))
    card = ctk.CTkFrame(parent, fg_color=C["card"],
                        corner_radius=12, border_width=1,
                        border_color=C["border"])
    card.pack(fill="x", pady=(0, 6))
    return card


def _fila(card: ctk.CTkFrame, label: str, desc: str = "") -> ctk.CTkFrame:
    """Fila estándar dentro de una card."""
    row = ctk.CTkFrame(card, fg_color="transparent")
    row.pack(fill="x", padx=20, pady=14)
    col = ctk.CTkFrame(row, fg_color="transparent")
    col.pack(side="left")
    ctk.CTkLabel(col, text=label,
                 font=FONT["body"],
                 text_color=C["text"]).pack(anchor="w")
    if desc:
        ctk.CTkLabel(col, text=desc,
                     font=FONT["small"],
                     text_color=C["muted"]).pack(anchor="w")
    return row


# ══════════════════════════════════════════════════════════════════════════════
# PANEL CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════════════════════

class PanelConfiguracion(ctk.CTkFrame):

    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=C["bg"])
        self.controller = controller

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

        ctk.CTkLabel(bar, text="CONFIGURACIÓN DEL SISTEMA",
                     font=FONT["h1"],
                     text_color=C["text"]).pack(side="left", padx=8)

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

        self._tab_general = self._tabs.add("  ⚙️  General  ")
        self._tab_sync    = self._tabs.add("  🔄  Red y Sincronización  ")
        self._tab_mant    = self._tabs.add("  ⚠️  Mantenimiento  ")

        self._build_tab_general()
        self._build_tab_sync()
        self._build_tab_mantenimiento()

    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA 1 – GENERAL
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_general(self):
        body = ctk.CTkScrollableFrame(self._tab_general, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=8, pady=8)

        # ── Apariencia ──
        card = _seccion(body, "Apariencia")

        row = _fila(card, "Tema Visual",
                    "Cambia el aspecto de toda la aplicación.")
        self._tema_var = SimpleVar(value="Dark")
        ctk.CTkSegmentedButton(
            row,
            values=["Light", "Dark", "System"],
            variable=self._tema_var,
            selected_color=C["primary"],
            selected_hover_color=C["primary_h"],
            unselected_color=C["surface"],
            unselected_hover_color=C["card_alt"],
            text_color=C["text"],
            font=FONT["body"],
            height=38,
            command=self._cambiar_tema,
        ).pack(side="right")

        row2 = _fila(card, "Escala de la Interfaz",
                     "Ajusta el tamaño de todos los elementos.")
        self._escala_var = SimpleVar(value="100%")
        ctk.CTkSegmentedButton(
            row2,
            values=["80%", "90%", "100%", "110%", "120%"],
            variable=self._escala_var,
            selected_color=C["primary"],
            selected_hover_color=C["primary_h"],
            unselected_color=C["surface"],
            unselected_hover_color=C["card_alt"],
            text_color=C["text"],
            font=FONT["body"],
            height=38,
            command=self._cambiar_escala,
        ).pack(side="right")

        # ── Información del sistema ──
        card2 = _seccion(body, "Información del Sistema")

        import sys, platform
        info = {
            "Python":    sys.version.split()[0],
            "Sistema":   platform.system() + " " + platform.release(),
            "Plataforma": platform.machine(),
        }
        for k, v in info.items():
            r = ctk.CTkFrame(card2, fg_color="transparent")
            r.pack(fill="x", padx=20, pady=8)
            ctk.CTkLabel(r, text=k, font=FONT["body"],
                         text_color=C["muted"]).pack(side="left")
            ctk.CTkLabel(r, text=v, font=("Consolas", 13),
                         text_color=C["text"]).pack(side="right")
            ctk.CTkFrame(card2, height=1, fg_color=C["border"]).pack(fill="x", padx=20)

    def _cambiar_tema(self, valor: str):
        ctk.set_appearance_mode(valor)

    def _cambiar_escala(self, valor: str):
        factor = float(valor.replace("%", "")) / 100
        ctk.set_widget_scaling(factor)

    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA 2 – RED Y SINCRONIZACIÓN
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_sync(self):
        body = ctk.CTkScrollableFrame(self._tab_sync, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=8, pady=8)

        api_url = getattr(self.controller, "API_BASE_URL", "http://127.0.0.1:8000/api")

        # ── Estado de conexión ──
        card = _seccion(body, "Estado de Conexión con Django")

        # URL del servidor
        url_row = ctk.CTkFrame(card, fg_color="transparent")
        url_row.pack(fill="x", padx=20, pady=(14, 4))
        ctk.CTkLabel(url_row, text="Servidor:", font=FONT["body"],
                     text_color=C["muted"]).pack(side="left")
        ctk.CTkLabel(url_row, text=api_url,
                     font=("Consolas", 13),
                     text_color=C["primary"]).pack(side="left", padx=10)

        # Indicador y botón
        status_row = ctk.CTkFrame(card, fg_color="transparent")
        status_row.pack(fill="x", padx=20, pady=(4, 14))

        self._lbl_estado = ctk.CTkLabel(
            status_row,
            text="○  Sin verificar",
            font=("Segoe UI Semibold", 13),
            text_color=C["muted"],
        )
        self._lbl_estado.pack(side="left")

        ctk.CTkButton(
            status_row,
            text="Probar Conexión",
            font=FONT["body"], width=160, height=38,
            fg_color=C["primary"], hover_color=C["primary_h"],
            corner_radius=8,
            command=self._probar_conexion,
        ).pack(side="right")

        ctk.CTkFrame(card, height=1, fg_color=C["border"]).pack(fill="x", padx=20)

        # ── Sincronización ──
        card2 = _seccion(body, "Sincronización de Catálogo")

        row = _fila(card2, "Descargar catálogo desde la nube",
                    "Sobreescribe el inventario local con los datos del servidor.")
        ctk.CTkButton(
            row,
            text="🔄  Sincronizar ahora",
            font=FONT["body"], width=180, height=38,
            fg_color=C["success"], hover_color=C["success_h"],
            corner_radius=8,
            command=self._sync_manual,
        ).pack(side="right")

        # Log de estado de sync
        log_frame = ctk.CTkFrame(card2, fg_color=C["surface"], corner_radius=8)
        log_frame.pack(fill="x", padx=20, pady=(4, 14))
        self._lbl_sync_log = ctk.CTkLabel(
            log_frame,
            text="Sin actividad reciente.",
            font=("Consolas", 11),
            text_color=C["muted"],
            justify="left",
        )
        self._lbl_sync_log.pack(anchor="w", padx=14, pady=10)

    def _probar_conexion(self):
        self._lbl_estado.configure(text="◌  Probando...", text_color=C["warning"])
        self.update()
        api_url = getattr(self.controller, "API_BASE_URL", "http://127.0.0.1:8000/api")
        try:
            res = requests.get(f"{api_url}/almacen/inventario/", timeout=4)
            # 401 también significa que el servidor responde
            if res.status_code < 500:
                self._lbl_estado.configure(
                    text=f"●  Conectado  (HTTP {res.status_code})",
                    text_color=C["success"],
                )
            else:
                self._lbl_estado.configure(
                    text=f"●  Error del servidor  (HTTP {res.status_code})",
                    text_color=C["warning"],
                )
        except requests.exceptions.ConnectionError:
            self._lbl_estado.configure(
                text="●  Sin conexión — servidor no alcanzable",
                text_color=C["danger"],
            )
        except requests.exceptions.Timeout:
            self._lbl_estado.configure(
                text="●  Tiempo de espera agotado (timeout 4s)",
                text_color=C["danger"],
            )
        except Exception as exc:
            self._lbl_estado.configure(
                text=f"●  Error inesperado: {exc}",
                text_color=C["danger"],
            )

    def _sync_manual(self):
        if hasattr(self.controller, "sincronizar_catalogo"):
            self._lbl_sync_log.configure(
                text="Sincronizando...", text_color=C["warning"])
            self.update()
            try:
                self.controller.sincronizar_catalogo()
                self._lbl_sync_log.configure(
                    text="✓  Sincronización completada.",
                    text_color=C["success"])
            except Exception as exc:
                self._lbl_sync_log.configure(
                    text=f"✗  Error: {exc}",
                    text_color=C["danger"])
        else:
            self._lbl_sync_log.configure(
                text="⚠  La sincronización automática está activa en segundo plano.",
                text_color=C["warning"])

    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA 3 – MANTENIMIENTO
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_mantenimiento(self):
        body = ctk.CTkScrollableFrame(self._tab_mant, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=8, pady=8)

        # Aviso
        aviso = ctk.CTkFrame(body, fg_color=C["danger_bg"],
                             corner_radius=12, border_width=1,
                             border_color=C["danger"])
        aviso.pack(fill="x", pady=(4, 16))
        ctk.CTkLabel(aviso,
                     text="⚠️  ZONA DE PELIGRO — Estas acciones son irreversibles",
                     font=("Segoe UI Semibold", 13),
                     text_color=C["danger"]).pack(anchor="w", padx=18, pady=(14, 2))
        ctk.CTkLabel(aviso,
                     text="Solo afectan la base de datos local de este computador.\n"
                          "No borran datos que ya fueron sincronizados con la nube.",
                     font=FONT["small"],
                     text_color=C["text_dim"],
                     justify="left").pack(anchor="w", padx=18, pady=(0, 14))

        # ── Acción 1: Historial de caja ──
        card1 = _seccion(body, "Historial de Transacciones")
        row1 = _fila(card1,
                     "Limpiar Ventas y Devoluciones",
                     "Borra todas las ventas y movimientos guardados.\n"
                     "El arqueo de caja quedará en $ 0.")
        ctk.CTkButton(
            row1,
            text="🗑  Borrar Historial",
            font=FONT["body"], width=170, height=38,
            fg_color=C["danger"], hover_color=C["danger_h"],
            corner_radius=8,
            command=self._limpiar_historial,
        ).pack(side="right")

        # ── Acción 2: Catálogo ──
        card2 = _seccion(body, "Catálogo de Productos")
        row2 = _fila(card2,
                     "Vaciar Catálogo Local",
                     "Elimina todos los productos del inventario local.\n"
                     "Deberás sincronizar de nuevo para recuperarlos.")
        ctk.CTkButton(
            row2,
            text="🗑  Vaciar Catálogo",
            font=FONT["body"], width=170, height=38,
            fg_color=C["danger"], hover_color=C["danger_h"],
            corner_radius=8,
            command=self._vaciar_catalogo,
        ).pack(side="right")

        # ── Acción 3: Reset total ──
        card3 = _seccion(body, "Reset Completo")
        row3 = _fila(card3,
                     "Borrar TODO (Historial + Catálogo)",
                     "Deja la base de datos local completamente vacía.\n"
                     "Usar solo para reinstalación o cambio de tienda.")
        ctk.CTkButton(
            row3,
            text="💀  Reset Total",
            font=("Segoe UI Black", 13), width=170, height=38,
            fg_color="#450a0a", hover_color=C["danger_h"],
            border_width=1, border_color=C["danger"],
            text_color=C["danger"],
            corner_radius=8,
            command=self._reset_total,
        ).pack(side="right")

    # ── Acciones de mantenimiento ──────────────────────────────────────────────

    def _limpiar_historial(self):
        if not messagebox.askyesno(
            "Confirmar",
            "¿Borrar TODAS las ventas y devoluciones de este equipo?\n\n"
            "Esta acción no se puede deshacer.",
            icon="warning", parent=self,
        ):
            return
        try:
            with _db() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM ventas_pendientes_sincronizar")
                cursor.execute("DELETE FROM devoluciones_pendientes")
                for tabla in ("ventas_pendientes_sincronizar",
                              "devoluciones_pendientes"):
                    cursor.execute(
                        "DELETE FROM sqlite_sequence WHERE name=?", (tabla,))
            messagebox.showinfo("Listo",
                                "Historial borrado. El arqueo de caja está limpio.",
                                parent=self)
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self)

    def _vaciar_catalogo(self):
        if not messagebox.askyesno(
            "Confirmar",
            "¿Vaciar el catálogo de productos local?\n\n"
            "El sistema quedará sin inventario hasta la próxima sincronización.",
            icon="warning", parent=self,
        ):
            return
        try:
            with _db() as conn:
                conn.cursor().execute("DELETE FROM productos_local")
            messagebox.showinfo("Listo",
                                "Catálogo vaciado. Sincroniza para recuperarlo.",
                                parent=self)
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self)

    def _reset_total(self):
        confirm = messagebox.askyesno(
            "⚠️ RESET TOTAL ⚠️",
            "Esto borrará:\n"
            "  • Todo el catálogo de productos\n"
            "  • Todo el historial de ventas\n"
            "  • Todo el historial de devoluciones\n\n"
            "¿Estás completamente seguro?",
            icon="warning", parent=self,
        )
        if not confirm:
            return
        # Segunda confirmación
        if not messagebox.askyesno(
            "Última confirmación",
            "Esta acción es IRREVERSIBLE.\n¿Continuar?",
            icon="warning", parent=self,
        ):
            return
        try:
            with _db() as conn:
                cursor = conn.cursor()
                for tabla in ("ventas_pendientes_sincronizar",
                              "devoluciones_pendientes",
                              "productos_local"):
                    cursor.execute(f"DELETE FROM {tabla}")
                cursor.execute("DELETE FROM sqlite_sequence")
            messagebox.showinfo("Reset Completo",
                                "La base de datos local ha sido vaciada.",
                                parent=self)
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self)