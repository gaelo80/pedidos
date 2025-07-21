# bodega/resources.py

from import_export import resources, fields
from import_export.widgets import IntegerWidget
from productos.models import Producto

class PlantillaConteoResource(resources.ModelResource):
    """
    Este Resource es solo para EXPORTAR la plantilla.
    No se usará para importar, ya que la lógica de importación es más compleja.
    """
    # Sobrescribimos el campo para asegurar que el stock se calcule en el momento de la exportación.
    stock_actual = fields.Field(
        column_name='Stock Sistema',
        attribute='stock_actual',
        readonly=True,
        widget=IntegerWidget()
    )
    
    # Añadimos una columna vacía para que el usuario la llene.
    cantidad_fisica_contada = fields.Field(
        column_name='CANTIDAD_FISICA_CONTADA'
    )

    class Meta:
        model = Producto
        # Campos que se van a exportar en la plantilla
        fields = (
            'id', 
            'referencia', 
            'nombre', 
            'color', 
            'talla', 
            'stock_actual', 
            'cantidad_fisica_contada'
        )
        export_order = fields # Mantener el orden definido
        # No queremos importar usando este Resource, solo exportar la plantilla.
        skip_unchanged = True
        report_skipped = False
        
    def dehydrate_cantidad_fisica_contada(self, producto):
        # Este método asegura que la columna 'CANTIDAD_FISICA_CONTADA' salga vacía en el Excel.
        return ''