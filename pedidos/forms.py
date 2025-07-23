# pedidos/forms.py
from django import forms
from productos.models import Producto
from decimal import Decimal
from clientes.models import Cliente
from pedidos.models import Pedido, DetallePedido
from clientes.models import Empresa
from prospectos.models import Prospecto

# ===================================================================
# FORMULARIO PARA LA CABECERA DEL PEDIDO
# ===================================================================
class PedidoForm(forms.ModelForm):
    """
    Formulario para la cabecera del Pedido (cliente, descuento, notas).
    Asegura que el cliente seleccionado pertenezca a la empresa correcta.
    """
    
    referencia = forms.ModelChoiceField(
        label="Referencia",
        queryset=Producto.objects.none(),  # lo filtras en __init__
        required=False,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_referencia'})
    )
    
    prospecto = forms.ModelChoiceField(
        queryset=Prospecto.objects.none(), # Se llena con JS vía API
        required=False, # No es obligatorio
        label="Cliente Nuevo (Prospecto)",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)

        if empresa is None:
            raise ValueError("Se requiere 'empresa' para inicializar PedidoForm.")

        self.fields['cliente'].required = False
        self.fields['cliente'].queryset = Cliente.objects.filter(empresa=empresa)
        self.fields['prospecto'].queryset = Prospecto.objects.filter(empresa=empresa, estado__in=['PENDIENTE', 'EN_ESTUDIO'])


        
    def clean(self):
        """
        Asegura que solo se seleccione un cliente o un prospecto, pero no ambos,
        y que al menos uno de los dos sea seleccionado.
        """
        cleaned_data = super().clean()
        cliente = cleaned_data.get('cliente')
        prospecto = cleaned_data.get('prospecto')

        if cliente and prospecto:
            raise forms.ValidationError("Por favor, seleccione un cliente existente O un prospecto, no ambos.", code='ambos_seleccionados')
        
        if not cliente and not prospecto:
            raise forms.ValidationError("Debe seleccionar un cliente existente o un prospecto para crear el pedido.", code='ninguno_seleccionado')
            
        return cleaned_data   
        
    

    class Meta:
        # Define el modelo y los campos que se usarán, siguiendo las buenas prácticas.
        model = Pedido
        fields = ['cliente', 'prospecto', 'porcentaje_descuento', 'notas']
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-control'}),
            'porcentaje_descuento': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm', 'step': '1', 'min': '0', 'max': '100'
            }),
            'notas': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
        labels = {
            'porcentaje_descuento': 'Descuento (%)'
        }

# ===================================================================
# FORMULARIO PARA LOS DETALLES DEL PEDIDO (PRODUCTOS)
# ===================================================================
class DetallePedidoForm(forms.ModelForm):
    """
    Formulario para una línea de producto en el pedido.
    Asegura que el producto seleccionado pertenezca a la empresa correcta.
    """
    def __init__(self, *args, **kwargs):
        # 1. Recibimos la empresa, igual que en PedidoForm.
        #    Esto es posible gracias a nuestro BaseDetallePedidoFormSet.
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        """
        Método de validación para asegurar la pertenencia del producto.
        Esta es la corrección de seguridad crítica.
        """
        cleaned_data = super().clean()
        producto = cleaned_data.get("producto")

        if self.empresa is None:
            raise forms.ValidationError("No se pudo verificar la empresa para el detalle del pedido.")

        # 2. Si el producto existe, verificamos que su empresa coincida.
        if producto and producto.empresa != self.empresa:
            raise forms.ValidationError(
                f"El producto '{producto}' no es válido para esta empresa."
            )
        return cleaned_data
    
    cantidad = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'style': 'width: 80px;'})
    )

    class Meta:
        model = DetallePedido
        fields = ['producto', 'cantidad']
        # El producto se maneja como un campo oculto porque la interfaz
        # de la matriz lo asigna. La seguridad está en el método clean().
        widgets = {
            'producto': forms.Select(attrs={'class': 'form-control'})
        }



# ===================================================================
# FORMSET PARA MANEJAR MÚLTIPLES DETALLES DE PEDIDO
# ===================================================================
# 1. Creamos una clase base personalizada para poder "inyectar" la empresa
#    en cada formulario DetallePedidoForm.
class BaseDetallePedidoFormSet(forms.BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        # Pasamos la empresa a cada formulario individual.
        kwargs['empresa'] = self.empresa
        return super()._construct_form(i, **kwargs)

# 2. Usamos la clase base para crear nuestro formset.
DetallePedidoFormSet = forms.inlineformset_factory(
    Pedido,
    DetallePedido,
    form=DetallePedidoForm,
    formset=BaseDetallePedidoFormSet, # ¡Usamos nuestra clase personalizada!
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)

# ===================================================================
# FORMULARIOS AUXILIARES (PARA APROBACIÓN/RECHAZO)
# ===================================================================
class MotivoDecisionForm(forms.Form):
    """
    Formulario simple para capturar un motivo en las vistas de
    aprobación o rechazo de pedidos.
    """
    motivo = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        required=False,
        label="Motivo/Observaciones"
    )