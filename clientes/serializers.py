from rest_framework import serializers
from .models import Ciudad, Cliente # Importa Ciudad y Cliente de los modelos de esta app



class CiudadSerializer(serializers.ModelSerializer):
    """Serializer simple para Ciudades (ej: para anidar o listas)."""
    class Meta:
        model = 'ciudad.Ciudad'
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
