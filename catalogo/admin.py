# catalogo/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import EnlaceCatalogoTemporal

@admin.register(EnlaceCatalogoTemporal)
class EnlaceCatalogoTemporalAdmin(admin.ModelAdmin):
    """
    Configuración SEGURA para la administración de Enlaces de Catálogo Temporales.
    """
    list_display = (
        'descripcion', 
        'empresa', # RECOMENDACIÓN: Mostrar la empresa en la lista.
        'token', 
        'creado_el', 
        'expira_el', 
        'activo', 
        'esta_disponible', 
        'veces_usado',
        'generado_por' # RECOMENDACIÓN: Saber quién lo generó.
    )
    list_filter = (
        'empresa', # RECOMENDACIÓN: Filtrar por empresa para superusuarios.
        'activo', 
        'creado_el', 
        'expira_el'
    )
    search_fields = ('token', 'descripcion', 'empresa__nombre', 'generado_por__username')
    readonly_fields = ('token', 'creado_el', 'veces_usado', 'ver_enlace_campo', 'generado_por', 'empresa')
    
    fieldsets = (
        (None, {
            'fields': ('descripcion', 'expira_el', 'activo')
        }),
        ('Información del Enlace (Automático)', {
            'fields': ('empresa', 'generado_por', 'token', 'creado_el', 'veces_usado', 'ver_enlace_campo'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        """
        <<< CORRECCIÓN CRÍTICA DE SEGURIDAD >>>
        Filtra los enlaces para que cada usuario solo vea los de su empresa.
        """
        qs = super().get_queryset(request).select_related('empresa', 'generado_por')
        if request.user.is_superuser:
            return qs
        
        empresa_actual = getattr(request, 'tenant', None)
        if empresa_actual:
            return qs.filter(empresa=empresa_actual)
        
        return qs.none()

    def save_model(self, request, obj, form, change):
        """
        <<< REFUERZO DE SEGURIDAD Y COHERENCIA >>>
        Asigna la empresa y el usuario generador al crear un nuevo enlace.
        """
        if not obj.pk: # Si es un objeto nuevo
            empresa_actual = getattr(request, 'tenant', None)
            if empresa_actual:
                obj.empresa = empresa_actual
            obj.generado_por = request.user
        super().save_model(request, obj, form, change)

    def ver_enlace_campo(self, obj):
        """Muestra la URL completa y copiable en los detalles del objeto."""
        if obj.token:
            url = obj.obtener_url_absoluta()
            # Nota: request.build_absolute_uri() no está disponible de forma fiable aquí.
            # Se muestra la URL relativa, que es segura y funcional.
            return format_html('<a href="{0}" target="_blank">{0}</a>', url)
        return "N/A (se genera al guardar)"
    ver_enlace_campo.short_description = "URL Compartible"
    
    def esta_disponible(self, obj):
        """Método para mostrar un booleano en la lista."""
        return obj.esta_disponible()
    esta_disponible.boolean = True
    esta_disponible.short_description = "Disponible"