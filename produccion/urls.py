from django.urls import path
from . import views

app_name = 'produccion'

urlpatterns = [
    path('', views.PanelProduccionView.as_view(), name='panel_produccion'),

    # Catálogo de Etapas
    path('etapas/', views.EtapaProduccionListView.as_view(), name='etapa_list'),
    path('etapas/nueva/', views.EtapaProduccionCreateView.as_view(), name='etapa_create'),
    path('etapas/<int:pk>/editar/', views.EtapaProduccionUpdateView.as_view(), name='etapa_update'),
    path('etapas/<int:pk>/eliminar/', views.EtapaProduccionDeleteView.as_view(), name='etapa_delete'),

    # Talleres externos
    path('talleres/', views.TallerListView.as_view(), name='taller_list'),
    path('talleres/nuevo/', views.TallerCreateView.as_view(), name='taller_create'),
    path('talleres/<int:pk>/editar/', views.TallerUpdateView.as_view(), name='taller_update'),

    # Órdenes de Producción
    path('ordenes/', views.OrdenProduccionListView.as_view(), name='orden_list'),
    path('ordenes/crear/', views.crear_orden_produccion, name='crear_orden'),
    path('api/tallas-de-referencia/', views.api_tallas_de_referencia, name='api_tallas_de_referencia'),
    path('ordenes/<int:pk>/', views.detalle_orden_produccion, name='detalle_orden'),
    path('ordenes/<int:pk>/anular/', views.anular_orden, name='anular_orden'),
    path('crear-bodega-calidad/', views.crear_bodega_calidad, name='crear_bodega_calidad'),

    # Tablero, lotes y partidas
    path('lotes/', views.tablero_lotes, name='tablero_lotes'),
    path('lotes/<int:pk>/', views.detalle_lote, name='detalle_lote'),
    path('lotes/<int:pk>/corte/', views.registrar_corte, name='registrar_corte'),
    path('partidas/<int:pk>/registrar/', views.registrar_partida, name='registrar_partida'),

    # Remisiones y recepciones de talleres
    path('remisiones/', views.remision_list, name='remision_list'),
    path('remisiones/nueva/', views.remision_crear, name='remision_crear'),
    path('remisiones/<int:pk>/', views.remision_detalle, name='remision_detalle'),
    path('remisiones/<int:remision_pk>/recibir/', views.recepcion_crear, name='recepcion_crear'),
    path('remisiones/linea/<int:pk>/corregir/<str:tipo>/', views.corregir_linea, name='corregir_linea'),
    path('recepciones/<int:pk>/', views.recepcion_detalle, name='recepcion_detalle'),

    # Defectos de calidad
    path('defectos/', views.defecto_list, name='defecto_list'),
    path('defectos/<int:pk>/decidir/', views.defecto_decidir, name='defecto_decidir'),

    # Informes
    path('informes/taller/', views.informe_taller, name='informe_taller'),
    path('informes/segundas-terceras/', views.informe_segundas_terceras, name='informe_segundas_terceras'),
]

# Todo el módulo exige que la empresa lo tenga contratado (ver views.requiere_modulo).
for _patron in urlpatterns:
    _patron.callback = views.requiere_modulo(_patron.callback)
