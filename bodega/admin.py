from django.contrib import admin
from .models import SalidaInternaCabecera, SalidaInternaDetalle
from bodega.models import (
    IngresoBodega, DetalleIngresoBodega, 
    PersonalBodega, MovimientoInventario,
    ComprobanteDespacho, DetalleComprobanteDespacho,
    CabeceraConteo, ConteoInventario
)

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



class DetalleIngresoBodegaInline(admin.TabularInline):
    model = DetalleIngresoBodega
    extra = 1
    autocomplete_fields = ['producto']



class IngresoBodegaAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha_hora', 'proveedor_info', 'documento_referencia', 'usuario')
    list_filter = ('fecha_hora', 'usuario')
    search_fields = ('id', 'proveedor_info', 'documento_referencia', 'detalles__producto__nombre')
    readonly_fields = ('fecha_hora', 'usuario')
    inlines = [DetalleIngresoBodegaInline]

   
    def save_model(self, request, obj, form, change):
        if not obj.pk: # Si es nuevo
            obj.usuario = request.user
        super().save_model(request, obj, form, change)


admin.site.register(IngresoBodega, IngresoBodegaAdmin)


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


class DetalleComprobanteDespachoInline(admin.TabularInline):
    model = DetalleComprobanteDespacho
    extra = 0 # No mostrar formularios extra vacíos por defecto
    autocomplete_fields = ['producto']
    readonly_fields = ('producto', 'cantidad_despachada', 'detalle_pedido_origen') # Hacemos que los detalles aquí sean de solo lectura

@admin.register(ComprobanteDespacho)
class ComprobanteDespachoAdmin(admin.ModelAdmin):
    list_display = ('id', 'pedido', 'fecha_hora_despacho', 'usuario_responsable')
    list_filter = ('fecha_hora_despacho', 'usuario_responsable')
    search_fields = ('id', 'pedido__id', 'pedido__cliente__nombre_completo', 'usuario_responsable__username')
    date_hierarchy = 'fecha_hora_despacho'
    inlines = [DetalleComprobanteDespachoInline]
    autocomplete_fields = ['pedido', 'usuario_responsable']

# Para ConteoInventario y su detalle (opcional, pero buena práctica)
class ConteoInventarioInline(admin.TabularInline): # Anteriormente 'DetalleConteoInventarioInline'
    model = ConteoInventario # El modelo se llama ConteoInventario
    extra = 0
    fields = ('producto', 'cantidad_sistema_antes', 'cantidad_fisica_contada', 'diferencia', 'usuario_conteo')
    readonly_fields = ('diferencia',) # La diferencia es una propiedad calculada
    autocomplete_fields = ['producto', 'usuario_conteo']

@admin.register(CabeceraConteo)
class CabeceraConteoAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha_conteo', 'motivo', 'usuario_registro', 'fecha_hora_registro')
    list_filter = ('fecha_conteo', 'usuario_registro')
    search_fields = ('id', 'motivo', 'notas_generales', 'usuario_registro__username')
    date_hierarchy = 'fecha_conteo'
    inlines = [ConteoInventarioInline]
    readonly_fields = ('fecha_hora_registro',)
    
class SalidaInternaDetalleInline(admin.TabularInline):
    model = SalidaInternaDetalle
    extra = 0
    autocomplete_fields = ['producto']
    fields = ('producto', 'cantidad_despachada', 'cantidad_devuelta', 'observaciones_detalle')
    readonly_fields = ('cantidad_devuelta',) # La cantidad devuelta se manejará por la vista de devolución

@admin.register(SalidaInternaCabecera)
class SalidaInternaCabeceraAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha_hora_salida', 'tipo_salida', 'destino_descripcion', 'responsable_entrega', 'estado')
    list_filter = ('tipo_salida', 'estado', 'fecha_hora_salida', 'responsable_entrega')
    search_fields = ('id', 'destino_descripcion', 'documento_referencia_externo', 'responsable_entrega__username')
    date_hierarchy = 'fecha_hora_salida'
    inlines = [SalidaInternaDetalleInline]
    autocomplete_fields = ['responsable_entrega']