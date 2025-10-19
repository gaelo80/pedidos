# catalogo/views.py
from django.shortcuts import render, redirect
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Prefetch, Q, Sum
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from .models import EnlaceCatalogoTemporal
from productos.models import Producto, ReferenciaColor, FotoProducto
from django.contrib.auth.decorators import login_required, user_passes_test
from core.auth_utils import es_administracion, es_bodega, es_vendedor, es_online, es_diseno, es_cartera, es_factura

@login_required
@user_passes_test(lambda u: es_online(u) or es_vendedor(u) or es_diseno(u) or es_bodega(u) or es_cartera(u) or es_administracion(u) or es_factura or u.is_superuser, login_url='core:acceso_denegado')
def lista_referencias_view(request):
    """
    Muestra las referencias únicas del catálogo para la empresa del usuario actual.
    """
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual and not request.user.is_superuser:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')
        
    query = request.GET.get('q', '')

    if request.user.is_superuser:
        base_qs = Producto.objects.filter(activo=True)
    else:
        base_qs = Producto.objects.filter(activo=True, empresa=empresa_actual)

    if query:
        base_qs = base_qs.filter(referencia__icontains=query)

    distinct_referencias = base_qs.values_list('referencia', flat=True).distinct().order_by('referencia')

    referencias_unicas_con_datos = []
    for ref_val in distinct_referencias:
        producto_representativo = base_qs.filter(
            referencia=ref_val
        ).select_related('articulo_color_fotos').prefetch_related('articulo_color_fotos__fotos_agrupadas').first()

        if producto_representativo:
            foto_url = None
            if producto_representativo.articulo_color_fotos and hasattr(producto_representativo.articulo_color_fotos, 'fotos_agrupadas'):
                primera_foto = producto_representativo.articulo_color_fotos.fotos_agrupadas.first()
                if primera_foto and primera_foto.imagen:
                    foto_url = primera_foto.imagen.url
            
            referencias_unicas_con_datos.append({
                'referencia': ref_val,
                'nombre': producto_representativo.nombre,
                'descripcion': producto_representativo.descripcion,
                'foto_url': foto_url
            })
    
    paginator = Paginator(referencias_unicas_con_datos, 18)
    page_number = request.GET.get('page')
    referencias_pagina = paginator.get_page(page_number)

    context = {
        'referencias_pagina': referencias_pagina,
        'titulo': 'Catálogo',
        'query': query,
    }
    return render(request, 'catalogo/lista_referencias.html', context)


@login_required
@user_passes_test(lambda u: es_online(u) or es_vendedor(u) or es_diseno(u) or es_bodega(u) or es_cartera(u) or es_administracion(u) or es_factura or u.is_superuser, login_url='core:acceso_denegado')
def detalle_referencia_view(request, referencia_str):
    """
    Muestra todas las variantes para una referencia, asegurando que pertenezcan
    a la empresa del usuario actual.
    """
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual and not request.user.is_superuser:
        messages.error(request, "Acceso no válido.")
        return redirect('core:index')
    
    # --- INICIO: Cargar Mapeo de Tallas (Refactor) ---
    TALLAS_MAPEO = (empresa_actual.talla_mapeo or {}) if empresa_actual else {}
    # --- FIN: Cargar Mapeo de Tallas ---
        
    if request.user.is_superuser:
        base_qs = Producto.objects.all()
    else:
        base_qs = Producto.objects.filter(empresa=empresa_actual)
        
    variantes_producto = base_qs.filter(
        referencia=referencia_str, 
        activo=True
    ).select_related(
        'articulo_color_fotos'
    ).prefetch_related(
        'articulo_color_fotos__fotos_agrupadas'
    ).order_by('color', 'talla')

    if not variantes_producto.exists():
        messages.warning(request, f"No se encontraron productos para la referencia '{referencia_str}' en su empresa.")
        return redirect('catalogo:lista_referencias')
    
    # --- INICIO: Aplicar Mapeo de Tallas (Refactor) ---
    # Convertimos a lista para poder modificar los objetos en memoria
    variantes_list = list(variantes_producto)
    for variante in variantes_list:
        talla_original = variante.talla or ''
        talla_como_texto = str(talla_original).strip()
        # Modificamos el atributo 'talla' que verá la plantilla
        variante.talla = TALLAS_MAPEO.get(talla_como_texto, talla_como_texto)
    # --- FIN: Aplicar Mapeo de Tallas ---

    producto_representativo = variantes_producto.first()
    context = {
        'referencia_actual': referencia_str,
        'nombre_general_referencia': producto_representativo.nombre,
        'descripcion_general_referencia': producto_representativo.descripcion,
        'variantes_list': variantes_list,
        'titulo': f'Referencia: {referencia_str}',
    }
    return render(request, 'catalogo/detalle_referencia.html', context)


