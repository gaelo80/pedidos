from django.db.models.signals import post_save # Señal que se dispara después de guardar un modelo
from django.dispatch import receiver # Decorador para conectar la función a la señal
from django.utils import timezone
from .models import DetalleDevolucion
from bodega.models import MovimientoInventario


@receiver(post_save, sender=DetalleDevolucion)
def registrar_entrada_devolucion(sender, instance, created, **kwargs):
    """
    Se activa después de guardar un DetalleDevolucion.
    Si el estado del producto es 'BUENO' y no se ha registrado ya la entrada
    para este detalle específico, crea el movimiento de inventario.
    """
    print(f"Señal post_save recibida para DetalleDevolucion #{instance.pk} con estado {instance.estado_producto}")

    ESTADO_REINGRESO_STOCK = 'BUENO'

    if instance.estado_producto == ESTADO_REINGRESO_STOCK:
        # --- PREVENCIÓN DE DUPLICADOS ---
        # Usamos una referencia única ligada al ID del DetalleDevolucion
        doc_ref = f'DEV_DET_{instance.pk}'
        existe_movimiento = MovimientoInventario.objects.filter(
            tipo_movimiento='ENTRADA_DEVOLUCION',
            documento_referencia=doc_ref
        ).exists()

        if not existe_movimiento:
            print(f"Estado es {ESTADO_REINGRESO_STOCK} y no hay movimiento previo. Registrando entrada...")
            try:
                MovimientoInventario.objects.create(
                    producto=instance.producto,
                    cantidad=instance.cantidad, # Positivo para entrada
                    tipo_movimiento='ENTRADA_DEVOLUCION',
                    fecha_hora=timezone.now(),
                    # Usuario que procesó la devolución (tomado de la cabecera)
                    usuario=instance.devolucion.usuario,
                    documento_referencia=doc_ref, # Referencia única al detalle
                    notas=f"Entrada por Devolución #{instance.devolucion.pk} / Detalle #{instance.pk}"
                )
                print(f"Movimiento ENTRADA_DEVOLUCION creado para DetalleDevolucion #{instance.pk}")
            except Exception as e:
                print(f"ERROR al crear movimiento de entrada por devolución para DetalleDevolucion #{instance.pk}: {e}")
        else:
            print(f"Ya existe movimiento ENTRADA_DEVOLUCION para DetalleDevolucion #{instance.pk}. No se crea nuevo.")
    else:
        print(f"El estado del DetalleDevolucion #{instance.pk} es {instance.estado_producto}, no {ESTADO_REINGRESO_STOCK}. No se registra entrada.")
