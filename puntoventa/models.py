# puntoventa/models.py
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.core.exceptions import ValidationError
from clientes.models import Empresa


def ruta_comprobante_transferencia(instance, filename):
    """Ruta de guardado para la foto del comprobante de una transferencia, organizada por empresa."""
    empresa_id = instance.venta.empresa_id if instance.venta_id else 'sin_asignar'
    extension = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'jpg'
    nombre_unico = uuid.uuid4().hex[:12]
    return f'puntoventa/comprobantes_transferencia/empresa_{empresa_id}/{nombre_unico}.{extension}'


class TurnoCaja(models.Model):
    """
    Un turno de caja: desde que un cajero abre una bodega de Punto de Venta
    con un monto inicial, hasta que la cierra contando el efectivo real.
    Todas las ventas de ese lapso quedan ligadas a este turno.
    """
    class EstadoTurno(models.TextChoices):
        ABIERTO = 'ABIERTO', 'Abierto'
        CERRADO = 'CERRADO', 'Cerrado'

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='turnos_caja', verbose_name="Empresa")
    bodega = models.ForeignKey(
        'bodega.Bodega', on_delete=models.PROTECT, related_name='turnos_caja',
        verbose_name="Bodega / Caja de Punto de Venta"
    )
    usuario_cajero = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='turnos_caja_abiertos',
        verbose_name="Cajero"
    )
    fecha_apertura = models.DateTimeField(auto_now_add=True, verbose_name="Fecha y Hora de Apertura")
    saldo_inicial = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Monto Inicial Declarado")

    fecha_cierre = models.DateTimeField(null=True, blank=True, verbose_name="Fecha y Hora de Cierre")
    saldo_final_contado = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Efectivo Contado al Cierre")
    diferencia = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Diferencia (Contado - Esperado)")

    estado = models.CharField(max_length=10, choices=EstadoTurno.choices, default=EstadoTurno.ABIERTO, verbose_name="Estado del Turno")

    def total_ventas_efectivo(self):
        return PagoVentaPOS.objects.filter(
            venta__turno=self, venta__estado=VentaPOS.EstadoVenta.COMPLETADA, metodo_pago='EFECTIVO'
        ).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')

    def total_ventas(self):
        return VentaPOS.objects.filter(turno=self, estado=VentaPOS.EstadoVenta.COMPLETADA).aggregate(
            total=Sum('total_venta')
        )['total'] or Decimal('0.00')

    def totales_por_metodo_pago(self):
        """Total vendido en este turno, agrupado por método de pago (efectivo/tarjeta/transferencia)."""
        filas = PagoVentaPOS.objects.filter(
            venta__turno=self, venta__estado=VentaPOS.EstadoVenta.COMPLETADA
        ).values('metodo_pago').annotate(total=Sum('monto'))
        totales = {valor: Decimal('0.00') for valor, _ in PagoVentaPOS.MetodoPago.choices}
        for fila in filas:
            totales[fila['metodo_pago']] = fila['total']
        return totales

    def total_reembolsos_efectivo(self):
        return DevolucionCambioPOS.objects.filter(turno=self).aggregate(
            total=Sum('monto_reembolsado_efectivo')
        )['total'] or Decimal('0.00')

    def total_cobros_adicionales_efectivo(self):
        return DevolucionCambioPOS.objects.filter(
            turno=self, metodo_pago_adicional=PagoVentaPOS.MetodoPago.EFECTIVO
        ).aggregate(total=Sum('monto_cobrado_adicional'))['total'] or Decimal('0.00')

    def saldo_esperado(self):
        """
        Efectivo que debería haber en caja: monto inicial + ventas en efectivo,
        menos lo reembolsado en efectivo por devoluciones, más lo cobrado en
        efectivo por diferencias de cambios de producto, todo de este turno.
        """
        return (
            self.saldo_inicial
            + self.total_ventas_efectivo()
            - self.total_reembolsos_efectivo()
            + self.total_cobros_adicionales_efectivo()
        )

    def __str__(self):
        return f"Turno #{self.pk} - {self.bodega.nombre} ({self.get_estado_display()})"

    class Meta:
        verbose_name = "Turno de Caja"
        verbose_name_plural = "Turnos de Caja"
        ordering = ['-fecha_apertura']
        constraints = [
            models.UniqueConstraint(
                fields=['bodega'],
                condition=models.Q(estado='ABIERTO'),
                name='un_turno_abierto_por_bodega'
            )
        ]


