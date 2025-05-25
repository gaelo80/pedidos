# catalogo/views.py
from django.shortcuts import render, redirect
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Prefetch, Q
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from .models import EnlaceCatalogoTemporal
from productos.models import Producto, ReferenciaColor, FotoProducto # Importa tu modelo Producto
from django.contrib.auth.decorators import login_required, user_passes_test
from core.auth_utils import es_admin_sistema, es_vendedor, es_online, es_diseno, es_cartera, es_admin_sistema_app, es_bodega, es_factura

@login_required
@user_passes_test(lambda u: es_online(u) or es_cartera(u) or es_factura(u) or es_diseno(u) or es_vendedor(u) or u.is_superuser or es_admin_sistema(u), login_url='core:acceso_denegado') # Ajusta permisos y URL
def lista_referencias_view(request):
    """
    Vista inicial del catálogo. Muestra referencias únicas con una imagen,
    nombre y descripción representativos. Permite buscar por referencia.
    """
    query = request.GET.get('q', '')
    
    # 1. Obtener las referencias únicas de productos activos
    #    values() especifica los campos por los que se agrupará implícitamente antes de anotar o agregar más.
    #    Aquí queremos una entrada por 'referencia'.
    referencias_qs = Producto.objects.filter(activo=True)

    if query:
        referencias_qs = referencias_qs.filter(referencia__icontains=query)

    # Agrupar por 'referencia' y obtener datos representativos para cada una
    # Usamos values() para agrupar y annotate() para obtener el nombre y descripción
    # Necesitaremos iterar en Python para la foto y el stock total si es complejo
    
    referencias_unicas_con_datos = []
    # Primero obtenemos las distintas referencias
    distinct_referencias = referencias_qs.values_list('referencia', flat=True).distinct().order_by('referencia')

    for ref_val in distinct_referencias:
        # Obtener el primer producto activo de esta referencia como representativo
        producto_representativo = Producto.objects.filter(
            referencia=ref_val, 
            activo=True
        ).select_related('articulo_color_fotos').prefetch_related('articulo_color_fotos__fotos_agrupadas').first()

        if producto_representativo:
            nombre_representativo = producto_representativo.nombre
            descripcion_representativa = producto_representativo.descripcion
            
            foto_url_representativa = None
            if producto_representativo.articulo_color_fotos:
                primera_foto_obj = producto_representativo.articulo_color_fotos.fotos_agrupadas.first()
                if primera_foto_obj and primera_foto_obj.imagen:
                    foto_url_representativa = primera_foto_obj.imagen.url
            
            referencias_unicas_con_datos.append({
                'referencia': ref_val,
                'nombre': nombre_representativo,
                'descripcion': descripcion_representativa,
                'foto_url': foto_url_representativa
            })

    paginator = Paginator(referencias_unicas_con_datos, 12) # Mostrar 12 referencias por página
    page_number = request.GET.get('page')
    try:
        referencias_pagina = paginator.page(page_number)
    except PageNotAnInteger:
        referencias_pagina = paginator.page(1)
    except EmptyPage:
        referencias_pagina = paginator.page(paginator.num_pages)

    context = {
        'referencias_pagina': referencias_pagina,
        'titulo': 'Catálogo',
        'query': query,
    }
    return render(request, 'catalogo/lista_referencias.html', context)

@login_required
@user_passes_test(lambda u: es_online(u) or es_vendedor(u) or es_diseno or u.is_superuser or es_admin_sistema(u), login_url='core:acceso_denegado') # Ajusta permisos y URL
def detalle_referencia_view(request, referencia_str):
    """
    Vista de detalle. Muestra todas las variantes (productos) para una referencia_str dada,
    incluyendo talla, color, descripción, foto individual y stock actual.
    """
    # Obtenemos todas las variantes activas para esta referencia
    variantes_producto = Producto.objects.filter(
        referencia=referencia_str, 
        activo=True
    ).select_related(
        'articulo_color_fotos' # Para la foto principal de la agrupación Color
    ).prefetch_related(
        'articulo_color_fotos__fotos_agrupadas' # Para las fotos
    ).order_by('color', 'talla') # Ordenar para una visualización consistente

    if not variantes_producto.exists():
        # Si no hay productos para esta referencia, puedes redirigir o mostrar un mensaje
        # Por ejemplo, redirigir a la lista principal del catálogo:
        # messages.warning(request, f"No se encontraron productos para la referencia '{referencia_str}'.")
        # return redirect('catalogo:lista_referencias')
        # O simplemente la plantilla manejará la lista vacía.
        pass

    # El nombre de la referencia debería ser bastante consistente entre variantes
    # Tomamos el nombre del primer producto encontrado como representativo para la referencia
    nombre_general_referencia = variantes_producto.first().nombre if variantes_producto.exists() else referencia_str
    descripcion_general_referencia = variantes_producto.first().descripcion if variantes_producto.exists() else ""


    context = {
        'referencia_actual': referencia_str,
        'nombre_general_referencia': nombre_general_referencia,
        'descripcion_general_referencia': descripcion_general_referencia,
        'variantes_list': variantes_producto, # Aquí cada 'variante' es un objeto Producto
        'titulo': f'Referencia: {referencia_str} - {nombre_general_referencia}',
    }
    return render(request, 'catalogo/detalle_referencia.html', context)

