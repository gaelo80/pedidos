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
     path('verificar-pedido/<int:pk>/', views.vista_verificar_pedido, name='verificar_pedido'),
     path('informes/despachos/', views.InformeDespachosView.as_view(), name='informe_despachos'),
     path('ingreso/<int:pk>/detalle/', views.vista_detalle_ingreso_bodega, name='detalle_ingreso'),    
     path('salidas-internas/', views.lista_salidas_internas, name='lista_salidas_internas'),
     path('salidas-internas/registrar/', views.registrar_salida_interna, name='registrar_salida_interna'),
     path('salidas-internas/<int:pk>/detalle/', views.detalle_salida_interna, name='detalle_salida_interna'),
     path('salidas-internas/<int:pk>/pdf/', views.generar_pdf_salida_interna, name='generar_pdf_salida_interna'),
     path('salidas-internas/<int:pk_cabecera>/registrar-devolucion/', views.registrar_devolucion_salida_interna, name='registrar_devolucion_salida_interna'),
     path('salidas-internas/<int:pk_cabecera>/pdf-devolucion/', views.generar_pdf_devolucion_salida_interna, name='generar_pdf_devolucion_salida_interna'),
     path('despacho/validar_item/', views.validar_item_despacho_ajax, name='validar_item_despacho_ajax'),
     path('informes-conteo/', views.lista_informes_conteo, name='lista_informes_conteo'),
          
]