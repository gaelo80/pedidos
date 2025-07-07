# notificaciones/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Notificacion

@login_required
def lista_notificaciones(request):
    """
    Muestra todas las notificaciones del usuario y las marca como leídas.
    """
    notificaciones = Notificacion.objects.filter(destinatario=request.user)
    
    # Obtenemos las no leídas ANTES de renderizar la plantilla
    notificaciones_no_leidas = notificaciones.filter(leido=False)
    
    # Las marcamos como leídas
    notificaciones_no_leidas.update(leido=True)

    return render(request, 'notificaciones/lista_notificaciones.html', {
        'notificaciones': notificaciones
    })
