# productos/resources.py
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget, BooleanWidget
from .models import Producto 
# Si tuvieras campos ForeignKey a otros modelos como Categoria, Marca, etc., también los importarías aquí.
# from .models import Categoria 

class ProductoResource(resources.ModelResource):
    # Si tienes campos ForeignKey y quieres importar/exportar usando un campo específico
    # del modelo relacionado (ej. 'nombre' de Categoria en lugar de su ID),
    # puedes definir widgets. Ejemplo:
    # categoria = fields.Field(
    #     column_name='categoria',
    #     attribute='categoria',
    #     widget=ForeignKeyWidget(Categoria, 'nombre')) # Asume que Categoria tiene un campo 'nombre' único

    # Para campos Booleanos, es bueno usar BooleanWidget para manejar 'True'/'False', '1'/'0', etc.
    activo = fields.Field(
        column_name='activo',
        attribute='activo',
        widget=BooleanWidget()
    )

    class Meta:
        model = Producto
        # Especifica los campos que quieres incluir en la importación/exportación.
        # Si omites 'fields', se incluirán todos los campos del modelo.
        fields = (
            'id', 'referencia', 'nombre', 'descripcion', 'talla', 'color', 
            'genero', 'costo', 'precio_venta', 'unidad_medida', 
            'codigo_barras', 'activo', 'ubicacion', 'fecha_creacion'
        )
        # Puedes excluir campos si es más fácil:
        # exclude = ('campo_a_excluir',)
        
        # Si quieres que la importación actualice registros existentes basados en 'id' (o 'codigo_barras' si es único y lo prefieres)
        import_id_fields = ['id'] 
        # Si quieres permitir la creación de nuevos registros si no se encuentra el id:
        skip_unchanged = True # No actualiza filas si no han cambiado
        report_skipped = True # Informa sobre filas omitidas
        
        # Para manejar errores durante la importación:
        # raise_errors = False # No detiene la importación en el primer error
        # skip_diff = True # Para el export, solo exporta si hay diferencias

    # Opcional: Puedes añadir lógica personalizada para limpiar datos durante la importación
    # def before_import_row(self, row, **kwargs):
    #     # Ejemplo: convertir un campo a mayúsculas
    #     if 'referencia' in row and row['referencia']:
    #         row['referencia'] = str(row['referencia']).upper()
    #     super().before_import_row(row, **kwargs)

    # def dehydrate_activo(self, producto):
    #     # Para personalizar cómo se exporta el campo 'activo'
    #     return 'Sí' if producto.activo else 'No'
