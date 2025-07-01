from rest_framework import serializers
from .models import Producto


class ProductoSerializer(serializers.ModelSerializer):
    """    
    Este serializer se encarga de dos cosas clave:
    1.  Mostrar el nombre de la empresa a la que pertenece un producto (solo lectura).
    2.  Asignar automáticamente un nuevo producto a la empresa del usuario que lo crea.
    """
    empresa = serializers.StringRelatedField(read_only=True)
    
    stock_actual = serializers.IntegerField(read_only=True)

    class Meta:
        model = Producto
        # Campos a incluir en la API para productos/variantes
        fields = [
            'id', 
            'empresa', # Campo de solo lectura que muestra el nombre
            'referencia', 
            'talla', 
            'color', 
            'nombre', 
            'descripcion',
            'precio_venta', 
            'unidad_medida', 
            'activo', 
            'stock_actual',
            'codigo_barras',
        
        ]
        
    def create(self, validated_data):
        """
        --- CAMBIO 3 (CRÍTICO): Inyección automática del inquilino al crear ---
        Sobrescribimos el método de creación para asignar la empresa automáticamente.
        """
        # Obtenemos el 'request' del contexto que la vista (ViewSet) nos debe pasar.
        request = self.context.get("request")

        # Verificación de seguridad: si la vista no nos pasa el request o el request no tiene
        # el atributo 'tenant', lanzamos un error para prevenir la creación de datos huérfanos.
        if not (request and hasattr(request, 'tenant')):
            raise serializers.ValidationError(
                {"detail": "Contexto de la petición inválido: no se pudo determinar la empresa."}
            )

        # Asignamos la empresa del usuario al diccionario de datos validados.
        validated_data['empresa'] = request.tenant
        
        # Llamamos al método de creación original de DRF, que ahora incluye la empresa.
        producto = super().create(validated_data)
        
        return producto

