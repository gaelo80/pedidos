from django.contrib import admin
# Añade CostoFijo y DetalleCostoFijo a la importación
from .models import Insumo, Proceso, Costeo, DetalleInsumo, DetalleProceso, CostoFijo, DetalleCostoFijo, Confeccionista, TarifaConfeccionista


@admin.register(TarifaConfeccionista)
class TarifaConfeccionistaAdmin(admin.ModelAdmin):
    list_display = ('confeccionista', 'proceso', 'costo')
    list_filter = ('confeccionista', 'proceso')
    search_fields = ('confeccionista__nombre', 'proceso__nombre')
    list_per_page = 20

class DetalleInsumoInline(admin.TabularInline):
    model = DetalleInsumo
    extra = 1

class DetalleProcesoInline(admin.TabularInline):
    model = DetalleProceso
    extra = 1

# Nuevo Inline para Costos Fijos
class DetalleCostoFijoInline(admin.TabularInline):
    model = DetalleCostoFijo
    extra = 0 # No añadir extras por defecto, se calculan solos
    readonly_fields = ('costo_fijo', 'valor_calculado') # Hacerlos de solo lectura

@admin.register(Costeo)
class CosteoAdmin(admin.ModelAdmin):
    # Añadir el nuevo inline
    inlines = [DetalleInsumoInline, DetalleProcesoInline, DetalleCostoFijoInline]
    list_display = ['referencia', 'empresa', 'cantidad_producida', 'costo_unitario', 'costo_total', 'fecha']
    readonly_fields = ('costo_total',) # Es mejor que el costo total sea de solo lectura

# Registra los otros modelos para que aparezcan en el admin
admin.site.register(Insumo)
admin.site.register(Proceso)
admin.site.register(Confeccionista)
admin.site.register(CostoFijo)