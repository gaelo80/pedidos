# pedidos/models.py
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Sum
from django.core.exceptions import ValidationError
from pedidos_online.models import ClienteOnline

class Pedido(models.Model):
    empresa = models.ForeignKey(
        'clientes.Empresa', 
        on_delete=models.CASCADE, 
        related_name='pedidos',
        verbose_name="Empresa",        
    )
    
    ESTADO_PEDIDO_CHOICES = [
        ('PENDIENTE_CLIENTE', 'Pendiente por Aprobación de Cliente'),
        ('BORRADOR', 'Borrador'),
        ('PENDIENTE_APROBACION_CARTERA', 'Pendiente Aprobación Cartera'),
        ('RECHAZADO_CARTERA', 'Rechazado por Cartera'),
        ('PENDIENTE_APROBACION_ADMIN', 'Pendiente Aprobación Administración'),
        ('RECHAZADO_ADMIN', 'Rechazado por Administración'),
        ('APROBADO_ADMIN', 'Aprobado por Administración (Listo Bodega)'),
        ('PROCESANDO', 'Procesando en Bodega'),
        ('COMPLETADO', 'Completado en Bodega'),
        ('ENVIADO_INCOMPLETO', 'Enviado Incompleto'),
        ('LISTO_BODEGA_DIRECTO', 'Listo para Bodega (Directo)'),
        ('ENVIADO', 'Enviado'),
        ('ENTREGADO', 'Entregado'),
        ('CANCELADO', 'Cancelado'),
        ('CAMBIO_REGISTRADO', 'Cambio de Producto Registrado'),
        
    ]
    
    cliente_online = models.ForeignKey(
        ClienteOnline,
        on_delete=models.PROTECT,
        related_name='pedidos_online_rel',
        verbose_name="Cliente Online",
        null=True, # <<< PERMITIR NULO
        blank=True
    )
    
    TIPO_PEDIDO_CHOICES = [
        ('ESTANDAR', 'Estándar'),
        ('ONLINE', 'Online'),
    ]
    
    tipo_pedido = models.CharField(
        max_length=10,
        choices=TIPO_PEDIDO_CHOICES,
        default='ESTANDAR',
        verbose_name="Tipo de Pedido"
    )

    
    cliente = models.ForeignKey(
        'clientes.Cliente',
        on_delete=models.PROTECT, 
        related_name='pedidos_estandar',
        verbose_name="Cliente", 
        null=True, 
        blank=True
    )
    
    prospecto = models.ForeignKey(
        'prospectos.Prospecto',
        on_delete=models.SET_NULL,
        related_name='pedidos_prospecto', 
        verbose_name="Prospecto (Cliente Nuevo)",
        null=True,
        blank=True
    )
    
    FORMA_PAGO_CHOICES = [
        ('CREDITO', 'Crédito'),
        ('CONTADO', 'Contado'),
        ('ADDI', 'Addi'),
        ('TARJETA_CREDITO', 'Tarjeta de Crédito'),
        ('TARJETA_DEBITO', 'Tarjeta Débito'),
        ('TRANSFERENCIA', 'Transferencia Bancaria'),
        ('OTRO_ONLINE', 'Otro Pago Online'),
    ]
    
    forma_pago = models.CharField(
        max_length=20,
        choices=FORMA_PAGO_CHOICES,
        default='CREDITO',
        verbose_name="Forma de Pago"
    )
    
    comprobante_pago = models.FileField(
        upload_to='comprobantes_pago/', # Directory where files will be saved
        null=True,
        blank=True,
        verbose_name="Comprobante de Pago"
    )
    
    
    
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

    mostrar_precios_pdf = models.BooleanField(
        default=True,  # Por defecto, mostrar precios
        verbose_name="Mostrar Precios en PDF"
    )
    
    IVA_RATE = Decimal('0.19')
    IVA_FACTOR = Decimal('1.00') + IVA_RATE
    
    @property
    def destinatario(self):
        """
        Devuelve el objeto del cliente o del prospecto asociado al pedido.
        Esto simplifica el acceso a los datos del destinatario en las plantillas.
        """
        if self.tipo_pedido == 'ONLINE' and self.cliente_online:
            return self.cliente_online
        if self.cliente:
            return self.cliente
        if self.prospecto:
            return self.prospecto
        
        # Objeto de respaldo si no hay ni cliente ni prospecto, para evitar errores.
        class DestinatarioVacio:
            nombre_completo = "No Asignado"
            identificacion = "N/A"
            telefono = "N/A"
            direccion = "N/A"
            email = "N/A"
            ciudad = None
        
        return DestinatarioVacio()  
    
    
    
    def clean(self):
        super().clean()

        # Validaciones para pedidos ESTANDAR
        if self.tipo_pedido == 'ESTANDAR':
            if self.cliente_online:
                raise ValidationError("Un pedido Estándar no puede tener un Cliente Online.")
            if self.cliente and self.prospecto:
                raise ValidationError("Un pedido Estándar no puede estar asociado a un cliente existente y a un prospecto al mismo tiempo.")
            if not self.cliente and not self.prospecto:
                raise ValidationError("Un pedido Estándar debe estar asociado a un cliente existente o a un prospecto.")

        # Validaciones para pedidos ONLINE
        elif self.tipo_pedido == 'ONLINE':
            if self.cliente or self.prospecto:
                raise ValidationError("Un pedido Online no puede tener un Cliente Estándar o un Prospecto.")
            if not self.cliente_online:
                raise ValidationError("Un pedido Online debe tener un Cliente Online asignado.")

        # Mantener las validaciones de empresa existentes y añadir para cliente_online
        empresa = getattr(self, 'empresa', None)
        if empresa:
            if self.cliente and self.cliente.empresa_id != self.empresa_id:
                raise ValidationError(f"El cliente '{self.cliente}' no pertenece a la empresa '{empresa}'.")
            if self.cliente_online and self.cliente_online.empresa_id != self.empresa_id:
                raise ValidationError(f"El cliente online '{self.cliente_online}' no pertenece a la empresa '{empresa}'.")
            if self.vendedor and hasattr(self.vendedor.user, 'empresa') and self.vendedor.user.empresa_id != self.empresa_id:
                raise ValidationError(f"El vendedor '{self.vendedor}' no pertenece a la empresa '{empresa}'.")
            if self.prospecto and self.prospecto.empresa_id != self.empresa_id:
                 raise ValidationError(f"El prospecto '{self.prospecto}' no pertenece a la empresa '{empresa}'.")
            
    def save(self, *args, **kwargs):
        if not self.empresa_id:
            if self.cliente and self.cliente.empresa_id:
                self.empresa_id = self.cliente.empresa_id
            elif self.vendedor and self.vendedor.empresa_id:
                self.empresa_id = self.vendedor.empresa_id
            elif self.prospecto and self.prospecto.empresa_id:
                self.empresa_id = self.prospecto.empresa_id
            elif self.cliente_online and self.cliente_online.empresa_id: # Añadir esta condición
                self.empresa_id = self.cliente_online.empresa_id
        super().save(*args, **kwargs)

    @property
    def subtotal_base_bruto(self):
        total = Decimal('0.00')
        for detalle in self.detalles.all():
            if detalle.precio_unitario and detalle.cantidad:
                base_unitaria = detalle.precio_unitario / self.IVA_FACTOR if self.IVA_FACTOR > Decimal('1.00') else detalle.precio_unitario
                total += (base_unitaria * detalle.cantidad)
        return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

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
        # Asegúrate de que destinatario siempre devuelva un objeto con nombre_completo
        nombre_referencia = self.destinatario.nombre_completo
        if self.prospecto:
            nombre_referencia = f"[Prospecto] {nombre_referencia}"
        elif self.tipo_pedido == 'ONLINE' and self.cliente_online:
            nombre_referencia = f"[Online] {nombre_referencia}"
        return f"Pedido #{self.pk} - {nombre_referencia} ({self.get_estado_display()})"
    
    
    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        ordering = ['-fecha_hora']