class VentaPOS(models.Model):
    """Una venta de mostrador realizada en un Punto de Venta."""
    class EstadoVenta(models.TextChoices):
        COMPLETADA = 'COMPLETADA', 'Completada'
        ANULADA = 'ANULADA', 'Anulada'

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='ventas_pos', verbose_name="Empresa")
    turno = models.ForeignKey(TurnoCaja, on_delete=models.PROTECT, related_name='ventas', verbose_name="Turno de Caja")
    cliente = models.ForeignKey(
        'clientes.Cliente', on_delete=models.PROTECT, related_name='ventas_pos',
        null=True, blank=True, verbose_name="Cliente",
        help_text="Vacío = Cliente Mostrador (venta genérica sin cliente registrado)."
    )
    fecha_hora = models.DateTimeField(auto_now_add=True, verbose_name="Fecha y Hora")
    consecutivo = models.PositiveIntegerField(verbose_name="Número de Recibo")
    total_venta = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Total de la Venta")
    estado = models.CharField(max_length=12, choices=EstadoVenta.choices, default=EstadoVenta.COMPLETADA, verbose_name="Estado")
    notas = models.TextField(blank=True, null=True, verbose_name="Notas / Observaciones")

    def save(self, *args, **kwargs):
        if not self.empresa_id and self.turno_id:
            self.empresa = self.turno.empresa
        if not self.consecutivo:
            ultimo = VentaPOS.objects.filter(empresa=self.empresa).aggregate(m=models.Max('consecutivo'))['m'] or 0
            self.consecutivo = ultimo + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Venta POS #{self.consecutivo} ({self.empresa.nombre})"

    class Meta:
        verbose_name = "Venta de Punto de Venta"
        verbose_name_plural = "Ventas de Punto de Venta"
        ordering = ['-fecha_hora']
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'consecutivo'], name='consecutivo_unico_por_empresa_pos')
        ]


class DetalleVentaPOS(models.Model):
    """Un producto dentro de una VentaPOS."""
    venta = models.ForeignKey(VentaPOS, on_delete=models.CASCADE, related_name='detalles', verbose_name="Venta")
    producto = models.ForeignKey('productos.Producto', on_delete=models.PROTECT, related_name='ventas_pos_detalle', verbose_name="Producto")
    cantidad = models.PositiveIntegerField(verbose_name="Cantidad")
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Precio Unitario")

    precio_override = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name="Precio Ajustado Manualmente",
        help_text="Si el cajero ajustó el precio de esta línea, el valor final queda aquí."
    )
    motivo_override = models.CharField(max_length=255, blank=True, null=True, verbose_name="Motivo del Ajuste de Precio")

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Subtotal")

    @property
    def precio_final(self):
        return self.precio_override if self.precio_override is not None else self.precio_unitario

    def clean(self):
        super().clean()
        if self.precio_override is not None and not (self.motivo_override and self.motivo_override.strip()):
            raise ValidationError({'motivo_override': "Debes indicar un motivo para ajustar manualmente el precio."})

    def save(self, *args, **kwargs):
        self.subtotal = self.cantidad * self.precio_final
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cantidad} x {self.producto} (Venta #{self.venta_id})"

    class Meta:
        verbose_name = "Detalle de Venta POS"
        verbose_name_plural = "Detalles de Venta POS"


class PagoVentaPOS(models.Model):
    """Un pago aplicado a una VentaPOS (permite pago dividido entre varios métodos)."""
    class MetodoPago(models.TextChoices):
        EFECTIVO = 'EFECTIVO', 'Efectivo'
        TARJETA = 'TARJETA', 'Tarjeta'
        TRANSFERENCIA = 'TRANSFERENCIA', 'Transferencia'

    venta = models.ForeignKey(VentaPOS, on_delete=models.CASCADE, related_name='pagos', verbose_name="Venta")
    metodo_pago = models.CharField(max_length=20, choices=MetodoPago.choices, verbose_name="Método de Pago")
    monto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto")
    monto_recibido = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name="Monto Recibido en Efectivo",
        help_text="Solo aplica a pagos en efectivo: cuánto entregó físicamente el cliente."
    )
    comprobante_transferencia = models.ImageField(
        upload_to=ruta_comprobante_transferencia, null=True, blank=True,
        verbose_name="Foto del Comprobante de Transferencia"
    )

    @property
    def cambio(self):
        if self.monto_recibido is None:
            return None
        return self.monto_recibido - self.monto

    def __str__(self):
        return f"{self.get_metodo_pago_display()}: ${self.monto} (Venta #{self.venta_id})"

    class Meta:
        verbose_name = "Pago de Venta POS"
        verbose_name_plural = "Pagos de Venta POS"


