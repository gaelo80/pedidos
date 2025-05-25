# factura/admin.py
from django.contrib import admin
from .models import EstadoFacturaDespacho

@admin.register(EstadoFacturaDespacho)
class EstadoFacturaDespachoAdmin(admin.ModelAdmin):
    """
    Configuración para la administración del modelo EstadoFacturaDespacho.
    """
    list_display = (
        'get_despacho_id',  # Usaremos un método para mostrar el ID del despacho
        'estado',
        'fecha_hora_facturado_sistema',
        'usuario_responsable',
        'referencia_factura_externa',
        'fecha_creacion_registro',
        'fecha_ultima_modificacion',
    )
    list_filter = (
        'estado',
        'fecha_hora_facturado_sistema',
        'usuario_responsable',
    )
    search_fields = (
        'despacho__id',  # Búsqueda directa por el ID del ComprobanteDespacho
        'despacho__pedido__id', # Búsqueda por el ID del Pedido asociado al ComprobanteDespacho
        'referencia_factura_externa',
        'usuario_responsable__username',
    )
    readonly_fields = (
        'fecha_creacion_registro',
        'fecha_ultima_modificacion',
        'despacho', # Generalmente no se querrá cambiar el despacho asociado una vez creado el estado.
    )
    fieldsets = (
        (None, {
            'fields': ('despacho', 'estado')
        }),
        ('Detalles de Facturación (Sistema Contable Externo)', {
            'fields': ('referencia_factura_externa', 'fecha_hora_facturado_sistema', 'notas_facturacion')
        }),
        ('Auditoría', {
            'fields': ('usuario_responsable', 'fecha_creacion_registro', 'fecha_ultima_modificacion')
        }),
    )

    def get_despacho_id(self, obj):
        """
        Retorna el ID del ComprobanteDespacho asociado.
        Esto es útil porque 'despacho' es la clave primaria y OneToOneField.
        """
        return obj.despacho_id # Accede directamente al ID del despacho
    get_despacho_id.admin_order_field = 'despacho__id' # Permite ordenar por esta columna
    get_despacho_id.short_description = 'ID Comprobante Despacho (Bodega)' # Etiqueta en el admin

    def save_model(self, request, obj, form, change):
        """
        Asigna automáticamente el usuario responsable si no está seteado
        y es una nueva creación.
        """
        if not obj.pk and not obj.usuario_responsable: # Si es nuevo y no tiene usuario
            obj.usuario_responsable = request.user
        super().save_model(request, obj, form, change)

