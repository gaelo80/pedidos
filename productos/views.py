# productos/views.py
from django.shortcuts import render, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView # Añadir DetailView si la necesitas
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin # Asumiendo que quieres proteger estas vistas
from django.contrib.auth.mixins import UserPassesTestMixin # Para permisos más específicos
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from django.shortcuts import redirect
from django.db.models import Q
from django.http import HttpResponse
from .models import Producto, FotoProducto, ReferenciaColor 
from .forms import ProductoForm 
from django.contrib.auth.decorators import login_required, permission_required
from core.auth_utils import es_administracion, es_diseno
from .forms import ProductoForm, ProductoImportForm
from .resources import ProductoResource
from tablib import Dataset
from .forms import SeleccionarAgrupacionParaFotosForm, FotoProductoFormSet
from core.mixins import TenantAwareMixin
from django.contrib.auth.mixins import UserPassesTestMixin
import logging
from django.forms import formset_factory
from .forms import ProductoBaseForm, ProductoTallaForm
from django.db import transaction, IntegrityError


logger = logging.getLogger(__name__)



class ProductoListView(TenantAwareMixin, LoginRequiredMixin, PermissionRequiredMixin, ListView):
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

        queryset = super().get_queryset().order_by('referencia', 'nombre', 'color', 'talla')
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(referencia__icontains=query) |
                Q(nombre__icontains=query) |
                Q(talla__icontains=query) |
                Q(color__icontains=query) |
                Q(codigo_barras__icontains=query)
            ).distinct()
        # RECOMENDACIÓN: Retornar el queryset modificado, no llamar a super() de nuevo.
        return queryset

    def get_context_data(self, **kwargs):        
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Listado de Productos (Variantes)"
        context['search_query'] = self.request.GET.get('q', '')        
        return context

