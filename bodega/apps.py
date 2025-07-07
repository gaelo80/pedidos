from django.apps import AppConfig

class BodegaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bodega' # Este debe ser el nombre de tu aplicación de bodega

    def ready(self):
        import bodega.signals # Importa las señales de tu app
