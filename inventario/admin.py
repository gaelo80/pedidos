# inventario/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from .models import (
    Ciudad, Cliente, Producto, Vendedor, Pedido, DetallePedido,
    MovimientoInventario, DevolucionCliente, DetalleDevolucion,
    IngresoBodega, DetalleIngresoBodega, PersonalBodega, ConteoInventario, DocumentoCartera
)

# Register your models here.

# --- Registros personalizados para modelos base ---

class ClienteAdmin(ImportExportModelAdmin):
    list_display = ('nombre_completo', 'identificacion', 'ciudad', 'telefono', 'email')
    search_fields = ('nombre_completo', 'identificacion', 'email')
    list_filter = ('ciudad',)
    list_per_page = 25
    
admin.site.register(Cliente, ClienteAdmin)
admin.site.register(ConteoInventario)

# --- Registro Personalizado para Producto --- ### CORRECCIÓN ABAJO ###
# inventario/admin.py

# ... (importaciones al principio del archivo) ...

# --- Registro Personalizado para Producto CORREGIDO ---
class ProductoResource(resources.ModelResource):
    class Meta:
        model = Producto
        fields = ('id', 'referencia', 'nombre', 'descripcion', 'talla', 'color', 'genero',
                  'costo', 'precio_venta', 'unidad_medida', 'ubicacion', 'activo', 'codigo_barras')
        import_id_fields = ['referencia', 'talla', 'color'] # Clave aquí
        skip_unchanged = True
        report_skipped = True



@admin.register(Producto) # Usando decorador (no necesitas admin.site.register(Producto,...) después)
class ProductoAdmin(ImportExportModelAdmin):
    # Columnas en la vista de lista (Estaban bien)
    list_display = ('referencia', 'nombre', 'talla', 'color', 'codigo_barras', 'precio_venta', 'stock_actual', 'activo', 'genero')

    # Campos para búsqueda directa (Coma añadida)
    search_fields = ('referencia', 'nombre', 'descripcion', 'talla', 'color', 'codigo_barras') # <-- Coma añadida

    # Campos para filtros laterales (Estaban bien)
    list_filter = ('activo', 'referencia', 'color', 'talla', 'genero')
    list_per_page = 25

    # --- fieldsets con estructura CORREGIDA ---
    # Es una tupla (o lista) que contiene tuplas de ('Titulo'/None, {'fields': ...})
    fieldsets = (
        (None, { # Grupo 1: Información básica
            'fields': ('activo', ('referencia', 'nombre'), ('color', 'talla'), 'genero', 'codigo_barras')
        }),
        ('Detalles y Precio', { # Grupo 2: Detalles
            'fields': (('costo', 'precio_venta'), 'unidad_medida', 'descripcion')
        }),
        ('Ubicación', { # Grupo 3: Ubicación
            'fields': ('ubicacion',)
        }),
    ) # <-- Cierre correcto de la tupla principal de fieldsets

    # --- readonly_fields va AFUERA de fieldsets ---
    readonly_fields = ('stock_actual',)
    

    # --- Método para help_texts con datalist (Estaba bien) ---
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # ... (código existente para añadir datalist y help_texts) ...
        nombre_field = form.base_fields.get('nombre')
        if nombre_field:
            existing_names = Producto.objects.values_list('nombre', flat=True).distinct().order_by('nombre')
            datalist_id = 'id_nombre_datalist_sugerencias'
            options_html = "".join([f'<option value="{name}"></option>' for name in existing_names])
            datalist_html = format_html('<datalist id="{}">{}</datalist>', datalist_id, format_html(options_html))
            nombre_field.widget.attrs['list'] = datalist_id
            nombre_field.widget.attrs['autocomplete'] = 'off'
            original_help_text = 'Ingrese el nombre descriptivo. Revise la lista o use la búsqueda para ver si ya existe un nombre para esta Referencia. Use las sugerencias:'
            nombre_field.help_text = format_html('{}{}', original_help_text, datalist_html)
        referencia_field = form.base_fields.get('referencia')
        if referencia_field:
            referencia_field.help_text = 'Código base del producto (ej: 0808).'
        return form

class VendedorAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_nombre_completo', 'telefono_contacto', 'codigo_interno', 'activo')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'user__email', 'codigo_interno')
    list_filter = ('activo',)
    list_per_page = 25

    def get_nombre_completo(self, obj):
        nombre = obj.user.get_full_name()
        return nombre if nombre else obj.user.username
    get_nombre_completo.short_description = 'Nombre Completo' # Nombre de la columna
admin.site.register(Vendedor, VendedorAdmin)

# --- PedidoAdmin con Detalles Inline ---
class DetallePedidoInline(admin.TabularInline):
    model = DetallePedido
    extra = 0
    autocomplete_fields = ['producto']
    # readonly_fields = ('precio_unitario',) # Comentado para permitir edición manual


class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'vendedor', 'fecha_hora', 'estado', 'ver_total', 'enlace_pdf')
    list_filter = ('estado', 'fecha_hora', 'vendedor__user__username', 'cliente__nombre_completo')
    search_fields = ('id', 'cliente__nombre_completo', 'cliente__identificacion', 'detalles__producto__nombre')
    readonly_fields = ('fecha_hora',)
    inlines = [DetallePedidoInline]
    autocomplete_fields = ['cliente', 'vendedor']

    def enlace_pdf(self, obj):
        url = reverse('generar_pedido_pdf', args=[obj.pk])
        return format_html('<a href="{}" target="_blank">Ver PDF</a>', url)
    enlace_pdf.short_description = 'PDF'

    def ver_total(self, obj):
        # Asegurarse que detalle.subtotal existe y no es None antes de sumar
        total = sum(detalle.subtotal for detalle in obj.detalles.all() if hasattr(detalle, 'subtotal') and detalle.subtotal is not None)
        # Ajusta el formato de moneda según tu localidad si es necesario
        return f"${total:,.2f}" # Ejemplo formato USD con comas y 2 decimales
    ver_total.short_description = 'Total Pedido'
admin.site.register(Pedido, PedidoAdmin)

# --- MovimientoInventarioAdmin ---
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = ('fecha_hora', 'producto', 'cantidad', 'tipo_movimiento', 'usuario', 'documento_referencia')
    list_filter = ('tipo_movimiento', 'fecha_hora', 'producto', 'usuario')
    search_fields = ('producto__nombre', 'producto__referencia', 'documento_referencia', 'usuario__username', 'notas')
    readonly_fields = ('fecha_hora', 'usuario',)
    list_per_page = 30

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)
admin.site.register(MovimientoInventario, MovimientoInventarioAdmin)

# --- DevolucionClienteAdmin con Detalles Inline ---
class DetalleDevolucionInline(admin.TabularInline):
    model = DetalleDevolucion
    extra = 1
    autocomplete_fields = ['producto']

class DevolucionClienteAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'fecha_hora', 'pedido_original', 'usuario')
    list_filter = ('fecha_hora', 'cliente', 'usuario')
    search_fields = ('id', 'cliente__nombre_completo', 'pedido_original__id', 'detalles__producto__nombre')
    readonly_fields = ('fecha_hora', 'usuario')
    autocomplete_fields = ['cliente', 'pedido_original']
    inlines = [DetalleDevolucionInline]

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)
admin.site.register(DevolucionCliente, DevolucionClienteAdmin)


# --- 3. REGISTRO PARA INGRESO BODEGA con Detalles Inline ---

# 3a. Define el Inline para DetalleIngresoBodega
class DetalleIngresoBodegaInline(admin.TabularInline):
    model = DetalleIngresoBodega
    extra = 1 # Muestra 1 línea vacía para añadir
    autocomplete_fields = ['producto'] # Necesita ProductoAdmin con search_fields (ya existe)
    # Podríamos añadir el campo costo_unitario aquí si queremos ingresarlo manualmente

