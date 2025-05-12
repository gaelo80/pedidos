# inventario/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views


# --- Router SOLO para la API de esta app ---
router = DefaultRouter()
router.register(r'ciudades', views.CiudadViewSet, basename='ciudad')
router.register(r'productos', views.ProductoViewSet, basename='producto')
router.register(r'clientes', views.ClienteViewSet, basename='cliente')
router.register(r'pedidos', views.PedidoViewSet, basename='pedido')
# Añade aquí el registro de otros ViewSets de API si los creas

# Define un nombre para el namespace (opcional, pero útil si usas namespace en el include)
app_name = 'inventario_api'

# urlpatterns solo exporta las URLs generadas por el router para la API
urlpatterns = [
    path('', views.vista_index, name='index'),
    path('clientes/buscar/', views.buscar_clientes_api, name='api_buscar_clientes'),
    path('productos/buscar/', views.buscar_productos_api, name='api_buscar_productos'),
    path('productos/referencia/<str:ref>/colores/', views.get_colores_por_referencia, name='api_get_colores'),
    path('productos/referencia/<str:ref>/color/<str:color_slug>/tallas/', views.get_tallas_por_ref_color, name='api_get_tallas'),
    path('api/v1/buscar-referencias/', views.buscar_referencias_api, name='api_buscar_referencias'),
    path('pedido/exito/<int:pk>/', views.vista_pedido_exito, name='pedido_creado_exito'), # <-- La nueva URL va aquí
    path('pedido/pdf/<int:pk>/', views.generar_pedido_pdf, name='generar_pedido_pdf'), # <-- La URL del PDF va aquí
    path('pedido/crear/', views.vista_crear_pedido_web, name='crear_pedido'),
    path('pedido/editar/<int:pk>/', views.vista_crear_pedido_web, name='editar_pedido'),
    path('pedidos/borradores/', views.vista_lista_pedidos_borrador, name='lista_pedidos_borrador'),
    path('clientes/<int:cliente_id>/detalles/', views.api_detalle_cliente, name='api_detalle_cliente'),
    path('conteo-inventario/', views.vista_conteo_inventario, name='vista_conteo_inventario'),
    path('conteo-inventario/informe/<int:cabecera_id>/pdf/', views.descargar_informe_conteo, name='descargar_informe_conteo'),
    path('pedido/comprobante_despacho/<int:pk>/', views.vista_generar_comprobante_despacho, name='generar_comprobante_despacho'),
    path('verificar_pedido/<int:pk>/', views.vista_verificar_pedido, name='verificar_pedido'),
    path('cartera/importar/', views.vista_importar_cartera, name='importar_cartera'),
    path('api/cliente/<int:cliente_id>/cartera/', views.api_cartera_cliente, name='api_cartera_cliente'),
    path('reportes/cartera/', views.reporte_cartera_general, name='reporte_cartera_general'),
    path('despacho/pedido/<int:pk>/', views.vista_despacho_pedido, name='despacho_pedido'),
    path('', include(router.urls)),
    
    

       
    
]

