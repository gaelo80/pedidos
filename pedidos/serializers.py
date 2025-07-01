from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from django.db import transaction
from productos.models import Producto
from pedidos.models import Pedido, DetallePedido
from clientes.models import Cliente



class DetallePedidoSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    producto_referencia = serializers.CharField(source='producto.referencia', read_only=True)
    producto_talla = serializers.CharField(source='producto.talla', read_only=True)
    producto_color = serializers.CharField(source='producto.color', read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    # El queryset se filtrará dinámicamente en __init__
    producto = serializers.PrimaryKeyRelatedField(queryset=Producto.objects.all())

    class Meta:
        model = DetallePedido
        fields = [
            'id', 'pedido', 'producto', 'producto_referencia', 'producto_nombre',
            'producto_talla', 'producto_color', 'cantidad', 'precio_unitario', 'subtotal',
        ]
        read_only_fields = (
            'id', 'pedido', 'subtotal', 'producto_nombre', 'producto_referencia',
            'producto_talla', 'producto_color', 'precio_unitario'
        )
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and hasattr(request, 'tenant'):
            tenant = request.tenant
            # Filtra el queryset para mostrar solo productos de la empresa actual
            self.fields['producto'].queryset = Producto.objects.filter(empresa=tenant, activo=True)

class PedidoSerializer(serializers.ModelSerializer):
    detalles = DetallePedidoSerializer(many=True)
    cliente_nombre = serializers.CharField(source='cliente.nombre_completo', read_only=True)
    vendedor_nombre = serializers.CharField(source='vendedor.user.username', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    
    cliente = serializers.PrimaryKeyRelatedField(queryset=Cliente.objects.all())

    class Meta:
        model = Pedido
        fields = [
            'id', 'cliente', 'cliente_nombre', 'vendedor', 'vendedor_nombre',
            'fecha_hora', 'estado', 'estado_display', 'detalles'
        ]
        # Campos asignados por el backend o no modificables directamente vía API
        read_only_fields = (
            'id', 'vendedor', 'fecha_hora', 'estado',
            'cliente_nombre', 'vendedor_nombre', 'estado_display'
        )
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and hasattr(request, 'tenant'):
            tenant = request.tenant
            # Filtra el queryset para el campo 'cliente'
            self.fields['cliente'].queryset = Cliente.objects.filter(empresa=tenant)
        
        
        
    def validate(self, data):
        request = self.context.get('request')
        if not request or not hasattr(request, 'tenant'):
            raise ValidationError("No se pudo determinar el contexto de la empresa.")
        
        tenant = request.tenant
        
        # Validar que el cliente pertenece a la empresa
        cliente = data.get('cliente')
        if cliente and cliente.empresa != tenant:
            raise ValidationError(f"El cliente '{cliente}' no pertenece a la empresa '{tenant.nombre}'.")

        # Validar stock y pertenencia de cada producto en los detalles
        if 'detalles' in data:
            for detalle_data in data['detalles']:
                producto = detalle_data['producto']
                cantidad_pedida = detalle_data['cantidad']

                # Validar que el producto pertenece a la empresa
                if producto.empresa != tenant:
                    raise ValidationError(f"El producto '{producto}' no pertenece a la empresa '{tenant.nombre}'.")

                # Validar stock
                if cantidad_pedida <= 0:
                    raise ValidationError(f"La cantidad para '{producto}' debe ser mayor que cero.")
                if cantidad_pedida > producto.stock_actual:
                    raise ValidationError(f"Stock insuficiente para {producto}. Solicitado: {cantidad_pedida}, Disponible: {producto.stock_actual}")
        return data

    def create(self, validated_data):
        # La vista (PedidoViewSet) debe inyectar 'empresa' y 'vendedor' en validated_data
        detalles_data = validated_data.pop('detalles')
        
        try:
            with transaction.atomic():
                pedido = Pedido.objects.create(**validated_data)
                for detalle_data in detalles_data:
                    producto_obj = detalle_data['producto']
                    DetallePedido.objects.create(
                        pedido=pedido,
                        producto=producto_obj,
                        cantidad=detalle_data['cantidad'],
                        # Asignación automática de precio desde el producto
                        precio_unitario=producto_obj.precio_venta
                    )
                return pedido
        except Exception as e:
            raise ValidationError(f"Error al crear los detalles del pedido: {e}")