# productos/forms.py
from django import forms
from .models import Producto
from bodega.models import Bodega

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
    
class ProductoBaseForm(forms.ModelForm):
    """
    Formulario para la información común del producto.
    """
    class Meta:
        model = Producto
        fields = [
            'referencia', 'nombre', 'descripcion', 'color', 
            'genero', 'costo', 'precio_venta', 'unidad_medida', 
            'ubicacion', 'activo', 'permitir_preventa',
        ]
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 2}),
        }
        # Excluimos 'talla' y 'codigo_barras' porque irán en el formset.

    def __init__(self, *args, **kwargs):
        empresa_actual = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)

        if empresa_actual:
            self.fields['ubicacion'].queryset = Bodega.objects.filter(empresa=empresa_actual, activa=True).order_by('orden', 'nombre')
            if not self.instance.pk and not self.initial.get('ubicacion'):
                bodega_principal = Bodega.objects.filter(empresa=empresa_actual, es_principal=True).first()
                if bodega_principal:
                    self.initial['ubicacion'] = bodega_principal.pk
        else:
            self.fields['ubicacion'].queryset = Bodega.objects.none()

        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            elif not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-control'

class ProductoTallaForm(forms.Form):
    """
    Formulario para una única fila de talla y código de barras.
    Añadimos widgets para un mejor control visual en la plantilla.
    """
    talla = forms.IntegerField(
        label="Talla",
        required=True,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Talla'})
    )
    codigo_barras = forms.CharField(
        label="Código de Barras",
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Código de Barras (Opcional)'})
    )


class ProductoTallaEditForm(forms.Form):
    """
    Igual que ProductoTallaForm, pero para editar tallas ya existentes:
    trae un 'producto_id' oculto para saber qué variante actualizar, y
    'talla' no es obligatoria para que las filas extra (para agregar tallas
    nuevas) puedan quedar en blanco sin generar error.
    """
    producto_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    talla = forms.IntegerField(
        label="Talla",
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Talla'})
    )
    codigo_barras = forms.CharField(
        label="Código de Barras",
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Código de Barras (Opcional)'})
    )