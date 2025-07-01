from django import forms
from productos.models import Producto
from .models import IngresoBodega, DetalleIngresoBodega
from .models import SalidaInternaCabecera, SalidaInternaDetalle
from django.utils import timezone



class IngresoBodegaForm(forms.ModelForm):
    """Formulario para los datos generales de un ingreso."""
    proveedor_info = forms.CharField(
        label="Información Proveedor/Origen",
        max_length=200,
        required=False, # O True si siempre debes saber de dónde viene
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    documento_referencia = forms.CharField(
        label="Documento Referencia (Factura Compra, Remisión, etc.)",
        max_length=100,
        required=False, # O True si siempre necesitas una referencia
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    notas = forms.CharField(
        label="Notas Adicionales",
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        required=False
    )

    class Meta:
        model = IngresoBodega
        # Campos a mostrar en el formulario de cabecera
        # Excluimos fecha_hora y usuario (se asignan en la vista)
        fields = ['proveedor_info', 'documento_referencia', 'notas']
        
    def __init__(self, *args, **kwargs):
        """
        Este método se personaliza para manejar argumentos extra enviados desde la vista.
        """
        # Capturamos y eliminamos el argumento 'empresa' que nos envía la vista.
        # Aunque no usemos la variable 'empresa' directamente en este formulario,
        # es crucial removerla de 'kwargs' para evitar el TypeError.
        empresa = kwargs.pop('empresa', None)

        # Llamamos al constructor padre con los argumentos ya "limpios".
        super().__init__(*args, **kwargs)


# --- NUEVO: Formulario para UNA línea de Detalle de Ingreso ---
class DetalleIngresoBodegaForm(forms.ModelForm):
    """Formulario para un producto ingresado a bodega."""

    # Usaremos Select2 con AJAX para buscar producto
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.filter(activo=True).order_by('referencia', 'nombre', 'color', 'talla'),
        label="Producto Ingresado",
        widget=forms.Select(attrs={'class': 'form-control producto-select-ingreso'}) # Clase para JS
    )

    cantidad = forms.IntegerField(
        label="Cantidad Ingresada",
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'style': 'width: 80px;'})
    )

    # costo_unitario es opcional en el modelo, lo hacemos no requerido aquí también
    costo_unitario = forms.DecimalField(
        label="Costo Unitario",
        max_digits=10,
        decimal_places=2,
        required=False, # El costo puede no saberse o registrarse siempre
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01', 'placeholder': 'Opcional'})
    )
    
    class Meta:
        model = DetalleIngresoBodega
        fields = ['producto', 'cantidad', 'costo_unitario']
        
    def __init__(self, *args, **kwargs):
            # 1. Extraemos y eliminamos 'empresa' de los argumentos para evitar el TypeError.
        empresa = kwargs.pop('empresa', None)
            
            # 2. Llamamos al constructor padre con los kwargs ya "limpios".
        super().__init__(*args, **kwargs)
            
            # 3. Usamos la 'empresa' para filtrar el campo de productos.
            #    ¡Este es un paso de seguridad muy importante!
        if empresa:
            self.fields['producto'].queryset = Producto.objects.filter(
                empresa=empresa, 
                activo=True
            ).order_by('referencia', 'nombre')
        else:
                # Como medida de seguridad, si no se proporciona una empresa, no mostramos ningún producto.
            self.fields['producto'].queryset = Producto.objects.none()


# --- NUEVO: FormSet para manejar MÚLTIPLES Detalles de Ingreso ---
DetalleIngresoFormSet = forms.inlineformset_factory(
    parent_model=IngresoBodega,      # Modelo padre
    model=DetalleIngresoBodega,    # Modelo detalle
    form=DetalleIngresoBodegaForm, # Formulario para cada detalle
    extra=3,                       # Mostrar 3 formularios extra por defecto (ajústalo)
    can_delete=False,              # No permitir borrar líneas en este formulario simple
    min_num=1,                     # Requerir al menos 1 producto ingresado
    validate_min=True,
)


class InfoGeneralConteoForm(forms.Form):
    fecha_actualizacion_stock = forms.DateField(
        label="Fecha Efectiva del Ajuste",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
        initial=timezone.now().date() # Por defecto hoy
    )
    motivo_conteo = forms.CharField(
        label="Motivo del Conteo/Ajuste",
        max_length=150,
        required=False, # Hazlo requerido si siempre debe haber un motivo
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Ej: Conteo cíclico Bodega A'})
    )
    revisado_con = forms.CharField(
        label="Revisado/Contado Con",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Nombre de la persona que verificó'})
    )
    notas_generales = forms.CharField(
        label="Notas Generales Adicionales",
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control form-control-sm'})
    )
    
    
class SalidaInternaCabeceraForm(forms.ModelForm):
    class Meta:
        model = SalidaInternaCabecera
        fields = [
            'tipo_salida', 'destino_descripcion', 
            'documento_referencia_externo', 'fecha_prevista_devolucion', 
            'observaciones_salida'
        ]
        widgets = {
            'tipo_salida': forms.Select(attrs={'class': 'form-select'}),
            'destino_descripcion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Vendedor Juan Pérez, Tienda Centro'}),
            'documento_referencia_externo': forms.TextInput(attrs={'class': 'form-control'}),
            'fecha_prevista_devolucion': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'observaciones_salida': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class SalidaInternaDetalleForm(forms.ModelForm):
    class Meta:
        model = SalidaInternaDetalle
        fields = ['producto', 'cantidad_despachada', 'observaciones_detalle']
        widgets = {
            'producto': forms.Select(attrs={'class': 'form-select select2-producto'}), # Para Select2 si lo usas
            'cantidad_despachada': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'observaciones_detalle': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
        }

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None) # Extraer el kwarg 'empresa'
        super().__init__(*args, **kwargs)
        
        if empresa:
            # Filtrar productos activos de la empresa actual para el dropdown
            self.fields['producto'].queryset = Producto.objects.filter(
                empresa=empresa,
                activo=True
            ).order_by('referencia', 'nombre')
        else:
            self.fields['producto'].queryset = Producto.objects.none()


DetalleSalidaInternaFormSet = forms.inlineformset_factory(
    SalidaInternaCabecera,
    SalidaInternaDetalle,
    form=SalidaInternaDetalleForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True
)