@login_required
@user_passes_test(lambda u: es_online(u) or es_vendedor(u) or es_online(u) or u.is_superuser or es_admin_sistema(u), login_url='core:acceso_denegado') # Ajusta permisos y URL
def ver_todas_fotos_referencia_view(request, referencia_str):
    """
    Muestra todas las fotos asociadas a una referencia_base específica.
    """
    # Obtener todas las instancias de ReferenciaColor que coincidan con la referencia_base
    # y precargar sus fotos asociadas.
    objetos_referencia_color = ReferenciaColor.objects.filter(
        referencia_base=referencia_str
    ).prefetch_related('fotos_agrupadas')

    lista_todas_fotos = []
    if objetos_referencia_color.exists():
        # Recopilar todas las fotos de todas las combinaciones de color para esta referencia_base
        # Se usa un set para las URLs para evitar duplicados si la misma imagen estuviera por alguna razón
        # asociada múltiples veces o a través de diferentes objetos ReferenciaColor (aunque no debería ser el caso
        # si cada FotoProducto es única).
        urls_fotos_vistas = set()
        for ref_color_obj in objetos_referencia_color:
            for foto_producto in ref_color_obj.fotos_agrupadas.all():
                if foto_producto.imagen and hasattr(foto_producto.imagen, 'url'):
                    if foto_producto.imagen.url not in urls_fotos_vistas:
                        lista_todas_fotos.append(foto_producto)
                        urls_fotos_vistas.add(foto_producto.imagen.url)
    
    # Obtener un nombre representativo para la referencia (del primer producto o ReferenciaColor)
    nombre_display_referencia = referencia_str # Fallback
    producto_ejemplo = Producto.objects.filter(referencia=referencia_str, activo=True).first()
    if producto_ejemplo:
        nombre_display_referencia = producto_ejemplo.nombre
    elif objetos_referencia_color.exists():
        nombre_display_referencia = objetos_referencia_color.first().nombre_display


    context = {
        'referencia_actual': referencia_str,
        'nombre_display_referencia': nombre_display_referencia,
        'lista_todas_fotos': lista_todas_fotos,
        'titulo': f'Fotos de la Referencia: {referencia_str} - {nombre_display_referencia}',
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
    try:
        enlace = EnlaceCatalogoTemporal.objects.get(token=token)
    except EnlaceCatalogoTemporal.DoesNotExist:
        messages.error(request, "El enlace de catálogo proporcionado no es válido.")
        return render(request, 'catalogo/enlace_mensaje.html', {
            'titulo_mensaje': 'Enlace Inválido',
            'mensaje': 'El enlace al catálogo que has utilizado no existe. Por favor, verifica el enlace o solicita uno nuevo.'
        }, status=404)

    if not enlace.esta_disponible():
        mensaje_error = "Este enlace de catálogo ha expirado."
        if not enlace.activo:
            mensaje_error = "Este enlace de catálogo ha sido desactivado."
        
        messages.error(request, mensaje_error)
        return render(request, 'catalogo/enlace_mensaje.html', {
            'titulo_mensaje': 'Enlace no Disponible',
            'mensaje': mensaje_error + " Por favor, solicita un nuevo enlace si necesitas acceder al catálogo."
        }, status=403)

    # Incrementar contador de uso (opcional)
    enlace.veces_usado += 1
    enlace.save(update_fields=['veces_usado'])

    # --- Lógica para mostrar el catálogo (similar a catalogo_publico_disponible) ---
    query = request.GET.get('q', '')
    referencias_colores_qs = ReferenciaColor.objects.prefetch_related(
        Prefetch(
            'fotos_agrupadas',
            queryset=FotoProducto.objects.order_by('orden')
        ),
        Prefetch(
            'variantes',
            queryset=Producto.objects.filter(activo=True).order_by('talla')
        )
    ).order_by('referencia_base', 'color')

    if query:
        referencias_colores_qs = referencias_colores_qs.filter(
            Q(referencia_base__icontains=query) |
            Q(color__icontains=query) |
            Q(nombre_display__icontains=query)
        ).distinct()

    items_catalogo_final = []
    for rc_item in referencias_colores_qs:
        variantes_con_info_stock = []
        tiene_algun_stock_esta_rc = False
        for producto_variante in rc_item.variantes.all():
            stock = producto_variante.stock_actual
            if stock > 0:
                tiene_algun_stock_esta_rc = True
            variantes_con_info_stock.append({
                'objeto': producto_variante,
                'talla': producto_variante.talla,
                'stock': stock,
                'disponible': stock > 0
            })
        if tiene_algun_stock_esta_rc:
            items_catalogo_final.append({
                'referencia_color_obj': rc_item,
                'nombre_display_final': rc_item.nombre_display or f"{rc_item.referencia_base} - {rc_item.color or 'Sin Color'}",
                'fotos': list(rc_item.fotos_agrupadas.all()),
                'variantes_info': variantes_con_info_stock,
            })

    paginator = Paginator(items_catalogo_final, 9)
    page_number = request.GET.get('page')
    try:
        pagina_items = paginator.page(page_number)
    except PageNotAnInteger:
        pagina_items = paginator.page(1)
    except EmptyPage:
        pagina_items = paginator.page(paginator.num_pages)

    context = {
        'pagina_items': pagina_items,
        'titulo': 'Catálogo Disponible (Compartido)',
        'query': query,
        'es_enlace_temporal': True,
        'valido_hasta': enlace.expira_el.strftime('%d/%m/%Y %H:%M %Z')
    }
    # Puedes reutilizar la misma plantilla del catálogo público
    return render(request, 'catalogo/catalogo_publico_disponible.html', context)

@login_required
@user_passes_test(es_vendedor, login_url='core:acceso_denegado')
def generar_enlace_usuario_view(request): # Esta vista ahora SOLO procesa el POST
    if request.method == 'POST':
        descripcion = request.POST.get('descripcion_enlace', f"Catálogo compartido por {request.user.get_full_name() or request.user.username}")
        dias_validez_str = request.POST.get('dias_validez', '7')

        try:
            dias_validez = int(dias_validez_str)
            if not (1 <= dias_validez <= 90):
                messages.error(request, "La duración del enlace debe ser entre 1 y 90 días.")
                # Redirige de vuelta a la página del formulario
                return redirect('catalogo:mostrar_formulario_generar_enlace')
        except ValueError:
            messages.error(request, "Por favor, introduce un número válido de días para la duración.")
            # Redirige de vuelta a la página del formulario
            return redirect('catalogo:mostrar_formulario_generar_enlace')

        nuevo_enlace = EnlaceCatalogoTemporal.objects.create(
            generado_por=request.user,
            descripcion=descripcion,
            expira_el=timezone.now() + timedelta(days=dias_validez)
        )
        url_completa_para_compartir = request.build_absolute_uri(nuevo_enlace.obtener_url_absoluta())

        request.session['enlace_generado_info'] = {
            'url': url_completa_para_compartir,
            'descripcion': nuevo_enlace.descripcion,
            'expira': nuevo_enlace.expira_el.strftime('%d/%m/%Y a las %H:%M %Z')
        }
        #messages.success(request, "¡Nuevo enlace de catálogo generado exitosamente!")
        # Redirige de vuelta a la página del formulario para mostrar el enlace y el mensaje
        return redirect('catalogo:mostrar_formulario_generar_enlace')

    # Si no es POST, significa que se accedió a esta URL directamente (no debería pasar si el form apunta aquí)
    # Podrías redirigir al formulario o al panel.
    #messages.warning(request, "Por favor, usa el formulario para generar un enlace.")
    return redirect('catalogo:mostrar_formulario_generar_enlace')

@login_required
@user_passes_test(es_vendedor, login_url='core:acceso_denegado') # Ajusta el permiso
def mostrar_formulario_generar_enlace_view(request):
    # Esta vista solo muestra el formulario. El procesamiento del POST lo hará
    # la vista generar_enlace_usuario_view que ya teníamos.

    # Recuperar información del último enlace generado para mostrarla si existe
    # (esto es si la vista de procesamiento POST redirige de vuelta aquí con info en sesión)
    context = {
        'titulo_pagina': 'Generar Enlace de Catálogo para Compartir',
    }
    enlace_info_de_sesion = request.session.pop('enlace_generado_info', None)
    if enlace_info_de_sesion:
        context['enlace_recien_generado'] = enlace_info_de_sesion

    return render(request, 'catalogo/generar_enlace_catalogo_form.html', context)