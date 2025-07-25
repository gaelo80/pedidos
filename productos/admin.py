from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from django.utils.html import format_html
from .models import Producto, FotoProducto, ReferenciaColor

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
    fields = ('imagen', 'orden', 'previsualizacion_imagen')
    readonly_fields = ('previsualizacion_imagen',)
    

    def previsualizacion_imagen(self, obj):
        # Muestra una miniatura si la imagen ya ha sido guardada
        if obj.imagen:
            return format_html('<img src="{}" style="max-height: 100px; max-width: 100px;" />', obj.imagen.url)
        return "(Ninguna imagen)"
    previsualizacion_imagen.short_description = 'Previsualización'
    
   
@admin.register(ReferenciaColor)
class ReferenciaColorAdmin(admin.ModelAdmin):
    list_display = ('nombre_display', 'empresa', 'cantidad_fotos_display') # Añadido 'empresa'
    search_fields = ('nombre_display', 'referencia_base', 'color', 'empresa__nombre') # Añadido búsqueda por empresa
    list_filter = ('empresa',) # El filtro más importante
    inlines = [FotoProductoInline]

    def cantidad_fotos_display(self, obj):
        return obj.fotos_agrupadas.count()
    cantidad_fotos_display.short_description = "Nº de Fotos"
  
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request, 'tenant'):
            return qs.filter(empresa=request.tenant)
        return qs.none()

    def save_model(self, request, obj, form, change):
        if not obj.pk and not request.user.is_superuser and hasattr(request, 'tenant'):
            obj.empresa = request.tenant
        super().save_model(request, obj, form, change)

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if not request.user.is_superuser:
            # Ocultamos el campo 'empresa' a los no-superusuarios
            new_fieldsets = []
            for name, options in fieldsets:
                # Copiamos la lista de campos para poder modificarla
                fields = list(options.get('fields', []))
                if 'empresa' in fields:
                    fields.remove('empresa')
                new_fieldsets.append((name, {'fields': tuple(fields)}))
            return new_fieldsets
        return fieldsets

@admin.register(Producto)
class ProductoAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    list_display = ('referencia', 'nombre', 'talla', 'color', 'get_articulo_color_fotos_display', 'activo', 'stock_actual', 'empresa')
    search_fields = ('empresa__nombre', 'referencia', 'nombre', 'talla', 'color', 'codigo_barras', 'articulo_color_fotos__nombre_display')
    list_filter = ('activo', 'genero', 'empresa')
    autocomplete_fields = ['articulo_color_fotos']
    readonly_fields = ('stock_actual', 'fecha_creacion')

    
    fieldsets = (
        ('Información Principal', {
            'fields': (
                'empresa',
                'nombre',
                'descripcion',
                ('referencia', 'talla', 'color'),
                'codigo_barras'
            )
        }),
        ('Agrupación y Fotos', {
            'fields': ('articulo_color_fotos',)
        }),
        ('Clasificación y Estado', {
            'fields': ('genero', 'activo')
        }),
        ('Costos, Precios y Stock', {
            'fields': (('costo', 'precio_venta'), 'unidad_medida', 'stock_actual')
        }),
        ('Metadata', {
            'fields': ('fecha_creacion',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('empresa') # Optimización
        if request.user.is_superuser:
            return qs
        if hasattr(request, 'tenant'):
            return qs.filter(empresa=request.tenant)
        return qs.none()

    def save_model(self, request, obj, form, change):
        if not obj.pk and not request.user.is_superuser and hasattr(request, 'tenant'):
            obj.empresa = request.tenant
        super().save_model(request, obj, form, change)
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Filtra el campo de autocompletar para que solo muestre ReferenciaColor de la misma empresa.
        if db_field.name == "articulo_color_fotos":
            if not request.user.is_superuser and hasattr(request, 'tenant'):
                kwargs["queryset"] = ReferenciaColor.objects.filter(empresa=request.tenant)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_fieldsets(self, request, obj=None):
        fieldsets = self.fieldsets
        if request.user.is_superuser:
            return fieldsets        

        new_fieldsets = []
        for name, options in fieldsets:
            # Copiamos la lista para poder modificarla
            fields = list(options.get('fields', []))
            if 'empresa' in fields:
                fields.remove('empresa')
            # Manejar tuplas anidadas
            new_fields = []
            for field in fields:
                if isinstance(field, tuple):
                    new_sub_tuple = tuple(f for f in field if f != 'empresa')
                    if new_sub_tuple: new_fields.append(new_sub_tuple)
                else:
                    new_fields.append(field)
            new_fieldsets.append((name, {'fields': tuple(new_fields)}))
        return tuple(new_fieldsets)

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
    list_display = ('get_referencia_color_display', 'get_empresa_display', 'orden', 'previsualizacion_imagen_lista')
    list_filter = ('referencia_color__empresa',) # Filtro a través de la relación
    search_fields = ('referencia_color__nombre_display', 'descripcion_foto')
    list_editable = ('orden',)
    autocomplete_fields = ['referencia_color']
    
    def get_queryset(self, request):
        # --- CAMBIO MULTI-INQUILINO (CRÍTICO) ---
        qs = super().get_queryset(request).select_related('referencia_color__empresa') # Optimización
        if request.user.is_superuser:
            return qs
        if hasattr(request, 'tenant'):
            # Filtramos a través de la relación anidada
            return qs.filter(referencia_color__empresa=request.tenant)
        return qs.none()
    
    def get_empresa_display(self, obj):
        return obj.referencia_color.empresa
    get_empresa_display.short_description = 'Empresa'
    get_empresa_display.admin_order_field = 'referencia_color__empresa'

    def get_referencia_color_display(self, obj):
        return str(obj.referencia_color)
    get_referencia_color_display.short_description = 'Artículo (Ref+Color)'

    def previsualizacion_imagen_lista(self, obj):
        if obj.imagen and hasattr(obj.imagen, 'url'):
            return format_html('<img src="{}" style="max-height: 50px; max-width: 50px;" />', obj.imagen.url)
        return "(Sin imagen)"
    previsualizacion_imagen_lista.short_description = 'Imagen'