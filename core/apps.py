from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        """
        El método ready() es el lugar ideal para importar y conectar las señales.
        """
        # Importa la señal aquí para evitar importaciones circulares
        from . import signals 
        from django.db.models.signals import post_migrate

        # Conecta la función al sender específico de esta app
        post_migrate.connect(signals.crear_grupos_y_permisos, sender=self)