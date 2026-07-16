from django import forms
from productos.models import Producto
from .models import IngresoBodega, DetalleIngresoBodega
from .models import SalidaInternaCabecera, SalidaInternaDetalle
from django.utils import timezone
from django.forms import BaseInlineFormSet
from django.forms import inlineformset_factory
from .models import CambioProducto
from .models import Bodega, AccesoBodega, TrasladoBodega
from django.contrib.auth import get_user_model


class IngresoBodegaForm(forms.ModelForm):
    """Formulario para los datos generales de un ingreso."""
    proveedor_info = forms.CharField(
        label="Información Proveedor/Origen",
        max_length=200,
        required=False, # O True si siempre debes saber de dónde viene
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    documento_referencia = forms.CharField(
        label="Documento Referencia (Factura Compra, Remisión, etc.)",
        max_length=100,
        required=False, # O True si siempre necesitas una referencia
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    notas = forms.CharField(
        label="Notas Adicionales",
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        required=False
    )

    class Meta:
        model = IngresoBodega
        # Campos a mostrar en el formulario de cabecera
        # Excluimos fecha_hora y usuario (se asignan en la vista)
        fields = ['bodega', 'proveedor_info', 'documento_referencia', 'notas']
        widgets = {
            'bodega': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        """
        Este método se personaliza para manejar argumentos extra enviados desde la vista.
        """
        empresa = kwargs.pop('empresa', None)

        super().__init__(*args, **kwargs)

        if empresa:
            self.fields['bodega'].queryset = Bodega.objects.filter(empresa=empresa, activa=True).order_by('orden', 'nombre')
            if not self.instance.pk and not self.initial.get('bodega'):
                bodega_principal = Bodega.objects.filter(empresa=empresa, es_principal=True).first()
                if bodega_principal:
                    self.initial['bodega'] = bodega_principal.pk
        else:
            self.fields['bodega'].queryset = Bodega.objects.none()


# --- NUEVO: Formulario para UNA línea de Detalle de Ingreso ---
class DetalleIngresoBodegaForm(forms.ModelForm):
    """Formulario para un producto ingresado a bodega."""

    # Usaremos Select2 con AJAX para buscar producto
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.filter(activo=True).order_by('referencia', 'nombre', 'color', 'talla'),
        label="Producto Ingresado",
        widget=forms.Select(attrs={'class': 'form-control producto-select-ingreso'}) # Clase para JS
    )

    cantidad = forms.IntegerField(
        label="Cantidad Ingresada",
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'style': 'width: 80px;'})
    )

    # costo_unitario es opcional en el modelo, lo hacemos no requerido aquí también
    costo_unitario = forms.DecimalField(
        label="Costo Unitario",
        max_digits=10,
        decimal_places=2,
        required=False, # El costo puede no saberse o registrarse siempre
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01', 'placeholder': 'Opcional'})
    )
    
    class Meta:
        model = DetalleIngresoBodega
        fields = ['producto', 'cantidad', 'costo_unitario']
        
    def __init__(self, *args, **kwargs):
            # 1. Extraemos y eliminamos 'empresa' de los argumentos para evitar el TypeError.
        empresa = kwargs.pop('empresa', None)
            
            # 2. Llamamos al constructor padre con los kwargs ya "limpios".
        super().__init__(*args, **kwargs)
            
            # 3. Usamos la 'empresa' para filtrar el campo de productos.
            #    ¡Este es un paso de seguridad muy importante!
        if empresa:
            self.fields['producto'].queryset = Producto.objects.filter(
                empresa=empresa, 
                activo=True
            ).order_by('referencia', 'nombre')
        else:
                # Como medida de seguridad, si no se proporciona una empresa, no mostramos ningún producto.
            self.fields['producto'].queryset = Producto.objects.none()


# --- NUEVO: FormSet para manejar MÚLTIPLES Detalles de Ingreso ---
DetalleIngresoFormSet = forms.inlineformset_factory(
    parent_model=IngresoBodega,      # Modelo padre
    model=DetalleIngresoBodega,    # Modelo detalle
    form=DetalleIngresoBodegaForm, # Formulario para cada detalle
    extra=3,                       # Mostrar 3 formularios extra por defecto (ajústalo)
    can_delete=False,              # No permitir borrar líneas en este formulario simple
    min_num=1,                     # Requerir al menos 1 producto ingresado
    validate_min=True,
)


class InfoGeneralConteoForm(forms.Form):
    fecha_actualizacion_stock = forms.DateField(
        label="Fecha Efectiva del Ajuste",
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'DD/MM/AAAA'}),
        initial=timezone.now().date(),
        input_formats=['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']
    )
    motivo_conteo = forms.CharField(
        label="Motivo del Conteo/Ajuste",
        max_length=150,
        required=False, # Hazlo requerido si siempre debe haber un motivo
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Ej: Conteo cíclico Bodega A'})
    )
    revisado_con = forms.CharField(
        label="Revisado/Contado Con",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Nombre de la persona que verificó'})
    )
    notas_generales = forms.CharField(
        label="Notas Generales Adicionales",
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control form-control-sm'})
    )
    
    
