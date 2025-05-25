from django import forms
from django.contrib.auth.forms import UserCreationForm, SetPasswordForm
from django.contrib.auth.models import User
from django.contrib.auth.models import Group, Permission 

class CustomUserCreationForm(UserCreationForm):
    # Puedes añadir campos adicionales aquí si lo necesitas, 
    # como email, first_name, last_name, que no están por defecto en UserCreationForm
    email = forms.EmailField(required=True, help_text='Requerido. Introduce una dirección de correo válida.')
    first_name = forms.CharField(max_length=30, required=False, label='Nombre')
    last_name = forms.CharField(max_length=150, required=False, label='Apellidos')

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('first_name', 'last_name', 'email',) # Añadir los campos

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({'class': 'form-control mb-2'})
        # Puedes quitar la ayuda de contraseña si lo deseas o modificarla
        # self.fields['password2'].help_text = None
        
class CustomUserChangeForm(forms.ModelForm):
    email = forms.EmailField(required=True, help_text='Requerido. Introduce una dirección de correo válida.')

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'is_active', 'is_staff')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items(): # Iterar sobre field_name y field
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                # A los checkboxes de Bootstrap se les suele aplicar 'form-check-input'
                widget.attrs.update({'class': 'form-check-input'})
            elif not isinstance(widget, (forms.RadioSelect, forms.ClearableFileInput, forms.FileInput)):
                # A otros campos (texto, email, etc.) se les aplica 'form-control'
                widget.attrs.update({'class': 'form-control mb-2'})
            # Puedes añadir condiciones para otros tipos de widgets si es necesario
            
class AdminSetPasswordForm(SetPasswordForm):
    # SetPasswordForm ya tiene los campos new_password1 y new_password2
    # y la lógica de validación.
    # Podemos personalizarlo si es necesario, por ejemplo, las clases de los widgets.
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs) # SetPasswordForm requiere 'user' en su __init__
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({'class': 'form-control mb-2'})


class GroupForm(forms.ModelForm): # Usaremos este form para crear y editar
    class Meta:
        model = Group
        fields = ['name'] # Inicialmente solo el nombre

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].widget.attrs.update({'class': 'form-control mb-2', 'placeholder': 'Nombre del grupo'})
        self.fields['name'].label = "Nombre del Grupo"
        
class GroupForm(forms.ModelForm):
    # El campo 'name' ya está manejado por ModelForm

    # Añadimos el campo para los permisos
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.all(),
        widget=forms.CheckboxSelectMultiple, # Muestra los permisos como checkboxes
        required=False, # Un grupo puede no tener permisos directos
        label="Permisos Asignados al Grupo"
    )

    class Meta:
        model = Group
        fields = ['name', 'permissions'] # Incluimos 'name' y 'permissions'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].widget.attrs.update({'class': 'form-control mb-2', 'placeholder': 'Nombre del grupo'})
        self.fields['name'].label = "Nombre del Grupo"
        
class CustomUserChangeForm(forms.ModelForm):
    email = forms.EmailField(required=True, help_text='Requerido. Introduce una dirección de correo válida.')

    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Grupos"
    )

    # Añadimos el campo para los permisos directos del usuario
    user_permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.all(), # Considera filtrar esto si es necesario (ver nota abajo)
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Permisos Individuales"
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 
                  'is_active', 'is_staff', 'groups', 'user_permissions') # Añadimos 'user_permissions'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput): # Para is_active, is_staff
                widget.attrs.update({'class': 'form-check-input'})
            elif isinstance(widget, forms.CheckboxSelectMultiple): # Para 'groups' y 'user_permissions'
                pass # Estilo se maneja mejor en la plantilla o CSS global para los checkboxes
            elif not isinstance(widget, (forms.RadioSelect, forms.ClearableFileInput, forms.FileInput)):
                widget.attrs.update({'class': 'form-control mb-2'})

        # Opcional: Ordenar los grupos y permisos en el formulario
        if 'groups' in self.fields:
             self.fields['groups'].queryset = Group.objects.order_by('name')
        if 'user_permissions' in self.fields:
            self.fields['user_permissions'].queryset = Permission.objects.select_related('content_type').order_by('content_type__app_label', 'content_type__model', 'codename')
