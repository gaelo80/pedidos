from django.contrib.auth.decorators import login_required, user_passes_test
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from productos.models import Producto
from rest_framework.response import Response
from django.http import JsonResponse
from django.db.models import Q


NO_COLOR_SLUG = '-'

@api_view(['GET'])
@permission_classes([IsAuthenticated]) # Requiere autenticación
def get_colores_por_referencia(request, ref):
    """
    Devuelve una lista de colores únicos ({valor, display}) para una referencia dada,
    manejando el caso 'Sin Color' (None o vacío en BD) con el slug NO_COLOR_SLUG.
    """
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        return Response({"error": "No se pudo identificar la empresa."}, status=403)    

    colores_qs = Producto.objects.filter(
        empresa=empresa_actual, 
        referencia=ref,
        activo=True
    ).values_list('color', flat=True).distinct().order_by('color')

    colores_procesados = set() # Para evitar duplicados si hay '' y None tratados igual
    respuesta = []
    has_no_color = False

    for color in colores_qs:
        if color is None or color == '':
            if not has_no_color: 
                has_no_color = True
        elif color not in colores_procesados:
            respuesta.append({'valor': color, 'display': color})
            colores_procesados.add(color)
  
    if has_no_color:
        respuesta.append({'valor': NO_COLOR_SLUG, 'display': 'Sin Color'})
    
    respuesta.sort(key=lambda x: x['display'])
    return Response(respuesta)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_tallas_por_ref_color(request, ref, color_slug):
    """
    Devuelve tallas, IDs, precio y stock para una ref+color,
    filtrando por la empresa del usuario autenticado.
    """
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        return Response({"error": "No se pudo identificar la empresa."}, status=403)
    
    # Determinar el valor para filtrar el color en la BD
    color_filtro = None if color_slug == NO_COLOR_SLUG else color_slug

    # Buscar variantes activas que coincidan y tengan talla
    variantes = Producto.objects.filter(
        empresa=empresa_actual,
        referencia=ref,
        color=color_filtro,
        activo=True,
        talla__isnull=False
    ) 

    # Convertir a lista para poder ordenar y acceder al precio
    variantes_lista = list(variantes)

    if not variantes_lista:
        return Response({"precio_venta": 0, "variantes": []})

    def sort_key(producto):
        try: 
            return float(producto.talla)
        except (ValueError, TypeError): 
            return float('inf')

    variantes_ordenadas = sorted(variantes_lista, key=sort_key)

    precio_grupo = variantes_ordenadas[0].precio_venta

    # Un vendedor estándar solo debe ver el stock que está en bodegas
    # habilitadas para su canal (o que tenga como excepción individual);
    # Admin/Bodega/Online siguen viendo el stock real total.
    usuario = request.user
    es_admin_o_especial = (
        usuario.is_superuser or
        usuario.groups.filter(name__icontains='bodega').exists() or
        usuario.groups.filter(name__icontains='online').exists()
    )

    def _stock_para_frontend(v):
        if es_admin_o_especial:
            return v.stock_actual
        return v.stock_disponible_para_canal('ESTANDAR', usuario=usuario)

    respuesta = {
        'precio_venta': precio_grupo,
        'variantes': [
            {
                'id': v.id,
                'talla': v.talla,
                'stock_actual': _stock_para_frontend(v),
                # --- LÍNEA AÑADIDA ---
                # Enviamos el valor del nuevo campo al frontend.
                'permitir_pedido_sin_stock': v.permitir_preventa
            } for v in variantes_ordenadas
        ]
    }
    return Response(respuesta)


@api_view(['GET'])
@permission_classes([IsAuthenticated]) 
def buscar_productos_api(request):
    """
    Busca productos por término para Select2, filtrando por empresa
    y reglas de visibilidad para vendedores estándar.
    """
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        return JsonResponse({'results': []}) 
    
    term = request.GET.get('term', '').strip()
    if len(term) < 2:
        return JsonResponse({'results': []})
            
    # 1. Consulta base
    queryset = Producto.objects.filter(
        empresa=empresa_actual,
        activo=True
    )

    # --- 2. CANDADO DE VISIBILIDAD MULTI-ROL ---
    usuario = request.user
    
    # Comprobamos si el usuario es Admin o si su grupo contiene la palabra 'online' o 'bodega'
    es_admin_o_especial = (
        usuario.is_superuser or 
        usuario.groups.filter(name__icontains='bodega').exists() or 
        usuario.groups.filter(name__icontains='online').exists()
    )
    
    # Si es Vendedor Estándar (NO admin, NO bodega, NO online), bloqueamos los ocultos
    if not es_admin_o_especial:
        queryset = queryset.filter(oculto_para_standar=False)
    # ------------------------------------------

    # 3. Filtrar por término
    queryset = queryset.filter(
        Q(referencia__icontains=term) | Q(nombre__icontains=term) | Q(codigo_barras__icontains=term)
    )[:20]

    results = []
    for prod in queryset:
        texto_opcion = f"{prod.referencia} - {prod.nombre or ''}"
        if prod.color: texto_opcion += f" / {prod.color}"
        if prod.talla: texto_opcion += f" / Talla: {prod.talla}"
        results.append({'id': prod.pk, 'text': texto_opcion})
    
    return JsonResponse({'results': results})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def buscar_referencias_api(request):
    """
    Busca referencias únicas para Select2, filtrando por la empresa
    y aplicando reglas de visibilidad.
    """
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        return JsonResponse({'results': []})

    term = request.GET.get('term', '').strip()
    if len(term) < 1:
        return JsonResponse({'results': []})

    # 1. Consulta base
    referencias_qs = Producto.objects.filter(
        empresa=empresa_actual,
        referencia__icontains=term,
        activo=True
    )

    # --- 2. CANDADO DE VISIBILIDAD MULTI-ROL ---
    usuario = request.user
    
    es_admin_o_especial = (
        usuario.is_superuser or 
        usuario.groups.filter(name__icontains='bodega').exists() or 
        usuario.groups.filter(name__icontains='online').exists()
    )
    
    if not es_admin_o_especial:
        referencias_qs = referencias_qs.filter(oculto_para_standar=False)
    # ------------------------------------------

    # 3. Agrupar y preparar respuesta
    referencias_qs = referencias_qs.values('referencia').distinct().order_by('referencia')[:20]
    results = [{'id': item['referencia'], 'text': item['referencia']} for item in referencias_qs]
    
    return JsonResponse({'results': results})