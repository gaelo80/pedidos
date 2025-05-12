# gestion_inventario/urls.py
from django.contrib import admin
from django.urls import path, include
from inventario import views as inventario_views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.views.generic.base import RedirectView
from inventario.views import CustomLoginView
from django.contrib.auth.views import LogoutView


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', CustomLoginView.as_view(), name='login'),
    path('api/v1/', include('inventario.urls')),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('pedido/<int:pk>/pdf/', inventario_views.generar_pedido_pdf, name='generar_pedido_pdf'),
    path('bodega/verificar_pedido/<int:pk>/', inventario_views.vista_verificar_pedido, name='verificar_pedido'), # Mantener una
    path('bodega/pedidos_pendientes/', inventario_views.vista_lista_pedidos_bodega, name='lista_pedidos_bodega'),
    path('', RedirectView.as_view(url='/accounts/login/', permanent=False), name='index'),
    path('pedido/crear/', inventario_views.vista_crear_pedido_web, name='crear_pedido_web'),
    path('pedido/editar/<int:pk>/', inventario_views.vista_crear_pedido_web, name='editar_pedido_web'),
    path('pedidos/borradores/', inventario_views.vista_lista_pedidos_borrador, name='lista_pedidos_borrador'),
    path('pedidos/borrador/eliminar/<int:pk>/', inventario_views.vista_eliminar_pedido_borrador, name='eliminar_pedido_borrador'),
    path('devoluciones/crear/', inventario_views.vista_crear_devolucion, name='crear_devolucion'),
    path('devoluciones/<int:devolucion_id>/imprimir/', inventario_views.imprimir_comprobante_devolucion, name='imprimir_comprobante_devolucion'),
    path('devoluciones/<int:pk>/', inventario_views.vista_detalle_devolucion, name='detalle_devolucion'),
    path('ingresos/registrar/', inventario_views.vista_registrar_ingreso, name='registrar_ingreso'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/logout/', LogoutView.as_view(), name='logout'),
    path('reportes/ventas-vendedor/', inventario_views.reporte_ventas_vendedor, name='reporte_ventas_vendedor'),
    path('acceso-denegado/', inventario_views.acceso_denegado_view, name='acceso_denegado'),


]