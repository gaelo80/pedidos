# pedidos/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse, NoReverseMatch
from .models import Pedido
from bodega.models import MovimientoInventario
from notificaciones.models import Notificacion
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

# ✅ ESTA FUNCIÓN SE QUEDA IGUAL, PERO AHORA LA LLAMAREMOS DESDE LAS VISTAS
def sincronizar_reservas_borrador(pedido):
    """
    Función experta para sincronizar el stock reservado con los detalles de un pedido en borrador.
    """
    logger.info(f"Sincronizando reservas para borrador #{pedido.numero_pedido_empresa}...")
    detalles_actuales = {detalle.producto_id: detalle for detalle in pedido.detalles.all()}
    reservas_existentes = MovimientoInventario.objects.filter(
        empresa=pedido.empresa,
        tipo_movimiento='SALIDA_VENTA_PENDIENTE',
        documento_referencia__startswith=f'Pedido #{pedido.numero_pedido_empresa}'
    )
    reservas_actuales = {reserva.producto_id: reserva for reserva in reservas_existentes}

    for producto_id, detalle in detalles_actuales.items():
        reserva = reservas_actuales.get(producto_id)
        cantidad_necesaria = -detalle.cantidad
        if not reserva:
            MovimientoInventario.objects.create(
                empresa=pedido.empresa, producto=detalle.producto, cantidad=cantidad_necesaria,
                tipo_movimiento='SALIDA_VENTA_PENDIENTE',
                documento_referencia=f'Pedido #{pedido.numero_pedido_empresa} (Reserva por Borrador)',
                usuario=pedido.vendedor.user if pedido.vendedor else None
            )
        elif reserva.cantidad != cantidad_necesaria:
            reserva.cantidad = cantidad_necesaria
            reserva.save()

    for producto_id, reserva in reservas_actuales.items():
        if producto_id not in detalles_actuales:
            cantidad_a_liberar = abs(reserva.cantidad)
            MovimientoInventario.objects.create(
                empresa=pedido.empresa, producto=reserva.producto, cantidad=cantidad_a_liberar,
                tipo_movimiento='ENTRADA_RECHAZO_PEDIDO',
                documento_referencia=f'Pedido #{pedido.numero_pedido_empresa} (Item Eliminado de Borrador)',
                usuario=pedido.vendedor.user if pedido.vendedor else None
            )
            reserva.delete()


@receiver(post_save, sender=Pedido)
def gestionar_stock_y_notificaciones_pedido(sender, instance, created, **kwargs):
    """
    Señal que maneja los cambios de estado de un pedido DESPUÉS de que deja de ser un borrador.
    """
    empresa_del_pedido = instance.empresa
    if not empresa_del_pedido:
        return

    # ✅ CORREGIDO: La señal ya NO se preocupa por el estado 'BORRADOR'.
    # La sincronización de borradores ahora se llama explícitamente desde las vistas.
    if instance.estado == 'BORRADOR':
        return

    # El resto de la lógica para convertir, liberar y notificar se mantiene igual.
    estados_que_confirman_venta = ['PENDIENTE_APROBACION_CARTERA', 'LISTO_BODEGA_DIRECTO', 'APROBADO_ADMIN', 'PROCESANDO', 'ENVIADO']
    # ... (el resto de la función se queda exactamente igual que en la versión anterior) ...
    if instance.estado in estados_que_confirman_venta:
        MovimientoInventario.objects.filter(
            empresa=empresa_del_pedido, tipo_movimiento='SALIDA_VENTA_PENDIENTE',
            documento_referencia__startswith=f'Pedido #{instance.numero_pedido_empresa}'
        ).update(
            tipo_movimiento='SALIDA_VENTA_DIRECTA',
            notas=f'Venta confirmada desde reserva. Estado: {instance.get_estado_display()}'
        )

    estados_que_liberan_stock = ['RECHAZADO_CARTERA', 'RECHAZADO_ADMIN', 'CANCELADO']
    if instance.estado in estados_que_liberan_stock:
        ventas_a_revertir = MovimientoInventario.objects.filter(
            empresa=empresa_del_pedido, tipo_movimiento__in=['SALIDA_VENTA_DIRECTA', 'SALIDA_VENTA_PENDIENTE'],
            documento_referencia__startswith=f'Pedido #{instance.numero_pedido_empresa}'
        )
        if ventas_a_revertir.exists():
            for venta in ventas_a_revertir:
                MovimientoInventario.objects.create(
                    empresa=empresa_del_pedido, producto=venta.producto, cantidad=abs(venta.cantidad),
                    tipo_movimiento='ENTRADA_RECHAZO_PEDIDO',
                    documento_referencia=f'Pedido #{instance.numero_pedido_empresa} ({instance.estado})',
                    usuario=instance.vendedor.user if instance.vendedor else None
                )
            ventas_a_revertir.delete()
    
    # Lógica de notificaciones
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