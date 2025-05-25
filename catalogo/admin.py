# catalogo/admin.py
from django.contrib import admin
from .models import EnlaceCatalogoTemporal # Asegúrate de importar tus otros modelos si es necesario

@admin.register(EnlaceCatalogoTemporal)
class EnlaceCatalogoTemporalAdmin(admin.ModelAdmin):
    list_display = ('descripcion', 'token', 'creado_el', 'expira_el', 'activo', 'esta_disponible', 'veces_usado', 'ver_enlace')
    list_filter = ('activo', 'creado_el', 'expira_el')
    search_fields = ('token', 'descripcion')
    readonly_fields = ('token', 'creado_el', 'veces_usado', 'ver_enlace_campo')
    fieldsets = (
        (None, {
            'fields': ('descripcion', 'expira_el', 'activo')
        }),
        ('Información del Token (Automático)', {
            'fields': ('token', 'creado_el', 'veces_usado', 'ver_enlace_campo'),
            'classes': ('collapse',), # Opcional, para colapsar esta sección
        }),
    )

    def ver_enlace(self, obj):
        from django.utils.html import format_html
        if obj.token:
            url = obj.obtener_url_absoluta()
            return format_html('<a href="{0}" target="_blank">Abrir Enlace</a>', url)
        return "N/A (Guardar para generar)"
    ver_enlace.short_description = "Enlace"

    def ver_enlace_campo(self, obj): # Para el campo readonly en fieldsets
        from django.utils.html import format_html
        if obj.token:
            url = obj.obtener_url_absoluta()
            # Obtener el host completo para que el enlace sea copiable fácilmente
            request = self.get_request_for_obj(obj) if hasattr(self, 'get_request_for_obj') else None
            full_url = request.build_absolute_uri(url) if request else url
            return format_html('<code>{0}</code>', full_url)
        return "N/A"
    ver_enlace_campo.short_description = "URL Compartible"

    # Helper para obtener el request en el admin (puede variar entre versiones de Django)
    _request_for_obj = None
    def get_request_for_obj(self, obj):
        return EnlaceCatalogoTemporalAdmin._request_for_obj

    def changelist_view(self, request, extra_context=None):
        EnlaceCatalogoTemporalAdmin._request_for_obj = request
        return super().changelist_view(request, extra_context)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        EnlaceCatalogoTemporalAdmin._request_for_obj = request
        return super().changeform_view(request, object_id, form_url, extra_context)

# ... (registra tus otros modelos aquí si los tienes)