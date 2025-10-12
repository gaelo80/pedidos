# pedidos/signals.py

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.urls import reverse, NoReverseMatch
from .models import Pedido
from bodega.models import MovimientoInventario
from productos.models import Producto  # <-- Importante añadir esto
from notificaciones.models import Notificacion
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(pre_delete, sender=Pedido)
def liberar_stock_al_eliminar_pedido(sender, instance, **kwargs):
    """
    Se activa antes de eliminar un Pedido.
    Libera el stock comprometido (reservado o de preventa) si el pedido se elimina.
    """
    logger.info(f"Señal pre_delete para Pedido #{instance.numero_pedido_empresa} en estado {instance.estado}.")

    # Busca movimientos de salida (reservas o preventas directas) asociados a este pedido.
    movimientos_a_eliminar = MovimientoInventario.objects.filter(
        empresa=instance.empresa,
        tipo_movimiento__in=['SALIDA_VENTA_PENDIENTE', 'SALIDA_VENTA_DIRECTA'],
        documento_referencia__startswith=f'Pedido #{instance.numero_pedido_empresa}'
    )
    
    if movimientos_a_eliminar.exists():
        count = movimientos_a_eliminar.count()
        # Al eliminar el movimiento, el stock se revierte automáticamente.
        movimientos_a_eliminar.delete()
        logger.info(f"Se eliminaron {count} movimientos de inventario asociados para liberar stock.")


@receiver(post_save, sender=Pedido)
def gestionar_stock_y_notificaciones_pedido(sender, instance, **kwargs):
    """
    Gestiona el inventario y las notificaciones basado en el estado del pedido.
    Diferencia entre productos normales (reserva) y de preventa (salida directa).
    """
    if instance.estado == 'BORRADOR':
        # La lógica de borradores se maneja explícitamente desde las vistas (autosave).
        return

    # --- 1. LÓGICA DE COMPROMISO DE STOCK (Al pasar de Borrador a Definitivo) ---
    if instance.estado == 'PENDIENTE_APROBACION_CARTERA':
        # Evita duplicar movimientos si la señal se dispara varias veces para el mismo estado.
        if MovimientoInventario.objects.filter(documento_referencia__startswith=f'Pedido #{instance.numero_pedido_empresa}').exists():
            return
            
        for detalle in instance.detalles.all():
            producto = detalle.producto
            cantidad_a_descontar = -detalle.cantidad  # Negativo para una salida

            if producto.permitir_preventa:
                # PREVENTA: Descontamos el stock real inmediatamente (puede quedar negativo).
                tipo_mov = 'SALIDA_VENTA_DIRECTA'
                doc_ref = f'Pedido #{instance.numero_pedido_empresa} (Preventa)'
            else:
                # NORMAL: Creamos una reserva que NO afecta el stock real aún.
                tipo_mov = 'SALIDA_VENTA_PENDIENTE'
                doc_ref = f'Pedido #{instance.numero_pedido_empresa} (Reserva)'

            MovimientoInventario.objects.create(
                empresa=instance.empresa,
                producto=producto,
                cantidad=cantidad_a_descontar,
                tipo_movimiento=tipo_mov,
                documento_referencia=doc_ref,
                usuario=instance.vendedor.user if instance.vendedor else None
            )

    # --- 2. LÓGICA DE LIBERACIÓN DE STOCK (CANCELACIONES/RECHAZOS) ---
    estados_que_liberan_stock = ['RECHAZADO_CARTERA', 'RECHAZADO_ADMIN', 'CANCELADO']
    if instance.estado in estados_que_liberan_stock:
        # Busca CUALQUIER tipo de salida (reserva o preventa directa) para revertirla.
        movimientos_a_revertir = MovimientoInventario.objects.filter(
            empresa=instance.empresa,
            tipo_movimiento__in=['SALIDA_VENTA_PENDIENTE', 'SALIDA_VENTA_DIRECTA'],
            documento_referencia__startswith=f'Pedido #{instance.numero_pedido_empresa}'
        )
        for mov in movimientos_a_revertir:
            # Creamos un movimiento opuesto de reingreso.
            MovimientoInventario.objects.create(
                empresa=mov.empresa,
                producto=mov.producto,
                cantidad=abs(mov.cantidad),  # Convierte de -5 a +5
                tipo_movimiento='ENTRADA_RECHAZO_PEDIDO',
                documento_referencia=f'Reversión Pedido #{instance.numero_pedido_empresa}',
                usuario=instance.vendedor.user if instance.vendedor else None,
                notas=f"Stock reintegrado por cambio a estado {instance.get_estado_display()}"
            )
        # Eliminamos el movimiento original para no tener registros contradictorios.
        movimientos_a_revertir.delete()

    # --- 3. LÓGICA DE NOTIFICACIONES (Se mantiene igual) ---
    mensaje, grupo_destino, url_destino = None, None, None
    if instance.estado == 'PENDIENTE_APROBACION_CARTERA':
        grupo_destino, mensaje = 'Cartera', f"El pedido #{instance.numero_pedido_empresa} de {instance.destinatario.nombre_completo} requiere aprobación."
        try: url_destino = reverse('pedidos:lista_aprobacion_cartera')
        except NoReverseMatch: logger.warning("URL 'pedidos:lista_aprobacion_cartera' no encontrada.")
    elif instance.estado == 'PENDIENTE_APROBACION_ADMIN':
        grupo_destino, mensaje = 'Administracion', f"El pedido #{instance.numero_pedido_empresa} fue aprobado por Cartera."
        try: url_destino = reverse('pedidos:lista_aprobacion_admin')
        except NoReverseMatch: logger.warning("URL 'pedidos:lista_aprobacion_admin' no encontrada.")
    elif instance.estado == 'APROBADO_ADMIN':
        grupo_destino, mensaje = 'Bodega', f"El pedido #{instance.numero_pedido_empresa} fue aprobado y está listo para despacho."
        try: url_destino = reverse('bodega:lista_pedidos_bodega')
        except NoReverseMatch: logger.warning("URL 'bodega:lista_pedidos_bodega' no encontrada.")
    
    if mensaje and grupo_destino:
        try:
            usuarios_a_notificar = User.objects.filter(groups__name=grupo_destino, empresa=instance.empresa, is_active=True)
            for usuario in usuarios_a_notificar:
                if not Notificacion.objects.filter(destinatario=usuario, mensaje=mensaje, leido=False).exists():
                    Notificacion.objects.create(destinatario=usuario, mensaje=mensaje, url=url_destino)
        except Group.DoesNotExist:
            logger.warning(f"El grupo '{grupo_destino}' no existe.")
        except Exception as e:
            logger.error(f"Error creando notificación para pedido #{instance.id}: {e}")