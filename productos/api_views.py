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
@authentication_classes([SessionAuthentication]) # O la que uses
@permission_classes([IsAuthenticated]) # Requiere autenticación para acceder
def get_colores_por_referencia(request, ref):
    """
    Devuelve una lista de colores únicos ({valor, display}) para una referencia dada,
    manejando el caso 'Sin Color' (None o vacío en BD) con el slug NO_COLOR_SLUG.
    """
    # Obtener colores distintos, incluyendo None o '' si existen
    colores_qs = Producto.objects.filter(
        referencia=ref,
        activo=True
    ).values_list('color', flat=True).distinct().order_by('color')

    colores_procesados = set() # Para evitar duplicados si hay '' y None tratados igual
    respuesta = []
    has_no_color = False

    for color in colores_qs:
        if color is None or color == '':
            if not has_no_color: # Añadir solo una vez la opción 'Sin Color'
                has_no_color = True
        elif color not in colores_procesados:
            respuesta.append({'valor': color, 'display': color})
            colores_procesados.add(color)

    # Si se encontró algún producto sin color (None o ''), añadir la opción especial
    if has_no_color:
        respuesta.append({'valor': NO_COLOR_SLUG, 'display': 'Sin Color'})

    # Ordenar alfabéticamente por el texto mostrado (display)
    respuesta.sort(key=lambda x: x['display'])

    return Response(respuesta)

@api_view(['GET'])
@authentication_classes([SessionAuthentication]) # O la que uses
@permission_classes([IsAuthenticated]) # Requiere autenticación
def get_tallas_por_ref_color(request, ref, color_slug):
    """
    Devuelve tallas y IDs de variante para ref y color, INCLUYENDO PRECIO y STOCK
    en la estructura correcta para el JS:
    {'precio_venta': P, 'variantes': [{'id': Y, 'talla': T, 'stock_actual': S}, ...]}.
    Ordena las tallas numéricamente.
    """
    # Determinar el valor para filtrar el color en la BD
    color_filtro = None if color_slug == NO_COLOR_SLUG else color_slug

    # Buscar variantes activas que coincidan y tengan talla
    variantes = Producto.objects.filter(
        referencia=ref,
        color=color_filtro,
        activo=True,
        talla__isnull=False
    ) # No ordenamos aún en DB si vamos a reordenar en Python

    # Convertir a lista para poder ordenar y acceder al precio
    variantes_lista = list(variantes)

    if not variantes_lista:
        # Si no hay variantes, devolver estructura vacía esperada por JS
        return Response({"precio_venta": 0, "variantes": []})

    # Función para ordenar tallas: numérico primero, luego texto/infinito
    def sort_key(producto):
        try: return float(producto.talla)
        except (ValueError, TypeError): return float('inf')

    # Ordenar la lista de variantes en Python
    variantes_ordenadas = sorted(variantes_lista, key=sort_key)

    # Tomar el precio de la primera variante encontrada (después de ordenar)
    # Asegúrate que esta lógica sea correcta
    precio_grupo = variantes_ordenadas[0].precio_venta

    # Construir la respuesta final, AÑADIENDO EL STOCK
    respuesta = {
        'precio_venta': precio_grupo,
        'variantes': [
            {
                'id': v.id,
                'talla': v.talla,
                # --- ¡¡CAMBIO PRINCIPAL AQUÍ!! ---
                'stock_actual': v.stock_actual # Asume que tu campo/propiedad se llama stock_actual
                # --- FIN DEL CAMBIO ---
            } for v in variantes_ordenadas
        ]
    }

    return Response(respuesta)


def buscar_productos_api(request):
    """
    Busca productos por término (referencia o descripción) y devuelve JSON para Select2.
    """
    term = request.GET.get('term', '').strip()
    resultados_json = {'results': []} # Formato esperado por Select2

    if len(term) >= 2: # Buscar solo si se escriben al menos 2 caracteres
        try:
            # --- AJUSTA ESTA BÚSQUEDA SEGÚN TUS CAMPOS ---
            # Busca por referencia O descripción (ignorando mayúsculas/minúsculas)
            # ¡Cambia 'referencia' y 'descripcion' si tus campos se llaman diferente!
            queryset = Producto.objects.filter(
            Q(referencia__icontains=term) | Q(descripcion__icontains=term)
            )
            # --- FIN AJUSTE BÚSQUEDA ---

            # Limita la cantidad de resultados
            productos_encontrados = queryset[:20] # Muestra máximo 20

            # Formatear para Select2: lista de diccionarios con 'id' y 'text'
            resultados = []
            for prod in productos_encontrados:
                # --- AJUSTA CÓMO SE MUESTRA EL TEXTO ---
                # Define cómo quieres que se vea cada opción en la lista desplegable
                texto_opcion = f"{prod.referencia} - {prod.nombre or ''}"
                if prod.color:
                     texto_opcion += f" / Color: {prod.color}"
                if prod.talla:
                     texto_opcion += f" / Talla: {prod.talla}"
                # --- FIN AJUSTE TEXTO ---

                resultados.append({'id': prod.pk, 'text': texto_opcion})

            resultados_json['results'] = resultados

        except Exception as e:
            print(f"Error en API buscar_productos_api: {e}")
            # Podrías devolver un error JSON si quieres, pero Select2 usualmente solo necesita 'results'

    # Devuelve siempre una respuesta JSON (aunque 'results' esté vacío)
    return JsonResponse(resultados_json)

def buscar_referencias_api(request):
    """
    Vista API para buscar referencias únicas para Select2.
    Espera un parámetro 'term' en la URL (ej: /api/buscar-referencias/?term=BUSQUEDA).
    """
    term = request.GET.get('term', '').strip()
    results = []

    if len(term) >= 1: # O 2, la longitud mínima que quieras para buscar
        # Busca productos cuya referencia contenga el término (ignorando mayúsculas/minúsculas)
        # distinct('referencia') obtiene solo una vez cada referencia encontrada
        # values('referencia') selecciona solo el campo referencia
        referencias_qs = Producto.objects.filter(
            referencia__icontains=term,
            activo=True # Opcional: solo buscar en productos activos
        ).values('referencia').distinct().order_by('referencia')[:20] # Limita a 20 resultados

        # Formatea para Select2: necesita 'id' y 'text'
        for item in referencias_qs:
            referencia_val = item['referencia']
            results.append({
                'id': referencia_val,   # El valor que se enviará (la propia referencia)
                'text': referencia_val # El texto que se mostrará
                # Podrías hacer el 'text' más descriptivo si quieres, ej:
                # 'text': f"{referencia_val} - Alguna descripción"
            })

    # Devuelve la respuesta en formato JSON que Select2 entiende
    return JsonResponse({'results': results})