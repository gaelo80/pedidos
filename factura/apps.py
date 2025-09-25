from django.apps import AppConfig


class FacturaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'factura'

    def ready(self):
        # Esta línea importa y registra las señales cuando Django arranca.
        import factura.signals