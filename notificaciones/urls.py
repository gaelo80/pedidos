# notificaciones/urls.py
from django.urls import path
from . import views

app_name = 'notificaciones'

urlpatterns = [
    path('', views.lista_notificaciones, name='lista_notificaciones'),
    path('check/cartera/', views.check_notificaciones_cartera_json, name='check_notificaciones_cartera_json'),
]
