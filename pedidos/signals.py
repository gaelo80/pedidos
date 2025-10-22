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


# pedidos/signals.py

@receiver(post_save, sender=Pedido)
def gestionar_stock_y_notificaciones_pedido(sender, instance, **kwargs):
    """
    Gestiona el inventario y las notificaciones basado en el estado y tipo del pedido.
    - Pedidos ESTANDAR reservan stock al pasar a PENDIENTE_APROBACION_CARTERA.
    - Pedidos ONLINE (Borrador y Definitivo) se manejan en su propia vista (crear_pedido_online).
    """
    # --- LÓGICA DE GESTIÓN DE STOCK ---

    # 1. Reserva para Pedidos ONLINE (Lógica movida a la vista, este bloque ya no es necesario)
    # (Asegúrate que este bloque if/elif inicial sobre 'ONLINE' y 'BORRADOR' esté eliminado)
    

    # 2. Reserva para Pedidos ESTANDAR al pasar a aprobación
    # (Asegúrate que este sea el primer 'if' o 'elif' de la lógica de stock)
    if instance.estado == 'PENDIENTE_APROBACION_CARTERA' and instance.tipo_pedido != 'ONLINE':
        # Evita duplicar si la señal se dispara varias veces.
        if MovimientoInventario.objects.filter(
            empresa=instance.empresa,
            documento_referencia__startswith=f'Pedido #{instance.numero_pedido_empresa}'
        ).exists():
            logger.debug(f"Movimientos ya existen para Pedido #{instance.numero_pedido_empresa} en estado {instance.estado}. No se crearán nuevos.")
        else:
            # Si no hay movimientos, creamos la reserva/salida inicial
            for detalle in instance.detalles.all():
                producto = detalle.producto
                cantidad_a_descontar = -detalle.cantidad

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
    # (Esta sección debe estar eliminada, como dijiste que hiciste,
    # ya que esta lógica ahora vive en views.py)
    

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

    # --- Lógica de envío de notificación (CORREGIDA) ---
    if mensaje:
        try:
            usuarios_a_notificar = []
            
            # 1. Notificación a un GRUPO (Cartera, Admin, Bodega)
            if grupo_destino:
                usuarios_a_notificar = list(User.objects.filter(
                    groups__name__iexact=grupo_destino, 
                    empresa=instance.empresa,
                    is_active=True
                ))
            
            # 2. Notificación a un USUARIO DIRECTO (Vendedor)
            elif usuario_directo:
                if usuario_directo.is_active:
                    usuarios_a_notificar = [usuario_directo]

            # 3. Crear la notificación
            for usuario in usuarios_a_notificar:
                
                # ¡VERIFICACIÓN DE SEGURIDAD!
                if not instance.empresa:
                    logger.error(f"Error al notificar: El Pedido #{instance.id} (Estado: {instance.estado}) no tiene empresa asignada.")
                    continue # Saltar si la empresa es Nula

                # Comprobamos que no exista una notificación duplicada
                if not Notificacion.objects.filter(
                    empresa=instance.empresa, # <-- Filtro con empresa
                    destinatario=usuario,
                    mensaje=mensaje,
                    leido=False
                ).exists():
                    
                    # ¡LA LÍNEA QUE CAUSA TU ERROR ESTÁ AQUÍ!
                    # Asegúrate de que tu código tenga 'empresa=instance.empresa'
                    Notificacion.objects.create(
                        empresa=instance.empresa, # <--- ESTA LÍNEA ES LA SOLUCIÓN
                        destinatario=usuario,
                        mensaje=mensaje,
                        url=url_destino
                    )
                    
        except Group.DoesNotExist:
            logger.warning(f"El grupo '{grupo_destino}' no existe.")
        except Exception as e:
            logger.error(f"Error creando notificación para pedido #{instance.id} (Estado: {instance.estado}): {e}")