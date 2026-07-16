# core/context_processors.py
from notificaciones.models import Notificacion
from pedidos.models import Pedido
from vendedores.models import Vendedor
from .auth_utils import es_administracion, es_bodega, es_vendedor, es_cartera, es_factura, es_diseno, es_online, es_administrador_app, es_cajero, puede_ver_panel_django_admin

def empresa_context(request):
    """
    Hace que el título web, el nombre y los assets (logo, banner) de la
    empresa estén disponibles en todas las plantillas, según el tenant actual.
    """
    if hasattr(request, 'tenant') and request.tenant:
        return {
            'titulo_web': request.tenant.titulo_web,
            'nombre_empresa': request.tenant.nombre,
            'empresa_actual': request.tenant,   # objeto completo: da acceso a .logo, .banner_inicio, etc.
        }
    return {}

def notificaciones_context(request):
    """
    Contador de notificaciones NO leídas del usuario EN LA EMPRESA ACTUAL,
    para el badge del navbar. Debe filtrar por tenant igual que las vistas.
    """
    if not request.user.is_authenticated:
        return {}

    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        return {'unread_notifications_count': 0}

    count = Notificacion.objects.filter(
        destinatario=request.user,
        empresa=empresa_actual,   # <-- ESTA LÍNEA FALTABA
        leido=False
    ).count()

    return {'unread_notifications_count': count}
    
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
            'es_cajero': False,
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
        'es_cajero': es_cajero(request.user),
        'puede_ver_panel_django_admin': puede_ver_panel_django_admin(request.user),

    }
    
    
def recordatorio_borradores_context(request):
    """
    Añade un contador de pedidos en estado BORRADOR que
    pertenecen al vendedor actual.
    """
    if not request.user.is_authenticated or not es_vendedor(request.user):
        return {'borradores_pendientes_count': 0}

    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        return {'borradores_pendientes_count': 0}

    # Buscamos el perfil de vendedor (necesario para la consulta)
    try:
        vendedor_actual = Vendedor.objects.get(user=request.user, user__empresa=empresa_actual)
    except Vendedor.DoesNotExist:
        return {'borradores_pendientes_count': 0}

    # Contamos los borradores de este vendedor en esta empresa
    count = Pedido.objects.filter(
        empresa=empresa_actual,
        vendedor=vendedor_actual,
        estado='BORRADOR'
    ).count()
    
    return {
        'borradores_pendientes_count': count
    }