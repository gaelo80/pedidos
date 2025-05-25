# cartera/forms.py
from django import forms

class UploadCarteraFileForm(forms.Form):
    TIPO_ARCHIVO_CHOICES = [
        ('LF', 'Archivo LF (Facturas Oficiales)'),
        ('FYN', 'Archivo FYN (Remisiones)'),
    ]
    # Campo para seleccionar qué tipo de archivo se está subiendo
    tipo_archivo = forms.ChoiceField(
        choices=TIPO_ARCHIVO_CHOICES, 
        label="Tipo de Archivo",
        widget=forms.Select(attrs={'class': 'form-select mb-3'}) # Añadida clase para Bootstrap
    )
    # Campo para subir el archivo (solo acepta Excel)
    archivo_excel = forms.FileField(
        label="Seleccionar Archivo Excel (.xlsx)", 
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.xlsx'})
    )
