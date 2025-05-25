# factura/urls.py
from django.urls import path
from . import views

app_name = 'factura'

urlpatterns = [

    path('despachos/', views.ListaDespachosAFacturarView.as_view(), name='lista_despachos_a_facturar'),
    path('despacho/<int:pk_despacho>/detalle/', views.DetalleDespachoFacturaView.as_view(), name='detalle_despacho_factura'),    
    path('informes/facturados-por-fecha/', views.InformeFacturadosPorFechaView.as_view(), name='informe_facturados_fecha'),    
    path('informes/despachos-por-cliente/', views.InformeDespachosPorClienteView.as_view(), name='informe_despachos_cliente'),    
    path('informes/despachos-por-estado/', views.InformeDespachosPorEstadoView.as_view(), name='informe_despachos_estado'),    
    path('informes/despachos-por-pedido/', views.InformeDespachosPorPedidoView.as_view(), name='informe_despachos_pedido'),

]