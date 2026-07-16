from django.apps import AppConfig


class PedidosWebConfig(AppConfig):
    name = 'pedidos_web'

    def ready(self):
        from . import signals  # noqa: F401 -- conecta la señal de sincronización en tiempo real