class SalidaInternaCabeceraForm(forms.ModelForm):
    class Meta:
        model = SalidaInternaCabecera
        fields = [
            'bodega_origen', 'tipo_salida', 'destino_descripcion',
            'documento_referencia_externo', 'fecha_prevista_devolucion',
            'observaciones_salida'
        ]
        widgets = {
            'bodega_origen': forms.Select(attrs={'class': 'form-select'}),
            'tipo_salida': forms.Select(attrs={'class': 'form-select'}),
            'destino_descripcion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Vendedor Juan Pérez, Tienda Centro'}),
            'documento_referencia_externo': forms.TextInput(attrs={'class': 'form-control'}),
            'fecha_prevista_devolucion': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'observaciones_salida': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)

        if empresa:
            self.fields['bodega_origen'].queryset = Bodega.objects.filter(empresa=empresa, activa=True).order_by('orden', 'nombre')
            if not self.instance.pk and not self.initial.get('bodega_origen'):
                bodega_principal = Bodega.objects.filter(empresa=empresa, es_principal=True).first()
                if bodega_principal:
                    self.initial['bodega_origen'] = bodega_principal.pk
        else:
            self.fields['bodega_origen'].queryset = Bodega.objects.none()

class SalidaInternaDetalleForm(forms.ModelForm):
    class Meta:
        model = SalidaInternaDetalle
        fields = ['producto', 'cantidad_despachada', 'observaciones_detalle']
        widgets = {
            'producto': forms.Select(attrs={'class': 'form-select select2-producto'}), # Para Select2 si lo usas
            'cantidad_despachada': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'observaciones_detalle': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
        }

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None) # Extraer el kwarg 'empresa'
        super().__init__(*args, **kwargs)
        
        if empresa:
            # Filtrar productos activos de la empresa actual para el dropdown
            self.fields['producto'].queryset = Producto.objects.filter(
                empresa=empresa,
                activo=True
            ).order_by('referencia', 'nombre')
        else:
            self.fields['producto'].queryset = Producto.objects.none()


class BaseDetalleSalidaInternaFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        productos_a_despachar = {}
        for form in self.forms:
            if not form.is_valid() or not form.cleaned_data or form.cleaned_data.get('DELETE'):
                continue

            producto = form.cleaned_data.get('producto')
            cantidad = form.cleaned_data.get('cantidad_despachada')

            if not producto or not cantidad: continue

            if cantidad <= 0:
                form.add_error('cantidad_despachada', 'La cantidad debe ser mayor a cero.')
                continue

            if producto in productos_a_despachar:
                productos_a_despachar[producto] += cantidad
            else:
                productos_a_despachar[producto] = cantidad

        for producto, cantidad_total in productos_a_despachar.items():
            if cantidad_total > producto.stock_actual:
                raise forms.ValidationError(
                    f"Stock insuficiente para '{producto}'. Solicitado: {cantidad_total}, Disponible: {producto.stock_actual}"
                )

# Reemplaza tu DetalleSalidaInternaFormSet existente con esto:
DetalleSalidaInternaFormSet = forms.inlineformset_factory(
    SalidaInternaCabecera,
    SalidaInternaDetalle,
    form=SalidaInternaDetalleForm,
    formset=BaseDetalleSalidaInternaFormSet, # Aquí se usa la nueva clase
    fk_name='cabecera_salida',  # Especificar explícitamente el nombre del FK
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True
)

class ImportarConteoForm(forms.Form):
    archivo_conteo = forms.FileField(
        label="Seleccionar Archivo (.xlsx, .csv)",
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.xlsx,.csv'})
    )
    

class DetalleIngresoBodegaForm(forms.ModelForm):
    class Meta:
        model = DetalleIngresoBodega
        fields = ['producto', 'cantidad', 'costo_unitario']

DetalleIngresoBodegaFormSet = inlineformset_factory(
    IngresoBodega,
    DetalleIngresoBodega,
    form=DetalleIngresoBodegaForm,
    extra=1, # Permite agregar una fila vacía por defecto
    can_delete=True # Habilita la opción de eliminar detalles
)

class DetalleIngresoModificarForm(forms.ModelForm):
    cantidad = forms.IntegerField(
        label="Cantidad",
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'style': 'width: 80px;'})
    )
    costo_unitario = forms.DecimalField(
        label="Costo Unitario",
        max_digits=10,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Opcional'})
    )
    
    class Meta:
        model = DetalleIngresoBodega
        fields = ['cantidad', 'costo_unitario']

# Nuevo formset para modificar solo los detalles
DetalleIngresoModificarFormSet = inlineformset_factory(
    parent_model=IngresoBodega,
    model=DetalleIngresoBodega,
    form=DetalleIngresoModificarForm, # Usamos el nuevo formulario
    extra=0, # No agregamos campos extra
    can_delete=False, # No se puede eliminar
    min_num=1,
    validate_min=True,
)


