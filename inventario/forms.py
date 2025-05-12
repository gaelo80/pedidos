# inventario/forms.py
from django import forms
from .models import Pedido, Cliente, DetallePedido, Producto, DevolucionCliente, DetalleDevolucion, IngresoBodega, DetalleIngresoBodega
from decimal import Decimal
from django.utils import timezone

class PedidoForm(forms.ModelForm):
    """Formulario para la cabecera del Pedido (cliente, descuento, notas)."""

    # Definir Cliente (ya lo tenías)
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.order_by('nombre_completo'),
        widget=forms.Select(attrs={'class': 'form-control'}), # Select2 lo reemplazará
        label="Cliente"
    )
    
    referencia = forms.CharField(
        # Solo la opción inicial vacía/placeholder
        #choices=[('', '-- Selecciona Referencia --')],
        required=False, # O False, según necesites que sea obligatorio elegir una ref para añadir productos
        label="Referencia", # Etiqueta que se mostrará
        widget=forms.Select(attrs={
            'class': 'form-select', # Clase para estilo Bootstrap
            'id': 'id_referencia'   # ID ESPECÍFICO que usará tu JavaScript para Select2
        })
    )

    # Definir Descuento (como lo teníamos antes)

    porcentaje_descuento = forms.IntegerField(
        #max_digits=3,       # Máximo 5 dígitos en total (ej: 100.00)
        #decimal_places=0,   # Permitir 0 decimales
        required=False,     # No es obligatorio poner descuento
        initial=Decimal('0'), # Valor inicial 0%
        min_value=Decimal('0'),    # Mínimo
        max_value=Decimal('100'),  # Máximo
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-sm', # Campo más pequeño
            'step': '1', # Permite pasos decimales pequeños
            'id': 'id_porcentaje_descuento' # Asegurar ID si es necesario
        }),
           label="Descuento (%)",
        help_text=""
    )



    # Definir Notas (como lo tenías antes)
    notas = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'id':'id_notas'}), # Aseguramos ID para CSS
        required=False,
       
    )

    class Meta:
        model = Pedido
        # --- CORREGIDO: Incluir los tres campos ---
        fields = ['cliente', 'porcentaje_descuento', 'notas']
        
        
        
class UploadCarteraFileForm(forms.Form):
    TIPO_ARCHIVO_CHOICES = [
        ('LF', 'Archivo LF (Facturas Oficiales)'),
        ('FYN', 'Archivo FYN (Remisiones)'),
    ]
    # Campo para seleccionar qué tipo de archivo se está subiendo
    tipo_archivo = forms.ChoiceField(choices=TIPO_ARCHIVO_CHOICES, 
                                     label="Tipo de Archivo",
                                     widget=forms.Select(attrs={'class': 'form-select'}))
    # Campo para subir el archivo (solo acepta Excel)
    archivo_excel = forms.FileField(label="Seleccionar Archivo Excel (.xlsx)", 
                                    widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.xlsx'}))
                                    # help_text="Asegúrese que el archivo tenga las cabeceras en la Fila 3.") # Opcional recordatorio


# --- CLASE DetallePedidoForm (SIN el campo 'notas' innecesario) ---
class DetallePedidoForm(forms.ModelForm):
    """Formulario para un producto en el pedido."""
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.filter(activo=True).order_by('referencia', 'nombre', 'color', 'talla'),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    cantidad = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'style': 'width: 80px;'})
    )

    class Meta:
        model = DetallePedido
        fields = ['producto', 'cantidad']


# --- DetallePedidoFormSet (sin cambios necesarios aquí) ---
DetallePedidoFormSet = forms.inlineformset_factory(
    Pedido,
    DetallePedido,
    form=DetallePedidoForm,
    extra=1,
    can_delete=False,
    min_num=1,
    validate_min=True,
)

class DevolucionClienteForm(forms.ModelForm):
    """Formulario para los datos generales de la devolución."""

    # Usar ModelChoiceField para permitir búsqueda fácil (luego con Select2)
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.order_by('nombre_completo'),
        label="Cliente que Devuelve", # Etiqueta que se mostrará
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_cliente_devolucion'}) # ID único
    )
    # Pedido original es opcional y puede ser difícil de buscar sin Select2-AJAX
    # Por ahora, un campo simple o lo excluimos y lo añadimos luego.
    # pedido_original = forms.ModelChoiceField(...)

    motivo = forms.CharField(
        label="Motivo General de la Devolución",
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        required=False
    )

    class Meta:
        model = DevolucionCliente
        # Campos a mostrar en el formulario de cabecera
        # Excluimos fecha_hora y usuario (se asignan en la vista)
        # Excluimos pedido_original por ahora para simplificar
        fields = ['cliente', 'motivo']


# --- NUEVO: Formulario para UNA línea de Detalle de Devolución ---
class DetalleDevolucionForm(forms.ModelForm):
    """Formulario para un producto devuelto."""

    # Usaremos Select2 con AJAX para buscar producto aquí
    # Por ahora, un ModelChoiceField simple, lo mejoraremos con JS
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.filter(activo=True).order_by('referencia', 'nombre', 'color', 'talla'),
        label="Producto Devuelto",
        widget=forms.Select(attrs={'class': 'form-control producto-select-devolucion'}) # Clase para JS
    )

    cantidad = forms.IntegerField(
        label="Cantidad Devuelta",
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'style': 'width: 80px;'})
    )

    # Usar el campo Choice del modelo directamente
    # estado_producto se renderizará como un Select por defecto
    class Meta:
        model = DetalleDevolucion
        fields = ['producto', 'cantidad', 'estado_producto']
        widgets = {
            'estado_producto': forms.Select(attrs={'class': 'form-select form-select-sm'})
        }


# --- NUEVO: FormSet para manejar MÚLTIPLES Detalles en UN formulario ---
# Permite crear/editar varios detalles asociados a UNA DevolucionCliente
DetalleDevolucionFormSet = forms.inlineformset_factory(
    parent_model=DevolucionCliente, # El modelo padre
    model=DetalleDevolucion,       # El modelo de los detalles
    form=DetalleDevolucionForm,    # El formulario a usar para cada detalle
    extra=0,                       # Cuántos formularios extra mostrar por defecto (para añadir nuevos)
    can_delete=True,              # Poner True si quieres permitir borrar líneas al editar
    min_num=1,                     # Requerir al menos 1 detalle
    validate_min=True,             # Validar que se envíe al menos min_num
)

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
        fields = ['proveedor_info', 'documento_referencia', 'notas']


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
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
        initial=timezone.now().date() # Por defecto hoy
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