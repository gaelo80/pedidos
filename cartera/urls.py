# cartera/urls.py
from django.urls import path
from . import views

app_name = 'cartera'  # Namespace para las URLs de esta app

urlpatterns = [
    path('importar/', views.vista_importar_cartera, name='importar_cartera'),
    path('reporte/', views.reporte_cartera_general, name='reporte_cartera_general'),
    path('api/cliente/<int:cliente_id>/documentos/', views.api_cartera_cliente, name='api_cartera_cliente'),
    path('eliminar-toda/', views.vista_eliminar_cartera, name='eliminar_toda_la_cartera'),
    # Podrías añadir más URLs específicas de cartera aquí
]
