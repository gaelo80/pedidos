# clientes/admin.py
from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import Cliente
from .models import Ciudad 
from import_export.admin import ImportExportModelAdmin


class ClienteAdmin(ImportExportModelAdmin):
    list_display = ('nombre_completo', 'identificacion', 'ciudad', 'telefono', 'email')
    search_fields = ('nombre_completo', 'identificacion', 'email')
    list_filter = ('ciudad',)
    list_per_page = 25
    
admin.site.register(Cliente, ClienteAdmin)

class CiudadAdmin(ImportExportModelAdmin):
    list_display = ('id', 'nombre') # Mostrar ID y nombre en la lista
    search_fields = ('nombre',)  # Permitir buscar por nombre
    list_per_page = 25 # Opcional: cuántas mostrar por página

admin.site.register(Ciudad, CiudadAdmin)