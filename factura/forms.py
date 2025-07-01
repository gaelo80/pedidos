# factura/forms.py
from django import forms
from .models import EstadoFacturaDespacho

# --- FORMULARIO PARA LA VISTA DE DETALLE ---
class MarcarFacturadoForm(forms.ModelForm):
    """
    Formulario para editar la información de facturación de un despacho.
    """
    # NOTA: Este formulario edita un objeto 'EstadoFacturaDespacho' existente.
    # No necesita ser consciente del inquilino porque no tiene campos que
    # consulten la base de datos (como un ModelChoiceField). La seguridad
    # se garantiza en la vista al obtener el objeto.
    
    referencia_factura_externa = forms.CharField(
        max_length=100,
        required=False,
        label="Referencia de Factura Externa",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: FEV-001234'}),
        help_text="Opcional. Ingrese el número o ID de la factura generada en el sistema contable."
    )

    notas_facturacion = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Anotaciones adicionales sobre esta facturación...'}),
        required=False,
        label="Notas Adicionales de Facturación"
    )

    class Meta:
        model = EstadoFacturaDespacho
        fields = ['referencia_factura_externa', 'notas_facturacion']


# --- FORMULARIOS PARA LOS INFORMES ---

class InformeFacturadosFechaForm(forms.Form):
    """
    Formulario para seleccionar el rango de fechas para el informe
    de despachos facturados.
    """
    fecha_inicio = forms.DateField(
        label="Fecha Inicio",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=True
    )
    fecha_fin = forms.DateField(
        label="Fecha Fin",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=True
    )

    def clean(self):
        cleaned_data = super().clean()
        fecha_inicio = cleaned_data.get("fecha_inicio")
        fecha_fin = cleaned_data.get("fecha_fin")

        if fecha_inicio and fecha_fin and fecha_fin < fecha_inicio:
            raise forms.ValidationError(
                "La fecha de fin no puede ser anterior a la fecha de inicio."
            )
        return cleaned_data
    
class InformeDespachosPorClienteForm(forms.Form):
    """
    Formulario para buscar despachos por cliente.
    """
    termino_busqueda_cliente = forms.CharField(
        label="Buscar Cliente (Nombre o Identificación)",
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese nombre o NIT/Cédula del cliente'})
    )
    
    # --- INICIO DE CAMBIOS MULTI-INQUILINO ---
    # AUNQUE ESTE FORMULARIO NO USA DIRECTAMENTE LA EMPRESA PARA FILTRAR UN QUERYSET,
    # ES UNA BUENA PRÁCTICA PREPARARLO PARA RECIBIR EL ARGUMENTO DESDE LA VISTA.
    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        # Aquí podrías usar 'empresa' en el futuro si añades, por ejemplo,
        # un ModelChoiceField que necesite ser filtrado.
    # --- FIN DE CAMBIOS MULTI-INQUILINO ---


class InformeDespachosPorEstadoForm(forms.Form):
    """
    Formulario para seleccionar el estado de facturación para el informe.
    """
    ESTADO_CHOICES_REPORTE = [('', 'Seleccione un estado')] + EstadoFacturaDespacho.ESTADO_CHOICES
    
    estado = forms.ChoiceField(
        label="Estado de Facturación",
        choices=ESTADO_CHOICES_REPORTE,
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
class InformeDespachosPorPedidoForm(forms.Form):
    """
    Formulario para ingresar el ID del pedido para el informe.
    """
    pedido_id = forms.IntegerField(
        label="ID del Pedido",
        required=True,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese el ID numérico del pedido'}),
        help_text="Ingrese el número identificador del pedido."
    )

    # --- INICIO DE CAMBIOS MULTI-INQUILINO ---
    # MISMA NOTA QUE EN InformeDespachosPorClienteForm.
    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
    # --- FIN DE CAMBIOS MULTI-INQUILINO ---