class CambioProductoForm(forms.ModelForm):
    class Meta:
        model = CambioProducto
        fields = [
            'producto_entrante', 'cantidad_entrante',
            'producto_saliente', 'cantidad_saliente',
            'motivo', 'documento_referencia'
        ]
        widgets = {
            'motivo': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        # Tomamos el 'tenant' (empresa) que pasaremos desde la vista
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        if not empresa:
            # Si no hay empresa, no mostramos productos para evitar fugas de datos
            self.fields['producto_entrante'].queryset = Producto.objects.none()
            self.fields['producto_saliente'].queryset = Producto.objects.none()
            return
        
        # Filtramos los QuerySets para mostrar solo productos de la empresa actual
        productos_empresa = Producto.objects.filter(empresa=empresa, activo=True)
        self.fields['producto_entrante'].queryset = productos_empresa
        self.fields['producto_saliente'].queryset = productos_empresa

    def clean(self):
        cleaned_data = super().clean()
        producto_saliente = cleaned_data.get('producto_saliente')
        cantidad_saliente = cleaned_data.get('cantidad_saliente')

        if producto_saliente and cantidad_saliente:
            # Validación CRÍTICA: Asegurarse de que hay suficiente stock disponible
            if producto_saliente.stock_actual < cantidad_saliente:
                # Usamos un error de formulario para notificar al usuario
                self.add_error('cantidad_saliente', forms.ValidationError(
                    f"No hay stock suficiente para '{producto_saliente}'. "
                    f"Stock actual: {producto_saliente.stock_actual}, se solicitan: {cantidad_saliente}."
                ))
        return cleaned_data


class BodegaForm(forms.ModelForm):
    class Meta:
        model = Bodega
        fields = [
            'nombre', 'codigo', 'tipo', 'es_principal', 'activa',
            'requiere_confirmacion_recepcion',
            'disponible_venta_estandar', 'disponible_venta_online', 'disponible_venta_web',
            'direccion', 'notas', 'orden', 'responsable',
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: PRINCIPAL, SALDOS-01'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control'}),
            'notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'orden': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'responsable': forms.Select(attrs={'class': 'form-select'}),
            'es_principal': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'requiere_confirmacion_recepcion': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'disponible_venta_estandar': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'disponible_venta_online': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'disponible_venta_web': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        self.empresa = empresa
        User = get_user_model()
        if empresa:
            self.fields['responsable'].queryset = User.objects.filter(empresa=empresa, is_active=True).order_by('username')
        else:
            self.fields['responsable'].queryset = User.objects.none()
        self.fields['responsable'].required = False

    def clean_es_principal(self):
        es_principal = self.cleaned_data.get('es_principal')
        if es_principal and self.empresa:
            ya_existe_otra_principal = Bodega.objects.filter(
                empresa=self.empresa, es_principal=True
            ).exclude(pk=self.instance.pk).exists()
            if ya_existe_otra_principal:
                raise forms.ValidationError(
                    "Ya existe otra Bodega Principal para esta empresa. "
                    "Primero quítale la marca de 'Principal' a la actual antes de asignarla aquí."
                )
        return es_principal


class AccesoBodegaForm(forms.ModelForm):
    class Meta:
        model = AccesoBodega
        fields = ['usuario', 'bodega', 'nivel']
        widgets = {
            'usuario': forms.Select(attrs={'class': 'form-select'}),
            'bodega': forms.Select(attrs={'class': 'form-select'}),
            'nivel': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        User = get_user_model()
        if empresa:
            self.fields['usuario'].queryset = User.objects.filter(empresa=empresa, is_active=True).order_by('username')
            self.fields['bodega'].queryset = Bodega.objects.filter(empresa=empresa).order_by('orden', 'nombre')
        else:
            self.fields['usuario'].queryset = User.objects.none()
            self.fields['bodega'].queryset = Bodega.objects.none()


class TrasladoBodegaForm(forms.ModelForm):
    class Meta:
        model = TrasladoBodega
        fields = ['bodega_origen', 'bodega_destino', 'documento_referencia', 'notas']
        widgets = {
            'bodega_origen': forms.Select(attrs={'class': 'form-select'}),
            'bodega_destino': forms.Select(attrs={'class': 'form-select'}),
            'documento_referencia': forms.TextInput(attrs={'class': 'form-control'}),
            'notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        if empresa:
            qs = Bodega.objects.filter(empresa=empresa, activa=True).order_by('orden', 'nombre')
            self.fields['bodega_origen'].queryset = qs
            self.fields['bodega_destino'].queryset = qs
        else:
            self.fields['bodega_origen'].queryset = Bodega.objects.none()
            self.fields['bodega_destino'].queryset = Bodega.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        origen = cleaned_data.get('bodega_origen')
        destino = cleaned_data.get('bodega_destino')
        if origen and destino and origen.pk == destino.pk:
            self.add_error('bodega_destino', "La bodega de destino debe ser diferente a la de origen.")
        return cleaned_data