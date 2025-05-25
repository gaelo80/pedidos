# factura/forms.py
from django import forms
from .models import EstadoFacturaDespacho

class MarcarFacturadoForm(forms.ModelForm):
    """
    Formulario para marcar un despacho como Facturado y añadir
    información relevante del sistema contable externo.
    """
    # Hacemos que la referencia externa sea opcional en el formulario,
    # pero podrías quererla obligatoria dependiendo de tu proceso.
    referencia_factura_externa = forms.CharField(
        max_length=100,
        required=False, # Cambia a True si siempre se debe ingresar
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Podrías añadir más personalizaciones aquí si es necesario,
        # por ejemplo, si el formulario se usa para actualizar y quieres
        # mostrar datos existentes de una manera específica.
class MarcarFacturadoForm(forms.ModelForm):
    """
    Formulario para marcar un despacho como Facturado y añadir
    información relevante del sistema contable externo.
    """
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Podrías añadir más personalizaciones aquí si es necesario


# NUEVO FORMULARIO PARA EL INFORME POR FECHAS
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

        if fecha_inicio and fecha_fin:
            if fecha_fin < fecha_inicio:
                raise forms.ValidationError(
                    "La fecha de fin no puede ser anterior a la fecha de inicio."
                )
        return cleaned_data
    
class InformeDespachosPorClienteForm(forms.Form):
    """
    Formulario para buscar despachos por cliente.
    Permite buscar por nombre o identificación del cliente.
    """
    termino_busqueda_cliente = forms.CharField(
        label="Buscar Cliente (Nombre o Identificación)",
        max_length=100,
        required=True, # Se requiere un término para buscar
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese nombre o NIT/Cédula del cliente'})
    )
    
    ESTADO_CHOICES_REPORTE = [('', 'Cualquier Estado')] + EstadoFacturaDespacho.ESTADO_CHOICES
    estado_factura = forms.ChoiceField(
         label="Estado de Facturación",
         choices=ESTADO_CHOICES_REPORTE,
         required=False,
         widget=forms.Select(attrs={'class': 'form-select'})
     )


class InformeDespachosPorEstadoForm(forms.Form):
    """
    Formulario para seleccionar el estado de facturación para el informe.
    """
    # Usamos los choices directamente del modelo EstadoFacturaDespacho
    # Añadimos una opción para "Todos" si se quisiera, aunque el requerimiento es por estado específico.
    # Si solo quieres "Facturado" y "Por Facturar", puedes hardcodear esas opciones.
    ESTADO_CHOICES_REPORTE = [('', 'Seleccione un estado')] + EstadoFacturaDespacho.ESTADO_CHOICES
    
    estado = forms.ChoiceField(
        label="Estado de Facturación",
        choices=ESTADO_CHOICES_REPORTE,
        required=True, # Se requiere seleccionar un estado
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