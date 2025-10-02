# bodega/urls.py
from django.urls import path, include # 'include' es opcional si no usas el router
# from rest_framework.routers import DefaultRouter # Comentado por ahora
from . import views # Importa las vistas de la app 'bodega'


# router = DefaultRouter() # Comentado por ahora, ya que no hay ViewSets aquí
# La línea router.register(...) se elimina.

app_name = 'bodega'

urlpatterns = [
     path('pedido/<int:pk>/generar-comprobante-despacho/', views.vista_generar_ultimo_comprobante_pedido, name='generar_comprobante_despacho'),
     path('comprobante/<int:pk_comprobante>/imprimir/', views.vista_imprimir_comprobante_especifico, name='imprimir_comprobante_especifico'),
     path('pedidos-pendientes/', views.vista_lista_pedidos_bodega, name='lista_pedidos_bodega'),
     path('ingresos/registrar/', views.vista_registrar_ingreso, name='vista_registrar_ingreso'),
     path('conteo-inventario/', views.vista_conteo_inventario, name='vista_conteo_inventario'),
     path('conteo-inventario/informe/<int:cabecera_id>/pdf/', views.descargar_informe_conteo, name='descargar_informe_conteo'),
     path('despacho/pedido/<int:pk>/', views.vista_despacho_pedido, name='despacho_pedido'),
     path('despacho/<int:pk>/guardar-parcial-ajax/', views.guardar_parcialmente_detalle_ajax, name='guardar_parcial_ajax'),
     path('despacho/<int:pk>/enviar-parcial-ajax/', views.enviar_despacho_parcial_ajax, name='enviar_parcial_ajax'),
     path('verificar-pedido/<int:pk>/', views.vista_verificar_pedido, name='verificar_pedido'),
     path('informes/despachos/', views.InformeDespachosView.as_view(), name='informe_despachos'),
     path('ingreso/<int:pk>/detalle/', views.vista_detalle_ingreso_bodega, name='detalle_ingreso'),    
     path('ingreso/<int:pk>/modificar/', views.IngresoUpdateView.as_view(), name='modificar_ingreso_bodega'),
     path('salidas-internas/', views.lista_salidas_internas, name='lista_salidas_internas'),
     path('salidas-internas/registrar/', views.registrar_salida_interna, name='registrar_salida_interna'),
     path('salidas-internas/<int:pk>/detalle/', views.detalle_salida_interna, name='detalle_salida_interna'),
     path('salidas-internas/<int:pk>/pdf/', views.generar_pdf_salida_interna, name='generar_pdf_salida_interna'),
     path('salidas-internas/<int:pk_cabecera>/registrar-devolucion/', views.registrar_devolucion_salida_interna, name='registrar_devolucion_salida_interna'),
     path('salidas-internas/<int:pk_cabecera>/pdf-devolucion/', views.generar_pdf_devolucion_salida_interna, name='generar_pdf_devolucion_salida_interna'),
     path('despacho/validar_item/', views.validar_item_despacho_ajax, name='validar_item_despacho_ajax'),
     path('informes-conteo/', views.lista_informes_conteo, name='lista_informes_conteo'),
     path('conteo-inventario/exportar-plantilla/<str:file_format>/', views.exportar_plantilla_conteo, name='exportar_plantilla_conteo'),   
     path('despacho/<int:pk>/finalizar-incompleto/', views.finalizar_pedido_incompleto, name='finalizar_pedido_incompleto'),       
     path('despacho/<int:pk>/cancelar/', views.cancelar_pedido_bodega, name='cancelar_pedido_bodega'),
     path('informe/inventario/', views.vista_informe_inventario, name='informe_inventario'),
     path('informe/inventario/exportar/', views.exportar_inventario_excel, name='exportar_inventario_excel'),
     path('informe-movimientos/', views.InformeMovimientoInventarioView.as_view(), name='informe_movimiento_inventario'),
     path('salidas-internas/<int:pk>/cerrar/', views.cerrar_salida_interna, name='cerrar_salida_interna'),
     path('cambio-producto/', views.realizar_cambio_producto, name='realizar_cambio_producto'),
     path('cambio-producto/<int:pk>/pdf/', views.generar_pdf_cambio_producto, name='generar_pdf_cambio_producto'),
     path('cambios-historial/', views.historial_cambios_producto, name='historial_cambios_producto'),
     path('informe/movimiento/producto/<int:pk>/', views.informe_movimiento_producto, name='informe_movimiento_producto'),
     path('buscar-informe-movimiento/', views.buscar_informe_movimiento, name='buscar_informe_movimiento'),
]