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
            'genero': None,
        }

    def __init__(self, *args, **kwargs):
        empresa_actual = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                # Los checkboxes usan una clase diferente en Bootstrap.
                field.widget.attrs['class'] = 'form-check-input'
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            else:
                # El resto de los inputs usan 'form-control'.
                field.widget.attrs['class'] = 'form-control'


class ProductoImportForm(forms.Form):
    """
    Formulario simple para la subida de archivos de importación masiva.
    La lógica de seguridad y procesamiento está en el 'ProductoResource', no aquí.
    """
    archivo_productos = forms.FileField(
        label="Seleccionar archivo (.csv, .xls, .xlsx)",
        help_text="Asegúrese de que el archivo coincida con el formato de exportación.",
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        # "Atrapamos" el parámetro 'empresa' y lo quitamos de kwargs
        self.empresa = kwargs.pop('empresa', None)
        # Llamamos al __init__ original sin el argumento inesperado
        super().__init__(*args, **kwargs)
    
class MultipleFileInput(forms.ClearableFileInput):
    """
    Un widget personalizado que permite la subida de múltiples archivos.
    Hereda de ClearableFileInput pero permite el atributo 'multiple'.
    """
    allow_multiple_selected = True
    
    def __init__(self, *args, **kwargs):
        # "Atrapamos" el parámetro 'empresa' y lo quitamos de kwargs
        self.empresa = kwargs.pop('empresa', None)
        # Llamamos al __init__ original sin el argumento inesperado
        super().__init__(*args, **kwargs)

class MultipleFileField(forms.FileField):
    """
    Un campo de formulario personalizado que utiliza el widget MultipleFileInput
    y está diseñado para manejar una lista de archivos.
    """
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result
    

class SeleccionarAgrupacionParaFotosForm(forms.Form):
    
    
    imagenes = MultipleFileField(
        label="Seleccionar Imágenes",
        required=True # Aseguramos que se suba al menos una imagen
    )

    articulo_color = forms.ModelChoiceField(
        queryset=ReferenciaColor.objects.none(),
        label="Agrupar por Referencia y Color",
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Selecciona la combinación de referencia y color a la que pertenecerán las fotos."
    )

    descripcion_general = forms.CharField(
        label="Descripción General para las Fotos",
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        help_text="(Opcional) Esta descripción se aplicará a todas las fotos que subas."
    )
    
   
    def __init__(self, *args, **kwargs):
        """
        Filtra el queryset de 'articulo_color' para mostrar solo las opciones
        de la empresa (tenant) actual.
        """
        empresa_actual = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)

        if empresa_actual:
            self.fields['articulo_color'].queryset = ReferenciaColor.objects.filter(
                empresa=empresa_actual
            ).distinct().order_by('referencia_base', 'color')
        else:
            # Si no hay empresa, el formulario no puede funcionar de forma segura.
            # Podrías lanzar un error o simplemente dejar el queryset vacío.
            self.fields['articulo_color'].queryset = ReferenciaColor.objects.none()