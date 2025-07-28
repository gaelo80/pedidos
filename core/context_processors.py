# core/context_processors.py
from notificaciones.models import Notificacion
from .auth_utils import es_administracion, es_bodega, es_vendedor, es_cartera, es_factura, es_diseno, es_online, es_administrador_app, puede_ver_panel_django_admin

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
    
    
def user_roles_context(request): # 
    """
    Añade variables al contexto de la plantilla para verificar la pertenencia a roles/grupos.
    """
    if not request.user.is_authenticated:
        return {
            'es_administrador_app': False, # 
            'es_administracion': False, # 
            'es_bodega': False, # 
            'es_vendedor': False, # 
            'es_cartera': False, # 
            'es_factura': False, # 
            'es_diseno': False, # 
            'es_online': False, # 
            'puede_ver_panel_django_admin': False,
        }

    return {
        'es_administrador_app': es_administrador_app(request.user), # 
        'es_administracion': es_administracion(request.user), # 
        'es_bodega': es_bodega(request.user), # 
        'es_vendedor': es_vendedor(request.user), # 
        'es_cartera': es_cartera(request.user), # 
        'es_factura': es_factura(request.user), # 
        'es_diseno': es_diseno(request.user), # 
        'es_online': es_online(request.user), # 
        'puede_ver_panel_django_admin': puede_ver_panel_django_admin(request.user),
        
    }