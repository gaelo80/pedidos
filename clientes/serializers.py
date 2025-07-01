# clientes/serializers.py
from rest_framework import serializers
from .models import Ciudad, Cliente, Empresa # Importa los modelos necesarios

class CiudadSerializer(serializers.ModelSerializer):
    """Serializer simple para Ciudades."""
    class Meta:
        # CORRECCIÓN: Se usa la referencia directa a la clase del modelo.
        model = Ciudad
        fields = ['id', 'nombre']


class ClienteSerializer(serializers.ModelSerializer):
    """
    Serializer SEGURO para Clientes, consciente del inquilino en operaciones
    de escritura.
    """
    # Campos de solo lectura para mostrar información relacionada de forma amigable.
    ciudad_nombre = serializers.StringRelatedField(source='ciudad.nombre', read_only=True)
    empresa_nombre = serializers.StringRelatedField(source='empresa.nombre', read_only=True)

    class Meta:
        model = Cliente
        fields = [
            'id', 
            'empresa', # Se incluye el campo empresa
            'empresa_nombre', # Campo de solo lectura para el nombre
            'nombre_completo', 
            'identificacion', 
            'direccion',
            'ciudad',          # ID de la ciudad para escritura
            'ciudad_nombre',   # Nombre de la ciudad para lectura
            'telefono', 
            'email',
        ]
        # <<< REFUERZO DE SEGURIDAD >>>
        # Marcamos 'empresa' como de solo lectura. El serializador se encargará
        # de asignarla automáticamente, no el usuario de la API.
        read_only_fields = ['empresa', 'empresa_nombre', 'ciudad_nombre']

    def validate_ciudad(self, value):
        """
        Valida que la ciudad proporcionada exista. Aunque Ciudad es un modelo global,
        esta validación previene errores si se envía un ID incorrecto.
        """
        if not Ciudad.objects.filter(pk=value.pk).exists():
            raise serializers.ValidationError(f"La ciudad con ID {value.pk} no existe.")
        return value

    def create(self, validated_data):
        """
        <<< CORRECCIÓN CRÍTICA DE SEGURIDAD >>>
        Sobrescribe el método de creación para inyectar automáticamente
        la empresa del usuario actual (inquilino).
        """
        # Obtenemos la empresa del contexto del request que el ViewSet le pasa al serializer.
        empresa_actual = self.context['request'].tenant
        if not empresa_actual:
            raise serializers.ValidationError("No se pudo determinar la empresa para el usuario actual. La creación del cliente ha sido denegada.")
        
        # Asignamos la empresa a los datos validados antes de crear el objeto.
        validated_data['empresa'] = empresa_actual
        
        # Creamos el cliente de forma segura.
        cliente = Cliente.objects.create(**validated_data)
        return cliente
