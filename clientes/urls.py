# clientes/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views
from . import views 



router_api = DefaultRouter()
router_api.register(r'ciudades', views.CiudadViewSet, basename='ciudad_api') 
router_api.register(r'clientes', views.ClienteViewSet, basename='cliente_api')

app_name = 'clientes'

urlpatterns = [
    # URLs para la API REST
    path('api/', include(router_api.urls)),
    path('', views.ClienteListView.as_view(), name='cliente_listado'), 
    path('nuevo/', views.ClienteCreateView.as_view(), name='cliente_crear'),
    path('<int:pk>/', views.ClienteDetailView.as_view(), name='cliente_detalle'), 
    path('<int:pk>/editar/', views.ClienteUpdateView.as_view(), name='cliente_editar'),
    path('<int:pk>/eliminar/', views.ClienteDeleteView.as_view(), name='cliente_eliminar'),
    path('ciudades/', views.CiudadListView.as_view(), name='ciudad_listado'),
    path('ciudades/nueva/', views.CiudadCreateView.as_view(), name='ciudad_crear'),
    path('ciudades/<int:pk>/editar/', views.CiudadUpdateView.as_view(), name='ciudad_editar'),
    path('ciudades/<int:pk>/eliminar/', views.CiudadDeleteView.as_view(), name='ciudad_eliminar'),
    path('ciudades/importar/', views.ciudad_import_view, name='ciudad_importar'),
    path('ciudades/exportar/<str:file_format>/', views.ciudad_export_view, name='ciudad_exportar'), 
    path('api/buscar/', api_views.buscar_clientes_api, name='api_buscar_clientes'),
    path('api/detalle/<int:cliente_id>/', api_views.api_detalle_cliente, name='api_detalle_cliente'),
    path('v2/listado/', views.ClienteListV2View.as_view(), name='cliente_listado_v2'),
    path('v2/detalle/<int:pk>/', views.ClienteDetailV2View.as_view(), name='cliente_detalle_v2')
]