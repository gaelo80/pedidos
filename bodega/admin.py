from django.contrib import admin
from .models import SalidaInternaCabecera, SalidaInternaDetalle, BorradorDespacho, DetalleBorradorDespacho
from bodega.models import (
    IngresoBodega, DetalleIngresoBodega, 
    PersonalBodega, MovimientoInventario,
    ComprobanteDespacho, DetalleComprobanteDespacho,
    CabeceraConteo, ConteoInventario
)

class TenantAwareAdmin(admin.ModelAdmin):
    """
    Un Mixin para ModelAdmin que automáticamente filtra los querysets por la empresa (tenant)
    del usuario actual. Los superusuarios pueden ver todos los objetos.
    """
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        tenant = getattr(request, 'tenant', None)
        if tenant:
            return qs.filter(empresa=tenant)
        return qs.none()

    def save_model(self, request, obj, form, change):
        """Asigna la empresa actual al objeto al crearlo si no es superusuario."""
        if not obj.pk and not request.user.is_superuser:
            tenant = getattr(request, 'tenant', None)
            if tenant:
                obj.empresa = tenant
        super().save_model(request, obj, form, change)


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
    
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        if obj: # obj es la instancia de IngresoBodega
            formset.form.base_fields['producto'].queryset = formset.form.base_fields['producto'].queryset.filter(
                empresa=obj.empresa
            )
        return formset
    
    
    
    


@admin.register(IngresoBodega)
class IngresoBodegaAdmin(TenantAwareAdmin):
    list_display = ('id', 'empresa', 'fecha_hora', 'proveedor_info', 'documento_referencia', 'usuario')
    list_filter = ('empresa', 'fecha_hora', 'usuario')
    search_fields = ('id', 'proveedor_info', 'documento_referencia', 'detalles__producto__nombre')
    readonly_fields = ('fecha_hora', 'usuario')
    inlines = [DetalleIngresoBodegaInline]

   
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        tenant = getattr(request, 'tenant', None)
        return qs.filter(empresa=tenant) if tenant else qs.none()

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser:
            if 'empresa' in form.base_fields:
                form.base_fields['empresa'].disabled = True
                form.base_fields['empresa'].initial = getattr(request, 'tenant', None)
        return form

    def save_model(self, request, obj, form, change):
        if not obj.pk: # Si es un objeto nuevo
            obj.usuario = request.user
        super().save_model(request, obj, form, change)
        
        
        
        
        
        

@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(TenantAwareAdmin):
    list_display = ('fecha_hora', 'empresa', 'producto', 'cantidad', 'tipo_movimiento', 'usuario', 'documento_referencia')
    list_filter = ('empresa', 'tipo_movimiento', 'fecha_hora', 'producto', 'usuario')
    search_fields = ('producto__nombre', 'producto__referencia', 'documento_referencia', 'usuario__username', 'notas')
    readonly_fields = ('fecha_hora', 'usuario', 'empresa', 'producto', 'cantidad', 'tipo_movimiento')
    list_per_page = 30
    
    def has_add_permission(self, request):
        return False 


class DetalleComprobanteDespachoInline(admin.TabularInline):
    model = DetalleComprobanteDespacho
    extra = 0 # No mostrar formularios extra vacíos por defecto
    autocomplete_fields = ['producto']
    readonly_fields = ('producto', 'cantidad_despachada', 'detalle_pedido_origen') # Hacemos que los detalles aquí sean de solo lectura
    
  

@admin.register(ComprobanteDespacho)
class ComprobanteDespachoAdmin(TenantAwareAdmin):
    list_display = ('id', 'empresa', 'pedido', 'fecha_hora_despacho', 'usuario_responsable')
    list_filter = ('empresa', 'fecha_hora_despacho', 'usuario_responsable')
    search_fields = ('id', 'pedido__id', 'pedido__cliente__nombre_completo', 'usuario_responsable__username')
    date_hierarchy = 'fecha_hora_despacho'
    inlines = [DetalleComprobanteDespachoInline]
    autocomplete_fields = ['pedido', 'usuario_responsable']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        tenant = getattr(request, 'tenant', None)
        return qs.filter(empresa=tenant) if tenant else qs.none()
    
    

