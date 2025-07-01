# pedidos/models.py
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Sum
from django.core.exceptions import ValidationError

class Pedido(models.Model):
    # --- CORRECCIÓN PARA LA MIGRACIÓN ---
    # Se añade null=True para permitir que las filas existentes en la base de datos
    # tengan este campo vacío temporalmente. Después de la migración, se puede
    # escribir un script para poblar este campo y luego quitar null=True.
    empresa = models.ForeignKey(
        'clientes.Empresa', 
        on_delete=models.CASCADE, 
        related_name='pedidos',
        verbose_name="Empresa",
        null=True
    )
    
    ESTADO_PEDIDO_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('PENDIENTE_APROBACION_CARTERA', 'Pendiente Aprobación Cartera'),
        ('RECHAZADO_CARTERA', 'Rechazado por Cartera'),
        ('PENDIENTE_APROBACION_ADMIN', 'Pendiente Aprobación Administración'),
        ('RECHAZADO_ADMIN', 'Rechazado por Administración'),
        ('APROBADO_ADMIN', 'Aprobado por Administración (Listo Bodega)'),
        ('PROCESANDO', 'Procesando en Bodega'),
        ('COMPLETADO', 'Completado en Bodega'),
        ('ENVIADO', 'Enviado'),
        ('ENTREGADO', 'Entregado'),
        ('CANCELADO', 'Cancelado'),
    ]
    
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.PROTECT, related_name='pedidos', verbose_name="Cliente", null=True, blank=True)
    vendedor = models.ForeignKey('vendedores.Vendedor', on_delete=models.PROTECT, related_name='pedidos', verbose_name="Vendedor")
    fecha_hora = models.DateTimeField(default=timezone.now, verbose_name="Fecha y Hora del Pedido")
    estado = models.CharField(max_length=35, choices=ESTADO_PEDIDO_CHOICES, default='BORRADOR', verbose_name="Estado del Pedido")
    notas = models.TextField(blank=True, null=True, verbose_name="Observaciones del Vendedor")
    porcentaje_descuento = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), verbose_name="Descuento Aplicado (%)")
    token_descarga_fotos = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    motivo_cartera = models.TextField(blank=True, null=True, verbose_name="Motivo/Notas Cartera")
    usuario_decision_cartera = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='pedidos_decision_cartera', verbose_name="Decisión Tomada por (Cartera)")
    fecha_decision_cartera = models.DateTimeField(null=True, blank=True, verbose_name="Fecha Decisión Cartera")
    motivo_admin = models.TextField(blank=True, null=True, verbose_name="Motivo/Notas Administración")
    usuario_decision_admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='pedidos_decision_admin', verbose_name="Decisión Tomada por (Admin.)")
    fecha_decision_admin = models.DateTimeField(null=True, blank=True, verbose_name="Fecha Decisión Administración")

    IVA_RATE = Decimal('0.19')
    IVA_FACTOR = Decimal('1.00') + IVA_RATE
    
    def clean(self):
        super().clean()
        # --- REFUERZO DE SEGURIDAD ---
        # Si el pedido tiene una empresa asignada, se valida la consistencia.
        if self.empresa:
            if self.cliente and self.cliente.empresa_id != self.empresa_id:
                raise ValidationError(f"El cliente '{self.cliente}' no pertenece a la empresa '{self.empresa}'.")
            
            if self.vendedor and self.vendedor.empresa_id != self.empresa_id:
                raise ValidationError(f"El vendedor '{self.vendedor}' no pertenece a la empresa '{self.empresa}'.")

    def save(self, *args, **kwargs):
        # --- LÓGICA DE AUTO-ASIGNACIÓN ---
        # Si no tiene empresa, intenta asignarla desde el cliente o vendedor.
        if not self.empresa_id:
            if self.cliente and self.cliente.empresa_id:
                self.empresa_id = self.cliente.empresa_id
            elif self.vendedor and self.vendedor.empresa_id:
                self.empresa_id = self.vendedor.empresa_id
        
        self.clean()
        super().save(*args, **kwargs)

    @property
    def subtotal_base_bruto(self):
        total = Decimal('0.00')
        for detalle in self.detalles.all():
            if detalle.precio_unitario and detalle.cantidad:
                base_unitaria = detalle.precio_unitario / self.IVA_FACTOR if self.IVA_FACTOR > Decimal('1.00') else detalle.precio_unitario
                total += (base_unitaria * detalle.cantidad)
        return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # (El resto de las properties no necesitan cambios)
    @property
    def subtotal_base_para_descuento(self):
        return self.subtotal_base_bruto

    @property
    def valor_total_descuento(self):
        if not self.porcentaje_descuento or self.porcentaje_descuento <= Decimal('0.00'):
            return Decimal('0.00')
        descuento_pct = self.porcentaje_descuento / Decimal('100.00')
        valor_dcto = self.subtotal_base_para_descuento * descuento_pct
        return valor_dcto.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @property
    def subtotal_final_neto(self):
        subtotal_neto = self.subtotal_base_para_descuento - self.valor_total_descuento
        return max(Decimal('0.00'), subtotal_neto)

    @property
    def valor_iva_final(self):
        iva_final = self.subtotal_final_neto * self.IVA_RATE
        return iva_final.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @property
    def total_a_pagar(self):
        total = self.subtotal_final_neto + self.valor_iva_final
        return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    @property
    def total_cantidad_productos(self):
        resultado = self.detalles.aggregate(cantidad_total=Sum('cantidad'))
        total = resultado.get('cantidad_total', 0) 
        return total if total is not None else 0
    
    def get_enlace_descarga_fotos(self, request=None):
        from django.urls import reverse
        try:
            path = reverse('pedidos:descargar_fotos_pedido', kwargs={'token_pedido': str(self.token_descarga_fotos)})
            if request:
                return request.build_absolute_uri(path)
            return path
        except Exception:
            return None

    def __str__(self):
        cliente_str = self.cliente.nombre_completo if self.cliente else "Sin Cliente"
        return f"Pedido #{self.pk} - {cliente_str} ({self.get_estado_display()})"
    
    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        ordering = ['-fecha_hora']

