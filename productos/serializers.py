from rest_framework import serializers
from .models import Producto


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
