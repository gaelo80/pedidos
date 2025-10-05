# clientes/resources.py

from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from .models import Ciudad, Cliente, Empresa

class CiudadResource(resources.ModelResource):
    class Meta:
        model = Ciudad
        fields = ('id', 'nombre')
        import_id_fields = ['id']


class ClienteResource(resources.ModelResource):
    # Definimos los campos de relación para limpiar los datos de entrada
    empresa = fields.Field(
        column_name='empresa',
        attribute='empresa',
        widget=ForeignKeyWidget(Empresa, 'pk'))

    ciudad = fields.Field(
        column_name='ciudad',
        attribute='ciudad',
        widget=ForeignKeyWidget(Ciudad, 'pk'))

    # ✅ ENFOQUE FINAL: Interceptamos la fila y manejamos la actualización manualmente
    def skip_row(self, instance, original, row, import_validation_errors=None):
        """
        Se ejecuta para cada fila. Si el cliente ya existe, lo actualizamos aquí
        mismo y le decimos a la librería que se salte el resto del proceso para esta fila.
        """
        try:
            # Limpiamos los datos de la fila usando los widgets definidos arriba
            empresa_id_limpio = self.fields['empresa'].clean(row)
            identificacion_limpia = row.get('identificacion')

            # Buscamos si el cliente ya existe
            cliente_existente = Cliente.objects.filter(
                empresa_id=empresa_id_limpio,
                identificacion=identificacion_limpia
            ).first()

            if cliente_existente:
                # SI EXISTE: lo ACTUALIZAMOS manualmente y nos saltamos el resto del proceso
                cliente_existente.nombre_completo = row.get('nombre_completo')
                cliente_existente.direccion = row.get('direccion')
                cliente_existente.telefono = row.get('telefono')
                cliente_existente.email = row.get('email')
                
                # Limpiamos y asignamos el ID de la ciudad
                ciudad_id_limpio = self.fields['ciudad'].clean(row)
                if ciudad_id_limpio:
                    cliente_existente.ciudad_id = ciudad_id_limpio

                # Convertimos '1', 'TRUE' a booleano, cualquier otra cosa a False
                activo_val = str(row.get('activo', 'TRUE')).upper()
                cliente_existente.activo = activo_val in ['TRUE', '1', 'VERDADERO']

                cliente_existente.save()  # Guardamos la instancia actualizada
                
                return True  # Le decimos a la librería: "Misión cumplida, sáltate esta fila".

        except Exception as e:
            # Si hay algún error en nuestra lógica, lo dejamos pasar para que la librería lo reporte
            # (ej: la ciudad no existe)
            pass

        # SI NO EXISTE: no hacemos nada y dejamos que la librería lo cree
        return super().skip_row(instance, original, row, import_validation_errors)

    class Meta:
        model = Cliente
        fields = ('id', 'empresa', 'nombre_completo', 'identificacion', 'direccion', 'ciudad', 'telefono', 'email', 'activo')
        # La clave de importación principal. Nuestra lógica en skip_row añade la validación por empresa.
        import_id_fields = ('identificacion',)
        skip_unchanged = True
        report_skipped = False
        exclude = ('fecha_creacion',)
        
    def get_queryset(self):
        # Si la vista no nos pasa la información del 'request', no devolvemos nada por seguridad.
        if not hasattr(self, 'request') or not self.request:
            return Cliente.objects.none()
        
        # Obtenemos la empresa (tenant) del usuario que está pidiendo la exportación.
        empresa_actual = getattr(self.request, 'tenant', None)
        
        if empresa_actual:
            # Filtramos el queryset para devolver solo los clientes de esa empresa.
            return Cliente.objects.filter(empresa=empresa_actual)
        
        # Si por alguna razón no hay empresa, no se exporta nada.
        return Cliente.objects.none()