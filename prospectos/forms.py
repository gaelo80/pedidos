# prospectos/forms.py
from django import forms
from django.forms import inlineformset_factory
from .models import Prospecto, DocumentoAdjunto

class ProspectoForm(forms.ModelForm):
    """
    Formulario para crear o editar la información principal de un Prospecto.
    """
    class Meta:
        model = Prospecto
        fields = [
            'nombre_completo', 'identificacion', 'ciudad',
            'direccion', 'telefono', 'email', 'notas_vendedor'
        ]
        widgets = {
            'nombre_completo': forms.TextInput(attrs={'class': 'form-control'}),
            'identificacion': forms.TextInput(attrs={'class': 'form-control'}),
            'ciudad': forms.Select(attrs={'class': 'form-select'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

class DocumentoAdjuntoForm(forms.ModelForm):
    """
    Formulario para una línea de carga de documento.
    """
    class Meta:
        model = DocumentoAdjunto
        fields = ['tipo_documento', 'archivo']
        widgets = {            
            'tipo_documento': forms.Select(attrs={'class': 'form-select form-select-sm tipo-documento-select'}),
            'archivo': forms.FileInput(attrs={'class': 'form-control form-control-sm'}),
        }


DocumentoFormSet = inlineformset_factory(
    Prospecto,
    DocumentoAdjunto,
    form=DocumentoAdjuntoForm,
    # Muestra 1 formulario vacío por defecto. Es más consistente con el HTML.
    extra=1,
    # Permite que el formset sea válido incluso si no se adjunta ningún documento.
    min_num=0,
    # Desactiva la validación del número mínimo de formularios.
    validate_min=False,
    # Permitir la eliminación es correcto, lo mantenemos.
    can_delete=True,
)

class RechazoForm(forms.Form):
    """
    Formulario simple para capturar el motivo del rechazo en un modal.
    """
    notas_evaluacion = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
        required=True,
        label="Motivo del Rechazo"
    )
    documento_adjunto_rechazo = forms.FileField(
        required=False, # No es obligatorio
        label="Adjuntar Documento (Opcional)",
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )