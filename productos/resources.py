# Archivo: productos/resources.py

from import_export import resources, fields
from import_export.instance_loaders import ModelInstanceLoader
from import_export.widgets import ForeignKeyWidget, BooleanWidget
from clientes.models import Empresa 
from .models import Producto


class CustomProductInstanceLoader(ModelInstanceLoader):
    def get_lookup_kwargs(self, row):
        """
        Define cómo buscar un producto existente.
        Usa la columna 'referencia' del archivo para la búsqueda.
        """
        return {
            'referencia': row.get('referencia'),
            'talla': row.get('talla'),
            'color': row.get('color')
        }

class ProductoResource(resources.ModelResource):
    """
    Este recurso ahora es consciente del inquilino. Se ha modificado para
    requerir una 'empresa' durante la inicialización y usarla para
    asignar la empresa correcta a cada producto durante la importación.
    """
    
    empresa = fields.Field(
        column_name='empresa',
        attribute='empresa',

        widget=ForeignKeyWidget(Empresa, 'pk')
    )

    activo = fields.Field(
        column_name='activo',
        attribute='activo',
        widget=BooleanWidget()
    )

    def __init__(self, empresa=None, **kwargs):
        super().__init__(**kwargs)
        if not empresa:
            raise ValueError("ProductoResource debe ser instanciado con una empresa.")
        self.empresa_actual = empresa

    def before_import_row(self, row, **kwargs):
        row['empresa'] = self.empresa_actual.id
        # CONVIERTE 'S'/'N' o 'si'/'no' a 1/0 para el BooleanWidget
        activo_val = str(row.get('activo', '')).strip().lower()
        if activo_val in ['s', 'si', 'true', '1']:
            row['activo'] = '1'
        else:
            row['activo'] = '0'
        
        
    def get_queryset(self):
        return self.Meta.model.objects.filter(empresa=self.empresa_actual)

    class Meta:
        model = Producto
        
        fields = (
            'id', 'empresa', 'referencia', 'nombre', 'descripcion', 'talla', 'color', 
            'genero', 'costo', 'precio_venta', 'unidad_medida', 
            'codigo_barras', 'activo', 'ubicacion'
        )
        
        import_id_fields = ('referencia', 'talla', 'color')
        instance_loader_class = CustomProductInstanceLoader        
        skip_unchanged = True
        report_skipped = True
        exclude = ('fecha_creacion',)
        
