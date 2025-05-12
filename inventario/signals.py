# inventario/signals.py
from django.db.models.signals import post_save # Señal que se dispara después de guardar un modelo
from django.dispatch import receiver # Decorador para conectar la función a la señal
from django.utils import timezone
from .models import Pedido, DetallePedido, MovimientoInventario, DetalleDevolucion # <-- Añadido DetalleDevolucion
from .models import Pedido, DetallePedido, MovimientoInventario, DetalleDevolucion, DetalleIngresoBodega


from .models import Pedido, DetallePedido, MovimientoInventario

# Usamos el decorador @receiver para conectar esta función a la señal post_save del modelo Pedido
@receiver(post_save, sender=Pedido)
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

# --- Podríamos añadir más señales aquí para otras lógicas ---
# ej: @receiver(post_save, sender=DetalleDevolucion)
# ej: @receiver(post_save, sender=DetalleIngresoBodega)

# inventario/signals.py

# ... (función registrar_salida_venta_pedido aquí arriba) ...


# Señal para manejar la entrada de stock por devoluciones en buen estado
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
        
        
        
        # inventario/signals.py

# ... (funciones registrar_salida_venta_pedido y registrar_entrada_devolucion aquí arriba) ...


# Señal para manejar la entrada de stock por ingresos a bodega (compras)
@receiver(post_save, sender=DetalleIngresoBodega)
def registrar_entrada_compra(sender, instance, created, **kwargs):
    """
    Se activa después de guardar un DetalleIngresoBodega.
    Crea el movimiento de inventario de ENTRADA_COMPRA si no existe ya uno
    para este detalle específico.
    """
    print(f"Señal post_save recibida para DetalleIngresoBodega #{instance.pk}")

    # --- PREVENCIÓN DE DUPLICADOS ---
    # Usamos una referencia única ligada al ID del DetalleIngresoBodega
    doc_ref = f'ING_DET_{instance.pk}'
    existe_movimiento = MovimientoInventario.objects.filter(
        tipo_movimiento='ENTRADA_COMPRA', # O el tipo que corresponda
        documento_referencia=doc_ref
    ).exists()

    if not existe_movimiento:
        print(f"No hay movimiento previo para {doc_ref}. Registrando entrada...")
        try:
            MovimientoInventario.objects.create(
                producto=instance.producto,
                cantidad=instance.cantidad, # Positivo para entrada
                tipo_movimiento='ENTRADA_COMPRA', # Asume que es por compra
                # Usamos la fecha/hora de la cabecera del ingreso
                fecha_hora=instance.ingreso.fecha_hora,
                # Usuario que registró el ingreso (tomado de la cabecera)
                usuario=instance.ingreso.usuario,
                documento_referencia=doc_ref, # Referencia única al detalle
                notas=f"Entrada por Ingreso Bodega #{instance.ingreso.pk} / Detalle #{instance.pk} (Ref: {instance.ingreso.documento_referencia or '-'})"
            )
            print(f"Movimiento ENTRADA_COMPRA creado para DetalleIngresoBodega #{instance.pk}")
        except Exception as e:
            print(f"ERROR al crear movimiento de entrada por compra para DetalleIngresoBodega #{instance.pk}: {e}")
    else:
        print(f"Ya existe movimiento ENTRADA_COMPRA para DetalleIngresoBodega #{instance.pk}. No se crea nuevo.")