class DetallePedido(models.Model):
    pedido = models.ForeignKey(Pedido, related_name='detalles', on_delete=models.CASCADE, verbose_name="Pedido Asociado") 
    producto = models.ForeignKey('productos.Producto', on_delete=models.PROTECT, related_name='detalles_pedido', verbose_name="Producto") 
    cantidad = models.PositiveIntegerField(default=1, verbose_name="Cantidad") 
    precio_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Precio Unitario (IVA Incl.)"
    )
    verificado_bodega = models.BooleanField(default=False, verbose_name="Verificado Bodega") 
    cantidad_verificada = models.IntegerField(null=True, blank=True, verbose_name="Cantidad Verificada") 
    
    def clean(self):
        super().clean()
        # La validación ahora es más robusta.
        if self.producto and self.pedido and self.pedido.empresa and self.producto.empresa != self.pedido.empresa:
            raise ValidationError(f"El producto '{self.producto}' no pertenece a la misma empresa que el Pedido #{self.pedido.pk}.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)   

    @property
    def subtotal(self):
        if self.precio_unitario is not None and self.cantidad is not None:
            return (Decimal(self.cantidad) * self.precio_unitario).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return Decimal('0.00')

    @property
    def cantidad_pendiente(self):
        if self.cantidad_verificada is None:
            return self.cantidad
        else:
            pendiente = self.cantidad - self.cantidad_verificada
            return max(0, pendiente)

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre} (Pedido #{self.pedido.pk})"

    class Meta:
        verbose_name = "Detalle de Pedido"
        verbose_name_plural = "Detalles de Pedido"
        unique_together = ('pedido', 'producto')