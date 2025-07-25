# devoluciones/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from clientes.models import Empresa

class DevolucionCliente(models.Model):
    """Representa una devolución de productos realizada por un cliente."""
    
    ESTADO_DEVOLUCION_CHOICES = [
        ('INICIADA', 'Iniciada por Vendedor'),
        ('RECIBIDA_EN_BODEGA', 'Recibida en Bodega'),
        ('VERIFICADA', 'Verificada y Finalizada'),
        ('CON_DIFERENCIAS', 'Verificada con Diferencias'),
    ]
    
    
    empresa = models.ForeignKey(
        Empresa, 
        on_delete=models.CASCADE, 
        related_name='devoluciones'
    )
    
    cliente = models.ForeignKey(
        'clientes.Cliente', 
        on_delete=models.PROTECT, 
        related_name='devoluciones', 
        verbose_name="Cliente que Devuelve"
    )
    pedido_original = models.ForeignKey(
        'pedidos.Pedido', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='devoluciones_asociadas', 
        verbose_name="Pedido Original (Opcional)"
    )
    fecha_hora = models.DateTimeField(
        default=timezone.now, 
        verbose_name="Fecha y Hora de Devolución"
    )
    motivo = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Motivo General"
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='devoluciones_procesadas', 
        verbose_name="Usuario que Procesa"
    )
    
    estado = models.CharField(
        max_length=20, 
        choices=ESTADO_DEVOLUCION_CHOICES, 
        default='INICIADA',
        verbose_name="Estado de la Devolución"
    )

    def clean(self):  
        super().clean()
        if self.empresa_id:
            if self.cliente_id and self.cliente.empresa_id != self.empresa_id:
                raise ValidationError({
                    'cliente': f"El cliente '{self.cliente}' no pertenece a la empresa '{self.empresa}'."
                })

            if self.pedido_original_id and self.pedido_original.empresa_id != self.empresa_id:
                raise ValidationError({
                    'pedido_original': f"El pedido #{self.pedido_original_id} no pertenece a la empresa '{self.empresa}'."
                })
                
    def save(self, *args, **kwargs):
        # Si aún no se ha definido empresa, intenta deducirla del cliente o pedido
        if not self.empresa_id:
            if self.cliente_id:
                self.empresa_id = self.cliente.empresa_id
            elif self.pedido_original_id:
                self.empresa_id = self.pedido_original.empresa_id

        self.full_clean()  # Esto llama a .clean() y asegura validación completa
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Devolución #{self.pk} ({self.empresa.nombre}) - {self.cliente.nombre_completo}"

    class Meta:
        verbose_name = "Devolución de Cliente"
        verbose_name_plural = "Devoluciones de Clientes"
        ordering = ['-empresa', '-fecha_hora']
        permissions = [
            ("can_receive_devolucion", "Puede recibir y verificar devoluciones en bodega"),
        ]


class DetalleDevolucion(models.Model):
    """Representa un producto específico dentro de una devolución."""
    ESTADO_PRODUCTO_DEVOLUCION_CHOICES = [
        ('BUENO', 'Buen estado (Reingresa a stock)'),
        ('DEFECTUOSO', 'Defectuoso (Revisión/Reparación)'),
        ('DESECHAR', 'Para Desechar'),
    ]
    devolucion = models.ForeignKey(
        DevolucionCliente, 
        related_name='detalles', 
        on_delete=models.CASCADE, 
        verbose_name="Devolución Asociada"
    )
    producto = models.ForeignKey(
        'productos.Producto', 
        on_delete=models.PROTECT, 
        related_name='productos_devueltos', 
        verbose_name="Producto Devuelto"
    )
    
    
    cantidad = models.PositiveIntegerField(
        default=1, 
        verbose_name="Cantidad Reportada por Vendedor" 
    )

    cantidad_recibida_bodega = models.PositiveIntegerField(
        default=0,
        verbose_name="Cantidad Recibida en Bodega"
    )
    
    
    estado_producto = models.CharField(
        max_length=15, 
        choices=ESTADO_PRODUCTO_DEVOLUCION_CHOICES, 
        default='BUENO', 
        verbose_name="Estado del Producto Devuelto"
    )
    
    def clean(self):
        """
        <<< REFUERZO DE SEGURIDAD E INTEGRIDAD >>>
        Valida que el producto pertenezca a la misma empresa que la devolución padre.
        """
        super().clean()
        if self.producto_id and self.devolucion_id:
            if self.producto.empresa_id != self.devolucion.empresa_id:
                raise ValidationError({
                    'producto': f"El producto '{self.producto}' no pertenece a la empresa '{self.devolucion.empresa}'."
                })

    def save(self, *args, **kwargs):
        # Ejecuta las validaciones antes de guardar.
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre} [{self.get_estado_producto_display()}]"

    class Meta:
        verbose_name = "Detalle de Devolución"
        verbose_name_plural = "Detalles de Devolución"
        # RECOMENDACIÓN: Añadir constraint a nivel de BD para mayor robustez.
        constraints = [
            models.UniqueConstraint(fields=['devolucion', 'producto', 'estado_producto'], name='devolucion_producto_estado_unico')
        ]