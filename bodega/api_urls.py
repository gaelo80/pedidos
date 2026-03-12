# bodega/api_urls.py
from django.urls import path
from . import api_views

app_name = 'bodega_api'

urlpatterns = [
    # List all pending pedidos for bodega
    path('pedidos/', api_views.PedidoBodegaListAPIView.as_view(), name='lista_pedidos_api'),

    # Get details of a specific pedido
    path('pedidos/<int:pk>/', api_views.PedidoBodegaDetalleAPIView.as_view(), name='detalle_pedido_api'),

    # Save draft scan quantities to BorradorDespacho
    path('pedidos/<int:pk>/guardar-borrador/', api_views.GuardarBorradorAPIView.as_view(), name='guardar_borrador_api'),

    # Confirm dispatch, create comprobante
    path('pedidos/<int:pk>/enviar-despacho/', api_views.EnviarDespachoAPIView.as_view(), name='enviar_despacho_api'),

    # Mark as incomplete, return pending stock
    path('pedidos/<int:pk>/finalizar-incompleto/', api_views.FinalizarIncompletoAPIView.as_view(), name='finalizar_incompleto_api'),

    # Cancel pedido, return all stock
    path('pedidos/<int:pk>/cancelar/', api_views.CancelarPedidoAPIView.as_view(), name='cancelar_api'),
]
