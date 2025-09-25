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
    fields = ('producto', 'cantidad', 'cantidad_verificada', 'precio_unitario', 'subtotal')
    readonly_fields = ('subtotal',)

    autocomplete_fields = ['producto']


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    
    # --- CONFIGURACIÓN VISUAL Y DE USABILIDAD (Se queda igual) ---
    list_display = ('numero_pedido_empresa',
        'id', 'empresa', 'cliente', 'vendedor', 'fecha_hora', 'estado',
        'ver_total', 'enlace_pdf', 'enlace_descarga_fotos_lista',
    )
    list_filter = ('empresa', 'estado', 'fecha_hora', 'vendedor__user__username')
    search_fields = ('id', 'cliente__nombre_completo', 'cliente__identificacion', 'vendedor__user__username')
    date_hierarchy = 'fecha_hora'
    inlines = [DetallePedidoInline]
    autocomplete_fields = ['cliente', 'vendedor']

    # --- CORRECCIÓN A READONLY_FIELDS ---
    # Cambiamos los nombres para que apunten a los nuevos métodos que definiremos más abajo
    readonly_fields = (
        'empresa', 'fecha_hora', 'token_descarga_fotos',
        'get_enlace_descarga_fotos_formulario',
        'mostrar_subtotal_base_bruto',
        'mostrar_valor_total_descuento',
        'mostrar_subtotal_final_neto',
        'mostrar_valor_iva_final',
        'mostrar_total_a_pagar',
        'mostrar_total_cantidad_productos',
        'usuario_decision_cartera', 'fecha_decision_cartera',
        'usuario_decision_admin', 'fecha_decision_admin',
    )

    # Organización de los campos en el formulario de detalle (Se queda igual)
    fieldsets = (
        ("Información Principal", {
            'fields': ('empresa', 'cliente', 'vendedor', 'estado', 'fecha_hora')
        }),
        # --- CORRECCIÓN EN FIELDSETS ---
        # Usamos los nombres de los nuevos métodos también aquí
        ('Montos y Descuento', {
            'fields': (
                'porcentaje_descuento',
                'mostrar_subtotal_base_bruto',
                'mostrar_valor_total_descuento',
                'mostrar_subtotal_final_neto',
                'mostrar_valor_iva_final',
                'mostrar_total_a_pagar',
                'mostrar_total_cantidad_productos',
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

    # --- LÓGICA DE SEGURIDAD (Se queda igual) ---
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        tenant = getattr(request, 'tenant', None)
        if request.user.is_superuser:
            return qs
        if tenant:
            return qs.filter(empresa=tenant)
        return qs.none()
    
    def save_model(self, request, obj, form, change):
        if not change:
            tenant = getattr(request, 'tenant', None)
            if tenant:
                obj.empresa = tenant
        super().save_model(request, obj, form, change)

    # --- NUEVOS MÉTODOS PARA MOSTRAR VALORES CALCULADOS ---
    @admin.display(description='Subtotal Base Bruto')
    def mostrar_subtotal_base_bruto(self, obj):
        return f"${obj.subtotal_base_bruto:,.2f}"

    @admin.display(description='Valor Descuento')
    def mostrar_valor_total_descuento(self, obj):
        return f"${obj.valor_total_descuento:,.2f}"

    @admin.display(description='Subtotal Neto')
    def mostrar_subtotal_final_neto(self, obj):
        return f"${obj.subtotal_final_neto:,.2f}"

    @admin.display(description='Valor IVA')
    def mostrar_valor_iva_final(self, obj):
        return f"${obj.valor_iva_final:,.2f}"

    @admin.display(description='Total a Pagar')
    def mostrar_total_a_pagar(self, obj):
        # Esta función ahora también da formato al número
        return f"${obj.total_a_pagar:,.2f}"

    @admin.display(description='Cantidad de Productos')
    def mostrar_total_cantidad_productos(self, obj):
        return obj.total_cantidad_productos

    # --- MÉTODOS AUXILIARES QUE YA TENÍAS (Se quedan igual) ---
    def ver_total(self, obj):
        # Reemplazamos esta lógica para llamar a nuestro nuevo método
        return self.mostrar_total_a_pagar(obj)
    ver_total.short_description = 'Total Pedido'

    def enlace_pdf(self, obj):
        if obj.pk:
            url = reverse('pedidos:generar_pedido_pdf', args=[obj.pk])
            return format_html('<a href="{}" target="_blank">Ver PDF</a>', url)
        return "N/A"
    enlace_pdf.short_description = 'PDF Pedido'

    def get_enlace_descarga_fotos_formulario(self, obj):
        if obj.token_descarga_fotos:
            enlace = obj.get_enlace_descarga_fotos()
            if enlace:
                return format_html("<a href='{0}' target='_blank'>Descargar Fotos</a>", enlace)
        return "No disponible"
    get_enlace_descarga_fotos_formulario.short_description = "Enlace de Descarga de Fotos"

    def enlace_descarga_fotos_lista(self, obj):
        if obj.token_descarga_fotos:
            enlace = obj.get_enlace_descarga_fotos()
            if enlace:
                return format_html("<a href='{0}' target='_blank'>Ver Fotos</a>", enlace)
        return "N/A"
    enlace_descarga_fotos_lista.short_description = "Fotos Pedido"