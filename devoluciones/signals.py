# devoluciones/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import DetalleDevolucion
from bodega.models import MovimientoInventario


@receiver(post_save, sender=DetalleDevolucion)
def registrar_entrada_devolucion(sender, instance, created, **kwargs):
    """
    Se activa después de guardar un DetalleDevolucion.
    Si el estado del producto es 'BUENO', crea un movimiento de inventario de entrada.
    Esta señal es segura para entornos multi-inquilino.
    """
    print(f"Señal post_save recibida para DetalleDevolucion #{instance.pk} con estado {instance.estado_producto}")

    ESTADO_REINGRESO_STOCK = 'BUENO'

    # Solo actuar si el producto está en buen estado y tiene una cantidad positiva.
    if instance.estado_producto == ESTADO_REINGRESO_STOCK and instance.cantidad > 0:
        
        # Usamos una referencia única para prevenir la creación de movimientos duplicados.
        doc_ref = f'DEV_DET_{instance.pk}'
        existe_movimiento = MovimientoInventario.objects.filter(
            # Se añade filtro por empresa para una búsqueda más eficiente y segura.
            empresa=instance.devolucion.empresa,
            tipo_movimiento='ENTRADA_DEVOLUCION',
            documento_referencia=doc_ref
        ).exists()

        if not existe_movimiento:
            print(f"Registrando entrada de inventario para DetalleDevolucion #{instance.pk}...")
            try:
                # <<< CORRECCIÓN CRÍTICA DE SEGURIDAD >>>
                # Se añade el campo 'empresa' al crear el MovimientoInventario.
                # Se obtiene de la devolución padre, asegurando la coherencia del inquilino.
                MovimientoInventario.objects.create(
                    empresa=instance.devolucion.empresa,
                    producto=instance.producto,
                    cantidad=instance.cantidad,
                    tipo_movimiento='ENTRADA_DEVOLUCION',
                    fecha_hora=timezone.now(),
                    usuario=instance.devolucion.usuario,
                    documento_referencia=doc_ref,
                    notas=f"Entrada por Devolución #{instance.devolucion.pk} / Detalle #{instance.pk}"
                )
                print(f"Movimiento de inventario creado exitosamente para el inquilino '{instance.devolucion.empresa.nombre}'.")
            except Exception as e:
                # Es crucial registrar cualquier error en la creación del movimiento.
                print(f"ERROR CRÍTICO al crear movimiento de inventario para DetalleDevolucion #{instance.pk}: {e}")
        else:
            print(f"El movimiento de inventario para DetalleDevolucion #{instance.pk} ya existe.")
    else:
        print(f"No se registra movimiento de inventario para DetalleDevolucion #{instance.pk} (Estado: {instance.estado_producto}, Cantidad: {instance.cantidad}).")
