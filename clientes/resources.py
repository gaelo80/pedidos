# clientes/resources.py
from import_export import resources
from .models import Ciudad

class CiudadResource(resources.ModelResource):
    class Meta:
        model = Ciudad
        fields = ('id', 'nombre') # Campos a incluir en la exportación/importación
        # skip_unchanged = True # Opcional: no actualizar filas si no han cambiado
        # report_skipped = True # Opcional: reportar filas omitidas
        # use_transactions = True # Opcional: usar transacciones de BD para importaciones
        # import_id_fields = ['nombre'] # Si quieres usar 'nombre' como ID para actualizar en lugar de 'id'
                                      # Cuidado: 'nombre' debe ser único si lo usas como ID.
