# clientes/views.py
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin # Para permisos
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from rest_framework import viewsets
from .models import Ciudad, Cliente
from io import BytesIO
from rest_framework import permissions # 'serializers' base no se usa directamente aquí
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly # Importar permisos específicos
from rest_framework.authentication import SessionAuthentication # O la que uses (TokenAuthentication, etc)
from rest_framework.response import Response
from xhtml2pdf import pisa
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse_lazy
from django.http import HttpResponse
from .serializers import CiudadSerializer, ClienteSerializer
from .forms import ClienteForm, CiudadForm, CiudadImportForm # Importar nuevos formularios
from .resources import CiudadResource # Importar el resource
from tablib import Dataset # Para la importación
from django.db.models import Q
from core.auth_utils import es_admin_sistema, es_cartera,  es_factura

# --- Vistas para API (Existentes) ---
class CiudadViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ciudad.objects.all().order_by('nombre')
    serializer_class = CiudadSerializer
    
class ClienteViewSet(viewsets.ModelViewSet):
    queryset = Cliente.objects.all().order_by('nombre_completo')
    serializer_class = ClienteSerializer
    # permission_classes = [IsAuthenticated]


class ClienteListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Cliente
    template_name = 'clientes/cliente_list.html'
    context_object_name = 'clientes' 
    paginate_by = 15

    def test_func(self):
        """
        Define la condición que el usuario debe cumplir para acceder a la vista.
        """
        return es_admin_sistema, es_cartera(self.request.user) # Reutiliza tu función de prueba existente

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para acceder al listado de clientes.")
        return redirect('core:index') 

    def get_queryset(self):
        queryset = super().get_queryset().select_related('ciudad').order_by('nombre_completo')
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

class ClienteDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Cliente
    template_name = 'clientes/cliente_detalle.html' # Plantilla que usa esta vista
    context_object_name = 'cliente' # Nombre del objeto en el contexto de la plantilla

    def test_func(self):
        """
        Define la condición que el usuario debe cumplir para acceder a la vista.
        """
        return es_admin_sistema or es_cartera(self.request.user) # Usa tu función de permisos
    
    def handle_no_permission(self):
        """
        Qué hacer si test_func() devuelve False.
        """
        messages.error(self.request, "No tienes permiso para ver los detalles de este cliente.")
        return redirect('clientes:cliente_listado') # Redirige a la lista de clientes


class ClienteCreateView(LoginRequiredMixin, UserPassesTestMixin, SuccessMessageMixin, CreateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'clientes/cliente_form.html'
    success_url = reverse_lazy('clientes:cliente_listado')
    success_message = "¡Cliente '%(nombre_completo)s' creado exitosamente!"

    def test_func(self):
        return self.request.user.is_staff or self.request.user.groups.filter(name__in=['Administracion', 'Ventas', 'Administrador Aplicacion']).exists()

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para crear clientes.")
        return redirect('clientes:cliente_listado')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Registrar Nuevo Cliente"
        context['nombre_boton'] = "Guardar Cliente"
        return context

class ClienteUpdateView(LoginRequiredMixin, UserPassesTestMixin, SuccessMessageMixin, UpdateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'clientes/cliente_form.html' # Reutiliza la misma plantilla de formulario
    success_url = reverse_lazy('clientes:cliente_listado')
    success_message = "Cliente '%(nombre_completo)s' actualizado exitosamente."

    def test_func(self):
        return es_admin_sistema or es_cartera or es_factura(self.request.user)

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para editar este cliente.")
        return redirect('clientes:cliente_listado')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f"Editar Cliente: {self.object.nombre_completo}"
        context['nombre_boton'] = "Actualizar Cliente"
        return context

class ClienteDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView): # SuccessMessageMixin no funciona bien con DeleteView sin sobreescribir delete()
    model = Cliente
    template_name = 'clientes/cliente_confirm_delete.html'
    success_url = reverse_lazy('clientes:cliente_listado')
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.groups.filter(name__in=['Administracion', 'Administrador Aplicacion']).exists()

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para eliminar clientes.")
        return redirect('clientes:cliente_listado')

    def form_valid(self, form):
        messages.success(self.request, f"Cliente '{self.object.nombre_completo}' eliminado exitosamente.")
        return super().form_valid(form)

# --- Vistas CRUD para Ciudad (Nuevas) ---

class CiudadListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Ciudad
    template_name = 'clientes/ciudad_list.html'
    context_object_name = 'ciudades'
    paginate_by = 20

    def test_func(self):
        return es_admin_sistema(self.request.user) # O un permiso más específico

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para ver el listado de ciudades.")
        return redirect('core:index') # Ajusta

class CiudadCreateView(LoginRequiredMixin, UserPassesTestMixin, SuccessMessageMixin, CreateView):
    model = Ciudad
    form_class = CiudadForm
    template_name = 'clientes/ciudad_form.html'
    success_url = reverse_lazy('clientes:ciudad_listado')
    success_message = "¡Ciudad '%(nombre)s' creada exitosamente!"

    def test_func(self):
        return es_admin_sistema(self.request.user) # Solo admin puede crear ciudades

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
        return es_admin_sistema(self.request.user)

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para editar esta ciudad.")
        return redirect('clientes:ciudad_listado')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f"Editar Ciudad: {self.object.nombre}"
        context['nombre_boton'] = "Actualizar Ciudad"
        return context

class CiudadDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Ciudad
    template_name = 'clientes/ciudad_confirm_delete.html'
    success_url = reverse_lazy('clientes:ciudad_listado')

    def test_func(self):
        return es_admin_sistema(self.request.user)

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para eliminar ciudades.")
        return redirect('clientes:ciudad_listado')

    def form_valid(self, form):
        # Verificar si la ciudad está siendo usada por algún cliente
        if self.object.clientes.exists(): # 'clientes' es el related_name en Cliente.ciudad
            messages.error(self.request, f"No se puede eliminar la ciudad '{self.object.nombre}' porque está asignada a uno o más clientes.")
            return redirect('clientes:ciudad_listado')
        messages.success(self.request, f"Ciudad '{self.object.nombre}' eliminada exitosamente.")
        return super().form_valid(form)

# --- Vistas para Importar/Exportar Ciudades (Nuevas) ---

@login_required
@user_passes_test(es_admin_sistema)
def ciudad_import_view(request):
    if request.method == 'POST':
        form = CiudadImportForm(request.POST, request.FILES)
        if form.is_valid():
            ciudad_resource = CiudadResource()
            dataset = Dataset()
            archivo_importado = request.FILES['archivo_ciudades']

            # Determinar formato y cargar datos
            if archivo_importado.name.endswith('.csv'):
                dataset.load(archivo_importado.read().decode('utf-8'), format='csv')
            elif archivo_importado.name.endswith(('.xls', '.xlsx')):
                # Para excel, import_data espera bytes
                dataset.load(archivo_importado.read(), format='xlsx' if archivo_importado.name.endswith('.xlsx') else 'xls')
            else:
                messages.error(request, "Formato de archivo no soportado. Use .csv, .xls o .xlsx.")
                return redirect('clientes:ciudad_importar')

            # Realizar la importación (dry_run=True para probar sin guardar)
            # result = ciudad_resource.import_data(dataset, dry_run=True, raise_errors=True)
            result = ciudad_resource.import_data(dataset, dry_run=False, raise_errors=False, use_transactions=True)


            if not result.has_errors() and not result.has_validation_errors():
                messages.success(request, "Ciudades importadas exitosamente.")
            else:
                # Construir mensajes de error más detallados
                # (Esto es un ejemplo, puedes personalizarlo mucho más)
                errores_str = []
                if result.has_validation_errors():
                    for invalid_row in result.invalid_rows:
                        errores_str.append(f"Fila {invalid_row.number}: {invalid_row.error_dict}")
                if result.has_errors():
                    for error_row in result.row_errors():
                         # error_row es una tupla (row_number, list_of_errors)
                        for error in error_row[1]:
                            errores_str.append(f"Fila {error_row[0]}: {error.error} - {error.traceback}")

                if errores_str:
                     messages.error(request, f"Errores durante la importación: {'; '.join(errores_str[:5])}") # Muestra los primeros 5
                else:
                    messages.warning(request, "Algunas filas no se importaron o tuvieron advertencias. Revisa los datos.")
            
            return redirect('clientes:ciudad_listado')
    else:
        form = CiudadImportForm()
    
    context = {
        'form': form,
        'titulo_pagina': "Importar Ciudades desde Archivo",
        'app_name': 'Clientes' # Para la plantilla base si es necesario
    }
    return render(request, 'clientes/ciudad_import.html', context)

@login_required
@user_passes_test(es_admin_sistema)
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
    else: # Default to xlsx
        response_content = dataset.xlsx
        content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        filename = 'ciudades_export.xlsx'

    response = HttpResponse(response_content, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

class ClienteListV2View(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Cliente
    template_name = 'clientes/v2/cliente_list_v2.html'
    context_object_name = 'clientes'
    paginate_by = 20

    def test_func(self):
        """
        Aquí defines la lógica para determinar si el usuario tiene permiso.
        Debe devolver True si el usuario tiene permiso, False en caso contrario.
        """
        user = self.request.user

        # EJEMPLO 1: Permitir solo a superusuarios
        # if user.is_superuser:
        #     return True

        # EJEMPLO 2: Permitir a usuarios de ciertos grupos (asegúrate que estos grupos existan)
        # if user.groups.filter(name__in=['Administracion', 'VentasV2']).exists():
        #     return True
        
        # EJEMPLO 3: Usar tus funciones de utilidad de core.auth_utils
        # if es_admin_sistema(user) or es_cartera(user): # Adapta a los permisos que necesites para esta V2
        #    return True

        # IMPORTANTE: Debes poner aquí la lógica de permisos que realmente quieres
        # para esta vista V2. Si no estás seguro, empieza permitiendo a todos los autenticados
        # y luego restringe más si es necesario:
        if user.is_authenticated: # Por ahora, permite a cualquier usuario autenticado
            return True
        
        return False # Denegar por defecto si ninguna condición se cumple

    def handle_no_permission(self):
        """
        Define qué hacer si test_func() devuelve False.
        """
        messages.error(self.request, "No tienes permiso para acceder a este listado de clientes.")
        # Redirige a una página apropiada, por ejemplo, el inicio o la página de login
        return redirect('core:index') # Asegúrate que 'core:index' exista o cambia a otra URL

    def get_queryset(self):
        queryset = super().get_queryset().select_related('ciudad').order_by('nombre_completo')
        query = self.request.GET.get('q_v2') # Usar un parámetro de búsqueda diferente
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

class ClienteDetailV2View(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Cliente
    template_name = 'clientes/v2/cliente_detalle_v2.html'
    context_object_name = 'cliente' # O el que uses
    
    def test_func(self):
        """
        Define aquí quién tiene permiso para ver el detalle del cliente.
        Devuelve True si tiene permiso, False si no.
        """
        user = self.request.user

        # EJEMPLO: Permitir si el usuario está autenticado.
        # Adapta esta lógica a tus necesidades reales.
        if user.is_authenticated:
            return True
        
        # EJEMPLO MÁS ESPECÍFICO:
        # if user.is_superuser or user.groups.filter(name='VentasV2').exists():
        #     return True
        #
        # if es_admin_sistema(user) or es_cartera(user): # Usando tus funciones
        #     return True

        return False # Denegar por defecto

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        print(f"Objeto para ClienteDetailV2View: {context.get('cliente')}") # Verifica el objeto
        if context.get('cliente'):
            print(f"Nombre del cliente: {context.get('cliente').nombre_completo}")
        # ...
        return context
