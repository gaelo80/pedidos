# productos/views.py
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView # Añadir DetailView si la necesitas
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin # Asumiendo que quieres proteger estas vistas
from django.contrib.auth.mixins import UserPassesTestMixin # Para permisos más específicos
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from django.shortcuts import redirect
from django.db.models import Q
from django.http import HttpResponse
from .models import Producto, FotoProducto 
from .forms import ProductoForm 
from django.contrib.auth.decorators import login_required, permission_required
from core.auth_utils import es_admin_sistema, es_diseno
from .forms import ProductoForm, ProductoImportForm
from .resources import ProductoResource
from tablib import Dataset
from .forms import SeleccionarAgrupacionParaFotosForm
from core.mixins import TenantAwareMixin
from django.contrib.auth.mixins import UserPassesTestMixin



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

class ProductoCreateView(TenantAwareMixin, LoginRequiredMixin, UserPassesTestMixin, PermissionRequiredMixin, SuccessMessageMixin, CreateView):
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

    def test_func(self):
        return self.request.user.is_superuser or es_diseno(self.request.user)

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
    """
    Gestiona la subida masiva de fotos, filtrando los artículos
    por la empresa identificada a través del dominio (request.tenant).
    """
    
    # 1. OBTENEMOS LA EMPRESA GRACIAS A NUESTRO MIDDLEWARE
    # getattr busca 'tenant' en request. Si no existe, devuelve None para evitar errores.
    empresa_actual = getattr(request, 'tenant', None)

    # Si por alguna razón no se identifica una empresa (ej. dominio no registrado),
    # no podemos continuar.
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa desde el dominio.")
        return redirect('core:index') # O a una página de error

    if request.method == 'POST':
        # 2. AL PROCESAR EL FORMULARIO, LE PASAMOS LA EMPRESA
        # para que pueda validar correctamente la selección del usuario.
        form = SeleccionarAgrupacionParaFotosForm(request.POST, request.FILES, empresa=empresa_actual)
        
        if form.is_valid():
            referencia_color_seleccionada = form.cleaned_data['articulo_color']
            descripcion_general = form.cleaned_data.get('descripcion_general', '')
            imagenes_subidas = request.FILES.getlist('imagenes') # 'imagenes' es el name del input en tu form.

            fotos_creadas_count = 0
            for imagen_file in imagenes_subidas:
                try:
                    # La lógica de creación se queda igual. El modelo se encargará del resto.
                    FotoProducto.objects.create(
                        referencia_color=referencia_color_seleccionada,
                        imagen=imagen_file,
                        descripcion_foto=descripcion_general
                    )
                    fotos_creadas_count += 1
                except Exception as e:
                    messages.error(request, f"Error al guardar la imagen {imagen_file.name}: {e}")
            
            if fotos_creadas_count > 0:
                messages.success(request, f"¡{fotos_creadas_count} foto(s) subida(s) exitosamente para {referencia_color_seleccionada}!")
            
            return redirect('productos:producto_subir_fotos_agrupadas') # Asegúrate que el nombre de la URL sea correcto
    else: # Método GET (cuando se carga la página por primera vez)
        # 3. TAMBIÉN LE PASAMOS LA EMPRESA AL CREAR EL FORMULARIO VACÍO
        # Esto es lo que filtra el menú desplegable que ve el usuario.
        form = SeleccionarAgrupacionParaFotosForm(empresa=empresa_actual)

    context = {
        'form': form,
        'titulo': f"Subir Fotos para: {empresa_actual.nombre}", # Título personalizado
    }
    return render(request, 'productos/subir_fotos_agrupadas.html', context)