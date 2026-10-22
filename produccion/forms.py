from django import forms
from productos.models import ReferenciaColor
from .models import DefectoCalidad, EtapaProduccion, OrdenProduccion, TallerExterno


class EtapaProduccionForm(forms.ModelForm):
    class Meta:
        model = EtapaProduccion
        fields = ['nombre', 'orden', 'es_externa', 'dias_alerta', 'es_control_calidad', 'es_ingreso_bodega', 'activa']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Bordado'}),
            'orden': forms.NumberInput(attrs={'class': 'form-control'}),
            'es_externa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'dias_alerta': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'es_control_calidad': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'es_ingreso_bodega': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'es_externa': '¿La hace un taller externo?',
            'dias_alerta': 'Días antes de marcar como atrasada',
            'es_control_calidad': '¿Aquí se clasifican buenas/segunda/tercera?',
            'es_ingreso_bodega': '¿Aquí se hace el ingreso real a bodega?',
        }

    def clean(self):
        datos = super().clean()
        if datos.get('es_externa') and (datos.get('es_control_calidad') or datos.get('es_ingreso_bodega')):
            raise forms.ValidationError("Una etapa externa no puede ser también de Control de Calidad ni de Ingreso a Bodega.")
        return datos


class TallerExternoForm(forms.ModelForm):
    class Meta:
        model = TallerExterno
        fields = ['nombre', 'nit', 'telefono', 'direccion', 'contacto', 'etapas', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'nit': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control'}),
            'contacto': forms.TextInput(attrs={'class': 'form-control'}),
            'etapas': forms.CheckboxSelectMultiple(),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, empresa=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['etapas'].queryset = EtapaProduccion.objects.filter(empresa=empresa, es_externa=True, activa=True)
        self.fields['etapas'].help_text = "Etapas externas que atiende este taller."


class OrdenProduccionForm(forms.ModelForm):
    class Meta:
        model = OrdenProduccion
        fields = ['referencia_color', 'permitir_venta_sin_stock', 'fecha_estimada_entrega', 'notas']
        widgets = {
            'referencia_color': forms.Select(attrs={'class': 'form-select select2-referencia-color', 'data-placeholder': 'Buscar referencia y color en el catálogo...'}),
            'permitir_venta_sin_stock': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'fecha_estimada_entrega': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
        labels = {
            'referencia_color': 'Referencia del catálogo',
            'permitir_venta_sin_stock': '¿Se puede vender mientras está en producción?',
        }

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        self.fields['fecha_estimada_entrega'].required = False
        if empresa:
            self.fields['referencia_color'].queryset = ReferenciaColor.objects.filter(empresa=empresa).order_by('referencia_base', 'color')
        else:
            self.fields['referencia_color'].queryset = ReferenciaColor.objects.none()


_num = lambda **attrs: forms.NumberInput(attrs={'class': 'form-control', 'min': 0, **attrs})


class CorteForm(forms.Form):
    cantidad = forms.IntegerField(min_value=1, label="Unidades cortadas", widget=_num())
    observaciones = forms.CharField(required=False, label="Novedades", widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))


class PasarPartidaForm(forms.Form):
    cantidad = forms.IntegerField(min_value=0, label="Unidades que pasan a la siguiente etapa", widget=_num())
    perdidas = forms.IntegerField(min_value=0, required=False, initial=0, label="Unidades perdidas (opcional)", widget=_num())
    motivo_perdida = forms.CharField(required=False, label="Motivo de la pérdida", widget=forms.TextInput(attrs={'class': 'form-control'}))
    observaciones = forms.CharField(required=False, label="Novedades", widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))


class CalidadForm(forms.Form):
    buenas = forms.IntegerField(min_value=0, label="Buenas", widget=_num())
    segundas = forms.IntegerField(min_value=0, required=False, initial=0, label="Segundas", widget=_num())
    terceras = forms.IntegerField(min_value=0, required=False, initial=0, label="Terceras", widget=_num())
    causa = forms.ChoiceField(
        required=False, label="Causa del defecto",
        choices=[('', '---------')] + list(DefectoCalidad.Causa.choices),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    etapa_causa = forms.ModelChoiceField(
        required=False, queryset=EtapaProduccion.objects.none(), label="Etapa donde se originó",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    perdidas = forms.IntegerField(min_value=0, required=False, initial=0, label="Unidades perdidas (opcional)", widget=_num())
    motivo_perdida = forms.CharField(required=False, label="Motivo de la pérdida", widget=forms.TextInput(attrs={'class': 'form-control'}))
    observaciones = forms.CharField(required=False, label="Novedades", widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))

    def __init__(self, *args, empresa=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['etapa_causa'].queryset = EtapaProduccion.objects.filter(empresa=empresa, activa=True)


class CorreccionForm(forms.Form):
    cantidad = forms.IntegerField(label="Corrección (+ suma, − resta)", widget=forms.NumberInput(attrs={'class': 'form-control'}))
    motivo = forms.CharField(label="Motivo", widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))


class DecisionDefectoForm(forms.Form):
    decision = forms.ChoiceField(
        choices=[c for c in DefectoCalidad.Decision.choices if c[0] != DefectoCalidad.Decision.PENDIENTE],
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    taller = forms.ModelChoiceField(
        required=False, queryset=TallerExterno.objects.none(), label="Taller al que se descuenta",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    motivo = forms.CharField(label="Motivo (queda registrado y aparece en el informe del taller)", widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))

    def __init__(self, *args, empresa=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['taller'].queryset = TallerExterno.objects.filter(empresa=empresa)
