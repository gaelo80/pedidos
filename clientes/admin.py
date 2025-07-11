# clientes/admin.py
from django.contrib import admin
from django.utils.html import format_html
from import_export.admin import ImportExportModelAdmin
from .models import Cliente, Ciudad, Empresa, Dominio
from .resources import ClienteResource

@admin.register(Empresa)
class EmpresaAdmin(ImportExportModelAdmin):
    list_display = ('nombre', 'nit', 'activo', 'fecha_creacion')
    list_filter = ('activo',)
    search_fields = ('nombre', 'nit')
    list_per_page = 20
    fieldsets = (
        ('Información Principal', {
            'fields': ('nombre', 'nit')
        }),
        ('Datos de Contacto', {
            # Agregamos los nuevos campos aquí
            'fields': ('direccion', 'ciudad', 'telefono', 'correo_electronico') 
        }),
        ('Personalización y Web', {
            'fields': ('logo', 'titulo_web') # <-- Aquí nos aseguramos de que el campo 'logo' se muestre.
        }),
        ('Estado y Fiscal', { # Cambié el nombre del grupo para mayor claridad
            # Y el de IVA aquí
            'fields': ('activo', 'responsable_de_iva')
        }),
    )
    
    readonly_fields = ('fecha_creacion',)

    def logo_thumbnail(self, obj):
        """
        Muestra una pequeña vista previa del logo en la lista de empresas.
        """
        if obj.logo:
            return format_html('<img src="{}" style="width: 70px; height: auto;" />', obj.logo.url)
        return "Sin logo"
    logo_thumbnail.short_description = 'Logotipo'

@admin.register(Dominio)
class DominioAdmin(admin.ModelAdmin):
    list_display = ('nombre_dominio', 'empresa', 'es_principal')
    list_filter = ('es_principal', 'empresa')
    search_fields = ('nombre_dominio', 'empresa__nombre')
    list_per_page = 20
    autocomplete_fields = ['empresa']

@admin.register(Cliente)
class ClienteAdmin(ImportExportModelAdmin):
    resource_classes = [ClienteResource]
    
    list_display = ('nombre_completo', 'identificacion', 'ciudad', 'get_empresa_nombre', 'telefono', 'email')
    search_fields = ('nombre_completo', 'identificacion', 'email', 'empresa__nombre')
    
    list_filter = ('empresa', 'ciudad',)
    list_per_page = 25     
    
    def get_form(self, request, obj=None, **kwargs):
        """
        Personaliza el formulario del admin.
        Si el usuario NO es superusuario, el campo 'empresa' se deshabilita.
        Si ES superusuario, el campo 'empresa' será un menú desplegable editable.
        """
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser:
            if 'empresa' in form.base_fields:
                form.base_fields['empresa'].disabled = True
                # Opcional: Asignar la empresa del usuario como valor inicial
                form.base_fields['empresa'].initial = getattr(request, 'tenant', None)
        return form
    
    def get_queryset(self, request):
        """
        FILTRADO SEGURO: Aísla la lista principal por inquilino.
        Tu implementación original era perfecta.
        """
        qs = super().get_queryset(request).select_related('empresa')
        tenant = getattr(request, 'tenant', None)
        if request.user.is_superuser:
            return qs
        if tenant:
            return qs.filter(empresa=tenant)
        return qs.none()

    def get_search_results(self, request, queryset, search_term):
        """
        BÚSQUEDA SEGURA: Aísla los resultados de autocompletado por inquilino.
        Tu implementación original era perfecta.
        """
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        tenant = getattr(request, 'tenant', None)
        if tenant and not request.user.is_superuser:
            queryset = queryset.filter(empresa=tenant)
        return queryset, use_distinct
    
    def save_model(self, request, obj, form, change):
        """
        Asigna la empresa automáticamente al crear si no es superusuario.
        Si es superusuario, confía en el valor seleccionado en el formulario.
        """
        # Si es un objeto nuevo (no un cambio) y el usuario no es superusuario
        if not change and not request.user.is_superuser:
            # Asigna la empresa del usuario actual
            obj.empresa = getattr(request, 'tenant', None)
        
        # El modelo se encargará de validar que la empresa no sea nula antes de guardar.
        super().save_model(request, obj, form, change)
        
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser  # o la condición que necesites

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def has_view_permission(self, request, obj=None):
        return request.user.has_perm('clientes.view_cliente')


    @admin.display(description='Empresa', ordering='empresa__nombre')
    def get_empresa_nombre(self, obj):
        """Método para mostrar el nombre de la empresa en list_display."""
        return obj.empresa.nombre

@admin.register(Ciudad) # RECOMENDACIÓN: Usar decorador para consistencia.
class CiudadAdmin(ImportExportModelAdmin):
    list_display = ('id', 'nombre')
    search_fields = ('nombre',)
    list_per_page = 25