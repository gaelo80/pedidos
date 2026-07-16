# productos/views.py
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView # Añadir DetailView si la necesitas
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin # Asumiendo que quieres proteger estas vistas
from django.contrib.auth.mixins import UserPassesTestMixin # Para permisos más específicos
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from django.shortcuts import redirect
from django.db.models import Q, Prefetch, Max
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from .models import Producto, FotoProducto, ReferenciaColor, generar_codigo_ean13
from django.contrib.auth.decorators import login_required, permission_required
from core.auth_utils import es_administracion, es_diseno
from .forms import ProductoImportForm
from .resources import ProductoResource
from tablib import Dataset
from core.mixins import TenantAwareMixin
from django.contrib.auth.mixins import UserPassesTestMixin
import logging
from django.forms import formset_factory
from .forms import ProductoBaseForm, ProductoTallaEditForm
from django.db import transaction, IntegrityError


logger = logging.getLogger(__name__)



class ProductoListView(TenantAwareMixin, LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    Muestra UNA fila por Referencia+Color (no una por cada talla), para no
    tener que revisar variante por variante. Al editar, se cargan todas las
    tallas que ya existan para esa referencia+color (ver
    'editar_producto_multi_talla').
    """
    model = Producto
    template_name = 'productos/producto_list.html'
    context_object_name = 'productos'
    paginate_by = 15

    permission_required = 'productos.view_producto'
    login_url = reverse_lazy('core:acceso_denegado')

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para ver el listado de productos.")
        return redirect(self.login_url)

    def get_queryset(self):
        # No usamos el bypass de superuser de TenantAwareMixin: el listado es
        # siempre de UNA empresa, incluso para un superusuario administrando
        # una empresa específica (de lo contrario se mezclarían productos de
        # todas las empresas del sistema y 'Editar' terminaría apuntando a la
        # variante de otra empresa, dando 404).
        empresa_actual = self.request.tenant
        queryset = Producto.objects.filter(empresa=empresa_actual)

        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(referencia__icontains=query) |
                Q(nombre__icontains=query) |
                Q(talla__icontains=query) |
                Q(color__nombre__icontains=query) |
                Q(codigo_barras__icontains=query)
            )

        # Una fila representativa por Referencia+Color (Postgres DISTINCT ON).
        # Se usa 'color_id' explícito (no 'color') porque Color tiene Meta.ordering
        # propio ('nombre'): Django expandiría 'color' a 'color__nombre' al
        # resolver el order_by, lo que ya no coincidiría con las columnas de
        # distinct() y rompe la restricción de Postgres para DISTINCT ON.
        return queryset.order_by('referencia', 'color_id', 'talla').distinct('referencia', 'color_id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Listado de Productos"
        context['search_query'] = self.request.GET.get('q', '')

        empresa_actual = self.request.tenant
        productos_pagina = context['productos']

        # Para cada fila representativa, calculamos cuántas tallas tiene y
        # cuáles, para mostrarlo de un vistazo sin entrar a cada una.
        for producto in productos_pagina:
            variantes = Producto.objects.filter(
                empresa=empresa_actual, referencia=producto.referencia, color=producto.color
            ).order_by('talla').values_list('talla', flat=True)
            producto.tallas_disponibles = list(variantes)
            producto.total_tallas = len(producto.tallas_disponibles)

        return context

@login_required
@permission_required('productos.change_producto', login_url='core:acceso_denegado')
def editar_producto_multi_talla(request, pk):
    """
    Edita de una sola vez todas las tallas que comparten referencia+color con
    el producto indicado (el mismo agrupamiento que ya usa la creación
    multi-talla), ya que entre tallas solo cambian la talla y el código de
    barras — el resto de la información es común.
    """
    empresa_actual = request.tenant
    producto_ref = get_object_or_404(Producto, pk=pk, empresa=empresa_actual)

    grupo_qs = Producto.objects.filter(
        empresa=empresa_actual,
        referencia=producto_ref.referencia,
        color=producto_ref.color,
    ).order_by('talla')

    ProductoTallaEditFormSet = formset_factory(ProductoTallaEditForm, extra=3)

    if request.method == 'POST':
        base_form = ProductoBaseForm(request.POST, empresa=empresa_actual)
        talla_formset = ProductoTallaEditFormSet(request.POST, prefix='tallas')

        if base_form.is_valid() and talla_formset.is_valid():
            datos_comunes = base_form.cleaned_data

            filas_a_guardar = [
                f.cleaned_data for f in talla_formset
                if f.cleaned_data and f.cleaned_data.get('talla')
            ]

            if not filas_a_guardar:
                messages.warning(request, "Debes conservar o agregar al menos una talla.")
            else:
                try:
                    with transaction.atomic():
                        for fila in filas_a_guardar:
                            producto_id = fila.get('producto_id')
                            es_nuevo = not producto_id
                            if producto_id:
                                producto_obj = get_object_or_404(Producto, pk=producto_id, empresa=empresa_actual)
                            else:
                                producto_obj = Producto(empresa=empresa_actual)

                            producto_obj.referencia = datos_comunes['referencia']
                            producto_obj.nombre = datos_comunes['nombre']
                            producto_obj.descripcion = datos_comunes.get('descripcion')
                            producto_obj.color = datos_comunes.get('color')
                            producto_obj.genero = datos_comunes.get('genero')
                            producto_obj.costo = datos_comunes.get('costo')
                            producto_obj.precio_venta = datos_comunes.get('precio_venta')
                            producto_obj.unidad_medida = datos_comunes.get('unidad_medida')
                            producto_obj.ubicacion = datos_comunes.get('ubicacion')
                            producto_obj.activo = datos_comunes.get('activo', True)
                            producto_obj.permitir_preventa = datos_comunes.get('permitir_preventa', False)
                            producto_obj.talla = fila.get('talla')
                            if es_nuevo:
                                # Talla nueva: si no se escribió un código manualmente,
                                # se genera un EAN13 automático (mismo esquema que en creación).
                                producto_obj.codigo_barras = fila.get('codigo_barras') or generar_codigo_ean13(empresa_actual)
                            else:
                                producto_obj.codigo_barras = fila.get('codigo_barras') or None
                            producto_obj.save()

                    messages.success(request, f"'{datos_comunes['referencia']} - {datos_comunes['nombre']}' actualizado exitosamente para {len(filas_a_guardar)} talla(s).")
                    return redirect('productos:producto_listado')

                except IntegrityError:
                    messages.error(
                        request,
                        "Error: una de las tallas (misma referencia, talla y color) ya existe, o el código de "
                        "barras está repetido. No se guardó ningún cambio."
                    )
        else:
            messages.error(request, "Por favor corrige los errores en el formulario.")
    else:
        base_form = ProductoBaseForm(instance=producto_ref, empresa=empresa_actual)
        initial_tallas = [
            {'producto_id': p.pk, 'talla': p.talla, 'codigo_barras': p.codigo_barras}
            for p in grupo_qs
        ]
        talla_formset = ProductoTallaEditFormSet(initial=initial_tallas, prefix='tallas')

    context = {
        'base_form': base_form,
        'talla_formset': talla_formset,
        'titulo_pagina': f"Editar Producto: {producto_ref.referencia}",
        'es_edicion': True,
    }
    return render(request, 'productos/producto_multi_talla_form.html', context)


class ProductoDetailView(TenantAwareMixin, LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Producto
    template_name = 'productos/producto_detalle.html' # Necesitarás crear esta plantilla
    context_object_name = 'producto'

    permission_required = 'productos.view_producto' # PERMISO REQUERIDO
    login_url = reverse_lazy('core:acceso_denegado')

    def get_queryset(self):
        # Ver nota en ProductoListView: nunca saltarse el filtro de empresa.
        return Producto.objects.filter(empresa=self.request.tenant)

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para ver el detalle de este producto.")
        return redirect(self.login_url) # O quizás a la lista de productos

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f"Detalle: {self.object.nombre} ({self.object.referencia})"
        return context

# Opcional: Vista de Eliminación (si la necesitas)
class ProductoDeleteView(TenantAwareMixin, LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, DeleteView):
    model = Producto
    template_name = 'productos/producto_confirm_delete.html' # Necesitarás crear esta plantilla
    success_url = reverse_lazy('productos:producto_listado')
    success_message = "Producto (Variante) eliminado exitosamente."

    permission_required = 'productos.delete_producto' # PERMISO REQUERIDO
    login_url = reverse_lazy('core:acceso_denegado')

    def get_queryset(self):
        # Ver nota en ProductoListView: nunca saltarse el filtro de empresa.
        return Producto.objects.filter(empresa=self.request.tenant)

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para eliminar productos.")
        return redirect(self.login_url)

    def form_valid(self, form):
         messages.success(self.request, self.success_message)
         return super().form_valid(form)


@login_required
@permission_required('productos.add_producto', login_url=reverse_lazy('core:acceso_denegado'))
def producto_import_view(request):    
       
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')    
    
    if request.method == 'POST':
        form = ProductoImportForm(request.POST, request.FILES, empresa=empresa_actual)
        if form.is_valid():
            producto_resource = ProductoResource(empresa=empresa_actual)            
            dataset = Dataset()
            archivo_importado = request.FILES['archivo_productos']

            if archivo_importado.name.endswith('.csv'):
                try:
                    imported_data = archivo_importado.read().decode('utf-8')
                    dataset.load(imported_data, format='csv')
                except UnicodeDecodeError:
                    messages.error(request, "Error de codificación en archivo CSV. Asegúrate que sea UTF-8.")
                    return redirect('productos:producto_importar')
            elif archivo_importado.name.endswith(('.xls', '.xlsx')):
                dataset.load(archivo_importado.read(), format='xlsx' if archivo_importado.name.endswith('.xlsx') else 'xls')
            else:
                messages.error(request, "Formato de archivo no soportado. Use .csv, .xls o .xlsx.")
                return redirect('productos:producto_importar')
            
            result = producto_resource.import_data(dataset, dry_run=False, raise_errors=False, use_transactions=True)

            if not result.has_errors() and not result.has_validation_errors():
                messages.success(request, "Productos importados exitosamente.")
            else:
                errores_str = []
                if result.has_validation_errors():
                    for invalid_row in result.invalid_rows:
                        # Acceder a error.error_dict si existe, o error directamente
                        error_detail = invalid_row.error_dict if hasattr(invalid_row.error, 'error_dict') else str(invalid_row.error)
                        errores_str.append(f"Fila {invalid_row.number}: {error_detail}")
                if result.has_errors():
                    for error_row in result.row_errors():
                        for error_obj in error_row[1]: # error_row[1] es una lista de objetos Error
                            errores_str.append(f"Fila {error_row[0]}: {error_obj.error} - {str(error_obj.traceback)[:200]}...")
                
                if errores_str:
                     messages.error(request, f"Errores durante la importación: {'; '.join(errores_str[:5])}")
                else:
                    messages.warning(request, "Algunas filas no se importaron o tuvieron advertencias. Revisa los datos y el archivo.")
            
            return redirect('productos:producto_listado')
    else:
        form = ProductoImportForm()
    
    context = {
        'form': form,
        'titulo_pagina': "Importar Productos desde Archivo",
    }
    return render(request, 'productos/producto_import_form.html', context)

@login_required
def producto_export_view(request, file_format='xlsx'):
    if not request.user.has_perm('productos.view_producto'):
        messages.error(request, "No tienes permiso para exportar productos.")
        return redirect(reverse_lazy('core:acceso_denegado')) # O a donde prefieras
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        return HttpResponse("Acceso no válido.", status=403)
    
    queryset = Producto.objects.filter(empresa=empresa_actual)
    
    producto_resource = ProductoResource(empresa=empresa_actual)
    dataset = producto_resource.export(queryset)
    
    if file_format.lower() == 'csv':
        response_content = dataset.csv
        content_type = 'text/csv'
        filename = 'productos_export.csv'
    elif file_format.lower() == 'xls':
        response_content = dataset.xls
        content_type = 'application/vnd.ms-excel'
        filename = 'productos_export.xls'
    else: 
        file_format = 'xlsx' 
        response_content = dataset.xlsx
        content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        filename = 'productos_export.xlsx'

    response = HttpResponse(response_content, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@permission_required('productos.upload_fotos_producto', login_url=reverse_lazy('core:acceso_denegado'))
def subir_fotos_agrupadas_view(request):
    """
    Lista todas las Referencia+Color de la empresa, una fila por cada una,
    con sus fotos en miniatura al final de la fila (o un aviso de que no
    tiene ninguna). Cada fila permite seleccionar imágenes y subirlas al
    instante (AJAX), y reordenar las miniaturas arrastrándolas con el mouse.
    """
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa desde el dominio.")
        return redirect('core:index')

    query = request.GET.get('q', '').strip()

    agrupaciones_qs = ReferenciaColor.objects.filter(empresa=empresa_actual).prefetch_related(
        Prefetch('fotos_agrupadas', queryset=FotoProducto.objects.order_by('orden'))
    )
    if query:
        agrupaciones_qs = agrupaciones_qs.filter(
            Q(referencia_base__icontains=query) | Q(color__icontains=query) | Q(nombre_display__icontains=query)
        )
    agrupaciones_qs = agrupaciones_qs.order_by('referencia_base', 'color')

    paginator = Paginator(agrupaciones_qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'titulo': f"Subir Fotos de Productos ({empresa_actual.nombre})",
        'page_obj': page_obj,
        'query': query,
    }
    return render(request, 'productos/subir_fotos_agrupadas.html', context)


@login_required
@permission_required('productos.upload_fotos_producto', login_url='core:acceso_denegado')
@require_POST
def subir_fotos_referencia_ajax(request, referencia_color_id):
    """Sube una o varias fotos para una Referencia+Color específica (AJAX)."""
    empresa_actual = getattr(request, 'tenant', None)
    referencia_color = get_object_or_404(ReferenciaColor, pk=referencia_color_id, empresa=empresa_actual)

    imagenes = request.FILES.getlist('imagenes')
    if not imagenes:
        return JsonResponse({'status': 'error', 'msg': 'No se recibió ninguna imagen.'}, status=400)

    orden_actual = referencia_color.fotos_agrupadas.aggregate(m=Max('orden'))['m']
    siguiente_orden = (orden_actual + 1) if orden_actual is not None else 0

    fotos_creadas = []
    for imagen_file in imagenes:
        foto = FotoProducto.objects.create(
            referencia_color=referencia_color,
            imagen=imagen_file,
            orden=siguiente_orden,
        )
        siguiente_orden += 1
        fotos_creadas.append({'id': foto.pk, 'url': foto.imagen.url, 'orden': foto.orden})

    return JsonResponse({'status': 'ok', 'fotos': fotos_creadas})


@login_required
@permission_required('productos.upload_fotos_producto', login_url='core:acceso_denegado')
@require_POST
def reordenar_fotos_ajax(request):
    """Recibe el nuevo orden (lista de IDs de FotoProducto) tras arrastrar las miniaturas."""
    empresa_actual = getattr(request, 'tenant', None)
    try:
        data = json.loads(request.body)
        referencia_color_id = data['referencia_color_id']
        orden_ids = data['orden']
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'status': 'error', 'msg': 'Datos inválidos.'}, status=400)

    referencia_color = get_object_or_404(ReferenciaColor, pk=referencia_color_id, empresa=empresa_actual)
    fotos = {f.pk: f for f in referencia_color.fotos_agrupadas.filter(pk__in=orden_ids)}

    if len(fotos) != len(orden_ids):
        return JsonResponse({'status': 'error', 'msg': 'Alguna foto no pertenece a esta referencia.'}, status=400)

    with transaction.atomic():
        for nuevo_orden, foto_id in enumerate(orden_ids):
            FotoProducto.objects.filter(pk=foto_id).update(orden=nuevo_orden)

    return JsonResponse({'status': 'ok'})


@login_required
@permission_required('productos.upload_fotos_producto', login_url='core:acceso_denegado')
@require_POST
def eliminar_foto_ajax(request, foto_id):
    """Elimina una foto puntual (AJAX)."""
    empresa_actual = getattr(request, 'tenant', None)
    foto = get_object_or_404(FotoProducto, pk=foto_id, referencia_color__empresa=empresa_actual)
    foto.delete()
    return JsonResponse({'status': 'ok'})


@login_required
@permission_required('productos.add_producto', login_url='core:acceso_denegado')
def crear_producto_multi_talla(request):
    """
    Crea un producto con una o varias tallas a la vez.
    Las tallas se eligen por checkbox (reales, ya usadas por el género elegido)
    y el código de barras EAN13 de cada variante se genera automáticamente.
    """
    empresa_actual = request.tenant

    if request.method == 'POST':
        base_form = ProductoBaseForm(request.POST, empresa=empresa_actual)

        # Recolectar y deduplicar las tallas marcadas, preservando el orden.
        # Se calcula fuera del is_valid() para poder re-marcar los checkboxes
        # si el formulario se vuelve a mostrar por errores en otro campo.
        tallas_limpias = []
        vistas = set()
        for talla_raw in request.POST.getlist('tallas'):
            try:
                talla_int = int(talla_raw)
            except (ValueError, TypeError):
                continue
            if talla_int not in vistas:
                vistas.add(talla_int)
                tallas_limpias.append(talla_int)

        if base_form.is_valid():
            datos_comunes = base_form.cleaned_data

            if not tallas_limpias:
                messages.warning(request, "Debes seleccionar al menos una talla.")
            else:
                try:
                    # TODO o NADA: si una variante falla, se revierten todas.
                    with transaction.atomic():
                        for talla in tallas_limpias:
                            Producto.objects.create(
                                empresa=empresa_actual,
                                referencia=datos_comunes['referencia'],
                                nombre=datos_comunes['nombre'],
                                descripcion=datos_comunes.get('descripcion'),
                                color=datos_comunes.get('color'),
                                genero=datos_comunes.get('genero'),
                                costo=datos_comunes.get('costo'),
                                precio_venta=datos_comunes.get('precio_venta'),
                                unidad_medida=datos_comunes.get('unidad_medida'),
                                ubicacion=datos_comunes.get('ubicacion'),
                                activo=datos_comunes.get('activo', True),
                                permitir_preventa=datos_comunes.get('permitir_preventa', False),
                                talla=talla,
                                codigo_barras=generar_codigo_ean13(empresa_actual),
                            )

                    messages.success(
                        request,
                        f"¡Se crearon {len(tallas_limpias)} variante(s) de producto exitosamente, "
                        "con código de barras EAN13 generado automáticamente!"
                    )
                    return redirect('productos:producto_listado')

                except IntegrityError:
                    # La transacción ya revirtió todo lo insertado.
                    messages.error(
                        request,
                        "Error: una de las variantes (misma referencia, talla y color) ya existe. "
                        "No se guardó ningún producto para evitar inconsistencias."
                    )
        # Si el formulario no es válido, se cae al render final con los errores.

    else:  # GET
        base_form = ProductoBaseForm(empresa=empresa_actual)
        tallas_limpias = []

    context = {
        'base_form': base_form,
        'titulo_pagina': "Crear Producto",
        'tallas_previas': tallas_limpias,
    }
    return render(request, 'productos/producto_multi_talla_form.html', context)