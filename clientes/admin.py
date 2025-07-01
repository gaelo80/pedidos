# clientes/admin.py
from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import Cliente, Ciudad, Empresa, Dominio

@admin.register(Empresa)
class EmpresaAdmin(ImportExportModelAdmin):
    list_display = ('nombre', 'nit', 'activo', 'fecha_creacion')
    list_filter = ('activo',)
    search_fields = ('nombre', 'nit')
    list_per_page = 20

@admin.register(Dominio)
class DominioAdmin(admin.ModelAdmin):
    list_display = ('nombre_dominio', 'empresa', 'es_principal')
    list_filter = ('es_principal', 'empresa')
    search_fields = ('nombre_dominio', 'empresa__nombre')
    list_per_page = 20
    autocomplete_fields = ['empresa']

@admin.register(Cliente) # RECOMENDACIÓN: Usar decorador para consistencia.
class ClienteAdmin(ImportExportModelAdmin):
    # RECOMENDACIÓN: Añadir 'get_empresa_nombre' para que los superusuarios vean a qué empresa pertenece cada cliente.
    list_display = ('nombre_completo', 'identificacion', 'ciudad', 'get_empresa_nombre', 'telefono', 'email')
    search_fields = ('nombre_completo', 'identificacion', 'email', 'empresa__nombre')
    # RECOMENDACIÓN: Añadir 'empresa' a los filtros para superusuarios.
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

    @admin.display(description='Empresa', ordering='empresa__nombre')
    def get_empresa_nombre(self, obj):
        """Método para mostrar el nombre de la empresa en list_display."""
        return obj.empresa.nombre

@admin.register(Ciudad) # RECOMENDACIÓN: Usar decorador para consistencia.
class CiudadAdmin(ImportExportModelAdmin):
    list_display = ('id', 'nombre')
    search_fields = ('nombre',)
    list_per_page = 25