# productos/forms.py
from django import forms
from decimal import Decimal
from .models import Producto, Color
from bodega.models import Bodega


class AjusteMasivoPrecioForm(forms.Form):
    """
    Filtro + regla para el ajuste masivo de precios ('productos:ajuste_masivo_precios').
    No toca ningún producto por sí solo -- la vista arma el queryset con estos
    mismos criterios y aplica la regla en dos pasos (vista previa y confirmación).
    """
    TIPO_AJUSTE_CHOICES = [
        ('SUMAR_FIJO', 'Sumar un valor fijo ($)'),
        ('RESTAR_FIJO', 'Restar un valor fijo ($)'),
        ('PORCENTAJE_SUBIR', 'Subir un porcentaje (%)'),
        ('PORCENTAJE_BAJAR', 'Bajar un porcentaje (%)'),
        ('FIJAR_VALOR', 'Fijar un precio exacto ($)'),
    ]

    q = forms.CharField(
        required=False, label="Buscar",
        help_text="Referencia, nombre, color, talla o código de barras.",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 0413, JEAN CLASICO, AZUL...'})
    )
    genero = forms.ChoiceField(
        required=False, label="Género/Categoría",
        choices=[('', 'Todos')] + list(Producto.GeneroOpciones.choices),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    solo_activos = forms.BooleanField(
        required=False, initial=True, label="Solo productos activos",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    precio_min = forms.DecimalField(
        required=False, min_value=0, label="Precio actual desde",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Sin límite'})
    )
    precio_max = forms.DecimalField(
        required=False, min_value=0, label="Precio actual hasta",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Sin límite'})
    )
    tipo_ajuste = forms.ChoiceField(
        label="Operación", choices=TIPO_AJUSTE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    valor = forms.DecimalField(
        label="Valor", min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )

    def clean(self):
        cleaned_data = super().clean()
        precio_min = cleaned_data.get('precio_min')
        precio_max = cleaned_data.get('precio_max')
        if precio_min is not None and precio_max is not None and precio_min > precio_max:
            raise forms.ValidationError("El precio 'desde' no puede ser mayor que el precio 'hasta'.")
        return cleaned_data


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

            self.fields['color'].queryset = Color.objects.filter(empresa=empresa_actual, activo=True).order_by('nombre')
        else:
            self.fields['ubicacion'].queryset = Bodega.objects.none()
            self.fields['color'].queryset = Color.objects.none()

        self.fields['color'].required = False
        self.fields['color'].widget.attrs['class'] = 'form-select select2-color'

        for field_name, field in self.fields.items():
            if field_name == 'color':
                continue
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            elif not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-control'

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