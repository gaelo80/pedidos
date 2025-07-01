# catalogo/urls.py
from django.urls import path
from . import views

app_name = 'catalogo'

urlpatterns = [
    # URL para el catálogo interno (lista de referencias)
    path('', views.lista_referencias_view, name='lista_referencias'),

    # URL para el detalle de una referencia específica
    path('referencia/<str:referencia_str>/', views.detalle_referencia_view, name='detalle_referencia'),
    
    # URL para ver todas las fotos de una referencia
    path('fotos/<str:referencia_str>/', views.ver_todas_fotos_referencia_view, name='ver_todas_fotos'),

    # --- URLs para enlaces temporales y compartidos ---

    # URL que un cliente final visitará usando un token. Es pública.
    path('enlace/<uuid:token>/', views.catalogo_publico_temporal_view, name='catalogo_publico_temporal'),

    # URL para que un vendedor vea el formulario para crear un nuevo enlace.
    # El enlace "Compartir Catálogo" del menú debería apuntar a ESTA URL.
    path('generar-enlace/', views.mostrar_formulario_generar_enlace_view, name='catalogo_mostrar_formulario_enlace'),

    # URL a la que el formulario envía los datos para procesar la creación del enlace.
    # Se usa el nombre que la plantilla esperaba para resolver la advertencia.
    path('procesar-enlace/', views.generar_enlace_usuario_view, name='catalogo_generar_enlace_usuario'),
]