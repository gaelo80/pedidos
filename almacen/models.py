from django.db import models
from django.conf import settings # <--- Importación correcta y segura
from productos.models import Producto 

class InventarioAlmacen(models.Model):
    """
    Esta tabla separa el almacén de la bodega. 
    Aquí manejamos el precio al detal y el stock físico que hay en la tienda.
    """
    producto = models.OneToOneField(Producto, on_delete=models.CASCADE, related_name='inventario_almacen')
    precio_detal = models.DecimalField(max_digits=12, decimal_places=2, help_text="Precio de venta en el almacén físico")
    stock_actual = models.IntegerField(default=0)
    
    def __str__(self):
        return f"{self.producto.descripcion} - Stock Almacén: {self.stock_actual}"

class FacturaAlmacen(models.Model):
    """
    Guarda el registro de las facturas que el .exe envía al final del día.
    """
    consecutivo_local = models.CharField(max_length=50, help_text="Número de factura generado por el .exe")
    fecha_venta = models.DateTimeField()
    
    # <--- Cambio aquí:
    vendedor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    total_venta = models.DecimalField(max_digits=12, decimal_places=2)
    metodo_pago = models.CharField(max_length=20, choices=[('EFECTIVO', 'Efectivo'), ('TARJETA', 'Tarjeta'), ('TRANSFERENCIA', 'Transferencia')])
    sincronizado_el = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Factura {self.consecutivo_local} - ${self.total_venta}"

class DetalleFacturaAlmacen(models.Model):
    factura = models.ForeignKey(FacturaAlmacen, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)