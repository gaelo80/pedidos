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
    path('api/color/crear/', api_views.api_crear_color, name='api_crear_color'),
    path('api/tallas-por-genero/', api_views.api_tallas_por_genero, name='api_tallas_por_genero'),
    path('api/exportar-catalogo-etiquetas/', api_views.api_exportar_catalogo_etiquetas, name='api_exportar_catalogo_etiquetas'),

    # --- Listado / CRUD ---
    path('listado/', views.ProductoListView.as_view(), name='producto_listado'),

    # Crear producto: usa SIEMPRE el formulario multi-talla (sirve para 1 o varias tallas)
    path('crear/', views.crear_producto_multi_talla, name='producto_crear'),
    # Alias antiguo, por si algún enlace todavía apunta a 'producto_crear_multi_talla'
    path('crear-multi-talla/', views.crear_producto_multi_talla, name='producto_crear_multi_talla'),

    path('<int:pk>/editar/', views.editar_producto_multi_talla, name='producto_editar'),
    path('<int:pk>/detalle/', views.ProductoDetailView.as_view(), name='producto_detalle'),
    path('<int:pk>/eliminar/', views.ProductoDeleteView.as_view(), name='producto_eliminar'),

    # --- Importar / Exportar ---
    path('importar/', views.producto_import_view, name='producto_importar'),
    path('exportar/<str:file_format>/', views.producto_export_view, name='producto_exportar'),

    # --- Otros ---
    path('subir-fotos-agrupadas/', views.subir_fotos_agrupadas_view, name='producto_subir_fotos_agrupadas'),
    path('fotos/<int:referencia_color_id>/subir/', views.subir_fotos_referencia_ajax, name='subir_fotos_referencia_ajax'),
    path('fotos/reordenar/', views.reordenar_fotos_ajax, name='reordenar_fotos_ajax'),
    path('fotos/<int:foto_id>/eliminar/', views.eliminar_foto_ajax, name='eliminar_foto_ajax'),

]