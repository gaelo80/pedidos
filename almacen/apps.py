from django.apps import AppConfig


class AlmacenConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'almacen'

    def ready(self):
        """Importar signals cuando la app esté lista."""
        from . import signals
