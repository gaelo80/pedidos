# pedidos_online/forms.py

from django import forms
from .models import ClienteOnline
from pedidos.models import Pedido # Importa el modelo Pedido
from clientes.models import Empresa # Asegúrate de importar Empresa

class ClienteOnlineForm(forms.ModelForm):
    """
    Formulario para crear y editar clientes del canal Online.
    Se usará para la creación rápida de clientes.
    """
    class Meta:
        model = ClienteOnline
        fields = [
            'nombre_completo', 'identificacion', 'telefono', 'email', 
            'direccion', 'tipo_cliente', 'forma_pago_preferida'
        ]
        widgets = {
            'nombre_completo': forms.TextInput(attrs={'class': 'form-control'}),
            'identificacion': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_cliente': forms.Select(attrs={'class': 'form-select'}),
            'forma_pago_preferida': forms.Select(attrs={'class': 'form-select'}),
        }

class PedidoOnlineForm(forms.ModelForm):
    """
    Formulario para la cabecera del Pedido Online.
    Similar al PedidoForm original, pero adaptado para el nuevo flujo.
    """
    # Reintroducimos cliente_online como un campo de formulario, pero no un ModelChoiceField
    # para que podamos manejar su validación y asignación manualmente.
    cliente_online = forms.IntegerField(required=False, widget=forms.HiddenInput())
    
    def __init__(self, *args, **kwargs):
        # Capturamos la 'empresa' que se pasa al inicializar el formulario
        self.empresa = kwargs.pop('empresa', None) 
        super().__init__(*args, **kwargs)

        if self.empresa is None: # Usar self.empresa aquí
            raise ValueError("Se requiere 'empresa' para inicializar PedidoOnlineForm.")

        # Ocultar los campos de cliente y prospecto del formulario base PedidoForm
        # ya que los pedidos online solo usan cliente_online
        if 'cliente' in self.fields:
            self.fields['cliente'].widget = forms.HiddenInput()
            self.fields['cliente'].required = False
        if 'prospecto' in self.fields:
            self.fields['prospecto'].widget = forms.HiddenInput()
            self.fields['prospecto'].required = False

        self.fields['forma_pago'].choices = [
            ('CREDITO', 'Crédito'),
            ('CONTADO', 'Contado'),
            ('ADDI', 'Addi'),
            ('TARJETA_CREDITO', 'Tarjeta de Crédito'),
            ('TARJETA_DEBITO', 'Tarjeta Débito'),
            ('TRANSFERENCIA', 'Transferencia Bancaria'),
            ('OTRO_ONLINE', 'Otro Pago Online'),
        ]
        # Asegurarse de que 'CREDITO' sea el valor inicial por defecto si no hay otro
        if not self.initial.get('forma_pago'):
            self.initial['forma_pago'] = 'CREDITO'


    def clean(self):
        cleaned_data = super().clean()
        
        # Forzamos el tipo de pedido en la instancia del modelo del formulario.
        # Esto es importante para las validaciones del modelo Pedido.
        self.instance.tipo_pedido = 'ONLINE'
        
        cliente_online_id = cleaned_data.get('cliente_online')
        
        # Usamos directamente self.empresa que fue asignada en __init__
        empresa_para_lookup = self.empresa 

        if not cliente_online_id:
            # Si no hay cliente_online_id, agregamos un error al formulario
            self.add_error(None, "Un pedido Online debe tener un Cliente asignado.")
        elif not empresa_para_lookup:
            # Este caso no debería ocurrir si la vista inicializa el formulario correctamente,
            # pero es una salvaguarda.
            self.add_error(None, "Error interno: La empresa no está disponible para validar el cliente online.")
        else:
            try:
                # Intentar obtener el ClienteOnline usando la empresa disponible
                cliente_online_obj = ClienteOnline.objects.get(pk=cliente_online_id, empresa=empresa_para_lookup)
                self.instance.cliente_online = cliente_online_obj
                # Asegurarse de que los campos de cliente estándar y prospecto sean None
                self.instance.cliente = None
                self.instance.prospecto = None
            except ClienteOnline.DoesNotExist:
                self.add_error(None, "El cliente online seleccionado no es válido o no existe.")
            except Exception as e:
                # Captura cualquier otra excepción durante la obtención del cliente online
                self.add_error(None, f"Error al procesar el cliente online: {e}")
                
                # Validar que la forma de pago sea una de las permitidas para pedidos ONLINE
        forma_pago = cleaned_data.get('forma_pago')
        if forma_pago not in [choice[0] for choice in self.fields['forma_pago'].choices]:
            self.add_error('forma_pago', "Forma de pago no válida para este tipo de pedido online.")
            
        return cleaned_data


    class Meta:
        model = Pedido
        # Solo incluimos los campos relevantes para la cabecera del pedido online
        # 'cliente_online' se maneja a través del campo definido arriba y no directamente del modelo
        fields = ['porcentaje_descuento', 'notas', 'forma_pago', 'comprobante_pago'] 
        widgets = {
            'porcentaje_descuento': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm', 'step': '1', 'min': '0', 'max': '100'
            }),
            'notas': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),         
            'forma_pago': forms.Select(attrs={'class': 'form-select max-w-xs'}),
            'comprobante_pago': forms.ClearableFileInput(attrs={'class': 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100'}),
        }
        labels = {
            'forma_pago': 'Forma de Pago', # Etiqueta para el nuevo campo
        }