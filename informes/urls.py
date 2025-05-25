# informes/urls.py
from django.urls import path
from . import views

app_name = 'informes'

urlpatterns = [
    
    path('ventas/general/', views.reporte_ventas_general, name='reporte_ventas_general'),
    path('ventas/vendedor/', views.reporte_ventas_vendedor, name='reporte_ventas_vendedor'),
    path('despachos/cumplimiento/', views.reporte_cumplimiento_despachos, name='reporte_cumplimiento_despachos'),
    path('pedidos/rechazados/', views.informe_pedidos_rechazados, name='informe_pedidos_rechazados'),
    path('pedidos/aprobados-bodega/', views.informe_pedidos_aprobados_bodega, name='informe_pedidos_aprobados_bodega'),
    path('bodega/ingresos/', views.informe_ingresos_bodega, name='informe_ingresos_bodega'),
    path('despachos/comprobantes/', views.informe_comprobantes_despacho, name='informe_comprobantes_despacho'),
    path('pedidos/total/', views.informe_total_pedidos, name='informe_total_pedidos'),
    path('devoluciones/listado/', views.informe_lista_devoluciones, name='informe_lista_devoluciones'),

]
