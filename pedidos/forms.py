from django import forms
from productos.models import Producto
from decimal import Decimal
from django.utils import timezone
from clientes.models import Cliente
from pedidos.models import Pedido, DetallePedido


class PedidoForm(forms.ModelForm):
    """Formulario para la cabecera del Pedido (cliente, descuento, notas)."""

    # Definir Cliente (ya lo tenías)
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.order_by('nombre_completo'),
        widget=forms.Select(attrs={'class': 'form-control'}), # Select2 lo reemplazará
        label="Cliente"
    )
    
    referencia = forms.CharField(
        # Solo la opción inicial vacía/placeholder
        #choices=[('', '-- Selecciona Referencia --')],
        required=False, # O False, según necesites que sea obligatorio elegir una ref para añadir productos
        label="Referencia", # Etiqueta que se mostrará
        widget=forms.Select(attrs={
            'class': 'form-select', # Clase para estilo Bootstrap
            'id': 'id_referencia'   # ID ESPECÍFICO que usará tu JavaScript para Select2
        })
    )

    # Definir Descuento (como lo teníamos antes)

    porcentaje_descuento = forms.IntegerField(
        #max_digits=3,       # Máximo 5 dígitos en total (ej: 100.00)
        #decimal_places=0,   # Permitir 0 decimales
        required=False,     # No es obligatorio poner descuento
        initial=Decimal('0'), # Valor inicial 0%
        min_value=Decimal('0'),    # Mínimo
        max_value=Decimal('100'),  # Máximo
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-sm', # Campo más pequeño
            'step': '1', # Permite pasos decimales pequeños
            'id': 'id_porcentaje_descuento' # Asegurar ID si es necesario
        }),
           label="Descuento (%)",
        help_text=""
    )



    # Definir Notas (como lo tenías antes)
    notas = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'id':'id_notas'}), # Aseguramos ID para CSS
        required=False,
       
    )

    class Meta:
        model = Pedido
        fields = ['cliente', 'porcentaje_descuento', 'notas']
        
        
        
class DetallePedidoForm(forms.ModelForm):
    """Formulario para un producto en el pedido."""
    #producto = forms.ModelChoiceField(
        #queryset=Producto.objects.filter(activo=True).order_by('referencia', 'nombre', 'color', 'talla'),
        #widget=forms.Select(attrs={'class': 'form-control'})
    #)
    cantidad = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'style': 'width: 80px;'})
    )

    class Meta:
        model = DetallePedido
        fields = ['producto', 'cantidad']


# --- DetallePedidoFormSet (sin cambios necesarios aquí) ---
DetallePedidoFormSet = forms.inlineformset_factory(
    Pedido,
    DetallePedido,
    form=DetallePedidoForm,
    extra=1,
    can_delete=False,
    min_num=1,
    validate_min=True,
)

class MotivoDecisionForm(forms.Form):
    motivo = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        required=False, # Puede ser opcional si solo se aprueba
        label="Motivo/Observaciones"
    )

# Opcional: Un formulario más específico si quieres actualizar el estado también
class DecisionPedidoForm(forms.ModelForm):
    motivo_decision = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        required=False, # O True si el motivo es siempre obligatorio al rechazar
        label="Motivo/Observaciones para esta etapa"
    )

    class Meta:
        model = Pedido
        fields = ['motivo_decision'] # Un campo temporal, lo mapearemos al campo correcto en la vista