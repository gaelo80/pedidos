# productos/forms.py
from django import forms
from .models import Producto, ReferenciaColor

class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = [
            'referencia', 
            'nombre', 
            'descripcion', 
            'talla', 
            'color', 
            'genero', 
            'costo', 
            'precio_venta', 
            'unidad_medida', 
            'codigo_barras', 
            'activo', 
            'ubicacion'
        ]
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
            'referencia': forms.TextInput(attrs={'placeholder': 'Ej: 0808, REF001'}),
            'nombre': forms.TextInput(attrs={'placeholder': 'Ej: Jean Clásico Caballero'}),
            'talla': forms.TextInput(attrs={'placeholder': 'Ej: 32, M, Única'}),
            'color': forms.TextInput(attrs={'placeholder': 'Ej: Azul Oscuro, Rojo'}),
            'costo': forms.NumberInput(attrs={'step': '0.01', 'placeholder': '0.00'}),
            'precio_venta': forms.NumberInput(attrs={'step': '0.01', 'placeholder': '0.00'}),
            'codigo_barras': forms.TextInput(attrs={'placeholder': 'Escanee o ingrese el código'}),
            'ubicacion': forms.TextInput(attrs={'placeholder': 'Ej: Estante A, Bodega 2'}),
        }
        help_texts = {
            'genero': None, # Quitar el help_text por defecto del modelo si no se quiere en el form
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Puedes añadir personalizaciones adicionales aquí si es necesario
        # Por ejemplo, hacer que algunos campos no sean obligatorios si el modelo lo permite
        # self.fields['descripcion'].required = False
        # self.fields['talla'].required = False # Ya son blank=True en el modelo
        # self.fields['color'].required = False # Ya son blank=True en el modelo
        # self.fields['codigo_barras'].required = False # Ya es blank=True en el modelo
        # self.fields['ubicacion'].required = False # Ya es blank=True en el modelo

        # Añadir clases CSS para Bootstrap si no usas crispy-forms en la plantilla del form
        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.TextInput, forms.Textarea, forms.NumberInput, forms.EmailInput, forms.PasswordInput, forms.DateInput, forms.Select)):
                current_attrs = field.widget.attrs
                current_attrs['class'] = current_attrs.get('class', '') + ' form-control'
                if isinstance(field.widget, forms.CheckboxInput): # Checkbox es diferente
                     current_attrs['class'] = current_attrs.get('class', '') + ' form-check-input'
                field.widget.attrs = current_attrs


class ProductoImportForm(forms.Form):
    archivo_productos = forms.FileField(
        label="Seleccionar archivo (.csv, .xls, .xlsx)",
        help_text="Asegúrate de que el archivo tenga las columnas correctas: "
                  "id, referencia, nombre, descripcion, talla, color, genero, costo, "
                  "precio_venta, unidad_medida, codigo_barras, activo, ubicacion, fecha_creacion. "
                  "Para 'activo', usa True/False o 1/0.",
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'})
    )
    

# Formulario para seleccionar el Producto (Variante) al que se añadirán las fotos
class SeleccionarAgrupacionParaFotosForm(forms.Form):
    articulo_color = forms.ModelChoiceField(
        queryset=ReferenciaColor.objects.all().order_by('referencia_base', 'color'),
        label="Seleccionar Referencia",
        widget=forms.Select(attrs={'class': 'form-select form-control mb-3'}),
        empty_label="-- Seleccione una Referencia --"
    )

    imagenes = forms.ImageField(
        required=True,
        label="Seleccionar Imágenes (puede seleccionar varias)"
    )


    descripcion_general = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control mb-3'}),
        required=False,
        label="Descripción General (opcional, para todas las fotos subidas)"
    )

    # Si quitamos el widget explícito arriba, podemos intentar añadir 'multiple' aquí,
    # aunque el error original sugiere que el __init__ del widget es el problema.
    # Esta es una forma alternativa de intentar modificar el widget del campo ya creado.
    #def __init__(self, *args, **kwargs):
        #super().__init__(*args, **kwargs)
        #self.fields['imagenes'].widget.attrs.update({
            #'multiple': True,
            #'class': 'form-control' # Para el estilo de Bootstrap
       # })