@login_required
@user_passes_test(lambda u: es_online(u) or es_vendedor(u) or es_diseno(u) or es_bodega(u) or es_cartera(u) or es_administracion(u) or es_factura or u.is_superuser, login_url='core:acceso_denegado')
def ver_todas_fotos_referencia_view(request, referencia_str):
    """
    Muestra todas las fotos asociadas a una referencia, filtrando por inquilino.
    """
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual and not request.user.is_superuser:
        messages.error(request, "Acceso no válido.")
        return redirect('core:index')

    if request.user.is_superuser:
        rc_base_qs = ReferenciaColor.objects.all()
        prod_base_qs = Producto.objects.filter(activo=True)
    else:
        rc_base_qs = ReferenciaColor.objects.filter(empresa=empresa_actual)
        prod_base_qs = Producto.objects.filter(activo=True, empresa=empresa_actual)

    objetos_referencia_color = rc_base_qs.filter(
        referencia_base=referencia_str
    ).prefetch_related('fotos_agrupadas')

    lista_todas_fotos = []
    if objetos_referencia_color.exists():
        urls_fotos_vistas = set()
        for ref_color_obj in objetos_referencia_color:
            for foto_producto in ref_color_obj.fotos_agrupadas.all():
                if foto_producto.imagen and hasattr(foto_producto.imagen, 'url'):
                    if foto_producto.imagen.url not in urls_fotos_vistas:
                        lista_todas_fotos.append(foto_producto)
                        urls_fotos_vistas.add(foto_producto.imagen.url)
    
    producto_ejemplo = prod_base_qs.filter(referencia=referencia_str).first()
    nombre_display_referencia = producto_ejemplo.nombre if producto_ejemplo else referencia_str

    context = {
        'referencia_actual': referencia_str,
        'nombre_display_referencia': nombre_display_referencia,
        'lista_todas_fotos': lista_todas_fotos,
        'titulo': f'Fotos de la Referencia: {referencia_str}',
    }
    return render(request, 'catalogo/todas_fotos_referencia.html', context)


def catalogo_publico_disponible(request):
    """
    Muestra un catálogo público de ReferenciaColor si cumplen las condiciones de stock o preventa.
    """
    query = request.GET.get('q', '')
    categoria_query = request.GET.get('categoria', '')
    
    

    referencias_colores_qs = ReferenciaColor.objects.annotate(
        stock_total=Sum('variantes__movimientos__cantidad')
    ).order_by('-stock_total', '-referencia_base').prefetch_related(
        Prefetch('fotos_agrupadas', queryset=FotoProducto.objects.order_by('orden')),
        Prefetch('variantes', queryset=Producto.objects.filter(activo=True).order_by('talla'))
    )

    if query:
        referencias_colores_qs = referencias_colores_qs.filter(
            Q(referencia_base__icontains=query) |
            Q(color__icontains=query) |
            Q(nombre_display__icontains=query)
        ).distinct()
        
    if categoria_query:
        referencias_colores_qs = referencias_colores_qs.filter(variantes__genero=categoria_query).distinct()
        
    items_catalogo_final = []
    for rc_item in referencias_colores_qs:
        
        # --- INICIO: Cargar Mapeo de Tallas (Refactor) ---
        # Cada ReferenciaColor pertenece a una empresa, cargamos su mapeo
        empresa_obj = rc_item.empresa
        TALLAS_MAPEO = (empresa_obj.talla_mapeo or {}) if empresa_obj else {}
        # --- FIN: Cargar Mapeo de Tallas ---
        
        variantes_con_info_stock = []
        mostrar_esta_referencia = False
        
        if not rc_item.variantes.all().exists():
            continue

        for producto_variante in rc_item.variantes.all():
            stock = producto_variante.stock_actual
            en_produccion = producto_variante.permitir_preventa

            if stock > 0 or en_produccion:
                mostrar_esta_referencia = True

