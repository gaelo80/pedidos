# recaudos/urls.py
from django.urls import path
from . import views

app_name = 'recaudos'

urlpatterns = [
    # --- URLs para Vendedores ---
    # Pagina principal de la app para un vendedor (su lista de recaudos)
    path('', views.lista_recaudos_vendedor, name='lista_recaudos'),
    
    # Formulario para registrar un nuevo pago
    path('registrar/', views.crear_recaudo, name='crear_recaudo'),
    
    # Vista de detalle para ver un recibo específico
    path('recibo/<int:pk>/', views.detalle_recibo, name='detalle_recibo'),

    # --- URLs para Consignaciones (las implementaremos después) ---
    path('consignar/', views.crear_consignacion, name='crear_consignacion'),
    
    # --- URLs para Administradores (las implementaremos después) ---
    path('panel-admin/', views.panel_administracion, name='panel_administracion'),
    path('consignacion/<int:pk>/verificar/', views.verificar_consignacion, name='verificar_consignacion'),
    path('reporte-general/', views.reporte_general_recaudos, name='reporte_general_recaudos'),
]
