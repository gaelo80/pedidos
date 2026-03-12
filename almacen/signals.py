"""
Señales para sincronizar InventarioAlmacen automáticamente.

Flujo correcto:
1. Bodega transfiere a Almacén → incrementa InventarioAlmacen.stock_actual
2. Almacén vende → decrementa InventarioAlmacen.stock_actual
3. Almacén recibe devolución → incrementa InventarioAlmacen.stock_actual
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Sum

from bodega.models import SalidaInternaDetalle
from almacen.models import DetalleFacturaAlmacen, InventarioAlmacen


@receiver(post_save, sender=DetalleFacturaAlmacen)
def decrementar_inventario_por_venta_almacen(sender, instance, created, **kwargs):
    """
    Cuando se vende en el almacén (FacturaAlmacen), decrementar InventarioAlmacen.

    Se dispara cuando:
    - AlmacenDesktop envía POST a /api/almacen/facturas/
    - Se crea un DetalleFacturaAlmacen
    """
    if created:
        try:
            inventario = InventarioAlmacen.objects.get(
                producto_id=instance.producto_id
            )
            inventario.stock_actual -= instance.cantidad
            inventario.save(update_fields=['stock_actual'])
        except InventarioAlmacen.DoesNotExist:
            # Si no existe InventarioAlmacen para este producto, no hacer nada
            # (probablemente es un producto que no está en el almacén)
            pass


@receiver(post_save, sender=SalidaInternaDetalle)
def incrementar_inventario_por_transferencia_almacen(sender, instance, created, **kwargs):
    """
    Cuando bodega transfiere a almacén (SalidaInterna con tipo=TRASLADO_INTERNO),
    incrementar InventarioAlmacen.

    Se dispara cuando:
    - Se registra una SalidaInterna en bodega/views.py
    - Se crea un SalidaInternaDetalle
    """
    if created:
        # Verificar que la salida es un traslado interno (hacia almacén)
        if instance.cabecera_salida.tipo_salida == 'TRASLADO_INTERNO':
            try:
                inventario = InventarioAlmacen.objects.get(
                    producto_id=instance.producto_id
                )
                inventario.stock_actual += instance.cantidad_despachada
                inventario.save(update_fields=['stock_actual'])
            except InventarioAlmacen.DoesNotExist:
                # Si no existe InventarioAlmacen, crear uno
                inventario = InventarioAlmacen.objects.create(
                    producto_id=instance.producto_id,
                    precio_detal=instance.producto.precio_venta or 0,
                    stock_actual=instance.cantidad_despachada
                )