# --- CORRECCIÓN DE SINTAXIS (Refactor) ---
            # 1. Calcular la talla mapeada ANTES de crear el diccionario
            talla_original = producto_variante.talla or ''
            talla_como_texto = str(talla_original).strip()
            talla_display = TALLAS_MAPEO.get(talla_como_texto, talla_como_texto)
            
            # 2. Ahora sí, crear el diccionario y añadirlo a la lista
            variantes_con_info_stock.append({
                'talla': talla_display, # <-- Talla Mapeada
                'stock': stock,
                'en_produccion': en_produccion,
                'disponible': stock > 0 or en_produccion,
            })
            # --- FIN DE LA CORRECCIÓN ---

        if mostrar_esta_referencia:
            items_catalogo_final.append({
                'referencia_color_obj': rc_item,
                'nombre_display_final': rc_item.nombre_display or f"{rc_item.referencia_base} - {rc_item.color or 'Sin Color'}",
                'fotos': list(rc_item.fotos_agrupadas.all()),
                'variantes_info': variantes_con_info_stock,
            })

    paginator = Paginator(items_catalogo_final, 18)
    page_number = request.GET.get('page')
    pagina_items = paginator.get_page(page_number)

    context = {
        'pagina_items': pagina_items,
        'titulo': 'Catálogo Disponible',
        'query': query,
        'categoria_seleccionada': categoria_query,
    }
    return render(request, 'catalogo/catalogo_publico_disponible.html', context)


def catalogo_publico_temporal_view(request, token):
    """
    Muestra un catálogo filtrado por empresa si las referencias cumplen condiciones de stock o preventa.
    """
    # (El código de validación del token y la empresa no cambia)
    try:
        enlace = EnlaceCatalogoTemporal.objects.select_related('empresa').get(token=token)
    except EnlaceCatalogoTemporal.DoesNotExist:
        return render(request, 'catalogo/enlace_mensaje.html', {'titulo_mensaje': 'Enlace Inválido', 'mensaje': 'El enlace al catálogo que has utilizado no existe.'}, status=404)

    if not enlace.esta_disponible():
        return render(request, 'catalogo/enlace_mensaje.html', {'titulo_mensaje': 'Enlace no Disponible', 'mensaje': 'Este enlace de catálogo ha expirado o ha sido desactivado.'}, status=403)

    enlace.veces_usado += 1
    enlace.save(update_fields=['veces_usado'])
    empresa_catalogo = enlace.empresa
    TALLAS_MAPEO = empresa_catalogo.talla_mapeo or {}

    query = request.GET.get('q', '')
    categoria_query = request.GET.get('categoria', '')
    
    
    referencias_colores_qs = ReferenciaColor.objects.filter(
        empresa=empresa_catalogo
    ).annotate(
        stock_total=Sum('variantes__movimientos__cantidad')
    ).order_by('-stock_total', '-referencia_base').prefetch_related(
        Prefetch('fotos_agrupadas', queryset=FotoProducto.objects.order_by('orden')),
        Prefetch('variantes', queryset=Producto.objects.filter(activo=True, empresa=empresa_catalogo).order_by('talla'))
    )
    
    
    if query:
        referencias_colores_qs = referencias_colores_qs.filter(
            Q(referencia_base__icontains=query) | Q(color__icontains=query) | Q(nombre_display__icontains=query)
        ).distinct()
       
    if categoria_query:
        referencias_colores_qs = referencias_colores_qs.filter(variantes__genero=categoria_query).distinct()

    items_catalogo_final = []
    for rc_item in referencias_colores_qs:
        variantes_con_info_stock = []
        mostrar_esta_referencia = False
        
        if not rc_item.variantes.all().exists():
            continue

        for producto_variante in rc_item.variantes.all():
            stock = producto_variante.stock_actual
            en_produccion = producto_variante.permitir_preventa

            if stock > 0 or en_produccion:
                mostrar_esta_referencia = True
            
