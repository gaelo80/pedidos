from django.contrib import admin
from .models import (
    CorreccionProduccion, DecisionDefecto, DefectoCalidad, EtapaProduccion, LoteProduccion,
    MovimientoLoteProduccion, OrdenProduccion, PartidaLote, RecepcionLinea, RecepcionTaller,
    RemisionLinea, RemisionTaller, RutaOrdenProduccion, TallerExterno,
)


class SoloLecturaMixin:
    """Documentos que sustentan pagos a talleres: no se editan ni se borran desde el admin."""
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class RutaInline(admin.TabularInline):
    model = RutaOrdenProduccion
    extra = 0


@admin.register(OrdenProduccion)
class OrdenProduccionAdmin(admin.ModelAdmin):
    inlines = [RutaInline]
    list_display = ['numero_orden', 'empresa', 'referencia_color', 'estado', 'total_tallas', 'fecha_creacion']
    list_filter = ['empresa', 'estado']
    search_fields = ['numero_orden', 'referencia_color__referencia_base']
    readonly_fields = ['numero_orden']


class MovimientoLoteInline(SoloLecturaMixin, admin.TabularInline):
    model = MovimientoLoteProduccion
    extra = 0


class PartidaInline(SoloLecturaMixin, admin.TabularInline):
    model = PartidaLote
    fk_name = 'lote'
    extra = 0
    fields = ['numero', 'etapa', 'taller', 'cantidad', 'estado', 'fecha_ingreso']


@admin.register(LoteProduccion)
class LoteProduccionAdmin(admin.ModelAdmin):
    inlines = [PartidaInline, MovimientoLoteInline]
    list_display = ['numero_lote', 'orden', 'talla', 'cantidad_inicial', 'estado']
    list_filter = ['estado']
    search_fields = ['numero_lote']


@admin.register(TallerExterno)
class TallerExternoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'empresa', 'nit', 'telefono', 'activo']
    list_filter = ['empresa', 'activo']
    search_fields = ['nombre', 'nit']


class RemisionLineaInline(SoloLecturaMixin, admin.TabularInline):
    model = RemisionLinea
    extra = 0


@admin.register(RemisionTaller)
class RemisionTallerAdmin(SoloLecturaMixin, admin.ModelAdmin):
    inlines = [RemisionLineaInline]
    list_display = ['numero', 'empresa', 'taller', 'etapa', 'fecha_hora', 'usuario']
    list_filter = ['empresa', 'taller']
    search_fields = ['numero']


class RecepcionLineaInline(SoloLecturaMixin, admin.TabularInline):
    model = RecepcionLinea
    extra = 0


@admin.register(RecepcionTaller)
class RecepcionTallerAdmin(SoloLecturaMixin, admin.ModelAdmin):
    inlines = [RecepcionLineaInline]
    list_display = ['numero', 'empresa', 'remision', 'fecha_hora', 'usuario']
    list_filter = ['empresa']
    search_fields = ['numero', 'remision__numero']


@admin.register(CorreccionProduccion)
class CorreccionProduccionAdmin(SoloLecturaMixin, admin.ModelAdmin):
    list_display = ['fecha_hora', 'tipo', 'remision_linea', 'cantidad', 'usuario']


class DecisionInline(SoloLecturaMixin, admin.TabularInline):
    model = DecisionDefecto
    extra = 0


@admin.register(DefectoCalidad)
class DefectoCalidadAdmin(SoloLecturaMixin, admin.ModelAdmin):
    inlines = [DecisionInline]
    list_display = ['fecha_hora', 'lote', 'cantidad_segunda', 'cantidad_tercera', 'causa', 'decision', 'taller_responsable']
    list_filter = ['decision', 'causa']


admin.site.register(EtapaProduccion)
