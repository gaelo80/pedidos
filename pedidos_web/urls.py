from django.urls import path
from . import views

app_name = 'pedidos_web'

urlpatterns = [
    path('webhook/shopify/nuevo-pedido/', views.webhook_nuevo_pedido_shopify, name='webhook_nuevo_pedido'),
    path('webhook/shopify/actualizar-producto/', views.webhook_producto_shopify, name='webhook_producto_shopify'),
    path('admin/shopify/sincronizar/', views.panel_sincronizacion_shopify, name='panel_sincronizacion'),
]