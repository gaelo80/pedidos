# cartera/admin.py
from django.contrib import admin
from .models import DocumentoCartera
from .models import DocumentoCartera, PerfilImportacionCartera

@admin.register(DocumentoCartera)
class DocumentoCarteraAdmin(admin.ModelAdmin):
    # Campos a mostrar en la lista
    list_display = (
        'cliente', 
        'empresa',
        'tipo_documento', 
        'numero_documento', 
        'fecha_documento', 
        'fecha_vencimiento', 
        'saldo_actual', 
        'esta_vencido', # Propiedad calculada
        'dias_mora',    # Propiedad calculada
        'nombre_vendedor_cartera', 
        'ultima_actualizacion_carga'
    )
    # Campos por los que se puede filtrar en la barra lateral
    list_filter = (
        'empresa',
        'tipo_documento', 
        'cliente__nombre_completo', # Filtrar por nombre de cliente
        'nombre_vendedor_cartera', 
        'fecha_vencimiento', 
        'fecha_documento'
    )
    # Campos en los que se puede buscar
    search_fields = (
        'numero_documento', 
        'cliente__identificacion', # Buscar por identificación del cliente
        'cliente__nombre_completo',# Buscar por nombre del cliente
        'nombre_vendedor_cartera'
        'empresa__nombre'
    )
    # Campos que no se pueden editar directamente en el admin (son calculados o automáticos)
    readonly_fields = ('dias_mora', 'esta_vencido', 'ultima_actualizacion_carga')
    # Número de ítems por página
    list_per_page = 30 
    
    # Para mejorar la visualización del filtro de cliente si tienes muchos
    autocomplete_fields = ['cliente'] # Asegúrate que ClienteAdmin tenga search_fields configurado

    def get_queryset(self, request):
        """
        Filtra los documentos de cartera para que cada usuario solo vea los de su empresa.
        """
        qs = super().get_queryset(request).select_related('empresa', 'cliente')
        if request.user.is_superuser:
            return qs
        tenant = getattr(request, 'tenant', None)
        return qs.filter(empresa=tenant) if tenant else qs.none()

    # --- CAMBIO DE SEGURIDAD: get_form ---
    def get_form(self, request, obj=None, **kwargs):
        """
        Personaliza el formulario del admin para manejar el campo 'empresa'.
        """
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser:
            if 'empresa' in form.base_fields:
                form.base_fields['empresa'].disabled = True
                form.base_fields['empresa'].initial = getattr(request, 'tenant', None)
        return form

    # --- CAMBIO DE SEGURIDAD: save_model ---
    def save_model(self, request, obj, form, change):
        """
        Asigna la empresa automáticamente al crear si no es superusuario.
        """
        if not change: # Solo al crear un objeto nuevo
            if not request.user.is_superuser:
                obj.empresa = getattr(request, 'tenant', None)
        
        # Para un superusuario, el valor de 'empresa' se toma del formulario.
        super().save_model(request, obj, form, change)
        
@admin.register(PerfilImportacionCartera)
class PerfilImportacionCarteraAdmin(admin.ModelAdmin):
    list_display = ('nombre_perfil', 'empresa', 'fila_inicio_header')
    list_filter = ('empresa',)
    fieldsets = (
        ('Información General', {
            'fields': ('empresa', 'nombre_perfil', 'fila_inicio_header')
        }),
        ('Mapeo de Columnas del Archivo Excel', {
            'description': "Escribe el nombre exacto de la columna como aparece en el archivo Excel.",
            'fields': (
                'columna_id_cliente', 
                'columna_numero_documento', 
                'columna_fecha_documento', 
                'columna_fecha_vencimiento', 
                'columna_saldo', 
                'columna_nombre_vendedor', 
                'columna_codigo_vendedor'
            )
        }),
    )