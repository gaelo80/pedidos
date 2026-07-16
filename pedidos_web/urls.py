from django.urls import path
from . import views

app_name = 'pedidos_web'

urlpatterns = [
    path('webhook/shopify/nuevo-pedido/', views.webhook_nuevo_pedido_shopify, name='webhook_nuevo_pedido'),
    path('webhook/shopify/actualizar-producto/', views.webhook_producto_shopify, name='webhook_producto_shopify'),
    path('admin/shopify/sincronizar/', views.panel_sincronizacion_shopify, name='panel_sincronizacion'),
    path('admin/shopify/sincronizar/progreso/', views.api_shopify_sync_progreso, name='api_shopify_sync_progreso'),

    path('admin/shopify/catalogo/', views.gestion_catalogo_shopify, name='gestion_catalogo_shopify'),
    path('admin/shopify/catalogo/tipos-y-categorias/', views.api_shopify_tipos_y_categorias, name='api_shopify_tipos_y_categorias'),
    path('admin/shopify/catalogo/<int:referencia_color_id>/subir/', views.api_shopify_subir, name='api_shopify_subir'),
    path('admin/shopify/catalogo/<int:referencia_color_id>/actualizar/', views.api_shopify_actualizar, name='api_shopify_actualizar'),
    path('admin/shopify/catalogo/<int:referencia_color_id>/bajar/', views.api_shopify_bajar, name='api_shopify_bajar'),
]