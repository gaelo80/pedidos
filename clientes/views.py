# clientes/views.py
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from rest_framework import viewsets, permissions
from .models import Ciudad, Cliente
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse
from .serializers import CiudadSerializer, ClienteSerializer
from .forms import ClienteForm, CiudadForm, CiudadImportForm, ClienteImportForm
from .resources import CiudadResource, ClienteResource
from tablib import Dataset
from django.db.models import Q
from core.auth_utils import es_administracion, es_cartera, es_factura, es_vendedor
from core.mixins import TenantAwareMixin




class CiudadViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ciudad.objects.all().order_by('nombre')
    serializer_class = CiudadSerializer
    permission_classes = [permissions.IsAdminUser]
    
class ClienteViewSet(TenantAwareMixin, viewsets.ModelViewSet):
    serializer_class = ClienteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        empresa_actual = getattr(self.request, 'tenant', None)
        if self.request.user.is_superuser:
            return Cliente.objects.all().order_by('nombre_completo')
        if empresa_actual:
            return Cliente.objects.filter(empresa=empresa_actual).order_by('nombre_completo')
        return Cliente.objects.none()

class ClienteListView(TenantAwareMixin, LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Cliente
    template_name = 'clientes/cliente_list.html'
    context_object_name = 'clientes' 
    paginate_by = 15

    def test_func(self):
        return es_administracion(self.request.user) or es_cartera(self.request.user) or es_factura(self.request.user)
    
    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para acceder al listado de clientes.")
        return redirect('core:index') 

    def get_queryset(self):
        empresa_actual = getattr(self.request, 'tenant', None)
        if self.request.user.is_superuser:
            base_qs = Cliente.objects.all()
        elif empresa_actual:
            base_qs = Cliente.objects.filter(empresa=empresa_actual)
        else:
            return Cliente.objects.none()

        queryset = base_qs.select_related('ciudad').order_by('nombre_completo')
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(nombre_completo__icontains=query) | 
                Q(identificacion__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Listado de Clientes"
        context['search_query'] = self.request.GET.get('q', '') 
        return context

class ClienteDetailView(TenantAwareMixin, LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Cliente
    template_name = 'clientes/cliente_detalle.html'
    context_object_name = 'cliente' 

    def test_func(self):
        return es_administracion(self.request.user) or es_cartera(self.request.user) or es_factura(self.request.user)
    
    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para ver los detalles de este cliente.")
        return redirect('clientes:cliente_listado')
    
    def get_queryset(self):
        empresa_actual = getattr(self.request, 'tenant', None)
        if self.request.user.is_superuser:
            return Cliente.objects.all()
        if empresa_actual:
            return Cliente.objects.filter(empresa=empresa_actual)
        return Cliente.objects.none()

class ClienteCreateView(TenantAwareMixin, LoginRequiredMixin, UserPassesTestMixin, SuccessMessageMixin, CreateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'clientes/cliente_form.html'
    success_url = reverse_lazy('clientes:cliente_listado')
    success_message = "¡Cliente '%(nombre_completo)s' creado exitosamente!"

    def test_func(self):
        return es_administracion(self.request.user) or es_cartera(self.request.user) or es_factura(self.request.user)

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para crear clientes.")
        return redirect('clientes:cliente_listado')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['empresa'] = getattr(self.request, 'tenant', None)
        return kwargs
    
    def form_valid(self, form):
        form.instance.empresa = getattr(self.request, 'tenant', None)
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Registrar Nuevo Cliente"
        context['nombre_boton'] = "Guardar Cliente"
        return context

class ClienteUpdateView(TenantAwareMixin, LoginRequiredMixin, UserPassesTestMixin, SuccessMessageMixin, UpdateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'clientes/cliente_form.html'
    success_url = reverse_lazy('clientes:cliente_listado')
    success_message = "Cliente '%(nombre_completo)s' actualizado exitosamente."

    def test_func(self):
        return es_administracion(self.request.user) or es_cartera(self.request.user) or es_factura(self.request.user)

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para editar este cliente.")
        return redirect('clientes:cliente_listado')

    def get_queryset(self):
        empresa_actual = getattr(self.request, 'tenant', None)
        if self.request.user.is_superuser:
            return Cliente.objects.all()
        if empresa_actual:
            return Cliente.objects.filter(empresa=empresa_actual)
        return Cliente.objects.none()
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['empresa'] = getattr(self.request, 'tenant', None)
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f"Editar Cliente: {self.object.nombre_completo}"
        context['nombre_boton'] = "Actualizar Cliente"
        return context

class ClienteDeleteView(TenantAwareMixin, LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Cliente
    template_name = 'clientes/cliente_confirm_delete.html'
    success_url = reverse_lazy('clientes:cliente_listado')
    
    def test_func(self):
        return es_administracion(self.request.user)

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para eliminar clientes.")
        return redirect('clientes:cliente_listado')

    def get_queryset(self):
        empresa_actual = getattr(self.request, 'tenant', None)
        if self.request.user.is_superuser:
            return Cliente.objects.all()
        if empresa_actual:
            return Cliente.objects.filter(empresa=empresa_actual)
        return Cliente.objects.none()

    def form_valid(self, form):
        messages.success(self.request, f"Cliente '{self.object.nombre_completo}' eliminado exitosamente.")
        return super().form_valid(form)
    
#********************************************************************************
# --- Vistas para Ciudad (Modelo Global) ---
#********************************************************************************

class CiudadListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Ciudad
    template_name = 'clientes/ciudad_list.html'
    context_object_name = 'ciudades'
    paginate_by = 20

    def test_func(self):
        return es_administracion(self.request.user)

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para ver el listado de ciudades.")
        return redirect('core:index')

class CiudadCreateView(LoginRequiredMixin, UserPassesTestMixin, SuccessMessageMixin, CreateView):
    model = Ciudad
    form_class = CiudadForm
    template_name = 'clientes/ciudad_form.html'
    success_url = reverse_lazy('clientes:ciudad_listado')
    success_message = "¡Ciudad '%(nombre)s' creada exitosamente!"

    def test_func(self):
        return es_administracion(self.request.user)

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para crear ciudades.")
        return redirect('clientes:ciudad_listado')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Registrar Nueva Ciudad"
        context['nombre_boton'] = "Guardar Ciudad"
        return context

class CiudadUpdateView(LoginRequiredMixin, UserPassesTestMixin, SuccessMessageMixin, UpdateView):
    model = Ciudad
    form_class = CiudadForm
    template_name = 'clientes/ciudad_form.html'
    success_url = reverse_lazy('clientes:ciudad_listado')
    success_message = "Ciudad '%(nombre)s' actualizada exitosamente."

    def test_func(self):
        return es_administracion(self.request.user)

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para editar esta ciudad.")
        return redirect('clientes:ciudad_listado')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f"Editar Ciudad: {self.object.nombre}"
        context['nombre_boton'] = "Actualizar Cliente"
        return context

class CiudadDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Ciudad
    template_name = 'clientes/ciudad_confirm_delete.html'
    success_url = reverse_lazy('clientes:ciudad_listado')

    def test_func(self):
        return es_administracion(self.request.user)

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para eliminar ciudades.")
        return redirect('clientes:ciudad_listado')

    def form_valid(self, form):     
        if self.object.clientes.exists():
            messages.error(self.request, f"No se puede eliminar la ciudad '{self.object.nombre}' porque está asignada a uno o más clientes.")
            return redirect('clientes:ciudad_listado')
        messages.success(self.request, f"Ciudad '{self.object.nombre}' eliminada exitosamente.")
        return super().form_valid(form)

#********************************************************************************
# --- Vistas para Import/Export y V2 (CÓDIGO RESTAURADO) ---
#********************************************************************************

@login_required
@user_passes_test(es_administracion)
def ciudad_import_view(request):
    if request.method == 'POST':
        form = CiudadImportForm(request.POST, request.FILES)
        if form.is_valid():
            ciudad_resource = CiudadResource()
            dataset = Dataset()
            archivo_importado = request.FILES['archivo_ciudades']

            if archivo_importado.name.endswith('.csv'):
                dataset.load(archivo_importado.read().decode('utf-8'), format='csv')
            elif archivo_importado.name.endswith(('.xls', '.xlsx')):
                dataset.load(archivo_importado.read(), format='xlsx' if archivo_importado.name.endswith('.xlsx') else 'xls')
            else:
                messages.error(request, "Formato de archivo no soportado. Use .csv, .xls o .xlsx.")
                return redirect('clientes:ciudad_importar')

            result = ciudad_resource.import_data(dataset, dry_run=False, raise_errors=False, use_transactions=True)

            if not result.has_errors() and not result.has_validation_errors():
                messages.success(request, "Ciudades importadas exitosamente.")
            else:
                errores_str = []
                if result.has_validation_errors():
                    for invalid_row in result.invalid_rows:
                        errores_str.append(f"Fila {invalid_row.number}: {invalid_row.error_dict}")
                if result.has_errors():
                    for error_row in result.row_errors():
                        for error in error_row[1]:
                            errores_str.append(f"Fila {error_row[0]}: {error.error} - {error.traceback}")
                if errores_str:
                    messages.error(request, f"Errores durante la importación: {'; '.join(errores_str[:5])}")
                else:
                    messages.warning(request, "Algunas filas no se importaron o tuvieron advertencias.")
            
            return redirect('clientes:ciudad_listado')
    else:
        form = CiudadImportForm()
    
    context = {
        'form': form,
        'titulo_pagina': "Importar Ciudades desde Archivo",
        'app_name': 'Clientes'
    }
    return render(request, 'clientes/ciudad_import.html', context)

@login_required
@user_passes_test(es_administracion)
def ciudad_export_view(request, file_format='xlsx'):
    ciudad_resource = CiudadResource()
    dataset = ciudad_resource.export()
    
    if file_format == 'csv':
        response_content = dataset.csv
        content_type = 'text/csv'
        filename = 'ciudades_export.csv'
    elif file_format == 'xls':
        response_content = dataset.xls
        content_type = 'application/vnd.ms-excel'
        filename = 'ciudades_export.xls'
    else: # xlsx
        response_content = dataset.xlsx
        content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        filename = 'ciudades_export.xlsx'

    response = HttpResponse(response_content, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

class ClienteListV2View(TenantAwareMixin, LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Cliente
    template_name = 'clientes/v2/cliente_list_v2.html'
    context_object_name = 'clientes'
    paginate_by = 20

    def test_func(self):
        return (
            es_administracion(self.request.user) or 
            es_cartera(self.request.user) or            
            es_vendedor(self.request.user) or 
            es_factura(self.request.user) or
            self.request.user.is_superuser
        )

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para acceder a este listado de clientes.")
        return redirect('core:index')

    def get_queryset(self):
        empresa_actual = getattr(self.request, 'tenant', None)
        if self.request.user.is_superuser:
            base_qs = Cliente.objects.all()
        elif empresa_actual:
            base_qs = Cliente.objects.filter(empresa=empresa_actual)
        else:
            return Cliente.objects.none()

        queryset = base_qs.select_related('ciudad').order_by('nombre_completo')
        query = self.request.GET.get('q_v2')
        if query:
            queryset = queryset.filter(
                Q(nombre_completo__icontains=query) |
                Q(identificacion__icontains=query) |
                Q(ciudad__nombre__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Listado de Clientes"
        context['search_query_v2'] = self.request.GET.get('q_v2', '')
        return context

class ClienteDetailV2View(TenantAwareMixin, LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Cliente
    template_name = 'clientes/v2/cliente_detalle_v2.html'
    context_object_name = 'cliente'
    
    def test_func(self):
        return (
            es_administracion(self.request.user) or 
            es_cartera(self.request.user) or            
            es_vendedor(self.request.user) or 
            es_factura(self.request.user) or
            self.request.user.is_superuser
        )

    def get_queryset(self):
        empresa_actual = getattr(self.request, 'tenant', None)
        if self.request.user.is_superuser:
            return Cliente.objects.all()
        if empresa_actual:
            return Cliente.objects.filter(empresa=empresa_actual)
        return Cliente.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if context.get('cliente'):
            print(f"Nombre del cliente: {context.get('cliente').nombre_completo}")
        return context
    
    
    
    
@login_required
@user_passes_test(es_administracion)
def cliente_export_view(request, file_format='xlsx'):
    """
    Gestiona la exportación de clientes a diferentes formatos de archivo.
    """
    cliente_resource = ClienteResource()
    cliente_resource.request = request 
    dataset = cliente_resource.export()

    # Asigna el formato de archivo y el tipo de contenido correcto
    if file_format == 'csv':
        response_content = dataset.csv
        content_type = 'text/csv'
        filename = 'clientes_export.csv'
    elif file_format == 'xls':
        response_content = dataset.xls
        content_type = 'application/vnd.ms-excel'
        filename = 'clientes_export.xls'
    else: 
        file_format = 'xlsx'
        response_content = dataset.xlsx
        content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        filename = 'clientes_export.xlsx'

    # Crea la respuesta HTTP para la descarga del archivo
    response = HttpResponse(response_content, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response

@login_required
@user_passes_test(es_administracion)
def cliente_import_view(request):
    if request.method == 'POST':
        form = ClienteImportForm(request.POST, request.FILES)
        if form.is_valid():
            cliente_resource = ClienteResource()
            dataset = Dataset()
            archivo_importado = request.FILES['archivo_clientes']

            # Lógica para leer el archivo
            if archivo_importado.name.endswith('.csv'):
                dataset.load(archivo_importado.read().decode('utf-8'), format='csv')
            elif archivo_importado.name.endswith(('.xls', '.xlsx')):
                dataset.load(archivo_importado.read())
            else:
                messages.error(request, "Formato de archivo no soportado. Use .csv, .xls o .xlsx.")
                return redirect('clientes:cliente_importar')

            try:
                # Importar los datos. Usamos raise_errors=True para capturar excepciones
                result = cliente_resource.import_data(dataset, dry_run=False, raise_errors=True, use_transactions=True)
                messages.success(request, "Importación de clientes finalizada con éxito.")

            except Exception as e:
                # Capturar y mostrar errores específicos durante la importación
                # Esto te dirá si un ID de ciudad o empresa no existe, por ejemplo.
                messages.error(request, f"Error durante la importación: {e}")
            
            return redirect('clientes:cliente_listado')
    else:
        form = ClienteImportForm()
    
    context = {
        'form': form,
        'titulo_pagina': "Importar Clientes"
    }
    # Puedes crear una plantilla 'cliente_import.html' o reutilizar la de ciudades
    return render(request, 'clientes/cliente_import.html', context)