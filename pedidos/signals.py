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
    Gestiona el inventario y las notificaciones basado en el estado y tipo del pedido.
    - Pedidos ESTANDAR reservan stock al pasar a PENDIENTE_APROBACION_CARTERA.
    - Pedidos ONLINE reservan stock inmediatamente al guardarse como BORRADOR.
    """

    # 2. Reserva para Pedidos ESTANDAR al pasar a aprobación
    if instance.estado == 'PENDIENTE_APROBACION_CARTERA' and instance.tipo_pedido != 'ONLINE':
        # Evita duplicar si la señal se dispara varias veces.
        # Busca cualquier movimiento (reserva o preventa) asociado a este pedido en este estado
        if MovimientoInventario.objects.filter(
            empresa=instance.empresa,
            documento_referencia__startswith=f'Pedido #{instance.numero_pedido_empresa}'
        ).exists():
             # Ya existen movimientos para este pedido, no hacer nada para evitar duplicados.
             # Podría ser una reserva pendiente o una salida directa si era preventa.
            logger.debug(f"Movimientos ya existen para Pedido #{instance.numero_pedido_empresa} en estado {instance.estado}. No se crearán nuevos.")
            # Continuar con notificaciones si es necesario (no retornamos aquí)
        else:
            # Si no hay movimientos, creamos la reserva/salida inicial
            for detalle in instance.detalles.all():
                producto = detalle.producto
                cantidad_a_descontar = -detalle.cantidad

                # Para pedidos estándar, siempre es reserva pendiente en esta etapa
                # (La lógica de preventa directa se movió al despacho)
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
            logger.info(f"Creadas reservas para pedido estándar #{instance.numero_pedido_empresa}.")







    # 3. LÓGICA DE LIBERACIÓN DE STOCK (CANCELACIONES/RECHAZOS)
    estados_que_liberan_stock = ['RECHAZADO_CARTERA', 'RECHAZADO_ADMIN', 'CANCELADO']
    if instance.estado in estados_que_liberan_stock:
        # Busca CUALQUIER tipo de salida PENDIENTE (reserva estándar o reserva online) para revertirla.
        movimientos_a_revertir = MovimientoInventario.objects.filter(
            empresa=instance.empresa,
            tipo_movimiento='SALIDA_VENTA_PENDIENTE', # Solo revertimos reservas pendientes
            documento_referencia__startswith=f'Pedido #{instance.numero_pedido_empresa}'
        )

        for mov in movimientos_a_revertir:
            # Creamos un movimiento opuesto de reingreso.
            MovimientoInventario.objects.create(
                empresa=mov.empresa,
                producto=mov.producto,
                cantidad=abs(mov.cantidad), # Convierte de -N a +N
                # Usamos un tipo genérico de entrada por rechazo/cancelación
                tipo_movimiento='ENTRADA_RECHAZO_PEDIDO',
                documento_referencia=f'Reversión Pedido #{instance.numero_pedido_empresa}',
                usuario=mov.usuario, # Usamos el usuario que hizo la reserva original si está disponible
                notas=f"Stock reintegrado por cambio a estado {instance.get_estado_display()}"
            )
            logger.info(f"Creado movimiento de reingreso para {mov.producto} (+{abs(mov.cantidad)}) debido a estado {instance.estado}.")

        # Eliminamos el movimiento de reserva original para limpiar.
        if movimientos_a_revertir.exists():
            count = movimientos_a_revertir.count()
            movimientos_a_revertir.delete()
            logger.info(f"Eliminados {count} movimientos de reserva pendientes para pedido #{instance.numero_pedido_empresa} por cambio a estado {instance.estado}. Stock revertido.")








    # --- 4. LÓGICA DE NOTIFICACIONES ---
    mensaje, grupo_destino, url_destino = None, None, None
    usuario_directo = None # Para notificaciones 1 a 1

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

    elif instance.estado == 'RECHAZADO_CARTERA':
        if instance.vendedor and instance.vendedor.user:
            usuario_directo = instance.vendedor.user
            mensaje = f"Pedido #{instance.numero_pedido_empresa} RECHAZADO por Cartera."
            try: url_destino = reverse('pedidos:detalle_pedido', kwargs={'pk': instance.pk})
            except NoReverseMatch: logger.warning(f"URL 'pedidos:detalle_pedido' para pk={instance.pk} no encontrada.")

    elif instance.estado == 'RECHAZADO_ADMIN':
        if instance.vendedor and instance.vendedor.user:
            usuario_directo = instance.vendedor.user
            mensaje = f"Pedido #{instance.numero_pedido_empresa} RECHAZADO por Administración."
            try: url_destino = reverse('pedidos:detalle_pedido', kwargs={'pk': instance.pk})
            except NoReverseMatch: logger.warning(f"URL 'pedidos:detalle_pedido' para pk={instance.pk} no encontrada.")

    # --- Lógica de envío de notificación (Modificada) ---
    if mensaje:
        try:
            usuarios_a_notificar = []
            if grupo_destino:
                usuarios_a_notificar = list(User.objects.filter(groups__name__iexact=grupo_destino, empresa=instance.empresa, is_active=True))
            elif usuario_directo:
                # Asegurarnos que el usuario directo pertenezca a la empresa (aunque ya debería)
                if hasattr(usuario_directo, 'empresa') and usuario_directo.empresa == instance.empresa:
                    usuarios_a_notificar = [usuario_directo]

            for usuario in usuarios_a_notificar:
                # Comprobamos que no exista una notificación igual Y de la misma empresa
                if not Notificacion.objects.filter(
                    empresa=instance.empresa,
                    destinatario=usuario,
                    mensaje=mensaje,
                    leido=False
                ).exists():

                    # Añadimos la empresa en la creación
                    Notificacion.objects.create(
                        empresa=instance.empresa,
                        destinatario=usuario,
                        mensaje=mensaje,
                        url=url_destino
                    )
        except Group.DoesNotExist:
            logger.warning(f"El grupo '{grupo_destino}' no existe.")
        except Exception as e:
            logger.error(f"Error creando notificación para pedido #{instance.id}: {e}")