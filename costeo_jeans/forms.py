from django import forms
from .models import Insumo, Proceso, Confeccionista, Costeo, DetalleInsumo, DetalleProceso, CostoFijo,TarifaConfeccionista
from django.forms import inlineformset_factory
from .models import MovimientoInsumo

# ... (InsumoForm, ProcesoForm, ConfeccionistaForm sin cambios)
class InsumoForm(forms.ModelForm):
    class Meta:
        model = Insumo
        fields = ['nombre', 'unidad_medida', 'costo_unitario', 'stock']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Tela Denim'}),
            'unidad_medida': forms.Select(attrs={'class': 'form-select'}),
            'costo_unitario': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 15.50'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Cantidad actual en inventario'}),
        }
        labels = {
            'nombre': 'Nombre del Insumo',
            'unidad_medida': 'Unidad de Medida',
            'costo_unitario': 'Costo por Unidad ($)',
            'stock': 'Stock Inicial',
        }
class ProcesoForm(forms.ModelForm):
    class Meta:
        model = Proceso
        fields = ['nombre', 'tipo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Lavado a piedra'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'costo': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Costo del proceso'}),
        }
        labels = {
            'nombre': 'Nombre del Proceso',
            'tipo': 'Tipo de Proceso',
            'costo': 'Costo ($)',
        }
class ConfeccionistaForm(forms.ModelForm):
    class Meta:
        model = Confeccionista
        fields = ['nombre', 'documento_identidad', 'telefono', 'direccion', 'aplica_iva']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'documento_identidad': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control'}),
            'aplica_iva': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'nombre': 'Nombre Completo',
            'documento_identidad': 'Documento de Identidad (C.C, NIT, etc.)',
            'telefono': 'Teléfono de Contacto',
            'direccion': 'Dirección',
            'aplica_iva': '¿Factura con IVA?',
        }
        
class TarifaConfeccionistaForm(forms.ModelForm):
    class Meta:
        model = TarifaConfeccionista
        fields = ['confeccionista', 'proceso', 'costo']
        widgets = {
            'confeccionista': forms.Select(attrs={'class': 'form-select'}),
            'proceso': forms.Select(attrs={'class': 'form-select'}),
            'costo': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Costo del servicio sin IVA'}),
        }

    def __init__(self, *args, **kwargs):
        # Filtra los dropdowns para mostrar solo los de la empresa actual
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        if empresa:
            self.fields['confeccionista'].queryset = Confeccionista.objects.filter(empresa=empresa)
            self.fields['proceso'].queryset = Proceso.objects.filter(empresa=empresa)

# --- NUEVO FORMULARIO DE COSTO FIJO ---
class CostoFijoForm(forms.ModelForm):
    class Meta:
        model = CostoFijo
        fields = ['nombre', 'tipo', 'valor', 'incluir_por_defecto']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control'}),
            'incluir_por_defecto': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

# --- Formularios del Asistente (sin cambios) ---
class CosteoModelForm(forms.ModelForm):
    class Meta:
        model = Costeo
        fields = ['referencia', 'cantidad_producida', 'precio_venta_unitario', 'porcentaje_descuento_cliente', 'porcentaje_comision_vendedor']
        widgets = {
            'referencia': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Jean Clásico 101'}),
            'cantidad_producida': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 1000'}),
            'precio_venta_unitario': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 85000.00'}),
            'porcentaje_descuento_cliente': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 10.00'}),
            'porcentaje_comision_vendedor': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 6.00'}),
        }
        labels = {
            'referencia': 'Referencia del Producto',
            'cantidad_producida': 'Cantidad a Producir (Unidades)',
            'precio_venta_unitario': 'Precio de Venta por Unidad ($)',
            'porcentaje_descuento_cliente': '% Descuento Cliente',
            'porcentaje_comision_vendedor': '% Comisión Vendedor',
        }
        
        
        
        
        
        
class DetalleInsumoForm(forms.ModelForm):
    class Meta:
        model = DetalleInsumo       
        fields = ['insumo', 'consumo_unitario']
        widgets = {
            'insumo': forms.Select(attrs={'class': 'form-select insumo-select'}), # Añadimos una clase para JS
            'consumo_unitario': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        if empresa:
            self.fields['insumo'].queryset = Insumo.objects.filter(empresa=empresa)
            
         
         
            
            
class DetalleProcesoForm(forms.ModelForm):
    class Meta:
        model = DetalleProceso
        fields = ['tarifa', 'cantidad']
        widgets = {
            'tarifa': forms.Select(attrs={'class': 'form-select'}),
            # Añadimos 'value': '1' para que las nuevas filas empiecen con 1
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'value': '1'}),
        }

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        if empresa:
            self.fields['tarifa'].queryset = TarifaConfeccionista.objects.filter(empresa=empresa).select_related('proceso', 'confeccionista')

        # Si el formulario no está ligado a un objeto existente (es nuevo y vacío),
        # nos aseguramos de que no tenga un valor inicial que fuerce la validación.
        if not self.instance.pk:
            self.fields['cantidad'].initial = 1
            
class MovimientoInsumoForm(forms.ModelForm):
    class Meta:
        model = MovimientoInsumo
        fields = ['insumo', 'cantidad', 'descripcion']
        widgets = {
            'insumo': forms.Select(attrs={'class': 'form-select'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Cantidad que ingresa'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Factura de compra #123'}),
        }

    def __init__(self, *args, **kwargs):
        # Filtra los insumos para que solo muestre los de la empresa actual
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        if empresa:
            self.fields['insumo'].queryset = Insumo.objects.filter(empresa=empresa)

DetalleInsumoFormSet = inlineformset_factory(Costeo, DetalleInsumo, form=DetalleInsumoForm, extra=1, can_delete=True)
DetalleProcesoFormSet = inlineformset_factory(Costeo, DetalleProceso, form=DetalleProcesoForm, extra=1, can_delete=True)