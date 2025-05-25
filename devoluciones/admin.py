from django.contrib import admin
from devoluciones.models import DetalleDevolucion, DevolucionCliente







class DetalleDevolucionInline(admin.TabularInline):
    model = DetalleDevolucion
    extra = 1
    autocomplete_fields = ['producto']

class DevolucionClienteAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'fecha_hora', 'pedido_original', 'usuario')
    list_filter = ('fecha_hora', 'cliente', 'usuario')
    search_fields = ('id', 'cliente__nombre_completo', 'pedido_original__id', 'detalles__producto__nombre')
    readonly_fields = ('fecha_hora', 'usuario')
    autocomplete_fields = ['cliente', 'pedido_original']
    inlines = [DetalleDevolucionInline]

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)
admin.site.register(DevolucionCliente, DevolucionClienteAdmin)
