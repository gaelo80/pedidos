# prospectos/api_views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q

from .models import Prospecto

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def buscar_prospectos_api(request):
    """
    Busca prospectos de forma segura para widgets como Select2, filtrando
    estrictamente por el inquilino (empresa) del usuario actual.
    """
    term = request.GET.get('term', '').strip()
    empresa_actual = getattr(request, 'tenant', None)

    # Si el usuario no es superusuario y no tiene una empresa asignada, no debe ver nada.
    if not request.user.is_superuser and not empresa_actual:
        return Response({"results": []})

    results = []
    if len(term) >= 2:
        # --- LÓGICA DE FILTRADO MULTI-INQUILINO REFORZADA ---
        if request.user.is_superuser:
            # Un superusuario puede buscar en todas las empresas.
            base_qs = Prospecto.objects.all()
        else:
            # Un usuario normal SOLO puede buscar en su propia empresa.
            base_qs = Prospecto.objects.filter(empresa=empresa_actual)
        
        # Aplicamos el filtro de búsqueda sobre el queryset ya seguro.
        prospectos_filtrados = base_qs.filter(
            Q(estado__in=['PENDIENTE', 'EN_ESTUDIO']) &
            (Q(nombre_completo__icontains=term) | Q(identificacion__icontains=term))
        ).order_by('nombre_completo')[:20]

        results = [
            {
                "id": prospecto.pk,
                "text": f"[PROSPECTO] {prospecto.nombre_completo} (ID: {prospecto.identificacion or 'N/A'})"
            }
            for prospecto in prospectos_filtrados
        ]
        
    return Response({"results": results})