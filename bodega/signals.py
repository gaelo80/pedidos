from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction # Sigue siendo bueno para la atomicidad de la creación del movimiento
from .models import MovimientoInventario, DetalleIngresoBodega
# La importación de Producto desde productos.models es correcta según tu archivo
from productos.models import Producto


@receiver(post_save, sender=DetalleIngresoBodega)
def crear_movimiento_para_ingreso_detalle(sender, instance, created, **kwargs):
    """
    Se activa después de guardar un DetalleIngresoBodega.
    Si es una nueva creación (created=True):
    1. Crea un movimiento de inventario de ENTRADA.
    El stock_actual del Producto se actualizará automáticamente porque
    es una @property que suma los movimientos.
    """
    print(f"DEBUG SEÑAL INGRESO DETALLE: Recibida para DetalleIngresoBodega #{instance.pk}. Creado: {created}")

    if created: 
        try:

            with transaction.atomic():
                
                doc_ref_movimiento = f'ING_DET_{instance.pk}'

                existe_movimiento_previo = MovimientoInventario.objects.filter(
                    empresa=instance.producto.empresa,
                    documento_referencia=doc_ref_movimiento,
                    producto=instance.producto,
                    tipo_movimiento='ENTRADA_COMPRA' # Asegúrate que este sea el tipo correcto
                ).exists()

                if not existe_movimiento_previo:
                    movimiento = MovimientoInventario.objects.create(
                        producto=instance.producto,
                        cantidad=instance.cantidad, # Cantidad positiva para un ingreso
                        tipo_movimiento='ENTRADA_COMPRA', # Ajusta si usas otro tipo para ingresos desde el admin
                        fecha_hora=instance.ingreso.fecha_hora, # Fecha/hora de la cabecera del ingreso
                        usuario=instance.ingreso.usuario, # Usuario que registró el ingreso
                        documento_referencia=doc_ref_movimiento,
                        notas=f"Entrada automática por Ingreso Bodega #{instance.ingreso.pk} (Detalle ID: {instance.pk}). Ref. Doc. Ingreso: {instance.ingreso.documento_referencia or '-'}"
                    )
                    print(f"DEBUG SEÑAL INGRESO DETALLE: Movimiento de inventario #{movimiento.pk} (ENTRADA_COMPRA) CREADO para DetalleIngresoBodega #{instance.pk}")
                else:
                    print(f"DEBUG SEÑAL INGRESO DETALLE: Movimiento de inventario para DetalleIngresoBodega #{instance.pk} (doc_ref: {doc_ref_movimiento}) YA EXISTÍA. No se creó uno nuevo.")


                producto_obj = instance.producto
                print(f"DEBUG SEÑAL INGRESO DETALLE: Producto afectado: '{producto_obj}'. Stock actual (calculado por @property): {producto_obj.stock_actual}")

        except Exception as e:
            print(f"ERROR CRÍTICO INESPERADO en señal 'crear_movimiento_para_ingreso_detalle' para DetalleIngresoBodega #{instance.pk}: {type(e).__name__} - {e}")
            import traceback
            traceback.print_exc()

    else:
        print(f"DEBUG SEÑAL INGRESO DETALLE: Ignorada para DetalleIngresoBodega #{instance.pk} (no fue una creación, created=False).")