class ProductoCreateView(TenantAwareMixin, LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    model = Producto
    form_class = ProductoForm
    template_name = 'productos/producto_form.html' # Usa la plantilla que diseñamos
    success_url = reverse_lazy('productos:producto_listado') # Redirige a la lista después de crear
    success_message = "Producto (Variante) '%(referencia)s - %(nombre)s' creado exitosamente."
   
    
    permission_required = 'productos.add_producto'
    login_url = reverse_lazy('core:acceso_denegado')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['empresa'] = self.request.tenant
        return kwargs

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para crear nuevos productos.")
        return redirect(self.login_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_form'] = "Registrar Nuevo Producto"
        context['nombre_boton'] = "Guardar Producto"        
        return context



class ProductoUpdateView(TenantAwareMixin, LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Producto
    form_class = ProductoForm
    template_name = 'productos/producto_form.html' # Reutiliza la misma plantilla de formulario
    success_url = reverse_lazy('productos:producto_listado')
    success_message = "Producto (Variante) '%(referencia)s - %(nombre)s' actualizado exitosamente."
    # permission_classes = [IsAuthenticated]
    permission_required = 'productos.change_producto' # PERMISO REQUERIDO
    login_url = reverse_lazy('core:acceso_denegado')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['empresa'] = self.request.tenant
        return kwargs

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para modificar productos.")
        return redirect(self.login_url)


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_form'] = f"Editar Producto: {self.object.nombre} ({self.object.referencia})"
        context['nombre_boton'] = "Actualizar Producto"
        return context
    
    def test_func(self):
        return self.request.user.is_superuser or es_diseno(self.request.user)


class ProductoDetailView(TenantAwareMixin, LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Producto
    template_name = 'productos/producto_detalle.html' # Necesitarás crear esta plantilla
    context_object_name = 'producto'
    
    permission_required = 'productos.view_producto' # PERMISO REQUERIDO
    login_url = reverse_lazy('core:acceso_denegado')

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

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para eliminar productos.")
        return redirect(self.login_url)

    def form_valid(self, form):
         # SuccessMessageMixin no funciona bien con DeleteView sin este truco
         # o sobreescribiendo el método delete()
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
    empresa_actual = getattr(request, 'tenant', None)

    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa desde el dominio.")
        return redirect('core:index')

    fotos_existentes = []
    formset_instance = None
    agrupacion_id_preseleccionada = request.GET.get('agrupacion_id', None)

    url_to_redirect_base = reverse('productos:producto_subir_fotos_agrupadas')

    if request.method == 'POST':
        logger.debug("Procesando petición POST.")
        form = SeleccionarAgrupacionParaFotosForm(request.POST, request.FILES, empresa=empresa_actual)

        referencia_color_seleccionada = None
        # Primero, intenta validar el formulario principal para obtener la agrupación
        if form.is_valid():
            referencia_color_seleccionada = form.cleaned_data['articulo_color']
            logger.debug(f"Formulario principal es válido. Agrupación seleccionada: {referencia_color_seleccionada}")
        else:
            logger.debug(f"Formulario principal NO es válido. Errores: {form.errors.as_json()}")
            # Si el formulario principal no es válido, intentamos cargar la agrupación
            # desde el POST para que el formset tenga una instancia válida si es posible.
            agrupacion_id_from_post = request.POST.get('articulo_color')
            if agrupacion_id_from_post:
                try:
                    referencia_color_seleccionada = ReferenciaColor.objects.get(
                        pk=agrupacion_id_from_post, empresa=empresa_actual
                    )
                    logger.debug(f"Agrupación recuperada del POST para el formset: {referencia_color_seleccionada}")
                except ReferenciaColor.DoesNotExist:
                    logger.warning(f"Agrupación ID {agrupacion_id_from_post} del POST no encontrada.")
                    pass

        # Inicializar el formset con o sin instancia, dependiendo de si se encontró una agrupación
        if referencia_color_seleccionada:
            formset_instance = FotoProductoFormSet(request.POST, request.FILES, instance=referencia_color_seleccionada, prefix='fotos')
            logger.debug("Formset inicializado con instancia de ReferenciaColor.")
        else:
            # Si no hay agrupación seleccionada o el formulario principal tiene errores
            # creamos un formset vacío pero con los datos del POST para que valide
            formset_instance = FotoProductoFormSet(request.POST, request.FILES, prefix='fotos')
            logger.debug("Formset inicializado sin instancia de ReferenciaColor.")

        # Validar ambos, pero la lógica de subida de nuevas fotos será condicional
        if form.is_valid() and formset_instance.is_valid():
            logger.debug("Formulario principal y Formset son VÁLIDOS. Procediendo a guardar.")

            # IMPORTANT: Re-confirmar la agrupación seleccionada si el formulario principal es válido
            # Esto es redundante si ya se hizo arriba, pero asegura que `referencia_color_seleccionada`
            # sea la instancia válida final para el guardado.
            referencia_color_seleccionada = form.cleaned_data['articulo_color']
            descripcion_general = form.cleaned_data.get('descripcion_general', '')
            imagenes_subidas = request.FILES.getlist('imagenes')

            fotos_creadas_count = 0
            # SOLO PROCESAR NUEVAS IMÁGENES SI REALMENTE HAY ARCHIVOS SUBIDOS
            if imagenes_subidas: # <--- CAMBIO CLAVE AQUI
                for imagen_file in imagenes_subidas:
                    try:
                        FotoProducto.objects.create(
                            referencia_color=referencia_color_seleccionada,
                            imagen=imagen_file,
                            descripcion_foto=descripcion_general
                        )
                        fotos_creadas_count += 1
                    except Exception as e:
                        messages.error(request, f"Error al guardar la imagen {imagen_file.name}: {e}")
            else:
                logger.debug("No se detectaron nuevas imágenes para subir.")

            # Guardar cambios del formset (actualizar/eliminar fotos existentes)
            try:
                formset_instance.save()
                if formset_instance.deleted_objects:
                    messages.success(request, f"Se eliminaron {len(formset_instance.deleted_objects)} fotos existentes.")

                # Mensaje para nuevas fotos, solo si se subieron
                if fotos_creadas_count > 0:
                    messages.success(request, f"¡{fotos_creadas_count} foto(s) subida(s) exitosamente para {referencia_color_seleccionada}!")
                elif not formset_instance.deleted_objects and not formset_instance.changed_objects:
                    # Si no se subieron nuevas fotos y no se eliminaron/cambiaron existentes
                    messages.info(request, "No se realizaron cambios en las fotos.")
                else:
                    messages.info(request, "Se guardaron los cambios en las fotos existentes.") # Mensaje más general si hubo cambios en existentes

            except Exception as e:
                messages.error(request, f"Error al actualizar/eliminar fotos existentes: {e}")
                # Si hay un error al guardar el formset, volvemos a renderizar con los errores
                context = {
                    'form': form,
                    'formset': formset_instance,
                    'titulo': f"Subir Fotos para: {empresa_actual.nombre}",
                    'fotos_existentes': referencia_color_seleccionada.fotos_agrupadas.all() if referencia_color_seleccionada else [],
                    'agrupacion_seleccionada_id': referencia_color_seleccionada.pk if referencia_color_seleccionada else None,
                }
                return render(request, 'productos/subir_fotos_agrupadas.html', context)

            # Si todo fue bien, redirigimos
            return redirect(f"{url_to_redirect_base}?agrupacion_id={referencia_color_seleccionada.pk}")

        else: # Formulario principal o formset no válidos
            logger.warning(f"Validación fallida. Errores del Formulario: {form.errors.as_json()}. Errores del Formset: {formset_instance.errors if formset_instance else 'No instanciado'}")
            # Aseguramos que el formset se re-instancie correctamente para mostrar errores
            if referencia_color_seleccionada and not formset_instance:
                formset_instance = FotoProductoFormSet(request.POST, request.FILES, instance=referencia_color_seleccionada, prefix='fotos')
            elif not referencia_color_seleccionada and not formset_instance:
                formset_instance = FotoProductoFormSet(request.POST, request.FILES, prefix='fotos')
            messages.error(request, "Por favor corrige los errores en el formulario.")

    else: # Método GET
        form = SeleccionarAgrupacionParaFotosForm(empresa=empresa_actual)

        if agrupacion_id_preseleccionada:
            try:
                referencia_color_instance = ReferenciaColor.objects.get(
                    pk=agrupacion_id_preseleccionada, empresa=empresa_actual
                )
                form.initial['articulo_color'] = referencia_color_instance
                formset_instance = FotoProductoFormSet(instance=referencia_color_instance, prefix='fotos')
                fotos_existentes = referencia_color_instance.fotos_agrupadas.all()
            except ReferenciaColor.DoesNotExist:
                messages.warning(request, "La agrupación de fotos seleccionada no existe o no pertenece a tu empresa.")
                formset_instance = FotoProductoFormSet(prefix='fotos')
        else:
            formset_instance = FotoProductoFormSet(prefix='fotos')

    context = {
        'form': form,
        'formset': formset_instance,
        'titulo': f"Subir Fotos para: {empresa_actual.nombre}",
        'fotos_existentes': fotos_existentes,
        'agrupacion_seleccionada_id': agrupacion_id_preseleccionada,
    }
    logger.debug("Renderizando plantilla con el contexto.")
    return render(request, 'productos/subir_fotos_agrupadas.html', context)

@login_required
@permission_required('productos.add_producto', login_url=reverse_lazy('core:acceso_denegado'))
@transaction.atomic # <--- 2. DECORADOR PARA TRANSACCIÓN ATÓMICA ("TODO O NADA")
def crear_producto_multi_talla(request):
    """
    Vista para crear un producto con múltiples tallas a la vez.
    Ahora con manejo de errores de duplicados y transacciones atómicas.
    """
    empresa_actual = request.tenant
    ProductoTallaFormSet = formset_factory(ProductoTallaForm, extra=6)

    if request.method == 'POST':
        base_form = ProductoBaseForm(request.POST)
        talla_formset = ProductoTallaFormSet(request.POST, prefix='tallas')

        if base_form.is_valid() and talla_formset.is_valid():
            
            # <--- 3. INICIA EL BLOQUE TRY...EXCEPT
            try:
                datos_comunes = base_form.cleaned_data
                productos_creados = 0

                for form in talla_formset:
                    if form.cleaned_data and form.cleaned_data.get('talla'):
                        talla_data = form.cleaned_data
                        
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
                            talla=talla_data.get('talla'),
                            codigo_barras=talla_data.get('codigo_barras')
                        )
                        productos_creados += 1
                
                if productos_creados > 0:
                    messages.success(request, f"¡Se crearon {productos_creados} variantes de producto exitosamente!")
                else:
                    messages.warning(request, "No se especificó ninguna talla, no se creó ningún producto.")
                
                return redirect('productos:producto_listado')

            except IntegrityError:
                # <--- 4. BLOQUE QUE MANEJA EL ERROR DE DUPLICADO
                messages.error(request, 
                    "Error: Uno de los productos que intentaste crear (con la misma referencia, talla y color) ya existe. No se ha guardado ningún producto para evitar inconsistencias."
                )
                # No necesitamos hacer nada más, la transacción atómica revierte los cambios.

    else: # Método GET
        base_form = ProductoBaseForm()
        talla_formset = ProductoTallaFormSet(prefix='tallas')

    context = {
        'base_form': base_form,
        'talla_formset': talla_formset,
        'titulo_pagina': "Crear Producto (Múltiples Tallas)",
    }
    return render(request, 'productos/producto_multi_talla_form.html', context)