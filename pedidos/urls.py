from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views 

router = DefaultRouter()
router.register(r'pedidos', views.PedidoViewSet, basename='pedidos') 

app_name = 'pedidos'

urlpatterns = [
    path('', include(router.urls)),
    path('crear/', views.vista_crear_pedido_web, name='crear_pedido_web'),
    path('editar/<int:pk>/', views.vista_crear_pedido_web, name='editar_pedido_web'),
    path('borradores/', views.vista_lista_pedidos_borrador, name='lista_pedidos_borrador'),
    path('borrador/eliminar/<int:pk>/', views.vista_eliminar_pedido_borrador, name='eliminar_pedido_borrador'),
    path('exito/<int:pk>/', views.vista_pedido_exito, name='pedido_creado_exito'),
    path('<int:pk>/pdf/', views.generar_pedido_pdf, name='generar_pedido_pdf'),
    path('pedido/<int:pk>/detalle/', views.vista_detalle_pedido, name='detalle_pedido'),
    path('descargar-fotos/<uuid:token_pedido>/', views.DescargarFotosPedidoView.as_view(), name='descargar_fotos_pedido'),
    path('cartera/pendientes/', views.lista_pedidos_para_aprobacion_cartera, name='lista_aprobacion_cartera'), 
    path('cartera/aprobar/<int:pk>/', views.aprobar_pedido_cartera, name='aprobar_pedido_cartera'), 
    path('cartera/rechazar/<int:pk>/', views.rechazar_pedido_cartera, name='rechazar_pedido_cartera'), 
    path('admin/pendientes/', views.lista_pedidos_para_aprobacion_admin, name='lista_aprobacion_admin'),
    path('admin/aprobar/<int:pk>/', views.aprobar_pedido_admin, name='aprobar_pedido_admin'),
    path('admin/rechazar/<int:pk>/', views.rechazar_pedido_admin, name='rechazar_pedido_admin'),
    path('borrador/<int:pk>/pdf/', views.generar_borrador_pdf, name='generar_borrador_pdf'),
    path('borrador/autosave/', views.autosave_pedido_borrador, name='autosave_pedido_borrador'),
    path('reportes/ventas-por-referencia/', views.vista_reporte_referencias, name='reporte_ventas_referencia'),

]