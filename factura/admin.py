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
        'get_empresa_nombre',
        'estado',
        'fecha_hora_facturado_sistema',
        'usuario_responsable',
        'referencia_factura_externa',
        'fecha_creacion_registro',
        'fecha_ultima_modificacion',
    )
    list_filter = (
        'empresa',  # Filtro por empresa
        'despacho__pedido__estado',  # Filtro por estado del pedido asociado al ComprobanteDespacho        
        'estado',
        'fecha_hora_facturado_sistema',
        'usuario_responsable',
    )
    search_fields = (
        'despacho__id',  # Búsqueda directa por el ID del ComprobanteDespacho
        'despacho__pedido__id', # Búsqueda por el ID del Pedido asociado al ComprobanteDespacho
        'referencia_factura_externa',
        'usuario_responsable__username',
        'empresa__nombre',  # Búsqueda por nombre de la empresa
    )
    readonly_fields = (
        'get_empresa_nombre',
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

    def get_queryset(self, request):
        """
        <<< CORRECCIÓN CRÍTICA DE SEGURIDAD >>>
        Filtra el queryset para mostrar únicamente los objetos que pertenecen
        a la empresa del usuario actual. Los superusuarios pueden ver todo.
        """
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        
        # Asumiendo que tienes un middleware que asigna 'tenant' al request.
        empresa_actual = getattr(request, 'tenant', None)
        if empresa_actual:
            return qs.filter(empresa=empresa_actual)
        
        # Si no hay empresa, no se muestra nada para evitar fugas de datos.
        return qs.none()

    def save_model(self, request, obj, form, change):
        """
        <<< REFUERZO DE SEGURIDAD Y COHERENCIA >>>
        Asegura que la empresa se asigne correctamente al guardar.
        """
        # La lógica en models.py ya hace esto, pero es una buena práctica
        # tener una defensa en profundidad en el admin.
        if obj.despacho and not obj.empresa_id:
            obj.empresa = obj.despacho.empresa
            
        # Asigna el usuario responsable si es un objeto nuevo.
        if not obj.pk and not obj.usuario_responsable:
            obj.usuario_responsable = request.user
            
        super().save_model(request, obj, form, change)


    def get_despacho_id(self, obj):
        return obj.despacho_id
    get_despacho_id.admin_order_field = 'despacho__id'
    get_despacho_id.short_description = 'ID Comprobante Despacho'

    @admin.display(description='Empresa', ordering='empresa__nombre')
    def get_empresa_nombre(self, obj):
        """Muestra el nombre de la empresa asociada."""
        if obj.empresa:
            return obj.empresa.nombre
        # Si el objeto aún no se ha guardado, intenta obtenerlo del despacho
        if obj.despacho and obj.despacho.empresa:
            return obj.despacho.empresa.nombre
        return "N/A"

