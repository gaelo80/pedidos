# productos/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views
from . import views # Asumiendo que ProductoViewSet está en productos.views si usas el router

# router = DefaultRouter() # Descomenta y configura si usas ViewSets de DRF para otras URLs de productos
# router.register(r'productos_viewset', views.ProductoViewSet, basename='producto_viewset') # Ejemplo

app_name = 'productos' # <--- CORREGIDO para coincidir con el uso en plantillas

urlpatterns = [

    path('api/buscar/', api_views.buscar_productos_api, name='api_buscar_productos'),
    path('api/buscar-referencias/', api_views.buscar_referencias_api, name='api_buscar_referencias'), # Usado en crear_pedido_web_matriz.html
    path('api/referencia/<str:ref>/colores/', api_views.get_colores_por_referencia, name='api_get_colores_por_referencia'),
    path('api/referencia/<str:ref>/color/<str:color_slug>/tallas/', api_views.get_tallas_por_ref_color, name='api_get_tallas_por_ref_color'),
    path('listado/', views.ProductoListView.as_view(), name='producto_listado' ),
    path('crear/', views.ProductoCreateView.as_view(), name='producto_crear'),
    path('<int:pk>/editar/', views.ProductoUpdateView.as_view(),  name='producto_editar'),
    path('<int:pk>/detalle/', views.ProductoDetailView.as_view(), name='producto_detalle' ),
    path('<int:pk>/eliminar/', views.ProductoDeleteView.as_view(), name='producto_eliminar'),
    path('api/buscar-referencias/', api_views.buscar_referencias_api, name='api_buscar_referencias'),
    path('importar/', views.producto_import_view, name='producto_importar'),
    path('exportar/<str:file_format>/', views.producto_export_view, name='producto_exportar'),
    path('subir-fotos-agrupadas/', views.subir_fotos_agrupadas_view, name='producto_subir_fotos_agrupadas'),
    
    
]