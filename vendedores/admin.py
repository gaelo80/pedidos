from django.contrib import admin
from .models import Vendedor

@admin.register(Vendedor)
class VendedorAdmin(admin.ModelAdmin):
    
    list_display = ('__str__', 'telefono_contacto', 'codigo_interno', 'activo', 'empresa')
    
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'codigo_interno', 'empresa__nombre')
    

    list_filter = ('empresa', 'activo')
    
    list_per_page = 25


    def get_queryset(self, request):
        """
        Filtra los objetos que se muestran en la lista principal del admin.
        - Si el usuario es un superadministrador, ve todos los objetos.
        - Si es un usuario normal, solo ve los de su propia empresa.
        """
        qs = super().get_queryset(request)

        if request.user.is_superuser:
            return qs

        if hasattr(request, 'tenant'):
            return qs.filter(empresa=request.tenant)        

        return qs.none()

    def save_model(self, request, obj, form, change):
        """
        Asegura que al crear un nuevo Vendedor, se le asigne la empresa correcta.
        """

        if not obj.pk and not request.user.is_superuser:
            if hasattr(request, 'tenant'):
                obj.empresa = request.tenant
        
        super().save_model(request, obj, form, change)

    def get_fieldsets(self, request, obj=None):
        """
        Controla qué campos se muestran en el formulario de edición/creación.
        """

        fieldsets = (
            (None, {'fields': ('empresa', 'user', 'activo')}),
            ('Información Adicional', {'fields': ('telefono_contacto', 'codigo_interno')}),
        )        

        if not request.user.is_superuser:
            fieldsets = (
                (None, {'fields': ('user', 'activo')}),
                ('Información Adicional', {'fields': ('telefono_contacto', 'codigo_interno')}),
            )
            
        return fieldsets