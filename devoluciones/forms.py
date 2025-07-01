from django import forms
from django.forms import inlineformset_factory

# Ajusta las rutas de importación si es necesario
from productos.models import Producto
from clientes.models import Cliente
from .models import DevolucionCliente, DetalleDevolucion

class DevolucionClienteForm(forms.ModelForm):
    """Formulario para los datos generales de la devolución."""

    # El campo se define aquí para poder modificar su queryset en __init__
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.none(), # Se inicia vacío, se poblará en __init__
        label="Cliente que Devuelve",
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_cliente_devolucion'})
    )
    
    motivo = forms.CharField(
        label="Motivo General de la Devolución",
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        required=False
    )

    class Meta:
        model = DevolucionCliente
        fields = ['cliente', 'motivo']
    
    # --- INICIO DE CAMBIOS MULTI-INQUILINO ---
    def __init__(self, *args, **kwargs):
        # 1. OBTENER LA EMPRESA QUE SE PASA DESDE LA VISTA
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)

        # 2. FILTRAR EL QUERYSET DEL CAMPO 'cliente'
        if empresa:
            self.fields['cliente'].queryset = Cliente.objects.filter(
                empresa=empresa
            ).order_by('nombre_completo')
        else:
            # Si no se pasa empresa, el queryset permanece vacío para seguridad.
            self.fields['cliente'].queryset = Cliente.objects.none()
    # --- FIN DE CAMBIOS MULTI-INQUILINO ---


class DetalleDevolucionForm(forms.ModelForm):
    """Formulario para un producto devuelto."""

    producto = forms.ModelChoiceField(
        queryset=Producto.objects.none(), # Se inicia vacío
        label="Producto Devuelto",
        widget=forms.Select(attrs={'class': 'form-control producto-select-devolucion'})
    )

    cantidad = forms.IntegerField(
        label="Cantidad Devuelta",
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'style': 'width: 80px;'})
    )

    class Meta:
        model = DetalleDevolucion
        fields = ['producto', 'cantidad', 'estado_producto']
        widgets = {
            'estado_producto': forms.Select(attrs={'class': 'form-select form-select-sm'})
        }
    
    # --- INICIO DE CAMBIOS MULTI-INQUILINO ---
    def __init__(self, *args, **kwargs):
        # 1. OBTENER LA EMPRESA QUE SE PASA DESDE LA VISTA A TRAVÉS DEL FORMSET
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)

        # 2. FILTRAR EL QUERYSET DEL CAMPO 'producto'
        if empresa:
            self.fields['producto'].queryset = Producto.objects.filter(
                empresa=empresa, 
                activo=True
            ).order_by('referencia', 'nombre', 'color', 'talla')
        else:
            self.fields['producto'].queryset = Producto.objects.none()
    # --- FIN DE CAMBIOS MULTI-INQUILINO ---


DetalleDevolucionFormSet = inlineformset_factory(
    parent_model=DevolucionCliente,
    model=DetalleDevolucion,
    form=DetalleDevolucionForm,
    extra=1, # Cambiado a 1 para que siempre aparezca una línea para añadir
    can_delete=True,
    min_num=1,
    validate_min=True,
)