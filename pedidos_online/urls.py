# pedidos_online/urls.py

from django.urls import path
from . import views

app_name = 'pedidos_online'

urlpatterns = [
    # --- Páginas Principales ---
    path('crear/', views.crear_pedido_online, name='crear_pedido_online'),
    path('editar/<int:pk>/', views.crear_pedido_online, name='editar_pedido_online'),
    
    # <<< NUEVA RUTA para la lista de borradores online >>>
    path('borradores/', views.lista_pedidos_borrador_online, name='lista_pedidos_borrador_online'),
    path('reportes/ventas-vendedor/', views.reporte_ventas_vendedor_online, name='reporte_ventas_vendedor_online'),
    path('reportes/ventas-general/', views.reporte_ventas_general_online, name='reporte_ventas_general_online'),

    path('cambios/registrar/', views.registrar_cambio_online, name='registrar_cambio_online'),
    path('cambios/registrar/<int:pedido_id>/', views.registrar_cambio_online, name='registrar_cambio_online_from_pedido'),
    path('comprobante/<int:pk>/cambio/', views.comprobante_cambio_online, name='comprobante_cambio_online'),

    # --- APIs para la Interfaz de Usuario ---
    path('api/buscar-clientes/', views.api_buscar_clientes_unificado, name='api_buscar_clientes_unificado'),
    path('api/crear-cliente-online/', views.api_crear_cliente_online, name='api_crear_cliente_online'), 
    path('api/referencia/<str:ref>/colores/', views.api_get_colores_for_referencia, name='api_get_colores_for_referencia'),
    path('api/referencia/<str:ref>/color/<path:color_slug>/tallas/', views.api_get_tallas_for_color, name='api_get_tallas_for_color'),
    path('api/get-cliente-estandar/<int:cliente_id>/', views.api_get_cliente_estandar_data, name='api_get_cliente_estandar_data'),  
    path('api/cliente-resumen/<str:client_type>/<int:client_pk>/', views.api_get_cliente_summary, name='api_get_cliente_summary'),  
    path('api/buscar-pedidos/', views.api_buscar_pedidos, name='api_buscar_pedidos'),
    path('api/pedidos/<int:pedido_id>/detalles/', views.api_get_pedido_detalles, name='api_get_pedido_detalles'),
    
]