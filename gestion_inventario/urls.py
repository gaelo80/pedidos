# gestion_inventario/urls.py 
from django.contrib import admin
from django.urls import path, include
from core.views import CustomLoginView 
from django.contrib.auth.views import LogoutView
from django.conf import settings
from django.conf.urls.static import static
from productos import api_views as productos_api_views


urlpatterns = [
    path('admin/', admin.site.urls),

    # Autenticación
    path('accounts/login/', CustomLoginView.as_view(), name='login'),
    path('accounts/logout/', LogoutView.as_view(next_page='login'), name='logout'), # Redirigir a login después de logout
    path('accounts/', include('django.contrib.auth.urls')), # Para password reset, etc.

    # Aplicación Core (Panel principal)
    # 'core:index' será la URL '/' (después de login)
    path('', include(('core.urls', 'core'), namespace='core')),

    # APIs y otras aplicaciones con prefijos claros
    path('api/v1/catalogo/', include(('productos.urls', 'productos'), namespace='productos_v1')),
    path('api/v1/clientes/', include(('clientes.urls', 'clientes'), namespace='clientes_v1')),
    path('api/v1/pedidos/', include(('pedidos.urls', 'pedidos'), namespace='pedidos_v1')),
    path('api/v1/productos/buscar/', productos_api_views.buscar_productos_api, name='global_api_buscar_productos'),
    path('api/clientes/', include(('clientes.urls', 'clientes_api_ns'), namespace='clientes')),  # Las URLs de clientes ya tienen 'api/' adentro

    # Aplicaciones con interfaz de usuario
    path('devoluciones/', include(('devoluciones.urls', 'devoluciones'), namespace='devoluciones')),
    path('bodega/', include(('bodega.urls', 'bodega'), namespace='bodega')),
    path('informes/', include(('informes.urls', 'informes'), namespace='informes')),
    path('cartera/', include(('cartera.urls', 'cartera'), namespace='cartera')),
    #path('factura/', include(('factura.urls', 'factura'), namespace='factura')),
    path('pedidos/', include(('pedidos.urls', 'pedidos'), namespace='pedidos')),
    path('productos/', include('productos.urls', namespace='productos')),
    path('facturacion/', include('factura.urls', namespace='factura')),
    path('catalogo/', include('catalogo.urls', namespace='catalogo')),
    path('gestion-usuarios/', include('user_management.urls')),
    

   
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)