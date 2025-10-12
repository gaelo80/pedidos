# productos/resources.py

from import_export import resources, fields
from import_export.instance_loaders import ModelInstanceLoader
from import_export.widgets import ForeignKeyWidget, BooleanWidget
from clientes.models import Empresa 
from .models import Producto


class CustomProductInstanceLoader(ModelInstanceLoader):
    def get_lookup_kwargs(self, row):
        return {
            'referencia': row.get('referencia'),
            'talla': row.get('talla'),
            'color': row.get('color')
        }

class ProductoResource(resources.ModelResource):
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

    # --- CAMPO AÑADIDO ---
    permitir_preventa = fields.Field(
        column_name='permitir_preventa',
        attribute='permitir_preventa',
        widget=BooleanWidget()
    )

    def __init__(self, empresa=None, **kwargs):
        super().__init__(**kwargs)
        if not empresa:
            raise ValueError("ProductoResource debe ser instanciado con una empresa.")
        self.empresa_actual = empresa

    def before_import_row(self, row, **kwargs):
        row['empresa'] = self.empresa_actual.id
        
        codigo_barras_val = row.get('codigo_barras')
        if not codigo_barras_val or str(codigo_barras_val).strip() == '':
            row['codigo_barras'] = None

        # Convierte 'S'/'N' o 'si'/'no' a 1/0 para el BooleanWidget
        activo_val = str(row.get('activo', '')).strip().lower()
        if activo_val in ['s', 'si', 'true', '1']:
            row['activo'] = '1'
        else:
            row['activo'] = '0'
        
        # --- LÓGICA AÑADIDA ---
        preventa_val = str(row.get('permitir_preventa', '')).strip().lower()
        if preventa_val in ['s', 'si', 'true', '1']:
            row['permitir_preventa'] = '1'
        else:
            row['permitir_preventa'] = '0'
        
    def get_queryset(self):
        return self.Meta.model.objects.filter(empresa=self.empresa_actual)

    class Meta:
        model = Producto
        
        fields = (
            'id', 'empresa', 'referencia', 'nombre', 'descripcion', 'talla', 'color', 
            'genero', 'costo', 'precio_venta', 'unidad_medida', 
            'codigo_barras', 'activo', 'permitir_preventa', 'ubicacion' # <-- CAMPO AÑADIDO
        )
        
        import_id_fields = ('referencia', 'talla', 'color')
        instance_loader_class = CustomProductInstanceLoader        
        skip_unchanged = True
        report_skipped = True
        exclude = ('fecha_creacion',)