# clientes/resources.py
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from .models import Ciudad, Cliente, Empresa # Asegúrate de importar Empresa

class CiudadResource(resources.ModelResource):
    """
    Resource para importar/exportar ciudades.
    """
    class Meta:
        model = Ciudad
        fields = ('id', 'nombre')
        import_id_fields = ['id']


class ClienteResource(resources.ModelResource):
    """
    Resource para importar/exportar clientes.
    Está configurado para IMPORTAR usando los IDs de Empresa y Ciudad.
    """
    # Widget para "traducir" el ID de la ciudad del archivo al objeto Ciudad en la BD
    ciudad = fields.Field(
        column_name='ciudad',
        attribute='ciudad',
        widget=ForeignKeyWidget(Ciudad, 'id'))

    # Widget para "traducir" el ID de la empresa del archivo al objeto Empresa en la BD
    empresa = fields.Field(
        column_name='empresa',
        attribute='empresa',
        widget=ForeignKeyWidget(Empresa, 'id'))

    class Meta:
        model = Cliente
        # Estos son los campos que tu archivo CSV/Excel debe tener como encabezados.
        # Nota que usamos 'empresa' y 'ciudad', no 'empresa__nombre'.
        fields = ('id', 'empresa', 'nombre_completo', 'identificacion', 'direccion', 'ciudad', 'telefono', 'email', 'activo')
        import_id_fields = ['id']
        skip_unchanged = True
        report_skipped = False