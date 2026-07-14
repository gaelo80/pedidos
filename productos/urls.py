# productos/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views
from . import views

app_name = 'productos'

urlpatterns = [

    # --- APIs ---
    path('api/buscar/', api_views.buscar_productos_api, name='api_buscar_productos'),
    path('api/buscar-referencias/', api_views.buscar_referencias_api, name='api_buscar_referencias'),
    path('api/referencia/<str:ref>/colores/', api_views.get_colores_por_referencia, name='api_get_colores_por_referencia'),
    path('api/referencia/<str:ref>/color/<str:color_slug>/tallas/', api_views.get_tallas_por_ref_color, name='api_get_tallas_por_ref_color'),

    # --- Listado / CRUD ---
    path('listado/', views.ProductoListView.as_view(), name='producto_listado'),

    # Crear producto: usa SIEMPRE el formulario multi-talla (sirve para 1 o varias tallas)
    path('crear/', views.crear_producto_multi_talla, name='producto_crear'),
    # Alias antiguo, por si algún enlace todavía apunta a 'producto_crear_multi_talla'
    path('crear-multi-talla/', views.crear_producto_multi_talla, name='producto_crear_multi_talla'),

    path('<int:pk>/editar/', views.ProductoUpdateView.as_view(), name='producto_editar'),
    path('<int:pk>/detalle/', views.ProductoDetailView.as_view(), name='producto_detalle'),
    path('<int:pk>/eliminar/', views.ProductoDeleteView.as_view(), name='producto_eliminar'),

    # --- Importar / Exportar ---
    path('importar/', views.producto_import_view, name='producto_importar'),
    path('exportar/<str:file_format>/', views.producto_export_view, name='producto_exportar'),

    # --- Otros ---
    path('subir-fotos-agrupadas/', views.subir_fotos_agrupadas_view, name='producto_subir_fotos_agrupadas'),

]