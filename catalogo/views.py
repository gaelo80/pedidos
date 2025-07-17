# catalogo/views.py
from django.shortcuts import render, redirect
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Prefetch, Q
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from .models import EnlaceCatalogoTemporal
from productos.models import Producto, ReferenciaColor, FotoProducto
from django.contrib.auth.decorators import login_required, user_passes_test
from core.auth_utils import es_admin_sistema, es_vendedor, es_online, es_diseno, es_cartera, es_factura

@login_required
@user_passes_test(lambda u: es_online(u) or es_cartera(u) or es_factura(u) or es_diseno(u) or es_vendedor(u) or u.is_superuser, login_url='core:acceso_denegado')
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
    
    paginator = Paginator(referencias_unicas_con_datos, 12)
    page_number = request.GET.get('page')
    referencias_pagina = paginator.get_page(page_number)

    context = {
        'referencias_pagina': referencias_pagina,
        'titulo': 'Catálogo',
        'query': query,
    }
    return render(request, 'catalogo/lista_referencias.html', context)


@login_required
@user_passes_test(lambda u: es_online(u) or es_vendedor(u) or es_diseno(u) or u.is_superuser, login_url='core:acceso_denegado')
def detalle_referencia_view(request, referencia_str):
    """
    Muestra todas las variantes para una referencia, asegurando que pertenezcan
    a la empresa del usuario actual.
    """
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual and not request.user.is_superuser:
        messages.error(request, "Acceso no válido.")
        return redirect('core:index')
        
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

    producto_representativo = variantes_producto.first()
    context = {
        'referencia_actual': referencia_str,
        'nombre_general_referencia': producto_representativo.nombre,
        'descripcion_general_referencia': producto_representativo.descripcion,
        'variantes_list': variantes_producto,
        'titulo': f'Referencia: {referencia_str}',
    }
    return render(request, 'catalogo/detalle_referencia.html', context)


