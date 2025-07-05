# prospectos/admin.py
from django.contrib import admin
from .models import Prospecto, DocumentoAdjunto

class DocumentoAdjuntoInline(admin.TabularInline):
    """
    Permite ver y añadir documentos directamente desde la página de un prospecto
    en el panel de administración.
    """
    model = DocumentoAdjunto
    extra = 1 # Muestra un campo vacío para añadir un nuevo documento.
    readonly_fields = ('fecha_carga',)
    fields = ('tipo_documento', 'archivo', 'fecha_carga')


@admin.register(Prospecto)
class ProspectoAdmin(admin.ModelAdmin):
    """
    Configuración del modelo Prospecto en el panel de administración de Django.
    """
    list_display = ('nombre_completo', 'identificacion', 'empresa', 'estado', 'vendedor_asignado', 'fecha_solicitud')
    list_filter = ('estado', 'empresa', 'fecha_solicitud')
    search_fields = ('nombre_completo', 'identificacion', 'vendedor_asignado__username')
    readonly_fields = ('fecha_solicitud',)
    
    # Muestra los documentos adjuntos dentro de la vista de detalle del prospecto.
    inlines = [DocumentoAdjuntoInline]

    fieldsets = (
        ("Información Principal", {
            'fields': ('empresa', 'nombre_completo', 'identificacion', 'ciudad', 'direccion', 'telefono', 'email')
        }),
        ("Estado de la Solicitud", {
            'fields': ('estado', 'vendedor_asignado', 'notas_evaluacion', 'fecha_solicitud')
        }),
    )

    def get_queryset(self, request):
        """
        Filtra los prospectos para que los usuarios no-superusuarios solo vean
        los de su propia empresa (tenant).
        """
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        
        tenant = getattr(request, 'tenant', None)
        if tenant:
            return qs.filter(empresa=tenant)
        
        return qs.none()

    def save_model(self, request, obj, form, change):
        """
        Asigna automáticamente la empresa del usuario al crear un prospecto
        desde el admin, si no es un superusuario.
        """
        if not change and not request.user.is_superuser:
            tenant = getattr(request, 'tenant', None)
            if tenant:
                obj.empresa = tenant
        super().save_model(request, obj, form, change)

@admin.register(DocumentoAdjunto)
class DocumentoAdjuntoAdmin(admin.ModelAdmin):
    """
    Configuración para visualizar todos los documentos adjuntos de forma independiente.
    """
    list_display = ('prospecto', 'tipo_documento', 'archivo', 'fecha_carga')
    list_filter = ('tipo_documento', 'fecha_carga', 'prospecto__empresa')
    search_fields = ('prospecto__nombre_completo', 'prospecto__identificacion')

    def get_queryset(self, request):
        """
        Filtra los documentos para que los usuarios no-superusuarios solo vean
        los de su propia empresa (tenant).
        """
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs.select_related('prospecto')

        tenant = getattr(request, 'tenant', None)
        if tenant:
            return qs.filter(prospecto__empresa=tenant).select_related('prospecto')

        return qs.none()