# 3b. Define el ModelAdmin para IngresoBodega
class IngresoBodegaAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha_hora', 'proveedor_info', 'documento_referencia', 'usuario')
    list_filter = ('fecha_hora', 'usuario')
    search_fields = ('id', 'proveedor_info', 'documento_referencia', 'detalles__producto__nombre')
    readonly_fields = ('fecha_hora', 'usuario') # Fecha y usuario no editables aquí
    inlines = [DetalleIngresoBodegaInline] # Incrusta los detalles del ingreso

    # Auto-asigna el usuario al guardar un nuevo ingreso
    def save_model(self, request, obj, form, change):
        if not obj.pk: # Si es nuevo
            obj.usuario = request.user
        super().save_model(request, obj, form, change)

# 3c. Registra IngresoBodega usando su clase Admin
admin.site.register(IngresoBodega, IngresoBodegaAdmin)

# En inventario/admin.py

# ... (importaciones y otras clases Admin) ...

# Define una clase Admin para Ciudad que habilite Import/Export
class CiudadAdmin(ImportExportModelAdmin):
    list_display = ('id', 'nombre') # Mostrar ID y nombre en la lista
    search_fields = ('nombre',)  # Permitir buscar por nombre
    list_per_page = 25 # Opcional: cuántas mostrar por página

admin.site.register(Ciudad, CiudadAdmin)

# NOTA: No registramos DetalleIngresoBodega por separado.

@admin.register(DocumentoCartera)
class DocumentoCarteraAdmin(admin.ModelAdmin):
        # Campos a mostrar en la lista
    list_display = (
        'cliente', 
        'tipo_documento', 
        'numero_documento', 
        'fecha_documento', 
        'fecha_vencimiento', 
        'saldo_actual', 
        'esta_vencido', # Propiedad calculada
        'dias_mora',    # Propiedad calculada
        'nombre_vendedor_cartera', 
        'ultima_actualizacion_carga'
    )
    # Campos por los que se puede filtrar en la barra lateral
    list_filter = (
        'tipo_documento', 
        #'esta_vencido', # Filtrar por si está vencido (basado en la property)
        'cliente', 
        'nombre_vendedor_cartera', 
        'fecha_vencimiento', 
        'fecha_documento'
    )
    # Campos en los que se puede buscar
    search_fields = (
        'numero_documento', 
        'cliente__identificacion', # Buscar por identificación del cliente
        'cliente__nombre_completo',# Buscar por nombre del cliente
        'nombre_vendedor_cartera'
    )
    # Campos que no se pueden editar directamente en el admin (son calculados o automáticos)
    readonly_fields = ('dias_mora', 'esta_vencido', 'ultima_actualizacion_carga')
    # Número de ítems por página
    list_per_page = 30 
    

@admin.register(PersonalBodega) # O usa admin.site.register(PersonalBodega, PersonalBodegaAdmin)
class PersonalBodegaAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_nombre_completo', 'codigo_empleado', 'area_asignada', 'activo') # Columnas a mostrar
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'codigo_empleado', 'area_asignada') # Campos de búsqueda
    list_filter = ('activo', 'area_asignada') # Filtros laterales
    autocomplete_fields = ['user'] # Facilita la selección del usuario
    list_per_page = 25

    # Función para obtener el nombre completo desde el usuario asociado
    def get_nombre_completo(self, obj):
        # Asegúrate que 'obj.user' no sea None antes de llamar a métodos
        if obj.user:
            nombre = obj.user.get_full_name()
            return nombre if nombre else obj.user.username
        return "Usuario no asignado" # O algún valor por defecto
    get_nombre_completo.short_description = 'Nombre Completo' # Nombre de la columna