# --- CORRECCIÓN DE SINTAXIS (Refactor) ---
            # 1. Calcular la talla mapeada ANTES de crear el diccionario
            talla_original = producto_variante.talla or ''
            talla_como_texto = str(talla_original).strip()
            talla_display = TALLAS_MAPEO.get(talla_como_texto, talla_como_texto)

            # 2. Ahora sí, crear el diccionario y añadirlo a la lista
            variantes_con_info_stock.append({
                'talla': talla_display, # <-- Talla Mapeada
                'stock': stock,
                'en_produccion': en_produccion,
                'disponible': stock > 0 or en_produccion
            })
            # --- FIN DE LA CORRECCIÓN ---
        
        if mostrar_esta_referencia:
            items_catalogo_final.append({
                'referencia_color_obj': rc_item,
                'nombre_display_final': rc_item.nombre_display or f"{rc_item.referencia_base} - {rc_item.color or 'Sin Color'}",
                'fotos': list(rc_item.fotos_agrupadas.all()),
                'variantes_info': variantes_con_info_stock,
            })

    paginator = Paginator(items_catalogo_final, 18)
    page_number = request.GET.get('page')
    pagina_items = paginator.get_page(page_number)

    context = {
        'pagina_items': pagina_items,
        'titulo': f"Catálogo Disponible {enlace.empresa.nombre}",
        'query': query,
        'categoria_seleccionada': categoria_query,
        'es_enlace_temporal': True,
        'valido_hasta': enlace.expira_el.strftime('%d/%m/%Y %H:%M %Z')
    }
    return render(request, 'catalogo/catalogo_publico_disponible.html', context)

@login_required
@user_passes_test(lambda u: es_vendedor(u) or es_cartera(u) or es_online(u) or es_factura(u) or es_administracion(u), login_url='core:acceso_denegado')
def generar_enlace_usuario_view(request):
    if request.method == 'POST':
        # CORRECCIÓN: Se obtiene la empresa del usuario actual.
        empresa_actual = getattr(request, 'tenant', None)
        if not empresa_actual:
            messages.error(request, "No se puede generar un enlace sin una empresa asociada.")
            return redirect('catalogo:mostrar_formulario_generar_enlace')

        try:
            dias_validez = int(request.POST.get('dias_validez', '7'))
            if not (1 <= dias_validez <= 90):
                messages.error(request, "La duración del enlace debe ser entre 1 y 90 días.")
                return redirect('catalogo:mostrar_formulario_generar_enlace')
        except ValueError:
            messages.error(request, "Por favor, introduce un número válido de días para la duración.")
            return redirect('catalogo:mostrar_formulario_generar_enlace')
        
        # CORRECCIÓN: Se asegura que 'empresa' se asigne al crear el enlace.
        nuevo_enlace = EnlaceCatalogoTemporal.objects.create(
            generado_por=request.user,
            empresa=empresa_actual,
            descripcion=request.POST.get('descripcion_enlace', f"Catálogo para {empresa_actual.nombre}"),
            expira_el=timezone.now() + timedelta(days=dias_validez)
        )
        
        url_completa = request.build_absolute_uri(nuevo_enlace.obtener_url_absoluta())
        request.session['enlace_generado_info'] = {
            'url': url_completa,
            'descripcion': nuevo_enlace.descripcion,
            'expira': nuevo_enlace.expira_el.strftime('%d/%m/%Y a las %H:%M %Z')
        }
        return redirect('catalogo:catalogo_mostrar_formulario_enlace')
    
    return redirect('catalogo:catalogo_mostrar_formulario_enlace')

@login_required
@user_passes_test(lambda u: es_vendedor(u) or es_cartera(u) or es_online(u) or es_factura(u) or es_administracion(u), login_url='core:acceso_denegado')
def mostrar_formulario_generar_enlace_view(request):
    """Esta vista no necesita cambios."""
    context = {'titulo_pagina': 'Generar Enlace de Catálogo para Compartir'}
    if 'enlace_generado_info' in request.session:
        context['enlace_recien_generado'] = request.session.pop('enlace_generado_info')
    return render(request, 'catalogo/generar_enlace_catalogo_form.html', context)