class PrecioEspecialPOS(models.Model):
    """
    Precio de liquidación/saldo para un producto específico, válido solo cuando
    se vende desde una bodega de Punto de Venta puntual (no afecta el precio de
    catálogo usado en el resto del sistema).
    """
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='precios_especiales_pos', verbose_name="Empresa")
    bodega = models.ForeignKey(
        'bodega.Bodega', on_delete=models.CASCADE, related_name='precios_especiales_pos',
        verbose_name="Bodega de Punto de Venta"
    )
    producto = models.ForeignKey(
        'productos.Producto', on_delete=models.CASCADE, related_name='precios_especiales_pos',
        verbose_name="Producto"
    )
    precio_especial = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Precio Especial (Saldo)")
    usuario_actualizacion = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Actualizado por"
    )
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    def save(self, *args, **kwargs):
        if not self.empresa_id and self.producto_id:
            self.empresa = self.producto.empresa
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.producto} @ {self.bodega.nombre}: ${self.precio_especial}"

    class Meta:
        verbose_name = "Precio Especial de Punto de Venta"
        verbose_name_plural = "Precios Especiales de Punto de Venta"
        constraints = [
            models.UniqueConstraint(fields=['bodega', 'producto'], name='un_precio_especial_por_producto_y_bodega')
        ]


class DevolucionCambioPOS(models.Model):
    """
    Devolución o cambio de producto en el Punto de Venta, siempre ligada a la
    VentaPOS original. El reembolso al cliente siempre sale en efectivo del
    turno que la procesa; si se entregan productos nuevos más costosos, la
    diferencia se cobra con cualquier método de pago.
    """
    class TipoDevolucion(models.TextChoices):
        DEVOLUCION = 'DEVOLUCION', 'Devolución (Reembolso)'
        CAMBIO = 'CAMBIO', 'Cambio de Producto'

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='devoluciones_pos', verbose_name="Empresa")
    venta_original = models.ForeignKey(
        VentaPOS, on_delete=models.PROTECT, related_name='devoluciones_cambios',
        verbose_name="Venta POS Original"
    )
    turno = models.ForeignKey(
        TurnoCaja, on_delete=models.PROTECT, related_name='devoluciones_cambios',
        verbose_name="Turno que Procesa"
    )
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="Procesado por")
    fecha_hora = models.DateTimeField(auto_now_add=True, verbose_name="Fecha y Hora")
    tipo = models.CharField(max_length=12, choices=TipoDevolucion.choices, verbose_name="Tipo")
    motivo = models.TextField(verbose_name="Motivo")

    total_valor_devuelto = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Valor de lo Devuelto")
    total_valor_entregado = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Valor de lo Entregado (Cambio)")

    monto_reembolsado_efectivo = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Reembolsado en Efectivo")
    metodo_pago_adicional = models.CharField(
        max_length=20, choices=PagoVentaPOS.MetodoPago.choices, null=True, blank=True,
        verbose_name="Método de Pago de la Diferencia (si el cliente debe más)"
    )
    monto_cobrado_adicional = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Cobrado Adicional")

    def clean(self):
        super().clean()
        if not (self.motivo and self.motivo.strip()):
            raise ValidationError({'motivo': "Debes indicar un motivo para la devolución o cambio."})

    def save(self, *args, **kwargs):
        if not self.empresa_id and self.venta_original_id:
            self.empresa = self.venta_original.empresa
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_tipo_display()} #{self.pk} (Venta POS #{self.venta_original.consecutivo})"

    class Meta:
        verbose_name = "Devolución/Cambio de Punto de Venta"
        verbose_name_plural = "Devoluciones/Cambios de Punto de Venta"
        ordering = ['-fecha_hora']


class DetalleDevolucionPOS(models.Model):
    """Un producto devuelto por el cliente, ligado a la línea de la venta original."""
    devolucion = models.ForeignKey(DevolucionCambioPOS, on_delete=models.CASCADE, related_name='detalles_devueltos', verbose_name="Devolución/Cambio")
    detalle_venta_original = models.ForeignKey(
        DetalleVentaPOS, on_delete=models.PROTECT, related_name='devoluciones_detalle',
        verbose_name="Línea de la Venta Original"
    )
    cantidad = models.PositiveIntegerField(verbose_name="Cantidad Devuelta")
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Precio Unitario (de la venta original)")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Subtotal")

    def save(self, *args, **kwargs):
        self.subtotal = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cantidad} x {self.detalle_venta_original.producto} (Devolución #{self.devolucion_id})"

    class Meta:
        verbose_name = "Detalle de Producto Devuelto"
        verbose_name_plural = "Detalles de Productos Devueltos"


class DetalleEntregaCambioPOS(models.Model):
    """Un producto nuevo entregado al cliente como parte de un cambio."""
    devolucion = models.ForeignKey(DevolucionCambioPOS, on_delete=models.CASCADE, related_name='detalles_entregados', verbose_name="Devolución/Cambio")
    producto = models.ForeignKey('productos.Producto', on_delete=models.PROTECT, related_name='entregas_cambio_pos', verbose_name="Producto Entregado")
    cantidad = models.PositiveIntegerField(verbose_name="Cantidad Entregada")
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Precio Unitario")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Subtotal")

    def save(self, *args, **kwargs):
        self.subtotal = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cantidad} x {self.producto} (Cambio #{self.devolucion_id})"

    class Meta:
        verbose_name = "Detalle de Producto Entregado en Cambio"
        verbose_name_plural = "Detalles de Productos Entregados en Cambio"
