from django.db.models.signals import post_save # Señal que se dispara después de guardar un modelo
from django.dispatch import receiver # Decorador para conectar la función a la señal
from django.utils import timezone
from bodega.models import MovimientoInventario




@receiver(post_save, sender='pedidos.Pedido')
def registrar_salida_venta_pedido(sender, instance, created, **kwargs):
    """
    Señal que se activa después de guardar un Pedido.
    Si el estado es 'ENVIADO' (o el que definamos como gatillo de salida de stock)
    y no se ha registrado ya la salida para este pedido,
    crea los movimientos de inventario correspondientes.
    """
    print(f"Señal post_save recibida para Pedido #{instance.pk} con estado {instance.estado}") # Mensaje de depuración

    # Define el estado que dispara la salida de inventario
    ESTADO_GATILLO_SALIDA = 'ENVIADO' # O podría ser 'COMPLETADO'

    if instance.estado == ESTADO_GATILLO_SALIDA:
        # --- PREVENCIÓN DE DUPLICADOS ---
        # Verifica si ya existen movimientos de SALIDA_VENTA para este pedido específico.
        existe_movimiento = MovimientoInventario.objects.filter(
            tipo_movimiento='SALIDA_VENTA',
            documento_referencia=f'PEDIDO_{instance.pk}' # Usamos una referencia única
        ).exists()

        if not existe_movimiento:
            print(f"Estado es {ESTADO_GATILLO_SALIDA} y no hay movimientos previos. Registrando salida...")
            try:
                # Recorre cada detalle del pedido
                for detalle in instance.detalles.all():
                    MovimientoInventario.objects.create(
                        producto=detalle.producto,
                        cantidad=-detalle.cantidad, # ¡Importante! Negativo para salida
                        tipo_movimiento='SALIDA_VENTA',
                        fecha_hora=timezone.now(),
                        # Asignamos el usuario que figura como vendedor en el pedido
                        # Podría ser None si el vendedor fue borrado y usamos SET_NULL
                        usuario=instance.vendedor.user if instance.vendedor else None,
                        documento_referencia=f'PEDIDO_{instance.pk}', # Referencia al pedido
                        notas=f"Salida automática por {ESTADO_GATILLO_SALIDA} de Pedido #{instance.pk}"
                    )
                print(f"Movimientos de SALIDA_VENTA creados para Pedido #{instance.pk}")
            except Exception as e:
                # Es importante manejar posibles errores aquí
                print(f"ERROR al crear movimientos para Pedido #{instance.pk}: {e}")
        else:
            print(f"Ya existen movimientos de SALIDA_VENTA para Pedido #{instance.pk}. No se crean nuevos.")
    else:
        print(f"El estado del Pedido #{instance.pk} es {instance.estado}, no {ESTADO_GATILLO_SALIDA}. No se registra salida.")