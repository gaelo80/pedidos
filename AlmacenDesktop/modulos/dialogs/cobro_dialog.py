"""
Diálogo de cobro y ventana de comprobante post-venta.
"""
import re
import urllib.parse
import webbrowser
from typing import Callable

import customtkinter as ctk
from tkinter import messagebox, BooleanVar

from modulos.carrito import Carrito
from repositories.venta_repo import VentaRepository

# ── Paleta ─────────────────────────────────────────────────────────────────────
C = {
    "bg":       "#0f1117",
    "surface":  "#1a1d27",
    "card":     "#20243a",
    "primary":  "#3b82f6",
    "primary_h":"#2563eb",
    "success":  "#10b981",
    "success_h":"#059669",
    "danger":   "#ef4444",
    "warning":  "#f59e0b",
    "text":     "#f1f5f9",
    "muted":    "#64748b",
    "border":   "#2d3348",
    "wa":       "#25D366",
    "wa_h":     "#128C7E",
}

F_TITLE = ("Segoe UI Semibold", 15)
F_BODY  = ("Segoe UI", 13)
F_MONO  = ("Consolas", 13)
F_BIG   = ("Segoe UI Black", 42)


def _entry(parent, placeholder="", **kw):
    return ctk.CTkEntry(
        parent,
        placeholder_text=placeholder,
        fg_color=C["card"],
        border_color=C["border"],
        text_color=C["text"],
        placeholder_text_color=C["muted"],
        height=40,
        font=F_BODY,
        **kw,
    )


# ══════════════════════════════════════════════════════════════════════════════
# VENTANA DE COBRO
# ══════════════════════════════════════════════════════════════════════════════

