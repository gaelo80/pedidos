# clientes/forms.py
from django import forms
from .models import Cliente, Ciudad

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        # Incluimos solo los campos que existen en tu modelo Cliente
        # y que son relevantes para la edición/creación manual.
        fields = [
            'nombre_completo', 
            'identificacion', 
            'ciudad', 
            'direccion',
            'telefono', 
            'email',
            # 'fecha_creacion' es auto_now_add, no se incluye en el form usualmente.
            # Los campos 'tipo_identificacion', 'tipo_cliente', 'cupo_credito', 
            # 'plazo_pago_dias', 'notas' no están en tu modelo Cliente actual.
        ]
        widgets = {
            'nombre_completo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Juan Pérez Gómez'}),
            'identificacion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 1234567890'}),
            'ciudad': forms.Select(attrs={'class': 'form-select'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Calle 10 # 20-30, Barrio Centro'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 3001234567'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Ej: cliente@example.com'}),
        }
        labels = {
            'nombre_completo': 'Nombre Completo del Cliente',
            'identificacion': 'Número de Identificación (NIT/Cédula)',
            'ciudad': 'Ciudad de Residencia',
            'direccion': 'Dirección Completa',
            'telefono': 'Número de Teléfono de Contacto',
            'email': 'Correo Electrónico',
        }
        help_texts = {
            'email': 'Asegúrate de que sea un correo válido.',
            'identificacion': 'Si es NIT, incluir dígito de verificación si es costumbre.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Opcional: Si quieres que el campo ciudad muestre las ciudades ordenadas
        # y evitar un error si Ciudad aún no tiene datos o la app no está completamente cargada.
        try:
            self.fields['ciudad'].queryset = Ciudad.objects.all().order_by('nombre')
        except Exception as e:
            # Podrías loggear el error si quieres: print(f"Error al cargar ciudades: {e}")
            # Esto evita que el formulario falle si hay problemas con la app Ciudad al inicio.
            pass 

# --- Formulario para Ciudad ---
class CiudadForm(forms.ModelForm):
    class Meta:
        model = Ciudad
        fields = ['nombre']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Medellín'}),
        }
        labels = {
            'nombre': 'Nombre de la Ciudad',
        }

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre')
        if nombre:
            # Convertir a título para consistencia, y verificar si ya existe (ignorando mayúsculas/minúsculas)
            # al guardar, pero la validación aquí puede ser más simple o más compleja según se necesite.
            # Si el campo 'nombre' en el modelo es unique=True, la BD ya manejará la unicidad.
            # Esta validación es más para la experiencia de usuario.
            queryset = Ciudad.objects.filter(nombre__iexact=nombre)
            if self.instance and self.instance.pk: # Si estamos editando
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise forms.ValidationError("Ya existe una ciudad con este nombre. Por favor, elige otro.")
        return nombre

# --- Formulario para Importar Ciudades ---
class CiudadImportForm(forms.Form):
    archivo_ciudades = forms.FileField(
        label="Seleccionar Archivo (.csv, .xls, .xlsx)",
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.csv,.xls,.xlsx'}),
        help_text="El archivo debe tener una columna llamada 'nombre' para los nombres de las ciudades."
    )