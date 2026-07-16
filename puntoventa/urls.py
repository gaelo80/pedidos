# puntoventa/urls.py
from django.urls import path
from . import views

app_name = 'puntoventa'

urlpatterns = [
    path('abrir-turno/', views.abrir_turno, name='abrir_turno'),
    path('cerrar-turno/', views.cerrar_turno, name='cerrar_turno'),
    path('turno/<int:pk>/', views.detalle_turno, name='detalle_turno'),
    path('turno/<int:pk>/informe-cierre/', views.informe_cierre_turno, name='informe_cierre_turno'),

    path('vender/', views.vista_venta, name='vender'),
    path('venta/<int:pk>/recibo/', views.recibo_venta, name='recibo_venta'),

    path('api/buscar-producto/', views.api_buscar_producto_venta, name='api_buscar_producto_venta'),
    path('api/buscar-cliente/', views.api_buscar_cliente_venta, name='api_buscar_cliente_venta'),
    path('api/cliente-rapido/', views.api_cliente_rapido, name='api_cliente_rapido'),
    path('api/carrito/agregar/', views.api_carrito_agregar, name='api_carrito_agregar'),
    path('api/carrito/actualizar/', views.api_carrito_actualizar, name='api_carrito_actualizar'),
    path('api/carrito/ajustar-precio/', views.api_carrito_ajustar_precio, name='api_carrito_ajustar_precio'),
    path('api/carrito/vaciar/', views.api_carrito_vaciar, name='api_carrito_vaciar'),
    path('api/carrito/estado/', views.api_carrito_estado, name='api_carrito_estado'),
    path('api/checkout/', views.api_checkout, name='api_checkout'),
    path('api/pago/subir-comprobante/', views.api_pago_subir_comprobante, name='api_pago_subir_comprobante'),

    path('precios-saldo/', views.gestionar_precios_pos, name='gestionar_precios_pos'),
    path('api/precios-saldo/buscar-producto/', views.api_buscar_producto_precios, name='api_buscar_producto_precios'),
    path('api/precios-saldo/guardar/', views.api_precio_especial_guardar, name='api_precio_especial_guardar'),
    path('api/precios-saldo/eliminar/', views.api_precio_especial_eliminar, name='api_precio_especial_eliminar'),

    path('historial/', views.historial_ventas, name='historial_ventas'),
    path('historial/exportar/', views.exportar_historial_excel, name='exportar_historial_excel'),

    path('inventario/', views.consulta_inventario_pos, name='consulta_inventario_pos'),

    path('salidas/registrar/', views.registrar_salida_pos, name='registrar_salida_pos'),
    path('salidas/', views.lista_salidas_pos, name='lista_salidas_pos'),

    path('devolucion-cambio/', views.vista_devolucion_cambio, name='devolucion_cambio'),
    path('api/devolucion-cambio/buscar-venta/', views.api_buscar_venta_pos, name='api_buscar_venta_pos'),
    path('api/devolucion-cambio/procesar/', views.api_procesar_devolucion_cambio, name='api_procesar_devolucion_cambio'),
    path('devoluciones/', views.historial_devoluciones_cambios, name='historial_devoluciones_cambios'),
]