class VentanaCobro(ctk.CTkToplevel):
    """
    Modal de cobro.
    on_exito(datos_completos, total, metodo) se invoca al confirmar.
    """

    METODOS = ["Efectivo", "Tarjeta Débito", "Tarjeta Crédito", "Transferencia / Nequi"]

    def __init__(self, parent, carrito: Carrito, on_exito: Callable):
        super().__init__(parent)
        self.carrito   = carrito
        self.on_exito  = on_exito
        self._fe_var   = BooleanVar(master=self.nametowidget("."), value=False)

        self.title("Procesar Pago")
        self.geometry("480x660")
        self.configure(fg_color=C["bg"])
        self.attributes("-topmost", True)
        self.grab_set()
        self.resizable(False, False)

        self._build()

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build(self):
        # Banner total
        banner = ctk.CTkFrame(self, fg_color=C["surface"],
                              corner_radius=0, height=110)
        banner.pack(fill="x")
        ctk.CTkLabel(banner, text="TOTAL A COBRAR",
                     font=("Segoe UI", 11),
                     text_color=C["muted"]).pack(pady=(18, 0))
        ctk.CTkLabel(banner,
                     text=f"$ {self.carrito.total:,.0f}",
                     font=F_BIG,
                     text_color=C["success"]).pack()

        # Cuerpo
        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=10)
        self._body = body

        # Método de pago
        ctk.CTkLabel(body, text="MÉTODO DE PAGO",
                     font=("Segoe UI Semibold", 11),
                     text_color=C["muted"]).pack(anchor="w", pady=(10, 4))

        self._seg_pago = ctk.CTkSegmentedButton(
            body,
            values=self.METODOS,
            selected_color=C["primary"],
            selected_hover_color=C["primary_h"],
            unselected_color=C["card"],
            unselected_hover_color=C["surface"],
            text_color=C["text"],
            font=F_BODY,
            dynamic_resizing=False,
            height=40,
        )
        self._seg_pago.set(self.METODOS[0])
        self._seg_pago.pack(fill="x", pady=(0, 10))
        self._seg_pago.configure(command=self._on_metodo_cambio)

        # ── Panel Efectivo: monto recibido + devuelta ──────────────────────────
        self._panel_efectivo = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=12)
        self._panel_efectivo.pack(fill="x", pady=(0, 6))

        ctk.CTkLabel(self._panel_efectivo, text="MONTO RECIBIDO DEL CLIENTE",
                     font=("Segoe UI Semibold", 11),
                     text_color=C["muted"]).pack(anchor="w", padx=16, pady=(14, 4))

        self._entry_recibido = ctk.CTkEntry(
            self._panel_efectivo,
            placeholder_text="0",
            height=52,
            font=("Segoe UI Black", 26),
            justify="right",
            fg_color=C["surface"],
            border_color=C["primary"],
            text_color=C["text"],
            placeholder_text_color=C["muted"],
            corner_radius=10,
        )
        self._entry_recibido.pack(fill="x", padx=16, pady=(0, 10))
        self._entry_recibido.bind("<KeyRelease>", self._calcular_devuelta)

        # Botones de billetes rápidos
        billetes_row = ctk.CTkFrame(self._panel_efectivo, fg_color="transparent")
        billetes_row.pack(fill="x", padx=16, pady=(0, 10))
        ctk.CTkLabel(billetes_row, text="Cobro rápido:",
                     font=("Segoe UI", 11),
                     text_color=C["muted"]).pack(side="left", padx=(0, 8))

        total = self.carrito.total
        # Genera sugerencias: total exacto + billetes comunes superiores
        sugerencias = self._sugerencias_billetes(total)
        for val in sugerencias:
            ctk.CTkButton(
                billetes_row,
                text=f"$ {val:,.0f}",
                font=("Segoe UI Semibold", 11),
                height=32, width=90,
                fg_color=C["surface"],
                hover_color=C["primary"],
                border_width=1,
                border_color=C["border"],
                text_color=C["text"],
                corner_radius=6,
                command=lambda v=val: self._set_recibido(v),
            ).pack(side="left", padx=3)

        # Fila de devuelta
        devuelta_frame = ctk.CTkFrame(self._panel_efectivo,
                                      fg_color=C["surface"], corner_radius=10)
        devuelta_frame.pack(fill="x", padx=16, pady=(0, 14))

        col_izq = ctk.CTkFrame(devuelta_frame, fg_color="transparent")
        col_izq.pack(side="left", padx=16, pady=10)
        ctk.CTkLabel(col_izq, text="DEVUELTA",
                     font=("Segoe UI Semibold", 11),
                     text_color=C["muted"]).pack(anchor="w")
        self._lbl_devuelta = ctk.CTkLabel(col_izq,
                                          text="$ 0",
                                          font=("Segoe UI Black", 28),
                                          text_color=C["success"])
        self._lbl_devuelta.pack(anchor="w")

        col_der = ctk.CTkFrame(devuelta_frame, fg_color="transparent")
        col_der.pack(side="right", padx=16, pady=10)
        ctk.CTkLabel(col_der, text="FALTA",
                     font=("Segoe UI Semibold", 11),
                     text_color=C["muted"]).pack(anchor="e")
        self._lbl_falta = ctk.CTkLabel(col_der,
                                       text=f"$ {total:,.0f}",
                                       font=("Segoe UI Black", 28),
                                       text_color=C["warning"])
        self._lbl_falta.pack(anchor="e")

        ctk.CTkFrame(body, height=1, fg_color=C["border"]).pack(fill="x", pady=6)

        # Switch factura electrónica
        fe_row = ctk.CTkFrame(body, fg_color="transparent")
        fe_row.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(fe_row, text="FACTURA ELECTRÓNICA (DIAN)",
                     font=("Segoe UI Semibold", 11),
                     text_color=C["muted"]).pack(side="left")
        ctk.CTkSwitch(fe_row, text="",
                      variable=self._fe_var,
                      onvalue=True, offvalue=False,
                      button_color=C["primary"],
                      progress_color=C["primary"],
                      command=self._toggle_fe).pack(side="right")

        # Formulario cliente (oculto por defecto)
        self._form_fe = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=12)
        ctk.CTkLabel(self._form_fe,
                     text="Datos del cliente",
                     font=F_TITLE,
                     text_color=C["text"]).pack(anchor="w", padx=16, pady=(14, 6))

        def _fila(label, placeholder, required=False):
            f = ctk.CTkFrame(self._form_fe, fg_color="transparent")
            f.pack(fill="x", padx=16, pady=3)
            txt = f"{label}  {'*' if required else ''}"
            ctk.CTkLabel(f, text=txt, font=("Segoe UI", 11),
                         text_color=C["text" if required else "muted"]).pack(anchor="w")
            e = _entry(f, placeholder)
            e.pack(fill="x", pady=(2, 0))
            return e

        self._e_doc    = _fila("NIT o Cédula",        "900123456-1",      required=True)
        self._e_nombre = _fila("Nombre / Razón Social","Empresa S.A.S.",   required=True)
        self._e_correo = _fila("Correo electrónico",   "cliente@correo.com")
        self._e_tel    = _fila("Teléfono",             "57300...")
        ctk.CTkFrame(self._form_fe, height=12, fg_color="transparent").pack()

        # Resumen de items
        ctk.CTkFrame(body, height=1, fg_color=C["border"]).pack(fill="x", pady=8)
        ctk.CTkLabel(body, text="RESUMEN",
                     font=("Segoe UI Semibold", 11),
                     text_color=C["muted"]).pack(anchor="w", pady=(4, 6))

        for item in self.carrito.items.values():
            row = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=8, height=44)
            row.pack(fill="x", pady=2)
            row.pack_propagate(False)
            ctk.CTkLabel(row, text=item.nombre,
                         font=F_BODY, text_color=C["text"],
                         anchor="w").pack(side="left", padx=14)
            ctk.CTkLabel(row, text=f"×{item.cantidad}  $ {item.subtotal:,.0f}",
                         font=F_MONO, text_color=C["muted"]).pack(side="right", padx=14)

        # Pie con botón confirmar
        pie = ctk.CTkFrame(self, fg_color=C["surface"],
                           corner_radius=0, height=76)
        pie.pack(fill="x", side="bottom")
        ctk.CTkButton(
            pie,
            text="CONFIRMAR VENTA",
            font=("Segoe UI Black", 16),
            height=50,
            fg_color=C["success"],
            hover_color=C["success_h"],
            text_color="white",
            corner_radius=10,
            command=self._procesar,
        ).pack(fill="x", padx=16, pady=13)

    # ── Efectivo helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _sugerencias_billetes(total: float) -> list:
        """Devuelve hasta 4 sugerencias de cobro rápido basadas en el total."""
        billetes = [1_000, 2_000, 5_000, 10_000, 20_000, 50_000, 100_000, 200_000]
        sugerencias = []
        for b in billetes:
            if b >= total:
                sugerencias.append(b)
            if len(sugerencias) == 4:
                break
        # Si el total exacto no está, ponlo primero
        if total not in sugerencias:
            sugerencias = [total] + sugerencias[:3]
        return sugerencias[:4]

    def _set_recibido(self, valor: float):
        """Rellena el campo con un valor predefinido."""
        self._entry_recibido.delete(0, "end")
        self._entry_recibido.insert(0, f"{valor:,.0f}")
        self._calcular_devuelta()
        self._entry_recibido.focus()

    def _calcular_devuelta(self, _event=None):
        """Actualiza los labels de devuelta y falta en tiempo real."""
        texto = self._entry_recibido.get().replace(",", "").replace(".", "").strip()
        total = self.carrito.total
        try:
            recibido = float(texto) if texto else 0.0
        except ValueError:
            recibido = 0.0

        devuelta = recibido - total
        if devuelta >= 0:
            self._lbl_devuelta.configure(
                text=f"$ {devuelta:,.0f}",
                text_color=C["success"],
            )
            self._lbl_falta.configure(text="$ 0", text_color=C["muted"])
        else:
            self._lbl_devuelta.configure(text="$ 0", text_color=C["muted"])
            self._lbl_falta.configure(
                text=f"$ {abs(devuelta):,.0f}",
                text_color=C["warning"],
            )

    def _on_metodo_cambio(self, valor: str):
        """Muestra u oculta el panel de efectivo según el método elegido."""
        if valor == "Efectivo":
            self._panel_efectivo.pack(fill="x", pady=(0, 6))
            self._calcular_devuelta()
        else:
            self._panel_efectivo.pack_forget()

    def _toggle_fe(self):
        if self._fe_var.get():
            self._form_fe.pack(fill="x", pady=(6, 0))
        else:
            self._form_fe.pack_forget()

    # ── Validación ─────────────────────────────────────────────────────────────

    def _validar(self) -> bool:
        if not self._fe_var.get():
            return True
        if not self._e_doc.get().strip():
            messagebox.showwarning("Campo requerido",
                                   "El NIT / Cédula es obligatorio.", parent=self)
            self._e_doc.focus()
            return False
        if not self._e_nombre.get().strip():
            messagebox.showwarning("Campo requerido",
                                   "El Nombre / Razón Social es obligatorio.", parent=self)
            self._e_nombre.focus()
            return False
        correo = self._e_correo.get().strip()
        if correo and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", correo):
            messagebox.showwarning("Correo inválido",
                                   "El formato del correo no es válido.", parent=self)
            self._e_correo.focus()
            return False
        return True

    # ── Procesamiento ──────────────────────────────────────────────────────────

    def _procesar(self):
        if not self._validar():
            return

        # Validar que el efectivo cubra el total
        if self._seg_pago.get() == "Efectivo":
            texto = self._entry_recibido.get().replace(",", "").replace(".", "").strip()
            try:
                recibido = float(texto) if texto else 0.0
            except ValueError:
                recibido = 0.0
            if recibido < self.carrito.total:
                falta = self.carrito.total - recibido
                messagebox.showwarning(
                    "Monto insuficiente",
                    f"El monto recibido no cubre el total.\nFaltan: $ {falta:,.0f}",
                    parent=self,
                )
                self._entry_recibido.focus()
                return

        datos_cliente = (
            {
                "requiere_fe": True,
                "documento":   self._e_doc.get().strip(),
                "nombre":      self._e_nombre.get().strip(),
                "correo":      self._e_correo.get().strip(),
                "telefono":    self._e_tel.get().strip(),
            }
            if self._fe_var.get()
            else {"requiere_fe": False}
        )

        metodo = self._seg_pago.get()

        # Calcular devuelta si fue efectivo
        devuelta = None
        if metodo == "Efectivo":
            texto = self._entry_recibido.get().replace(",", "").replace(".", "").strip()
            try:
                recibido = float(texto)
                devuelta = recibido - self.carrito.total
            except ValueError:
                pass

        try:
            VentaRepository.guardar(self.carrito, metodo, datos_cliente)
        except Exception as exc:
            messagebox.showerror("Error al guardar venta",
                                 f"No se pudo registrar la venta:\n{exc}", parent=self)
            return

        datos_completos = {
            "items":    self.carrito.to_dict(),
            "cliente":  datos_cliente,
            "devuelta": devuelta,
        }
        self.destroy()
        self.on_exito(datos_completos, self.carrito.total, metodo)


