from django.contrib import admin
from .models import (
    TurnoCaja, VentaPOS, DetalleVentaPOS, PagoVentaPOS, PrecioEspecialPOS,
    DevolucionCambioPOS, DetalleDevolucionPOS, DetalleEntregaCambioPOS,
)


class DetalleVentaPOSInline(admin.TabularInline):
    model = DetalleVentaPOS
    extra = 0


class PagoVentaPOSInline(admin.TabularInline):
    model = PagoVentaPOS
    extra = 0


@admin.register(TurnoCaja)
class TurnoCajaAdmin(admin.ModelAdmin):
    list_display = ('pk', 'empresa', 'bodega', 'usuario_cajero', 'fecha_apertura', 'estado', 'saldo_inicial', 'saldo_final_contado', 'diferencia')
    list_filter = ('empresa', 'estado', 'bodega')
    search_fields = ('bodega__nombre', 'usuario_cajero__username')


@admin.register(VentaPOS)
class VentaPOSAdmin(admin.ModelAdmin):
    list_display = ('consecutivo', 'empresa', 'turno', 'cliente', 'fecha_hora', 'total_venta', 'estado')
    list_filter = ('empresa', 'estado')
    search_fields = ('consecutivo', 'cliente__nombre_completo')
    inlines = [DetalleVentaPOSInline, PagoVentaPOSInline]


@admin.register(PrecioEspecialPOS)
class PrecioEspecialPOSAdmin(admin.ModelAdmin):
    list_display = ('producto', 'bodega', 'precio_especial', 'usuario_actualizacion', 'fecha_actualizacion')
    list_filter = ('empresa', 'bodega')
    search_fields = ('producto__referencia', 'producto__nombre')


class DetalleDevolucionPOSInline(admin.TabularInline):
    model = DetalleDevolucionPOS
    extra = 0


class DetalleEntregaCambioPOSInline(admin.TabularInline):
    model = DetalleEntregaCambioPOS
    extra = 0


@admin.register(DevolucionCambioPOS)
class DevolucionCambioPOSAdmin(admin.ModelAdmin):
    list_display = ('pk', 'tipo', 'venta_original', 'turno', 'usuario', 'fecha_hora', 'total_valor_devuelto', 'total_valor_entregado')
    list_filter = ('empresa', 'tipo')
    search_fields = ('venta_original__consecutivo',)
    inlines = [DetalleDevolucionPOSInline, DetalleEntregaCambioPOSInline]
