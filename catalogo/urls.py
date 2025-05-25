# catalogo/urls.py
from django.urls import path
from . import views

app_name = 'catalogo'

urlpatterns = [
    path('', views.lista_referencias_view, name='lista_referencias'), # Vista inicial
    path('referencia/<str:referencia_str>/', views.detalle_referencia_view, name='detalle_referencia'), # Vista de detalle
    path('referencia/<str:referencia_str>/todas-fotos/', views.ver_todas_fotos_referencia_view, name='ver_todas_fotos_referencia'),
    path('disponible/', views.catalogo_publico_disponible, name='catalogo_publico_disponible'),
    path('compartir/<uuid:token>/', views.catalogo_publico_temporal_view, name='catalogo_publico_temporal'),
    path('panel/generar-enlace/', views.generar_enlace_usuario_view, name='catalogo_generar_enlace_usuario'),
    path('panel/generar-enlace/formulario/', views.mostrar_formulario_generar_enlace_view, name='mostrar_formulario_generar_enlace'),
]
