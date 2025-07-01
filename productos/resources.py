# Archivo: productos/resources.py

from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget, BooleanWidget
from .models import Producto


class ProductoResource(resources.ModelResource):
    """
    Este recurso ahora es consciente del inquilino. Se ha modificado para
    requerir una 'empresa' durante la inicialización y usarla para
    asignar la empresa correcta a cada producto durante la importación.
    """
    
    # REGLA DE ORO: Añadir un campo para la empresa, usando un ForeignKeyWidget.
    # Esto es útil tanto para la exportación (mostrará el nombre de la empresa)
    # como para la importación (puede buscar la empresa por nombre si es necesario).
    empresa = fields.Field(
        column_name='empresa',
        attribute='empresa',
        widget=ForeignKeyWidget('clientes.Empresa', 'nombre')
    )

    activo = fields.Field(
        column_name='activo',
        attribute='activo',
        widget=BooleanWidget()
    )

    # ==========================================================================
    # REFACTORIZACIÓN CLAVE PARA MULTI-INQUILINO
    # ==========================================================================
    def __init__(self, empresa=None, **kwargs):
        """
        Sobrescribimos __init__ para almacenar la empresa del inquilino actual.
        La vista le pasará la empresa al crear una instancia de este recurso.
        """
        super().__init__(**kwargs)
        if not empresa:
            raise ValueError("ProductoResource debe ser instanciado con una empresa.")
        self.empresa_actual = empresa

    def before_import_row(self, row, **kwargs):
        """
        Este método se ejecuta para cada fila ANTES de que se intente guardar.
        Es el lugar perfecto para inyectar el ID de la empresa.
        """
        # REGLA DE ORO: Asignar el ID de la empresa actual a la columna 'empresa'
        # de la fila que se va a importar. Esto asegura que cada nuevo producto
        # pertenezca al inquilino correcto.
        row['empresa'] = self.empresa_actual.id
        
        
    def get_or_init_instance(self, instance_loader, row):
        """
        Este es el método de seguridad más importante para las actualizaciones.
        
        Sobrescribimos este método para asegurar que cuando django-import-export
        busque un producto existente para actualizarlo, la búsqueda se filtre
        POR LA EMPRESA DEL USUARIO ACTUAL.
        
        Sin esto, un usuario podría adivinar el 'id' o la 'referencia' de un
        producto de otra empresa y sobrescribir sus datos.
        """
        # Obtenemos los campos que definen la unicidad de un producto.
        lookup_kwargs = instance_loader.get_lookup_kwargs(row)
        
        # AÑADIMOS EL FILTRO DEL INQUILINO a los argumentos de búsqueda.
        lookup_kwargs['empresa'] = self.empresa_actual
        
        try:
            # Intentamos encontrar la instancia DENTRO de la empresa actual.
            return self.get_queryset().get(**lookup_kwargs)
        except self.get_queryset().model.DoesNotExist:
            # Si no existe, procedemos a crear una nueva instancia (pero sin guardarla aún).
            return self.init_instance(row)   
    # ==========================================================================

    class Meta:
        model = Producto
        
        fields = (
            'id', 'empresa', 'referencia', 'nombre', 'descripcion', 'talla', 'color', 
            'genero', 'costo', 'precio_venta', 'unidad_medida', 
            'codigo_barras', 'activo', 'ubicacion'
        )
        
        # --- MEJORA DE SEGURIDAD ---
        # Cambiamos import_id_fields a una clave natural que tiene sentido dentro
        # de una empresa. Esto, combinado con get_or_init_instance, asegura
        # que las actualizaciones sean seguras.
        import_id_fields = ('referencia', 'talla', 'color')
        
        skip_unchanged = True
        report_skipped = True
        # Excluimos 'fecha_creacion' de la importación para evitar errores.
        # Este campo generalmente se gestiona automáticamente por la base de datos.
        exclude = ('fecha_creacion',)