class DetalleBorradorDespachoInline(admin.TabularInline):
    model = DetalleBorradorDespacho
    extra = 0
    readonly_fields = ('producto', 'cantidad_escaneada_en_borrador')
    can_delete = True # Permitir borrar detalles si es necesario

@admin.register(BorradorDespacho)
class BorradorDespachoAdmin(TenantAwareAdmin):
  
    list_display = ('id', 'pedido', 'empresa', 'usuario')
    list_filter = ('empresa', 'usuario')
    search_fields = ('pedido__id', 'pedido__numero_pedido_empresa', 'usuario__username')
    inlines = [DetalleBorradorDespachoInline]
       
    readonly_fields = ('pedido', 'empresa', 'usuario')

    


class ConteoInventarioInline(admin.TabularInline): # Anteriormente 'DetalleConteoInventarioInline'
    model = ConteoInventario # El modelo se llama ConteoInventario
    extra = 0
    fields = ('producto', 'cantidad_sistema_antes', 'cantidad_fisica_contada', 'diferencia', 'usuario_conteo')
    readonly_fields = ('diferencia',) # La diferencia es una propiedad calculada
    autocomplete_fields = ['producto', 'usuario_conteo']
    
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        if obj: # obj es la instancia de CabeceraConteo
            formset.form.base_fields['producto'].queryset = formset.form.base_fields['producto'].queryset.filter(
                empresa=obj.empresa
            )
        return formset
    

@admin.register(CabeceraConteo)
class CabeceraConteoAdmin(TenantAwareAdmin):
    list_display = ('id', 'empresa', 'fecha_conteo', 'motivo', 'usuario_registro', 'fecha_hora_registro')
    list_filter = ('empresa', 'fecha_conteo', 'usuario_registro')
    search_fields = ('id', 'motivo', 'notas_generales', 'usuario_registro__username')
    date_hierarchy = 'fecha_conteo'
    inlines = [ConteoInventarioInline]
    readonly_fields = ('fecha_hora_registro',)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        tenant = getattr(request, 'tenant', None)
        return qs.filter(empresa=tenant) if tenant else qs.none()

    def save_model(self, request, obj, form, change):
        if not change:
            if not request.user.is_superuser:
                obj.empresa = getattr(request, 'tenant', None)
            obj.usuario_registro = request.user
        super().save_model(request, obj, form, change)
    
class SalidaInternaDetalleInline(admin.TabularInline):
    model = SalidaInternaDetalle
    extra = 0
    autocomplete_fields = ['producto']
    fields = ('producto', 'cantidad_despachada', 'cantidad_devuelta', 'observaciones_detalle')
    readonly_fields = ('cantidad_devuelta',) # La cantidad devuelta se manejará por la vista de devolución
    
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        if obj: # obj es la instancia de SalidaInternaCabecera
            formset.form.base_fields['producto'].queryset = formset.form.base_fields['producto'].queryset.filter(
                empresa=obj.empresa
            )
        return formset
    
    
    
    
    

@admin.register(SalidaInternaCabecera)
class SalidaInternaCabeceraAdmin(TenantAwareAdmin):
    list_display = ('id', 'empresa', 'fecha_hora_salida', 'tipo_salida', 'destino_descripcion', 'responsable_entrega', 'estado')
    list_filter = ('empresa', 'tipo_salida', 'estado', 'fecha_hora_salida', 'responsable_entrega')
    search_fields = ('id', 'destino_descripcion', 'documento_referencia_externo', 'responsable_entrega__username')
    date_hierarchy = 'fecha_hora_salida'
    inlines = [SalidaInternaDetalleInline]
    autocomplete_fields = ['responsable_entrega']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        tenant = getattr(request, 'tenant', None)
        return qs.filter(empresa=tenant) if tenant else qs.none()

    def save_model(self, request, obj, form, change):
        if not change:
            if not request.user.is_superuser:
                obj.empresa = getattr(request, 'tenant', None)
            obj.responsable_entrega = request.user
        super().save_model(request, obj, form, change)