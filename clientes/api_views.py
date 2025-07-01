# clientes/api_views.py
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from .models import Cliente
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from rest_framework.response import Response

@login_required # Usa los decoradores estándar de Django si es una API interna
def api_detalle_cliente(request, cliente_id):
    """
    Devuelve detalles de un cliente de forma segura, asegurando que
    pertenezca al inquilino del usuario actual.
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    # Obtenemos el inquilino del request.
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        return JsonResponse({'error': 'Acceso no válido. Empresa no identificada.'}, status=403)

    try:
        # <<< CORRECCIÓN CRÍTICA DE SEGURIDAD >>>
        # Se añade el filtro por 'empresa=empresa_actual' para evitar fugas de datos.
        cliente = get_object_or_404(Cliente, pk=cliente_id, empresa=empresa_actual)

        # Preparamos los datos del cliente para la respuesta.
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

    except Cliente.DoesNotExist:
         return JsonResponse({'error': 'Cliente no encontrado'}, status=404)
    except Exception as e:
        print(f"Error en api_detalle_cliente: {e}")
        return JsonResponse({'error': 'Error interno al obtener detalles'}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def buscar_clientes_api(request):
    """
    Busca clientes de forma segura para widgets como Select2, filtrando
    por el inquilino del usuario actual.
    """
    term = request.GET.get('term', '').strip()
    
    # Obtenemos el inquilino del request.
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual and not request.user.is_superuser:
        # Si no es superusuario y no hay inquilino, no devolvemos resultados.
        return Response({"results": []})

    results = []

    if len(term) >= 2:
        # <<< CORRECCIÓN CRÍTICA DE SEGURIDAD >>>
        # 1. Filtramos primero por la empresa del usuario.
        if request.user.is_superuser:
            # Un superusuario puede buscar en todas las empresas.
            base_qs = Cliente.objects.all()
        else:
            base_qs = Cliente.objects.filter(empresa=empresa_actual)
        
        # 2. Aplicamos el filtro de búsqueda sobre el queryset ya seguro.
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