# ══════════════════════════════════════════════════════════════════════════════
# VENTANA DE COMPROBANTE
# ══════════════════════════════════════════════════════════════════════════════

class VentanaComprobante(ctk.CTkToplevel):
    """Muestra el comprobante post-venta y permite enviarlo por WhatsApp."""

    def __init__(self, parent, datos: dict, total: float, metodo: str):
        super().__init__(parent)
        self.datos  = datos
        self.total  = total
        self.metodo = metodo

        self.title("Venta Registrada")
        self.geometry("460x500")
        self.configure(fg_color=C["bg"])
        self.attributes("-topmost", True)
        self.resizable(False, False)

        self._msg_wa = self._construir_mensaje()
        self._build()

    def _construir_mensaje(self) -> str:
        cliente      = self.datos.get("cliente", {})
        requiere_fe  = cliente.get("requiere_fe", False)

        if requiere_fe:
            lineas = [
                "🚨 *SOLICITUD DE FACTURA ELECTRÓNICA DIAN* 🚨", "",
                "👤 *DATOS DEL CLIENTE:*",
                f"  NIT/CC: {cliente.get('documento', '')}",
                f"  Nombre: {cliente.get('nombre', '')}",
                f"  Correo: {cliente.get('correo', '') or 'No indicado'}",
                f"  Teléfono: {cliente.get('telefono', '') or 'No indicado'}",
                "", "🛒 *PRENDAS VENDIDAS:*",
            ]
        else:
            lineas = ["🛒 *COMPROBANTE DE COMPRA*", ""]

        for d in self.datos["items"].values():
            lineas.append(f"  ▪ {d['nombre']} ×{d['cant']}  →  $ {d['subtotal']:,.0f}")

        lineas += ["", f"💰 *TOTAL:* $ {self.total:,.0f}  ({self.metodo})"]
        return "\n".join(lineas)

    def _build(self):
        # Banner éxito
        banner = ctk.CTkFrame(self, fg_color=C["success"],
                              corner_radius=0, height=90)
        banner.pack(fill="x")
        ctk.CTkLabel(banner, text="✓  VENTA REGISTRADA",
                     font=("Segoe UI Black", 22),
                     text_color="white").pack(expand=True)

        # Total
        ctk.CTkLabel(self, text=f"$ {self.total:,.0f}",
                     font=("Segoe UI Black", 36),
                     text_color=C["success"]).pack(pady=(20, 0))
        ctk.CTkLabel(self, text=self.metodo,
                     font=F_BODY,
                     text_color=C["muted"]).pack()

        # Devuelta (solo efectivo)
        devuelta = self.datos.get("devuelta")
        if devuelta is not None and devuelta >= 0:
            dev_frame = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=10)
            dev_frame.pack(fill="x", padx=20, pady=(14, 0))
            ctk.CTkLabel(dev_frame, text="DEVUELTA AL CLIENTE",
                         font=("Segoe UI Semibold", 11),
                         text_color=C["muted"]).pack(pady=(10, 0))
            ctk.CTkLabel(dev_frame,
                         text=f"$ {devuelta:,.0f}",
                         font=("Segoe UI Black", 32),
                         text_color=C["warning"]).pack(pady=(0, 10))

        # Aviso factura electrónica
        cliente = self.datos.get("cliente", {})
        if cliente.get("requiere_fe"):
            aviso = ctk.CTkFrame(self, fg_color="#2d1a0a", corner_radius=10)
            aviso.pack(fill="x", padx=20, pady=16)
            ctk.CTkLabel(aviso,
                         text="⚠  Se requiere Facturación Electrónica DIAN\n"
                              "Envía los datos al área de contabilidad.",
                         font=F_BODY,
                         text_color=C["warning"],
                         justify="center").pack(pady=14)
        else:
            ctk.CTkLabel(self,
                         text="¿Deseas enviar el comprobante al cliente?",
                         font=F_BODY,
                         text_color=C["muted"]).pack(pady=16)

        # Botones
        ctk.CTkButton(
            self,
            text="🟢  Enviar por WhatsApp",
            font=("Segoe UI Semibold", 15),
            height=52,
            fg_color=C["wa"],
            hover_color=C["wa_h"],
            corner_radius=10,
            command=self._enviar_wa,
        ).pack(fill="x", padx=20, pady=(0, 10))

        ctk.CTkButton(
            self,
            text="Cerrar sin enviar",
            font=F_BODY, height=40,
            fg_color="transparent",
            border_width=1, border_color=C["border"],
            text_color=C["muted"],
            hover_color=C["card"],
            corner_radius=10,
            command=self.destroy,
        ).pack(fill="x", padx=20)

    def _enviar_wa(self):
        cliente     = self.datos.get("cliente", {})
        requiere_fe = cliente.get("requiere_fe", False)
        titulo      = ("Número de Contabilidad (WhatsApp):"
                       if requiere_fe else "WhatsApp del cliente:")

        tel_raw = ctk.CTkInputDialog(
            text=f"{titulo}\n(Incluye código de país, ej: 57300...)",
            title="Enviar WhatsApp",
        ).get_input()

        if tel_raw:
            tel = re.sub(r"\D", "", tel_raw)
            if len(tel) < 10:
                messagebox.showwarning("Número inválido",
                                       "El número debe tener al menos 10 dígitos.",
                                       parent=self)
                return
            url = f"https://wa.me/{tel}?text={urllib.parse.quote(self._msg_wa)}"
            webbrowser.open(url)
            self.destroy()