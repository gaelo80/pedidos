# notificaciones/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse, NoReverseMatch
from .models import Notificacion

@login_required
def lista_notificaciones(request):
    """
    Muestra SÓLO las notificaciones NO LEÍDAS del usuario y las marca como leídas.
    Esto soluciona el problema de la "lista interminable".
    """
    
    # 1. Aplicamos el filtro Multi-Empresa (¡CRÍTICO!)
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        # Manejar el caso donde no hay empresa (aunque login_required debería prevenirlo)
        return render(request, 'notificaciones/lista_notificaciones.html', {
            'notificaciones': Notificacion.objects.none()
        })

    # 2. Obtenemos SÓLO las no leídas de esta empresa
    notificaciones_no_leidas = Notificacion.objects.filter(
        destinatario=request.user,
        empresa=empresa_actual,
        leido=False
    ).order_by('-fecha_creacion')

    # 3. Obtenemos los IDs ANTES de marcar, para pasarlos a la plantilla
    ids_a_marcar = list(notificaciones_no_leidas.values_list('id', flat=True))

    # 4. Las marcamos como leídas en la base de datos
    if ids_a_marcar:
        Notificacion.objects.filter(pk__in=ids_a_marcar).update(leido=True)

    # 5. Pasamos SÓLO las que acabamos de marcar a la plantilla
    return render(request, 'notificaciones/lista_notificaciones.html', {
        'notificaciones': notificaciones_no_leidas 
    })


# --- NUEVA VISTA PARA EL POLLING AJAX ---

@login_required
def check_notificaciones_cartera_json(request):
    """
    Devuelve un JSON con el conteo de notificaciones PENDIENTES
    que son específicamente para 'Cartera'.
    """
    
    # 1. Aplicamos el filtro Multi-Empresa
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        return JsonResponse({'error': 'Empresa no encontrada'}, status=400)

    try:
        # 2. Esta es la 'huella digital' que identifica las notificaciones
        #    que queremos en el popup, según tu signals.py
        url_cartera = reverse('pedidos:lista_aprobacion_cartera')
    except NoReverseMatch:
        # Si la URL no existe, no podemos filtrar, devolvemos 0
        return JsonResponse({'count': 0, 'status': 'url_no_encontrada'})

    # 3. Contamos cuántas notificaciones no leídas de Cartera tiene el usuario
    count = Notificacion.objects.filter(
        destinatario=request.user,
        empresa=empresa_actual,
        leido=False,
        url=url_cartera  # La clave: solo contamos las de aprobación de cartera
    ).count()

    return JsonResponse({'count': count})