@login_required
@user_passes_test(lambda u: es_online(u) or es_vendedor(u) or es_diseno(u) or u.is_superuser, login_url='core:acceso_denegado')
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
    Muestra un catálogo público de ReferenciaColor que tienen al menos una variante
    (Producto) activa y con stock. Detalla la disponibilidad por talla.
    """
    query = request.GET.get('q', '')

    # 1. Obtener todas las ReferenciaColor.
    #    Prefetch sus fotos y sus variantes (Productos activos).
    referencias_colores_qs = ReferenciaColor.objects.prefetch_related(
        Prefetch(
            'fotos_agrupadas', # related_name desde FotoProducto a ReferenciaColor
            queryset=FotoProducto.objects.order_by('orden')
        ),
        Prefetch(
            'variantes', # related_name desde Producto a ReferenciaColor
            queryset=Producto.objects.filter(activo=True).order_by('talla') # Solo Productos (variantes) activos
        )
    ).order_by('referencia_base', 'color') #

    # 2. Aplicar filtro de búsqueda si existe (sobre campos de ReferenciaColor)
    if query:
        referencias_colores_qs = referencias_colores_qs.filter(
            Q(referencia_base__icontains=query) |
            Q(color__icontains=query) |
            Q(nombre_display__icontains=query)
        ).distinct()

    # 3. Procesar en Python para verificar stock (ya que stock_actual es una property)
    #    y construir la lista final de ítems para el catálogo.
    items_catalogo_final = []
    for rc_item in referencias_colores_qs:
        variantes_con_info_stock = []
        tiene_algun_stock_esta_rc = False

        # rc_item.variantes ya contiene los Productos activos prefetcheados
        for producto_variante in rc_item.variantes.all(): # Iterar sobre las variantes (Producto)
            stock = producto_variante.stock_actual # Llama a la property
            if stock > 0:
                tiene_algun_stock_esta_rc = True
            variantes_con_info_stock.append({
                'objeto': producto_variante, # El objeto Producto completo
                'talla': producto_variante.talla, #
                'stock': stock,
                'disponible': stock > 0
            })

        # Solo incluir esta ReferenciaColor si tiene al menos una variante con stock
        if tiene_algun_stock_esta_rc:
            items_catalogo_final.append({
                'referencia_color_obj': rc_item, # El objeto ReferenciaColor
                'nombre_display_final': rc_item.nombre_display or f"{rc_item.referencia_base} - {rc_item.color or 'Sin Color'}", #
                'fotos': list(rc_item.fotos_agrupadas.all()), # Lista de objetos FotoProducto
                'variantes_info': variantes_con_info_stock, # Lista de dicts con info de stock por talla
            })

    # Paginación
    paginator = Paginator(items_catalogo_final, 9) # Ajusta el número de ítems por página
    page_number = request.GET.get('page')
    try:
        pagina_items = paginator.page(page_number)
    except PageNotAnInteger:
        pagina_items = paginator.page(1)
    except EmptyPage:
        pagina_items = paginator.page(paginator.num_pages)

    context = {
        'pagina_items': pagina_items,
        'titulo': 'Catálogo Disponible',
        'query': query,
    }
    return render(request, 'catalogo/catalogo_publico_disponible.html', context)



def catalogo_publico_temporal_view(request, token):
    """
    Muestra un catálogo filtrado por la empresa asociada al token.
    """
    try:
        enlace = EnlaceCatalogoTemporal.objects.select_related('empresa').get(token=token)
    except EnlaceCatalogoTemporal.DoesNotExist:
        return render(request, 'catalogo/enlace_mensaje.html', {'titulo_mensaje': 'Enlace Inválido', 'mensaje': 'El enlace al catálogo que has utilizado no existe.'}, status=404)

    if not enlace.esta_disponible():
        return render(request, 'catalogo/enlace_mensaje.html', {'titulo_mensaje': 'Enlace no Disponible', 'mensaje': 'Este enlace de catálogo ha expirado o ha sido desactivado.'}, status=403)

    enlace.veces_usado += 1
    enlace.save(update_fields=['veces_usado'])
    
    empresa_catalogo = enlace.empresa
    if not empresa_catalogo:
         return render(request, 'catalogo/enlace_mensaje.html', {'titulo_mensaje': 'Error de Configuración', 'mensaje': 'Este enlace no está asociado a ninguna empresa.'}, status=500)

    query = request.GET.get('q', '')
    
    referencias_colores_qs = ReferenciaColor.objects.filter(
        empresa=empresa_catalogo
    ).prefetch_related(
        Prefetch('fotos_agrupadas', queryset=FotoProducto.objects.order_by('orden')),
        Prefetch('variantes', queryset=Producto.objects.filter(activo=True, empresa=empresa_catalogo).order_by('talla'))
    ).order_by('referencia_base', 'color')

    if query:
        referencias_colores_qs = referencias_colores_qs.filter(
            Q(referencia_base__icontains=query) | Q(color__icontains=query) | Q(nombre_display__icontains=query)
        ).distinct()

    items_catalogo_final = []
    for rc_item in referencias_colores_qs:
        variantes_con_info_stock = []
        tiene_algun_stock_esta_rc = False
        for producto_variante in rc_item.variantes.all():
            stock = producto_variante.stock_actual
            if stock > 0:
                tiene_algun_stock_esta_rc = True
            variantes_con_info_stock.append({'objeto': producto_variante, 'talla': producto_variante.talla, 'stock': stock, 'disponible': stock > 0})
        
        if tiene_algun_stock_esta_rc:
            items_catalogo_final.append({
                'referencia_color_obj': rc_item,
                'nombre_display_final': rc_item.nombre_display or f"{rc_item.referencia_base} - {rc_item.color or 'Sin Color'}",
                'fotos': list(rc_item.fotos_agrupadas.all()),
                'variantes_info': variantes_con_info_stock,
            })

    paginator = Paginator(items_catalogo_final, 9)
    page_number = request.GET.get('page')
    pagina_items = paginator.get_page(page_number)

    context = {
        'pagina_items': pagina_items,
        'titulo': f"Catálogo Disponible {enlace.empresa.nombre}",
        'query': query,
        'es_enlace_temporal': True,
        'valido_hasta': enlace.expira_el.strftime('%d/%m/%Y %H:%M %Z')
    }
    return render(request, 'catalogo/catalogo_publico_disponible.html', context)

@login_required
@user_passes_test(lambda u: es_vendedor(u) or es_cartera(u) or es_online(u) or es_factura(u) or es_factura(u), login_url='core:acceso_denegado')
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
@user_passes_test(lambda u: es_vendedor(u) or es_cartera(u) or es_online(u) or es_factura(u) or es_factura(u), login_url='core:acceso_denegado')
def mostrar_formulario_generar_enlace_view(request):
    """Esta vista no necesita cambios."""
    context = {'titulo_pagina': 'Generar Enlace de Catálogo para Compartir'}
    if 'enlace_generado_info' in request.session:
        context['enlace_recien_generado'] = request.session.pop('enlace_generado_info')
    return render(request, 'catalogo/generar_enlace_catalogo_form.html', context)