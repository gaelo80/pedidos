from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# Create your models here.
class DevolucionCliente(models.Model):
        """Representa una devolución de productos realizada por un cliente."""
        cliente = models.ForeignKey('clientes.Cliente', on_delete=models.PROTECT, related_name='devoluciones', verbose_name="Cliente que Devuelve")
        pedido_original = models.ForeignKey('pedidos.Pedido', on_delete=models.SET_NULL, null=True, blank=True, related_name='devoluciones_asociadas', verbose_name="Pedido Original (Opcional)")
        fecha_hora = models.DateTimeField(default=timezone.now, verbose_name="Fecha y Hora de Devolución")
        motivo = models.TextField(blank=True, null=True, verbose_name="Motivo General")
        usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='devoluciones_procesadas', verbose_name="Usuario que Procesa")

        def __str__(self):
            return f"Devolución #{self.pk} - {self.cliente.nombre_completo}"

        class Meta:
            verbose_name = "Devolución de Cliente"
            verbose_name_plural = "Devoluciones de Clientes"
            ordering = ['-fecha_hora']


class DetalleDevolucion(models.Model):
        """Representa un producto específico dentro de una devolución."""
        ESTADO_PRODUCTO_DEVOLUCION_CHOICES = [
            ('BUENO', 'Buen estado (Reingresa a stock)'),
            ('DEFECTUOSO', 'Defectuoso (Revisión/Reparación)'),
            ('DESECHAR', 'Para Desechar'),
        ]
        devolucion = models.ForeignKey(DevolucionCliente, related_name='detalles', on_delete=models.CASCADE, verbose_name="Devolución Asociada")
        producto = models.ForeignKey('productos.Producto', on_delete=models.PROTECT, related_name='productos_devueltos', verbose_name="Producto Devuelto")
        cantidad = models.PositiveIntegerField(default=1, verbose_name="Cantidad Devuelta")
        estado_producto = models.CharField(max_length=15, choices=ESTADO_PRODUCTO_DEVOLUCION_CHOICES, default='BUENO', verbose_name="Estado del Producto Devuelto")

        def __str__(self):
            return f"{self.cantidad} x {self.producto.nombre} [{self.get_estado_producto_display()}]"

        class Meta:
            verbose_name = "Detalle de Devolución"
            verbose_name_plural = "Detalles de Devolución"
            unique_together = ('devolucion', 'producto')
