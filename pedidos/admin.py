# pedidos/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Pedido, DetallePedido

# ===================================================================
# INLINE PARA LOS DETALLES DEL PEDIDO
# ===================================================================
class DetallePedidoInline(admin.TabularInline):
    model = DetallePedido
    extra = 0 # No mostrar formularios extra por defecto
    fields = ('producto', 'cantidad', 'precio_unitario', 'subtotal')
    readonly_fields = ('subtotal',)

    # --- ¡PUNTO CRÍTICO DE SEGURIDAD! ---
    # El campo de autocompletado para 'producto' depende de que el 'ProductoAdmin'
    # en 'productos/admin.py' esté correctamente asegurado con los métodos
    # get_queryset() y get_search_results() para filtrar por empresa.
    autocomplete_fields = ['producto']

# ===================================================================
# ADMIN PRINCIPAL PARA EL MODELO PEDIDO
# ===================================================================
@admin.register(Pedido) # Usamos el decorador @admin.register para registrar el modelo
class PedidoAdmin(admin.ModelAdmin):
    
    # --- CONFIGURACIÓN VISUAL Y DE USABILIDAD ---
    # Se añade 'empresa' para que los superusuarios puedan ver a quién pertenece cada pedido.
    list_display = (
        'id',
        'empresa',
        'cliente',
        'vendedor',
        'fecha_hora',
        'estado',
        'ver_total',
        'enlace_pdf',
        'enlace_descarga_fotos_lista', # <- AÑADIDO DE VUELTA
    )
    # Se añade 'empresa' a los filtros.
    list_filter = ('empresa', 'estado', 'fecha_hora', 'vendedor__user__username')
    search_fields = ('id', 'cliente__nombre_completo', 'cliente__identificacion', 'vendedor__user__username')
    date_hierarchy = 'fecha_hora'
    inlines = [DetallePedidoInline]

    # --- ¡PUNTO CRÍTICO DE SEGURIDAD! ---
    # Estos campos dependen de que 'ClienteAdmin' y 'VendedorAdmin' estén
    # correctamente asegurados para filtrar por empresa.
    autocomplete_fields = ['cliente', 'vendedor']

    # Se hacen los campos de decisión y la empresa de solo lectura para mantener la integridad.
    readonly_fields = (
        'empresa',
        'fecha_hora',
        'token_descarga_fotos',
        'get_enlace_descarga_fotos_formulario',
        'subtotal_base_bruto',
        'valor_total_descuento',
        'subtotal_final_neto',
        'valor_iva_final',
        'total_a_pagar',
        'total_cantidad_productos',
        'usuario_decision_cartera', 
        'fecha_decision_cartera',
        'usuario_decision_admin', 
        'fecha_decision_admin',
    )

    # Organización de los campos en el formulario de detalle.
    fieldsets = (
        ("Información Principal", {
            'fields': ('empresa', 'cliente', 'vendedor', 'estado', 'fecha_hora')
        }),
        ('Montos y Descuento', {
            'fields': (
                'porcentaje_descuento',
                'subtotal_base_bruto',
                'valor_total_descuento',
                'subtotal_final_neto',
                'valor_iva_final',
                'total_a_pagar',
                'total_cantidad_productos',
            )
        }),
        ('Observaciones y Decisiones de Aprobación', {
            'fields': (
                'notas',
                'motivo_cartera', 'usuario_decision_cartera', 'fecha_decision_cartera',
                'motivo_admin', 'usuario_decision_admin', 'fecha_decision_admin',
            ),
            'classes': ('collapse',),
        }),
        ('Información Adicional', {
            'fields': ('get_enlace_descarga_fotos_formulario',),
            'classes': ('collapse',),
        }),
    )

    # --- CORRECCIÓN DE SEGURIDAD 1: Filtrado de la lista principal ---
    def get_queryset(self, request):
        """
        Filtra los pedidos para mostrar únicamente los que pertenecen a la 
        empresa del usuario actual (tenant).
        """
        qs = super().get_queryset(request)
        tenant = getattr(request, 'tenant', None)
        
        # Un superusuario puede ver los pedidos de todas las empresas.
        if request.user.is_superuser:
            return qs
        
        # Un usuario normal solo ve los de su empresa.
        if tenant:
            return qs.filter(empresa=tenant)
        
        # Como medida de seguridad, no se muestra nada si no se detecta una empresa.
        return qs.none()
    
    # --- CORRECCIÓN DE SEGURIDAD 2: Asignación al guardar un nuevo pedido ---
    def save_model(self, request, obj, form, change):
        """
        Asigna automáticamente la empresa del usuario actual al crear
        un nuevo pedido desde el panel de administración.
        """
        # 'change' es False cuando el objeto se está creando.
        if not change:
            tenant = getattr(request, 'tenant', None)
            if tenant:
                obj.empresa = tenant
        
        super().save_model(request, obj, form, change)

    # --- MÉTODOS AUXILIARES PARA MOSTRAR EN EL ADMIN ---
    def ver_total(self, obj):
        if hasattr(obj, 'total_a_pagar'):
            return f"${obj.total_a_pagar:,.2f}"
        return "N/A"
    ver_total.short_description = 'Total Pedido'

    def enlace_pdf(self, obj):
        if obj.pk:
            url = reverse('pedidos:generar_pedido_pdf', args=[obj.pk])
            return format_html('<a href="{}" target="_blank">Ver PDF</a>', url)
        return "N/A"
    enlace_pdf.short_description = 'PDF Pedido'

    def get_enlace_descarga_fotos_formulario(self, obj):
        """Muestra el enlace de descarga en el formulario de detalle."""
        if obj.token_descarga_fotos:
            enlace = obj.get_enlace_descarga_fotos()
            if enlace:
                return format_html("<a href='{0}' target='_blank'>Descargar Fotos</a>", enlace)
        return "No disponible"
    get_enlace_descarga_fotos_formulario.short_description = "Enlace de Descarga de Fotos"

    # --- FUNCIÓN AÑADIDA DE VUELTA ---
    def enlace_descarga_fotos_lista(self, obj):
        """Para mostrar un enlace corto en la lista de Pedidos."""
        if obj.token_descarga_fotos:
            enlace = obj.get_enlace_descarga_fotos()
            if enlace:
                return format_html("<a href='{0}' target='_blank'>Ver Fotos</a>", enlace)
        return "N/A"
    enlace_descarga_fotos_lista.short_description = "Fotos Pedido"