from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, SetPasswordForm
from django.contrib.auth.models import User, Group, Permission
from django.db.models import Q

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True, 
        help_text='Requerido. Introduce una dirección de correo válida.'
    )
    first_name = forms.CharField(max_length=150, required=False, label='Nombre')
    last_name = forms.CharField(max_length=150, required=False, label='Apellidos')
    
    tenant = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('first_name', 'last_name', 'email',)

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control mb-2'})

        if 'groups' in self.fields:
            # Esta línea es un ejemplo si quisiéramos filtrar. Por ahora no es necesaria.
            # if self.tenant:
            #     self.fields['groups'].queryset = Group.objects.filter(empresa=self.tenant)
            self.fields['groups'].queryset = Group.objects.order_by('name')           
            
            
class CustomUserChangeForm(forms.ModelForm):
    """
    Formulario para la edición de usuarios existentes.
    Permite modificar datos básicos y asignar roles (grupos) y permisos.
    """    
    email = forms.EmailField(required=True, help_text='Requerido.')
    
        # Campo para asignar los grupos/roles al usuario.
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Roles Asignados"
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 
                  'is_active', 'is_staff', 'groups')
        

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # Si el formulario está ligado a una instancia de usuario, establecemos los grupos iniciales.
        if self.instance.pk:
            self.fields['groups'].initial = self.instance.groups.all()

        # Aplicamos estilos de Bootstrap
        for field_name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.update({'class': 'form-check-input'})
            elif isinstance(widget, forms.CheckboxSelectMultiple):
                # Dejamos los checkboxes de selección múltiple sin clase para un estilo más limpio
                pass
            else:
                widget.attrs.update({'class': 'form-control mb-2'})
                
                
    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            user.groups.set(self.cleaned_data['groups'])
            self.save_m2m()
        return user
       
            
class AdminSetPasswordForm(SetPasswordForm):
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs) 
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control mb-2'})  

class GroupForm(forms.ModelForm):
    """
    Formulario para crear y editar Grupos (Roles).
    Importante: Las vistas que usan este formulario están restringidas a Superusuarios,
    por lo que es correcto que puedan ver y asignar cualquier permiso del sistema.
    """
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Permisos Asignados al Grupo"
    )

    class Meta:
        model = Group
        fields = ['name', 'permissions']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Si estamos editando un grupo existente, seleccionamos sus permisos actuales.
        if self.instance.pk:
            self.fields['permissions'].initial = self.instance.permissions.all()

        # Aplicamos estilos y ordenamos los permisos para que sea más fácil navegar.
        self.fields['name'].widget.attrs.update({'class': 'form-control mb-2', 'placeholder': 'Nombre del Rol'})
        self.fields['name'].label = "Nombre del Rol"
        self.fields['permissions'].queryset = Permission.objects.select_related('content_type').order_by(
            'content_type__app_label', 'codename'
        )
        
    def save(self, commit=True):
        # Manejo de la relación ManyToMany para los permisos
        group = super().save(commit=commit)
        if commit:
            group.permissions.set(self.cleaned_data['permissions'])
        return group
    
    
        
