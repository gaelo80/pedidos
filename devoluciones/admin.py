# devoluciones/admin.py
from django.contrib import admin
from .models import DetalleDevolucion, DevolucionCliente

class DetalleDevolucionInline(admin.TabularInline):
    model = DetalleDevolucion
    extra = 1
    autocomplete_fields = ['producto']
    
    # <<< REFUERZO DE SEGURIDAD >>>
    # Asegura que los campos de selección en el inline también estén filtrados.
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Para el campo 'producto' en el inline.
        if db_field.name == "producto":
            # Obtenemos el objeto padre (DevolucionCliente) si ya existe.
            parent_obj_id = request.resolver_match.kwargs.get('object_id')
            if parent_obj_id:
                try:
                    devolucion = DevolucionCliente.objects.get(pk=parent_obj_id)
                    # Filtramos los productos por la empresa de la devolución padre.
                    kwargs["queryset"] = db_field.related_model.objects.filter(empresa=devolucion.empresa)
                except DevolucionCliente.DoesNotExist:
                    pass
            else:
                # Si es una nueva devolución, el queryset se filtrará dinámicamente
                # cuando el usuario seleccione un cliente y se guarde la cabecera.
                # La validación en el modelo previene inconsistencias.
                pass
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(DevolucionCliente)
class DevolucionClienteAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_empresa_nombre', 'cliente', 'fecha_hora', 'pedido_original', 'usuario')
    list_filter = ('empresa', 'fecha_hora', 'cliente__nombre_completo', 'usuario')
    search_fields = ('id', 'cliente__nombre_completo', 'pedido_original__id', 'detalles__producto__nombre')
    readonly_fields = ('fecha_hora', 'usuario', 'get_empresa_nombre')
    autocomplete_fields = ['cliente', 'pedido_original']
    inlines = [DetalleDevolucionInline]

    # <<< NOTA IMPORTANTE DE SEGURIDAD >>>
    # Para que los 'autocomplete_fields' ('cliente', 'producto', etc.) sean completamente seguros,
    # las clases Admin de sus modelos respectivos (ClienteAdmin, ProductoAdmin) deben
    # sobrescribir el método 'get_search_results' para filtrar por request.tenant.

    def get_queryset(self, request):
        """
        <<< CORRECCIÓN CRÍTICA DE SEGURIDAD >>>
        Filtra el queryset para aislar los datos por inquilino.
        """
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        
        empresa_actual = getattr(request, 'tenant', None)
        if empresa_actual:
            return qs.filter(empresa=empresa_actual)
        
        return qs.none()

    def save_model(self, request, obj, form, change):
        """
        <<< REFUERZO DE SEGURIDAD >>>
        Asigna el usuario y la empresa correcta al guardar desde el admin.
        """
        if not obj.pk: # Si es un objeto nuevo
            obj.usuario = request.user
            # Asigna la empresa del usuario actual si no está ya establecida.
            if not obj.empresa_id:
                obj.empresa = getattr(request, 'tenant', None)
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        """
        Asegura que la lógica de guardado del formset también sea consciente del inquilino si es necesario.
        """
        # La validación en el modelo DetalleDevolucion ya previene inconsistencias,
        # por lo que no se necesita lógica extra aquí, pero es un buen lugar para añadirla si fuera necesario.
        super().save_formset(request, form, formset, change)

    @admin.display(description='Empresa', ordering='empresa__nombre')
    def get_empresa_nombre(self, obj):
        """Muestra el nombre de la empresa."""
        return obj.empresa.nombre if obj.empresa else "N/A"