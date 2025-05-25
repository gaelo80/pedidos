from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, get_object_or_404, redirect
from clientes.models import Cliente
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from rest_framework.response import Response


@login_required
def api_detalle_cliente(request, cliente_id):
    """
    Devuelve detalles de un cliente por su ID.
    """
    # Solo permite peticiones GET
    if request.method == 'GET':
        try:
            # Busca el cliente en la base de datos usando el ID de la URL
            # !!! USA 'Cliente' o el nombre de tu modelo de cliente !!!
            cliente = get_object_or_404(Cliente, pk=cliente_id)

            # Prepara los datos que quieres enviar al navegador
            # !!! IMPORTANTE: CAMBIA los nombres después de 'cliente.'
            #     para que coincidan con los nombres de los campos en TU MODELO Cliente !!!
            #     (Puedes ver los nombres correctos en tu archivo models.py)
            datos_cliente = {
                'id': cliente.pk, # El ID siempre es 'pk'
                'nombre': cliente.nombre_completo, # CAMBIA ESTO si tu campo de nombre se llama diferente
                'nit': cliente.identificacion, # CAMBIA ESTO si tu campo de NIT/ID se llama diferente
                'direccion': cliente.direccion, # CAMBIA ESTO por tu campo de dirección
                'telefono': cliente.telefono, # CAMBIA ESTO por tu campo de teléfono
                'email': cliente.email, # CAMBIA ESTO por tu campo de email
                'ciudad': cliente.ciudad.nombre,       # Ahora es una cadena de texto (o None)
                            # 'ciudad': cliente.ciudad.nombre if cliente.ciudad else None, # Ejemplo
            }
            # Envía los datos como respuesta JSON
            return JsonResponse(datos_cliente)

        except Exception as e:
            # Si ocurre un error inesperado
            print(f"Error en api_detalle_cliente: {e}") # Muestra el error en la consola del servidor
            # Envía un mensaje de error genérico al navegador
            return JsonResponse({'error': 'Error interno al obtener detalles'}, status=500)
    else:
        # Si intentan usar un método diferente a GET (como POST)
        return JsonResponse({'error': 'Método no permitido'}, status=405)


@api_view(['GET'])
@permission_classes([IsAuthenticated]) # Asegura que solo usuarios logueados puedan buscar
def buscar_clientes_api(request):
    """
    Busca clientes por nombre o identificación para el widget Select2.
    Espera un parámetro 'term' en la query string.
    """
    term = request.GET.get('term', '').strip()
    results = []

    if len(term) >= 2: # Empezar a buscar después de 2 caracteres (opcional)
        clientes = Cliente.objects.filter(
            Q(nombre_completo__icontains=term) | Q(identificacion__icontains=term)
        ).order_by('nombre_completo')[:20] # Limita a 20 resultados por rendimiento

        results = [
            {
                "id": cliente.pk,
                # Texto que se mostrará en el desplegable de resultados
                "text": f"{cliente.nombre_completo} (NIT/ID: {cliente.identificacion or 'N/A'})"
            }
            for cliente in clientes
        ]
    # Select2 espera un formato específico: un objeto con una clave 'results'
    return Response({"results": results})
