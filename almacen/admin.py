from django.contrib import admin
from .models import InventarioAlmacen, FacturaAlmacen, DetalleFacturaAlmacen

@admin.register(InventarioAlmacen)
class InventarioAlmacenAdmin(admin.ModelAdmin):
    list_display = ('producto', 'precio_detal', 'stock_actual')
    search_fields = ('producto__descripcion', 'producto__referencia')
    list_filter = ('stock_actual',)

@admin.register(FacturaAlmacen)
class FacturaAlmacenAdmin(admin.ModelAdmin):
    list_display = ('consecutivo_local', 'fecha_venta', 'total_venta', 'vendedor', 'sincronizado_el')
    readonly_fields = ('sincronizado_el',)

admin.site.register(DetalleFacturaAlmacen)