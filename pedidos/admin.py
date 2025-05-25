# pedidos/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
# from import_export.admin import ImportExportModelAdmin # Mantienes esto si lo usas
# from import_export import resources # Mantienes esto si lo usas
from .models import Pedido, DetallePedido

# class PedidoResource(resources.ModelResource): # Si usas ImportExport
#     class Meta:
#         model = Pedido

class DetallePedidoInline(admin.TabularInline):
    model = DetallePedido
    extra = 0
    autocomplete_fields = ['producto']
    # Considera hacer campos readonly si es apropiado para el inline
    # readonly_fields = ('precio_unitario', 'subtotal_display') # Ejemplo
    fields = ('producto', 'cantidad', 'precio_unitario', 'subtotal') # Asegúrate que subtotal_display exista o usa 'subtotal'
    readonly_fields = ('subtotal',)


    def subtotal_display(self, obj): # Ejemplo de cómo mostrar una propiedad del modelo DetallePedido
        if obj.pk and hasattr(obj, 'subtotal'):
            return f"${obj.subtotal:,.2f}" # Asume que DetallePedido.subtotal es una propiedad
        return "N/A"
    subtotal_display.short_description = 'Subtotal Línea'


class PedidoAdmin(admin.ModelAdmin):
    
    list_display = (
        'id',
        'cliente',
        'vendedor',
        'fecha_hora',
        'estado',
        'ver_total',
        'enlace_pdf',
        'enlace_descarga_fotos_lista' # Añadido para la lista
    )
    list_filter = ('estado', 'fecha_hora', 'vendedor__user__username', 'cliente__nombre_completo')
    search_fields = ('id', 'cliente__nombre_completo', 'cliente__identificacion', 'detalles__producto__nombre', 'vendedor__user__username')
    
    readonly_fields = (
        'fecha_hora',
        'token_descarga_fotos',
        'get_enlace_descarga_fotos_formulario', # Para el formulario de detalle
        # Propiedades calculadas del modelo Pedido
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
    
    inlines = [DetallePedidoInline]
    autocomplete_fields = ['cliente', 'vendedor']
    date_hierarchy = 'fecha_hora'

    fieldsets = (
        (None, {
            'fields': ('cliente', 'vendedor', 'estado', 'fecha_hora')
        }),
        ('Montos del Pedido', { # Sección para montos y descuento
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
        
        ('Observaciones y Decisiones', { # Nueva sección o integrada en otra
            'fields': (
                'notas', # Notas del vendedor
                'motivo_cartera', 'usuario_decision_cartera', 'fecha_decision_cartera',
                'motivo_admin', 'usuario_decision_admin', 'fecha_decision_admin',
            ),
            'classes': ('collapse',), #
        }),
                
        ('Información Adicional y Enlaces', {
            'fields': (
                #'notas',
                'token_descarga_fotos',
                'get_enlace_descarga_fotos_formulario'
            ),
            'classes': ('collapse',),
        }),
    )

    def enlace_pdf(self, obj):
        if obj.pk:
            url = reverse('pedidos:generar_pedido_pdf', args=[obj.pk])
            return format_html('<a href="{}" target="_blank">Ver PDF</a>', url)
        return "N/A"
    enlace_pdf.short_description = 'PDF Pedido'

    def ver_total(self, obj):
        if hasattr(obj, 'total_a_pagar'):
             return f"${obj.total_a_pagar:,.2f}" # Usa la propiedad del modelo
        return "N/A" # Fallback si no existe la propiedad
    ver_total.short_description = 'Total Pedido'
    
    def get_enlace_descarga_fotos_formulario(self, obj):
        """Para mostrar en el formulario de detalle del Pedido (en readonly_fields)."""
        if obj.token_descarga_fotos:
            try:
                enlace = obj.get_enlace_descarga_fotos() # Llama al método del modelo Pedido
                if enlace:
                    return format_html("<a href='{0}' target='_blank'>{0}</a>", enlace)
                return "No se pudo generar el enlace (verificar URL)"
            except Exception as e:
                return f"Error generando enlace: {e}"
        return "N/A (Sin token)"
    get_enlace_descarga_fotos_formulario.short_description = "Enlace Descarga Fotos (Formulario)"

    def enlace_descarga_fotos_lista(self, obj):
        """Para mostrar en la lista de Pedidos (en list_display)."""
        if obj.token_descarga_fotos:
            try:
                enlace = obj.get_enlace_descarga_fotos()
                if enlace:
                    return format_html("<a href='{0}' target='_blank'>Ver Fotos</a>", enlace)
                return "N/A (Link)"
            except Exception:
                return "Error Link" 
        return "N/A (Token)"
    enlace_descarga_fotos_lista.short_description = "Fotos Pedido"

admin.site.register(Pedido, PedidoAdmin)

