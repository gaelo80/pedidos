# puntoventa/forms.py
from decimal import Decimal
from django import forms
from bodega.models import Bodega
from .models import TurnoCaja


class AbrirTurnoForm(forms.Form):
    bodega = forms.ModelChoiceField(
        queryset=Bodega.objects.none(),
        label="Bodega / Caja de Punto de Venta",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    saldo_inicial = forms.DecimalField(
        label="Monto Inicial en Caja",
        min_value=Decimal('0.00'),
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'})
    )

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        if empresa:
            bodegas_disponibles = Bodega.objects.filter(
                empresa=empresa, activa=True, tipo=Bodega.TipoBodega.PUNTO_VENTA
            ).exclude(
                turnos_caja__estado=TurnoCaja.EstadoTurno.ABIERTO
            ).order_by('orden', 'nombre')
            self.fields['bodega'].queryset = bodegas_disponibles
        else:
            self.fields['bodega'].queryset = Bodega.objects.none()


class CerrarTurnoForm(forms.Form):
    saldo_final_contado = forms.DecimalField(
        label="Efectivo Contado en Caja",
        min_value=Decimal('0.00'),
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-lg', 'step': '0.01', 'placeholder': '0.00'})
    )
