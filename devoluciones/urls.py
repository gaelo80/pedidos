# devoluciones/urls.py
from django.urls import path
from . import views # Importa las vistas de la app devoluciones

app_name = 'devoluciones' # Define un namespace para estas URLs

urlpatterns = [
    path('crear/', views.vista_crear_devolucion, name='crear_devolucion'),
    path('<int:pk>/', views.vista_detalle_devolucion, name='detalle_devolucion'),
    path('<int:devolucion_id>/imprimir/', views.imprimir_comprobante_devolucion, name='imprimir_comprobante_devolucion'),

]