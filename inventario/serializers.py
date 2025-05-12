# inventario/serializers.py
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from django.db import transaction
# Importa TODOS los modelos que realmente usas en los serializers DE ESTE ARCHIVO
from .models import (
    Ciudad, Cliente, Producto, Vendedor, Pedido, DetallePedido
    # Añade aquí otros modelos si creas serializers para ellos
)

# --- Serializers ---

class CiudadSerializer(serializers.ModelSerializer):
    """Serializer simple para Ciudades (ej: para anidar o listas)."""
    class Meta:
        model = Ciudad
        fields = ['id', 'nombre']


class ClienteSerializer(serializers.ModelSerializer):
    """Serializer para Clientes."""
    # Muestra el nombre de la ciudad en lugar de solo el ID al leer
    ciudad_nombre = serializers.StringRelatedField(source='ciudad', read_only=True)

    class Meta:
        model = Cliente
        fields = [
            'id', 'nombre_completo', 'identificacion', 'direccion',
            'ciudad',           # Se espera el ID de la ciudad al escribir
            'ciudad_nombre',    # Se muestra el nombre al leer
            'telefono', 'email',
        ]


class ProductoSerializer(serializers.ModelSerializer):
    """Serializer para Productos (Variantes)."""
    # La propiedad @stock_actual del modelo se incluye automáticamente y es de solo lectura
    stock_actual = serializers.IntegerField(read_only=True)

    class Meta:
        model = Producto
        # Campos a incluir en la API para productos/variantes
        fields = [
            'id', 'referencia', 'talla', 'color', 'nombre', 'descripcion',
            'precio_venta', 'unidad_medida', 'activo', 'stock_actual',
            # 'ubicacion', # Descomenta si quieres exponer la ubicación vía API
            # 'costo', # Probablemente no necesario en API para ventas
        ]
        # Campos que no se pueden modificar vía este serializer
        read_only_fields = ['stock_actual', 'activo']


class DetallePedidoSerializer(serializers.ModelSerializer):
    """Serializer para las líneas de detalle DENTRO de un PedidoSerializer (anidado)."""
    # Muestra información legible del producto (solo lectura)
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    producto_referencia = serializers.CharField(source='producto.referencia', read_only=True) # Añadido para info
    producto_talla = serializers.CharField(source='producto.talla', read_only=True) # Añadido para info
    producto_color = serializers.CharField(source='producto.color', read_only=True) # Añadido para info

    # Acepta el ID de un Producto (variante) activo como entrada al crear/actualizar
    producto = serializers.PrimaryKeyRelatedField(queryset=Producto.objects.filter(activo=True))

    # Muestra el subtotal calculado desde la propiedad del modelo
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, required=False)

    class Meta:
        model = DetallePedido
        fields = [
            'id',
            'pedido',           # Generalmente gestionado por el serializer padre (PedidoSerializer)
            'producto',         # ID de la variante específica (para escribir)
            # Campos extra para lectura fácil en la respuesta API:
            'producto_referencia',
            'producto_nombre',
            'producto_talla',
            'producto_color',
            # Campos principales del detalle:
            'cantidad',
            'precio_unitario',  # Se muestra (asignado por backend)
            'subtotal',         # Se muestra (calculado por backend)
        ]
        # Campos que no se envían en el JSON al crear un pedido anidado
        # o que son calculados/asignados por el backend.
        read_only_fields = (
            'id', 'pedido', 'subtotal', 'producto_nombre', 'producto_referencia',
            'producto_talla', 'producto_color', 'precio_unitario'
        )


class PedidoSerializer(serializers.ModelSerializer):
    """Serializer para Pedido, maneja detalles anidados, validación de stock y asignación de precio."""
    # Campo para manejar detalles anidados (lectura y escritura)
    detalles = DetallePedidoSerializer(many=True)
    # Campos de solo lectura para mostrar nombres relacionados
    cliente_nombre = serializers.CharField(source='cliente.nombre_completo', read_only=True)
    vendedor_nombre = serializers.CharField(source='vendedor.user.username', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)

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

    def validate(self, data):
        """Valida stock disponible para los detalles del pedido."""
        if 'detalles' in data:
            detalles_data = data['detalles']
            for detalle_data in detalles_data:
                if 'producto' not in detalle_data or 'cantidad' not in detalle_data:
                    continue # Saltar si faltan datos clave en el detalle

                producto = detalle_data['producto'] # Instancia de Producto (variante)
                cantidad_pedida = detalle_data['cantidad']
                stock_disponible = producto.stock_actual

                # Asegurarnos que estamos comparando números
                if isinstance(cantidad_pedida, int) and isinstance(stock_disponible, int):
                    if cantidad_pedida <= 0: # No permitir cantidad 0 o negativa
                         raise serializers.ValidationError(f"La cantidad para '{producto}' debe ser mayor que cero.")
                    if cantidad_pedida > stock_disponible:
                        raise serializers.ValidationError(
                            f"Stock insuficiente para {producto}. " # Usamos el __str__ del producto
                            f"Solicitado: {cantidad_pedida}, Disponible: {stock_disponible}"
                        )
                else:
                     # Error si la cantidad o el stock no son números válidos (inesperado aquí)
                     raise serializers.ValidationError(f"No se pudo validar stock para {producto}.")
        return data

    def create(self, validated_data):
        """Crea Pedido y sus Detalles, asignando precio automáticamente."""
        # validated_data ya pasó por validate()
        detalles_data = validated_data.pop('detalles')
        # El 'cliente' viene en validated_data.
        # El 'vendedor' y 'estado' se inyectan desde perform_create en la vista.
        try:
            with transaction.atomic(): # Usar transacción por seguridad
                pedido = Pedido.objects.create(**validated_data)
                # Crear los detalles asociados
                for detalle_data in detalles_data:
                    producto_obj = detalle_data['producto']
                    cantidad_obj = detalle_data['cantidad']
                    # ASIGNACIÓN AUTOMÁTICA DE PRECIO desde el producto/variante
                    precio_obj = producto_obj.precio_venta
                    DetallePedido.objects.create(
                        pedido=pedido,
                        producto=producto_obj,
                        cantidad=cantidad_obj,
                        precio_unitario=precio_obj # Precio tomado del producto
                    )
            return pedido
        except Exception as e:
            # Capturar cualquier error durante la creación para devolver un error API claro
            raise serializers.ValidationError(f"Error al crear los detalles del pedido: {e}")

# --- FIN PedidoSerializer ---

# No añadir ViewSets ni código de vistas aquí.