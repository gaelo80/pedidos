# factura/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse, NoReverseMatch
from django.contrib.auth import get_user_model
import logging

from notificaciones.models import Notificacion
from .models import EstadoFacturaDespacho # Asegúrate de importar tu modelo

User = get_user_model()
logger = logging.getLogger(__name__)

@receiver(post_save, sender=EstadoFacturaDespacho)
def notificar_despacho_por_facturar(sender, instance, created, **kwargs):
    """
    Señal que se activa al guardar un EstadoFacturaDespacho.
    Si se acaba de crear y está 'POR_FACTURAR', notifica al grupo 'Factura'.
    """
    # Solo actuar si el objeto es nuevo y está listo para facturar
    if created and instance.estado == 'POR_FACTURAR':
        grupo_destino = 'Factura'
        
        # Construir un mensaje claro
        mensaje = (
            f"El despacho #{instance.despacho.pk} "
            f"(del pedido #{instance.despacho.pedido.numero_pedido_empresa}) "
            f"está listo para facturar."
        )
        
        url_destino = None
        try:
            # URL a la que el usuario será dirigido al hacer clic
            url_destino = reverse('factura:lista_despachos_a_facturar')
        except NoReverseMatch:
            logger.warning("No se encontró la URL 'factura:lista_despachos_a_facturar'.")

        try:
            # Buscar todos los usuarios del grupo 'Factura' en la misma empresa
            usuarios_a_notificar = User.objects.filter(
                groups__name=grupo_destino,
                empresa=instance.empresa, # Asumiendo que EstadoFacturaDespacho tiene empresa
                is_active=True
            )
            
            if not usuarios_a_notificar.exists():
                logger.warning(f"No se encontraron usuarios activos en el grupo '{grupo_destino}' para la empresa {instance.empresa.nombre}.")
                return

            for usuario in usuarios_a_notificar:
                # Evitar duplicados (añadimos 'empresa' al filtro)
                if not Notificacion.objects.filter(empresa=instance.empresa, destinatario=usuario, mensaje=mensaje, leido=False).exists():
                    Notificacion.objects.create(
                        empresa=instance.empresa, # <--- ¡AÑADIR ESTA LÍNEA!
                        destinatario=usuario,
                        mensaje=mensaje,
                        url=url_destino
                    )
            
            logger.info(f"Notificaciones creadas para el grupo '{grupo_destino}' sobre el despacho #{instance.despacho.pk}.")

        except Exception as e:
            logger.error(f"Error creando notificación para el despacho #{instance.despacho.pk}: {e}")