class DetallePedido(models.Model):
    pedido = models.ForeignKey(Pedido, related_name='detalles', on_delete=models.CASCADE, verbose_name="Pedido Asociado") 
    producto = models.ForeignKey('productos.Producto', on_delete=models.PROTECT, related_name='detalles_pedido', verbose_name="Producto") 
    
    cantidad = models.IntegerField(default=1, verbose_name="Cantidad") 
    
    TIPO_DETALLE_CHOICES = [
        ('ENVIO', 'Producto Enviado'),
        ('DEVOLUCION', 'Producto Devuelto'),
    ]
    tipo_detalle = models.CharField(
        max_length=10,
        choices=TIPO_DETALLE_CHOICES,
        default='ENVIO', # Por defecto, la mayoría de los detalles son envíos
        verbose_name="Tipo de Detalle"
    )
    
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

            if self.tipo_detalle == 'DEVOLUCION':
                return f"DEVOLUCIÓN: {self.cantidad} x {self.producto.nombre} (Pedido #{self.pedido.pk})"
            return f"{self.cantidad} x {self.producto.nombre} (Pedido #{self.pedido.pk})"

    class Meta:
        verbose_name = "Detalle de Pedido"
        verbose_name_plural = "Detalles de Pedido"
        unique_together = ('pedido', 'producto', 'tipo_detalle')