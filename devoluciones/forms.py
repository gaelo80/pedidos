from django import forms

# Ajusta las rutas de importación si es necesario
from clientes.models import Cliente
from .models import DevolucionCliente

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