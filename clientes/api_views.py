# clientes/api_views.py
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from .models import Cliente
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from rest_framework.response import Response

@login_required
def api_detalle_cliente(request, cliente_id):
    """
    Devuelve detalles de un cliente de forma segura, asegurando que
    pertenezca al inquilino del usuario actual.
    """
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        return JsonResponse({'error': 'Acceso no válido. Empresa no identificada.'}, status=403)

    # El filtro por 'empresa=empresa_actual' es la clave de la seguridad.
    cliente = get_object_or_404(Cliente, pk=cliente_id, empresa=empresa_actual)

    datos_cliente = {
        'id': cliente.pk,
        'nombre': cliente.nombre_completo,
        'nit': cliente.identificacion,
        'direccion': cliente.direccion,
        'telefono': cliente.telefono,
        'email': cliente.email,
        'ciudad': cliente.ciudad.nombre if cliente.ciudad else None,
    }
    return JsonResponse(datos_cliente)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def buscar_clientes_api(request):
    """
    Busca clientes de forma segura para widgets como Select2, filtrando
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
            base_qs = Cliente.objects.all()
        else:
            # Un usuario normal SOLO puede buscar en su propia empresa.
            base_qs = Cliente.objects.filter(empresa=empresa_actual)
        
        # Aplicamos el filtro de búsqueda sobre el queryset ya seguro.
        clientes_filtrados = base_qs.filter(
            Q(nombre_completo__icontains=term) | Q(identificacion__icontains=term)
        ).order_by('nombre_completo')[:20]

        results = [
            {
                "id": cliente.pk,
                "text": f"{cliente.nombre_completo} (ID: {cliente.identificacion or 'N/A'})"
            }
            for cliente in clientes_filtrados
        ]
        
    return Response({"results": results})