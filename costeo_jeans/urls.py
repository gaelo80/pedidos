from django.urls import path
from . import views

app_name = 'costeo_jeans'

urlpatterns = [
    # Panel de Control
    path('', views.PanelCosteoView.as_view(), name='panel_costeo'),

    # Gestión de Insumos
    path('insumos/', views.InsumoListView.as_view(), name='insumo_list'),
    path('insumos/nuevo/', views.InsumoCreateView.as_view(), name='insumo_create'),
    path('insumos/<int:pk>/editar/', views.InsumoUpdateView.as_view(), name='insumo_update'),
    path('insumos/<int:pk>/eliminar/', views.InsumoDeleteView.as_view(), name='insumo_delete'),

    # Gestión de Procesos
    path('procesos/', views.ProcesoListView.as_view(), name='proceso_list'),
    path('procesos/nuevo/', views.ProcesoCreateView.as_view(), name='proceso_create'),
    path('procesos/<int:pk>/editar/', views.ProcesoUpdateView.as_view(), name='proceso_update'),
    path('procesos/<int:pk>/eliminar/', views.ProcesoDeleteView.as_view(), name='proceso_delete'),

    # Gestión de Confeccionistas
    path('confeccionistas/', views.ConfeccionistaListView.as_view(), name='confeccionista_list'),
    path('confeccionistas/nuevo/', views.ConfeccionistaCreateView.as_view(), name='confeccionista_create'),
    path('confeccionistas/<int:pk>/editar/', views.ConfeccionistaUpdateView.as_view(), name='confeccionista_update'),
    path('confeccionistas/<int:pk>/eliminar/', views.ConfeccionistaDeleteView.as_view(), name='confeccionista_delete'),

    # --- NUEVAS URLS PARA COSTOS FIJOS ---
    path('costos-fijos/', views.CostoFijoListView.as_view(), name='costofijo_list'),
    path('costos-fijos/nuevo/', views.CostoFijoCreateView.as_view(), name='costofijo_create'),
    path('costos-fijos/<int:pk>/editar/', views.CostoFijoUpdateView.as_view(), name='costofijo_update'),
    path('costos-fijos/<int:pk>/eliminar/', views.CostoFijoDeleteView.as_view(), name='costofijo_delete'),

    # Asistente de Costeo
    path('crear/paso1/', views.costeo_create_step1, name='costeo_create_step1'),
    path('<int:costeo_id>/crear/paso2/', views.costeo_create_step2, name='costeo_create_step2'),
    path('<int:costeo_id>/resumen/', views.costeo_summary, name='costeo_summary'),
    path('<int:costeo_id>/exportar/pdf/', views.export_costeo_pdf, name='export_costeo_pdf'),
    path('<int:costeo_id>/editar/paso1/', views.costeo_update_step1, name='costeo_update_step1'),
    path('<int:costeo_id>/editar/paso2/', views.costeo_update_step2, name='costeo_update_step2'),


    # Historial
    path('historial/', views.CosteoHistoryListView.as_view(), name='costeo_historial'),
    path('informes/', views.InformesView.as_view(), name='informes'),
    
    # ---TARIFAS ---
path('tarifas/', views.TarifaListView.as_view(), name='tarifa_list'),
path('tarifas/nueva/', views.TarifaCreateView.as_view(), name='tarifa_create'),
path('tarifas/<int:pk>/editar/', views.TarifaUpdateView.as_view(), name='tarifa_update'),
path('tarifas/<int:pk>/eliminar/', views.TarifaDeleteView.as_view(), name='tarifa_delete'),
]