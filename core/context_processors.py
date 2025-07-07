# core/context_processors.py
from notificaciones.models import Notificacion

def empresa_context(request):
    """
    Hace que el título web y el nombre de la empresa estén disponibles
    en todas las plantillas, basado en el tenant actual.
    """
    # BUSCAMOS LA VARIABLE 'request.tenant'
    if hasattr(request, 'tenant') and request.tenant:
        return {
            'titulo_web': request.tenant.titulo_web,
            'nombre_empresa': request.tenant.nombre
        }
    return {}

def notificaciones_context(request):
    """
    Hace que el contador de notificaciones no leídas esté disponible
    en todas las plantillas para el usuario autenticado.
    """
    if not request.user.is_authenticated:
        return {}
    
    count = Notificacion.objects.filter(destinatario=request.user, leido=False).count()
    
    return {
        'unread_notifications_count': count
    }