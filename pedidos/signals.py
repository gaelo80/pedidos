# pedidos/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse, NoReverseMatch
from django.utils import timezone
from bodega.models import MovimientoInventario
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
import logging
from notificaciones.models import Notificacion
from pedidos.models import Pedido

User = get_user_model()

# Configura un logger para este módulo
logger = logging.getLogger(__name__)

@receiver(post_save, sender='pedidos.Pedido')
def registrar_salida_venta_pedido(sender, instance, created, **kwargs):
    """
    Señal que se activa después de guardar un Pedido.
    Si el estado es 'ENVIADO', crea los movimientos de inventario correspondientes,
    asegurándose de que pertenezcan a la misma empresa que el pedido.
    """
    ESTADO_GATILLO_SALIDA = 'ENVIADO'

    if instance.estado == ESTADO_GATILLO_SALIDA:
        
        # 1. --- CORRECCIÓN DE SEGURIDAD: Usar la empresa del pedido ---
        empresa_del_pedido = instance.empresa
        
        # Si por alguna razón el pedido no tiene empresa, no podemos continuar.
        if not empresa_del_pedido:
            logger.error(f"Pedido #{instance.pk} no tiene una empresa asociada. No se puede crear movimiento de inventario.")
            return

        # 2. --- CORRECCIÓN DE SEGURIDAD: Añadir filtro por empresa ---
        existe_movimiento = MovimientoInventario.objects.filter(
            empresa=empresa_del_pedido, 
            tipo_movimiento='SALIDA_VENTA',
            documento_referencia=f'PEDIDO_{instance.pk}'
        ).exists()

        if not existe_movimiento:
            logger.info(f"Registrando salida de inventario para Pedido #{instance.pk} de la empresa {empresa_del_pedido.nombre}.")
            try:
                for detalle in instance.detalles.all():
                    # 3. --- CORRECCIÓN DE SEGURIDAD: Asignar la empresa al crear ---
                    MovimientoInventario.objects.create(
                        empresa=empresa_del_pedido,
                        producto=detalle.producto,
                        cantidad=-detalle.cantidad,
                        tipo_movimiento='SALIDA_VENTA',
                        fecha_hora=timezone.now(),
                        usuario=instance.vendedor.user if instance.vendedor else None,
                        documento_referencia=f'PEDIDO_{instance.pk}',
                        notas=f"Salida automática por {ESTADO_GATILLO_SALIDA} de Pedido #{instance.pk}"
                    )
                logger.info(f"Movimientos de SALIDA_VENTA creados para Pedido #{instance.pk}")
            except Exception as e:
                logger.error(f"ERROR al crear movimientos para Pedido #{instance.pk}: {e}")
        else:
            logger.warning(f"Ya existen movimientos de SALIDA_VENTA para Pedido #{instance.pk}. No se crean nuevos.")
            

@receiver(post_save, sender=Pedido)
def crear_notificacion_cambio_estado_pedido(sender, instance, **kwargs):
    mensaje = None
    grupo_destino = None
    url_destino = None

    # Lógica para determinar a quién notificar, usando los nombres de TUS estados.
    if instance.estado == 'PENDIENTE_APROBACION_CARTERA':
        grupo_destino = 'Cartera'
        mensaje = f"El pedido #{instance.id} de {instance.destinatario.nombre_completo} requiere tu aprobación."
        try:
            url_destino = reverse('pedidos:lista_aprobacion_cartera')
        except NoReverseMatch:
            logger.warning("No se encontró la URL 'pedidos:lista_aprobacion_cartera'.")

    elif instance.estado == 'PENDIENTE_APROBACION_ADMIN':
        grupo_destino = 'Administracion'
        mensaje = f"El pedido #{instance.id} fue aprobado por Cartera y requiere tu aprobación."
        try:
            url_destino = reverse('pedidos:lista_aprobacion_admin')
        except NoReverseMatch:
            logger.warning("No se encontró la URL 'pedidos:lista_aprobacion_admin'.")
        
    elif instance.estado == 'APROBADO_ADMIN':
        grupo_destino = 'Bodega'
        mensaje = f"El pedido #{instance.id} fue aprobado y está listo para despacho en bodega."
        try:
            url_destino = reverse('bodega:lista_pedidos_bodega')
        except NoReverseMatch:
            logger.warning("No se encontró la URL 'bodega:lista_pedidos_bodega'.")

    if mensaje and grupo_destino:
        try:
            # La consulta ahora usa el modelo de usuario correcto (User = get_user_model())
            usuarios_a_notificar = User.objects.filter(
                groups__name=grupo_destino,
                empresa=instance.empresa,
                is_active=True
            )
            
            for usuario in usuarios_a_notificar:
                # Evitar duplicados: solo crear si no existe una notificación igual y no leída
                if not Notificacion.objects.filter(destinatario=usuario, mensaje=mensaje, leido=False).exists():
                    Notificacion.objects.create(
                        destinatario=usuario,
                        mensaje=mensaje,
                        url=url_destino
                    )
        except Group.DoesNotExist:
            logger.warning(f"El grupo '{grupo_destino}' no existe. No se pudo notificar.")
        except Exception as e:
            logger.error(f"Error creando notificación para pedido #{instance.id}: {e}")