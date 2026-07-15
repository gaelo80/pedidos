# notificaciones/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Notificacion

@login_required
def lista_notificaciones(request):
    """
    Muestra el historial de notificaciones del usuario en la empresa actual
    (leídas y no leídas) y marca como leídas las pendientes, sin ocultarlas.
    """
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        return render(request, 'notificaciones/lista_notificaciones.html', {
            'notificaciones': Notificacion.objects.none(),
            'ids_recien_leidas': [],
        })

    # Historial completo de esta empresa (no solo las no leídas)
    notificaciones = Notificacion.objects.filter(
        destinatario=request.user,
        empresa=empresa_actual
    ).order_by('-fecha_creacion')

    # Capturamos las que estaban SIN leer, para poder resaltarlas como "nuevas"
    ids_recien_leidas = list(
        notificaciones.filter(leido=False).values_list('id', flat=True)
    )

    # Las marcamos como leídas (el badge baja a 0) PERO seguimos mostrándolas todas
    if ids_recien_leidas:
        Notificacion.objects.filter(pk__in=ids_recien_leidas).update(leido=True)

    return render(request, 'notificaciones/lista_notificaciones.html', {
        'notificaciones': notificaciones,
        'ids_recien_leidas': ids_recien_leidas,
    })