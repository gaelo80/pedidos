# core/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from clientes import api_views
from . import views

router = DefaultRouter()


app_name = 'core'

urlpatterns = [
    
    path('', views.vista_index, name='index'),
    path('acceso-denegado/', views.acceso_denegado_view, name='acceso_denegado'),
    path('offline/', views.offline_view, name='offline'),

]