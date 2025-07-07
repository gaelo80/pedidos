# En cartera/forms.py
from django import forms
from .models import PerfilImportacionCartera, DocumentoCartera # <--- AÑADE DocumentoCartera

class UploadCarteraFileForm(forms.Form):
    # El campo ahora será una lista de perfiles disponibles para la empresa
    perfil_importacion = forms.ModelChoiceField(
        queryset=PerfilImportacionCartera.objects.none(), # Se llenará dinámicamente
        label="Seleccionar Perfil de Importación",
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="-- Elige un formato de archivo --",
        required=True
    )
    
    # --- CAMBIO CLAVE: AÑADIMOS EL SELECTOR DE TIPO DE DOCUMENTO ---
    tipo_documento = forms.ChoiceField(
        choices=DocumentoCartera.TIPO_DOCUMENTO_CHOICES,
        label="Tipo de Documento a Importar",
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=True
    )

    archivo_excel = forms.FileField(
        label="Seleccionar Archivo Excel (.xlsx)", 
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.xlsx'}),
        required=True
    )

    def __init__(self, *args, **kwargs):
        # Necesitamos la empresa para saber qué perfiles mostrar
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)

        if empresa:
            self.fields['perfil_importacion'].queryset = PerfilImportacionCartera.objects.filter(empresa=empresa)
            # Aseguramos que el campo tenga una opción por defecto si no hay perfiles
            if not self.fields['perfil_importacion'].queryset.exists():
                self.fields['perfil_importacion'].empty_label = "-- No hay perfiles configurados para esta empresa --"
                self.fields['perfil_importacion'].widget.attrs['disabled'] = True
