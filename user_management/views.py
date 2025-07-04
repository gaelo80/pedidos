from django.contrib.auth import get_user_model
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from .forms import CustomUserCreationForm, CustomUserChangeForm, AdminSetPasswordForm, GroupForm
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.contrib.auth.models import Group
from vendedores.models import Vendedor
from core.auth_utils import es_admin_sistema
from core.mixins import TenantAwareMixin

User = get_user_model()

class UserListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = User
    template_name = 'user_management/user_list.html' # Plantilla para listar usuarios
    context_object_name = 'users' # Nombre del contexto para la lista de usuarios
    permission_required = 'auth.view_user' # Permiso para ver usuarios    
    paginate_by = 20 # Puedes ajustar el número de usuarios por página
    
    def test_func(self):
        # SOLO LOS ADMINS DEL SISTEMA PUEDEN VER ESTA LISTA
        return es_admin_sistema(self.request.user)

    # AÑADIDO: PATRÓN DE MANEJO DE PERMISOS DE 'clientes'
    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para acceder a la gestión de usuarios.")
        return redirect('core:index') 

    def get_queryset(self):
        """MODIFICADO: APLICANDO EL PATRÓN EXACTO DE 'clientes/views.py'"""
        empresa_actual = getattr(self.request, 'tenant', None)
        if self.request.user.is_superuser:
            base_qs = User.objects.all()
        elif empresa_actual and es_admin_sistema(self.request.user):
            # AHORA USAMOS EL CAMPO 'empresa' DIRECTO EN EL MODELO User
            base_qs = User.objects.filter(empresa=empresa_actual)
        else:
            return User.objects.none()

        # AQUÍ PUEDES AÑADIR LÓGICA DE BÚSQUEDA SI LO NECESITAS
        return base_qs.select_related('empresa').order_by('username')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Listado de Usuarios'
        return context
    

class UserCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = User
    form_class = CustomUserCreationForm
    template_name = 'user_management/user_form.html'
    success_url = reverse_lazy('user_management:user_list') 
    permission_required = 'auth.add_user'
    success_message = "¡Usuario '%(username)s' creado exitosamente!"
    
    def test_func(self):
        return es_admin_sistema(self.request.user)

    # AÑADIDO: PATRÓN DE MANEJO DE PERMISOS
    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para crear usuarios.")
        return redirect('user_management:user_list')

    # AÑADIDO: MÉTODO PARA PASAR LA EMPRESA AL FORMULARIO
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['empresa'] = getattr(self.request, 'tenant', None)
        return kwargs

    def form_valid(self, form):
        """MODIFICADO: ASIGNAMOS LA EMPRESA ANTES DE GUARDAR"""
        if not self.request.user.is_superuser:
            form.instance.empresa = getattr(self.request, 'tenant', None)
        # La llamada a super().form_valid(form) ahora guarda el usuario con la empresa
        return super().form_valid(form)
    
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Crear Nuevo Usuario'
        context['nombre_boton'] = 'Crear Usuario'
        return context 
    
    
    
    
    
    
    
    
class UserUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = User
    form_class = CustomUserChangeForm
    template_name = 'user_management/user_form.html'
    success_url = reverse_lazy('user_management:user_list')
    permission_required = 'auth.change_user'
    success_message = "Usuario '%(username)s' actualizado exitosamente."
    
    def test_func(self):
        return es_admin_sistema(self.request.user)

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para editar usuarios.")
        return redirect('user_management:user_list')


    def get_queryset(self):
        """MODIFICADO: APLICANDO EL PATRÓN EXACTO DE 'clientes/views.py'"""
        empresa_actual = getattr(self.request, 'tenant', None)
        if self.request.user.is_superuser:
            return User.objects.all()
        if empresa_actual and es_admin_sistema(self.request.user):
            return User.objects.filter(empresa=empresa_actual)
        return User.objects.none()
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['empresa'] = getattr(self.request, 'tenant', None)
        return kwargs


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Editar Usuario: {self.object.username}'
        context['nombre_boton'] = 'Guardar Cambios'
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Usuario '{self.object.username}' actualizado exitosamente.")
        return response
    
    
class UserDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = User
    template_name = 'user_management/user_confirm_delete.html'
    success_url = reverse_lazy('user_management:user_list')
    permission_required = 'auth.delete_user'
    context_object_name = 'user_to_delete'


    def get_queryset(self):
        """
        MODIFICADO: APLICANDO EL PATRÓN DE FILTRADO DIRECTO.
        """
        qs = super().get_queryset()
        if self.request.user.is_superuser:
            return qs        
        
        empresa_actual = getattr(self.request, 'tenant', None)
        if empresa_actual:
            return qs.filter(empresa=empresa_actual) # Filtro directo
        
        return qs.none()


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Eliminar Usuario: {self.object.username}'
        return context

    def post(self, request, *args, **kwargs):
        username_to_delete = self.get_object().username
        response = super().post(request, *args, **kwargs)
        messages.success(request, f"Usuario '{username_to_delete}' eliminado exitosamente.")
        return response
    
    def dispatch(self, request, *args, **kwargs):
        # La lógica para evitar auto-eliminación y eliminación de superusuarios se mantiene.
        user_to_delete = self.get_object()
        if user_to_delete == request.user:
            messages.error(request, "No puedes eliminarte a ti mismo.")
            return redirect('user_management:user_list')
        if user_to_delete.is_superuser and not request.user.is_superuser:
            raise PermissionDenied("No tienes permiso para eliminar a un superusuario.")
        return super().dispatch(request, *args, **kwargs)
   
    
