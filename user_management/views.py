from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from .forms import CustomUserCreationForm, CustomUserChangeForm, AdminSetPasswordForm, GroupForm
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.contrib.auth.models import Group

class UserListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = User
    template_name = 'user_management/user_list.html'
    context_object_name = 'users'
    permission_required = 'auth.view_user'

    def get_queryset(self):
        return User.objects.all().order_by('username')

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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Crear Nuevo Usuario'
        context['nombre_boton'] = 'Crear Usuario'
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Usuario '{self.object.username}' creado exitosamente.")
        return response
    
class UserUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = User
    form_class = CustomUserChangeForm
    template_name = 'user_management/user_form.html'
    success_url = reverse_lazy('user_management:user_list')
    permission_required = 'auth.change_user'

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
        user_to_delete = self.get_object()
        if user_to_delete == request.user:
            messages.error(request, "No puedes eliminarte a ti mismo.")
            return redirect('user_management:user_list')

        # Opcional: Evitar que no superusuarios eliminen superusuarios
        if user_to_delete.is_superuser and not request.user.is_superuser:
            messages.error(request, "No tienes permiso para eliminar a un superusuario.")
            # O lanzar PermissionDenied() que llevaría a una página 403
            raise PermissionDenied("No tienes permiso para eliminar a un superusuario.")

        return super().dispatch(request, *args, **kwargs)
    
@login_required
@permission_required('auth.change_user', raise_exception=True) # O un permiso más específico si lo creas
def user_set_password_view(request, pk):
    user_to_change = get_object_or_404(User, pk=pk)

    # Opcional: Lógica para prevenir cambiar contraseña a superusuarios por no-superusuarios,
    # o a uno mismo de esta forma (aunque un usuario puede cambiar su propia contraseña por otro medio)
    if user_to_change.is_superuser and not request.user.is_superuser:
        messages.error(request, "No tienes permiso para cambiar la contraseña de un superusuario.")
        return redirect('user_management:user_list')
    # if user_to_change == request.user and not request.user.is_superuser: # Evitar auto-cambio por esta vía para no superuser
    #     messages.error(request, "Para cambiar tu propia contraseña, usa la opción de cambio de contraseña personal.")
    #     return redirect('user_management:user_update', pk=user_to_change.pk)


    if request.method == 'POST':
        form = AdminSetPasswordForm(user=user_to_change, data=request.POST)
        if form.is_valid():
            form.save() # Esto se encarga de user.set_password() y user.save()
            messages.success(request, f"Contraseña para '{user_to_change.username}' actualizada exitosamente.")
            # Aquí podrías añadir lógica para enviar una notificación al usuario si lo deseas
            # update_session_auth_hash(request, user_to_change) # Si el admin cambia su propia clave y sigue logueado
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

class GroupListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
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
    
class GroupCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
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
    
class GroupUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
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
    
class GroupDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
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