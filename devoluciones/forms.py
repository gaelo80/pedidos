from django import forms
from productos.models import Producto
from .models import DevolucionCliente, DetalleDevolucion
from decimal import Decimal
from django.utils import timezone
from clientes.models import Cliente


class DevolucionClienteForm(forms.ModelForm):
    """Formulario para los datos generales de la devolución."""

    # Usar ModelChoiceField para permitir búsqueda fácil (luego con Select2)
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.order_by('nombre_completo'),
        label="Cliente que Devuelve", # Etiqueta que se mostrará
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_cliente_devolucion'}) # ID único
    )
    # Pedido original es opcional y puede ser difícil de buscar sin Select2-AJAX
    # Por ahora, un campo simple o lo excluimos y lo añadimos luego.
    # pedido_original = forms.ModelChoiceField(...)

    motivo = forms.CharField(
        label="Motivo General de la Devolución",
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        required=False
    )

    class Meta:
        model = DevolucionCliente
        # Campos a mostrar en el formulario de cabecera
        # Excluimos fecha_hora y usuario (se asignan en la vista)
        # Excluimos pedido_original por ahora para simplificar
        fields = ['cliente', 'motivo']


# --- NUEVO: Formulario para UNA línea de Detalle de Devolución ---
class DetalleDevolucionForm(forms.ModelForm):
    """Formulario para un producto devuelto."""

    # Usaremos Select2 con AJAX para buscar producto aquí
    # Por ahora, un ModelChoiceField simple, lo mejoraremos con JS
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.filter(activo=True).order_by('referencia', 'nombre', 'color', 'talla'),
        label="Producto Devuelto",
        widget=forms.Select(attrs={'class': 'form-control producto-select-devolucion'}) # Clase para JS
    )

    cantidad = forms.IntegerField(
        label="Cantidad Devuelta",
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'style': 'width: 80px;'})
    )

    # Usar el campo Choice del modelo directamente
    # estado_producto se renderizará como un Select por defecto
    class Meta:
        model = DetalleDevolucion
        fields = ['producto', 'cantidad', 'estado_producto']
        widgets = {
            'estado_producto': forms.Select(attrs={'class': 'form-select form-select-sm'})
        }


DetalleDevolucionFormSet = forms.inlineformset_factory(
    parent_model=DevolucionCliente, # El modelo padre
    model=DetalleDevolucion,       # El modelo de los detalles
    form=DetalleDevolucionForm,    # El formulario a usar para cada detalle
    extra=0,                       # Cuántos formularios extra mostrar por defecto (para añadir nuevos)
    can_delete=True,              # Poner True si quieres permitir borrar líneas al editar
    min_num=1,                     # Requerir al menos 1 detalle
    validate_min=True,             # Validar que se envíe al menos min_num
)