@login_required
@permission_required('auth.change_user', raise_exception=True)
def user_set_password_view(request, pk):
    user_to_change = get_object_or_404(User, pk=pk)
    
    empresa_actual = getattr(request, 'tenant', None)
    if not request.user.is_superuser and empresa_actual:
        if user_to_change.empresa != empresa_actual:
            raise PermissionDenied("No tienes permiso para cambiar la contraseña de este usuario.")
    
    if not request.user.is_superuser and hasattr(request, 'tenant'):
        if not Vendedor.objects.filter(user=user_to_change, empresa=request.tenant).exists():
            raise PermissionDenied("No tienes permiso para cambiar la contraseña de este usuario.")

    if user_to_change.is_superuser and not request.user.is_superuser:
        raise PermissionDenied("No tienes permiso para cambiar la contraseña de un superusuario.")    

    if user_to_change.is_superuser and not request.user.is_superuser:
        messages.error(request, "No tienes permiso para cambiar la contraseña de un superusuario.")

    if request.method == 'POST':
        form = AdminSetPasswordForm(user=user_to_change, data=request.POST)
        if form.is_valid():
            form.save() # Esto se encarga de user.set_password() y user.save()
            messages.success(request, f"Contraseña para '{user_to_change.username}' actualizada exitosamente.")

            return redirect('user_management:user_list')
        else:
            messages.error(request, "Por favor corrige los errores en el formulario.")
    else:
        form = AdminSetPasswordForm(user=user_to_change)

    context = {
        'form': form,
        'user_to_change': user_to_change,
        'titulo': f"Cambiar Contraseña para: {user_to_change.username}",
        'nombre_boton': "Establecer Nueva Contraseña"
    }
    return render(request, 'user_management/user_password_set_form.html', context)


class SuperuserRequiredMixin:
    """Mixin que deniega el acceso a usuarios que no son superusuarios."""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "Esta sección solo está disponible para administradores del sistema.")
            return redirect('core:index') # O a una página de acceso denegado
        return super().dispatch(request, *args, **kwargs)

class GroupListView(LoginRequiredMixin, SuperuserRequiredMixin, PermissionRequiredMixin, ListView):
    model = Group
    template_name = 'user_management/group_list.html'
    context_object_name = 'groups'
    permission_required = 'auth.view_group' # Permiso para ver grupos
    # paginate_by = 20 # Opcional

    def get_queryset(self):
        return Group.objects.all().order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Listado de Grupos de Usuarios'
        return context
    
class GroupCreateView(LoginRequiredMixin, SuperuserRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Group
    form_class = GroupForm
    template_name = 'user_management/group_form.html' # Plantilla genérica para formularios de grupo
    success_url = reverse_lazy('user_management:group_list')
    permission_required = 'auth.add_group' # Permiso para añadir grupos

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Crear Nuevo Grupo'
        context['nombre_boton'] = 'Crear Grupo'
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Grupo '{self.object.name}' creado exitosamente.")
        return response
    
class GroupUpdateView(LoginRequiredMixin, SuperuserRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Group
    form_class = GroupForm # Reutilizamos el mismo formulario
    template_name = 'user_management/group_form.html' # Reutilizamos la plantilla del formulario
    success_url = reverse_lazy('user_management:group_list')
    permission_required = 'auth.change_group' # Permiso para modificar grupos

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Editar Grupo: {self.object.name}'
        context['nombre_boton'] = 'Guardar Cambios'
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Grupo '{self.object.name}' actualizado exitosamente.")
        return response
    
class GroupDeleteView(LoginRequiredMixin, SuperuserRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Group
    template_name = 'user_management/group_confirm_delete.html' # Nueva plantilla de confirmación
    success_url = reverse_lazy('user_management:group_list')
    permission_required = 'auth.delete_group' # Permiso para eliminar grupos
    context_object_name = 'group_to_delete'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Eliminar Grupo: {self.object.name}'
        return context

    def post(self, request, *args, **kwargs):
        group_name_to_delete = self.get_object().name
        response = super().post(request, *args, **kwargs)
        messages.success(request, f"Grupo '{group_name_to_delete}' eliminado exitosamente.")
        return response