from django.contrib import admin
from .models import Notificacion

# Register your models here.
class NotificacionAdmin(admin.ModelAdmin):
        list_display = ('destinatario', 'mensaje_corto', 'fecha_creacion', 'leido', 'url')
        list_filter = ('leido', 'fecha_creacion', 'destinatario__username') # Puedes filtrar por usuario, leído, etc.
        search_fields = ('mensaje', 'destinatario__username') # Permite buscar por mensaje o usuario
        readonly_fields = ('fecha_creacion',) # La fecha de creación no debería ser editable

        # Define una propiedad para mostrar un mensaje corto en list_display
        def mensaje_corto(self, obj):
            return obj.mensaje[:75] + '...' if len(obj.mensaje) > 75 else obj.mensaje
        mensaje_corto.short_description = 'Mensaje'

    # Registra tu modelo en el administrador de Django
admin.site.register(Notificacion, NotificacionAdmin)