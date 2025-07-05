# prospectos/urls.py
from django.urls import path
from . import views
from . import api_views

app_name = 'prospectos'

urlpatterns = [

    path('solicitud/nueva/', views.SolicitudCrearView.as_view(), name='crear_solicitud'),
    path('solicitudes/', views.SolicitudListView.as_view(), name='lista_solicitudes'),
    path('solicitud/<int:pk>/', views.SolicitudDetailView.as_view(), name='detalle_solicitud'),
    path('solicitud/<int:pk>/aprobar/', views.aprobar_solicitud, name='aprobar_solicitud'),
    path('solicitud/<int:pk>/rechazar/', views.rechazar_solicitud, name='rechazar_solicitud'),
    path('api/buscar/', api_views.buscar_prospectos_api, name='api_buscar_prospectos'),
]