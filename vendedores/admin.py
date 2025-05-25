from django.contrib import admin
from .models import Vendedor

class VendedorAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_nombre_completo', 'telefono_contacto', 'codigo_interno', 'activo')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'user__email', 'codigo_interno')
    list_filter = ('activo',)
    list_per_page = 25

    def get_nombre_completo(self, obj):
        nombre = obj.user.get_full_name()
        return nombre if nombre else obj.user.username
    get_nombre_completo.short_description = 'Nombre Completo' # Nombre de la columna
admin.site.register(Vendedor, VendedorAdmin)