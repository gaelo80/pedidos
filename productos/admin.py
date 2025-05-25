from django.contrib import admin
from .models import Producto
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from django.utils.html import format_html
from .models import Producto, FotoProducto,ReferenciaColor

# Register your models here.
class ProductoResource(resources.ModelResource):
    class Meta:
        model = Producto
        fields = ('id', 'referencia', 'nombre', 'descripcion', 'talla', 'color', 'genero',
                  'costo', 'precio_venta', 'unidad_medida', 'ubicacion', 'activo', 'codigo_barras')
        import_id_fields = ['referencia', 'talla', 'color'] # Clave aquí
        skip_unchanged = True
        report_skipped = True

class FotoProductoInline(admin.TabularInline): # o admin.StackedInline para otra disposición
    model = FotoProducto
    extra = 1 # Número de formularios de fotos vacíos para añadir nuevas
    fields = ('imagen', 'descripcion_foto', 'orden', 'previsualizacion_imagen') # Campos a mostrar
    readonly_fields = ('previsualizacion_imagen',) # Hacer la previsualización de solo lectura

    def previsualizacion_imagen(self, obj):
        # Muestra una miniatura si la imagen ya ha sido guardada
        if obj.imagen:
            return format_html('<img src="{}" style="max-height: 100px; max-width: 100px;" />', obj.imagen.url)
        return "(Ninguna imagen)"
    previsualizacion_imagen.short_description = 'Previsualización'
    
@admin.register(ReferenciaColor)
class ReferenciaColorAdmin(admin.ModelAdmin):
    list_display = ('referencia_base', 'color', 'nombre_display', 'cantidad_fotos_display')
    search_fields = ('referencia_base', 'color', 'nombre_display')
    list_filter = ('referencia_base', 'color') # Filtros directos
    inlines = [FotoProductoInline] # Las fotos ahora son inline de ReferenciaColor

    def cantidad_fotos_display(self, obj):
        # 'fotos_agrupadas' es el related_name de FotoProducto.articulo_agrupador
        return obj.fotos_agrupadas.count()
    cantidad_fotos_display.short_description = "Nº de Fotos"



@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('referencia', 'nombre', 'talla', 'color', 'get_articulo_color_fotos_display', 'activo', 'stock_actual')
    search_fields = ('referencia', 'nombre', 'talla', 'color', 'codigo_barras', 'articulo_color_fotos__nombre_display') # MODIFICADO
    list_filter = ('activo', 'genero', 'referencia', 'color', 'articulo_color_fotos__referencia_base') # MODIFICADO
    
    # Para seleccionar la ReferenciaColor a la que pertenece esta variante
    autocomplete_fields = ['articulo_color_fotos']
    
    # Ya NO FotoProductoInline aquí, porque las fotos se asocian a ReferenciaColor
    # inlines = [FotoProductoInline] # <--- ELIMINAR ESTA LÍNEA SI EXISTÍA

    # Puedes definir fieldsets para organizar cómo se muestra articulo_color_fotos
    fieldsets = (
        (None, {
            'fields': ('nombre', 'descripcion', ('referencia', 'talla', 'color'), 'codigo_barras')
        }),
        ('Agrupación y Fotos (Asociar a Referencia+Color)', { # Nueva sección
            'fields': ('articulo_color_fotos',)
        }),
        ('Clasificación y Estado', {
            'fields': ('genero', 'activo')
        }),
        ('Costos y Precios', {
            'fields': (('costo', 'precio_venta'), 'unidad_medida')
        }),
        ('Logística', {
            'fields': ('ubicacion', 'stock_actual_display') # stock_actual_display para solo lectura
        }),
        # ('Fechas', {
        #     'fields': ('fecha_creacion',), # Usualmente readonly
        # })
    )
    readonly_fields = ('stock_actual_display', 'fecha_creacion') # Ejemplo

    def get_articulo_color_fotos_display(self, obj):
        if obj.articulo_color_fotos:
            return str(obj.articulo_color_fotos)
        return "N/A"
    get_articulo_color_fotos_display.short_description = 'Agrupación Fotos (Ref+Color)'
    get_articulo_color_fotos_display.admin_order_field = 'articulo_color_fotos'

    def stock_actual_display(self, obj):
        return obj.stock_actual # Llama a la propiedad @property
    stock_actual_display.short_description = 'Stock Actual (Calculado)'

@admin.register(FotoProducto)
class FotoProductoAdmin(admin.ModelAdmin):
    # Ahora filtramos y buscamos a través de 'articulo_agrupador' que es la FK a ReferenciaColor
    list_display = ('get_articulo_agrupador_display', 'imagen', 'descripcion_foto', 'orden', 'previsualizacion_imagen_lista')
    list_filter = ('articulo_agrupador__referencia_base', 'articulo_agrupador__color') # MODIFICADO
    search_fields = ('articulo_agrupador__nombre_display', 'descripcion_foto') # MODIFICADO
    list_editable = ('orden',)

    def get_articulo_agrupador_display(self, obj):
        return str(obj.articulo_agrupador) # Mostrar el __str__ de ReferenciaColor
    get_articulo_agrupador_display.short_description = 'Artículo (Ref+Color)'
    get_articulo_agrupador_display.admin_order_field = 'articulo_agrupador' # Para ordenar

    def previsualizacion_imagen_lista(self, obj):
        if obj.imagen and hasattr(obj.imagen, 'url'):
            return format_html('<img src="{}" style="max-height: 50px; max-width: 50px;" />', obj.imagen.url)
        return "(Ninguna imagen)"
    previsualizacion_imagen_lista.short_description = 'Imagen'