# recaudos/forms.py
from django import forms
from django.core.exceptions import ValidationError
from .models import Recaudo, Consignacion
from clientes.models import Cliente
from decimal import Decimal

class RecaudoForm(forms.ModelForm):
    """
    Formulario para que un vendedor cree un nuevo recaudo.
    """
    # El campo cliente se llenará dinámicamente en la vista
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.none(),
        label="Cliente",
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Selecciona el cliente que realizó el pago."
    )

    class Meta:
        model = Recaudo
        fields = ['cliente', 'monto_recibido', 'concepto']
        widgets = {
            'monto_recibido': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00', 'step': '0.01'}),
            'concepto': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Detalle de las facturas o pagos realizados por el cliente...'}),
        }
        labels = {
            'monto_recibido': 'Monto Recibido en Efectivo',
            'concepto': 'Concepto del Pago',
        }

    def __init__(self, *args, **kwargs):
        # Recibimos la empresa desde la vista para filtrar los clientes
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        if empresa:
            self.fields['cliente'].queryset = Cliente.objects.filter(empresa=empresa, activo=True).order_by('nombre_completo')
            self.fields['cliente'].empty_label = "-- Selecciona un cliente --"

class ConsignacionForm(forms.ModelForm):
    """
    Formulario para que un vendedor registre una consignación,
    agrupando recaudos que tiene en su poder.
    """
    # Campo para seleccionar qué recaudos se incluyen en esta consignación
    recaudos = forms.ModelMultipleChoiceField(
        queryset=Recaudo.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label="Selecciona los Recaudos a Incluir en este Depósito",
        required=True
    )

    class Meta:
        model = Consignacion
        fields = ['fecha_consignacion', 'monto_total', 'numero_referencia', 'comprobante_adjunto', 'recaudos']
        widgets = {
            'fecha_consignacion': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'monto_total': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00', 'readonly': 'readonly'}),
            'numero_referencia': forms.TextInput(attrs={'class': 'form-control'}),
            'comprobante_adjunto': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'fecha_consignacion': 'Fecha del Depósito',
            'monto_total': 'Monto Total del Depósito (Calculado automáticamente)',
            'numero_referencia': 'Número de Referencia o Transacción',
            'comprobante_adjunto': 'Adjuntar Comprobante (Foto o PDF)',
        }
    
    def __init__(self, *args, **kwargs):
        # Recibimos el vendedor y la empresa para filtrar los recaudos pendientes
        vendedor = kwargs.pop('vendedor', None)
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        if vendedor and empresa:
            queryset_recaudos = Recaudo.objects.filter(
                empresa=empresa,
                vendedor=vendedor,
                estado=Recaudo.Estado.EN_MANOS_DEL_VENDEDOR
            )
            self.fields['recaudos'].queryset = queryset_recaudos
            
            # Si no hay recaudos pendientes, lo indicamos.
            if not queryset_recaudos.exists():
                 self.fields['recaudos'].help_text = "No tienes recaudos pendientes para consignar."


    def clean_recaudos(self):
        recaudos_seleccionados = self.cleaned_data.get('recaudos')
        if not recaudos_seleccionados:
            raise ValidationError("Debes seleccionar al menos un recaudo para incluir en la consignación.")
        return recaudos_seleccionados

    def clean(self):
        cleaned_data = super().clean()
        # La validación del monto total se hará en la vista,
        # ya que el campo es de solo lectura y se calcula con JS.
        # Esto evita errores si el usuario no tiene JS habilitado.
        return cleaned_data