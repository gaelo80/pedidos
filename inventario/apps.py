# inventario/apps.py
from django.apps import AppConfig

class InventarioConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventario'

    # Añade este método para importar las señales cuando la app esté lista
    def ready(self):
        import inventario.signals # Importa tu archivo de señales