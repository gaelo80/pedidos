# gestion_inventario/urls.py 
from django.contrib import admin
from django.urls import path, include
from core.views import CustomLoginView 
from django.contrib.auth.views import LogoutView
from django.conf import settings
from django.conf.urls.static import static
from productos import api_views as productos_api_views
from core import views as core_views


urlpatterns = [
    path('admin/', admin.site.urls),

    # Autenticación
    path('accounts/login/', CustomLoginView.as_view(), name='login'),
    path('accounts/logout/', LogoutView.as_view(next_page='login'), name='logout'), # Redirigir a login después de logout
    path('accounts/', include('django.contrib.auth.urls')), 
    path('', include(('core.urls', 'core'), namespace='core')),
    path('api/v1/catalogo/', include(('productos.urls', 'productos'), namespace='productos_v1')),
    path('api/v1/clientes/', include(('clientes.urls', 'clientes'), namespace='clientes_v1')),
    path('api/v1/pedidos/', include(('pedidos.urls', 'pedidos'), namespace='pedidos_v1')),
    path('api/v1/productos/buscar/', productos_api_views.buscar_productos_api, name='global_api_buscar_productos'),
    path('api/clientes/', include(('clientes.urls', 'clientes_api_ns'), namespace='clientes')),  # Las URLs de clientes ya tienen 'api/' adentro
    path('devoluciones/', include(('devoluciones.urls', 'devoluciones'), namespace='devoluciones')),
    path('bodega/', include(('bodega.urls', 'bodega'), namespace='bodega')),
    path('informes/', include(('informes.urls', 'informes'), namespace='informes')),
    path('cartera/', include(('cartera.urls', 'cartera'), namespace='cartera')),
    path('pedidos/', include(('pedidos.urls', 'pedidos'), namespace='pedidos')),
    path('productos/', include('productos.urls', namespace='productos')),
    path('facturacion/', include('factura.urls', namespace='factura')),
    path('catalogo/', include('catalogo.urls', namespace='catalogo')),
    path('gestion-usuarios/', include('user_management.urls')),
    path('prospectos/', include('prospectos.urls', namespace='prospectos')),
    path('costeo/', include('costeo_jeans.urls')),
    path('recaudos/', include('recaudos.urls')),
    path('notificaciones/', include('notificaciones.urls', namespace='notificaciones')),
    path('pedidos-online/', include('pedidos_online.urls')),
    path('serviceworker.js', core_views.service_worker_view, name='service_worker'),

    

   
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)