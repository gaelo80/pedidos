from django.urls import path
from .views import (
    UserListView, 
    UserCreateView, 
    UserUpdateView, 
    UserDeleteView, 
    user_set_password_view,
    GroupListView,
    GroupCreateView,
    GroupUpdateView,
    GroupDeleteView

)

app_name = 'user_management' # Namespace para las URLs de esta app

urlpatterns = [
    path('users/', UserListView.as_view(), name='user_list'),
    path('users/create/', UserCreateView.as_view(), name='user_create'),
    path('users/<int:pk>/update/', UserUpdateView.as_view(), name='user_update'),
    path('users/<int:pk>/delete/', UserDeleteView.as_view(), name='user_delete'),
    path('users/<int:pk>/set-password/', user_set_password_view, name='user_set_password'),
    
    # URLs de Grupos
    path('groups/', GroupListView.as_view(), name='group_list'),
    path('groups/create/', GroupCreateView.as_view(), name='group_create'),
    path('groups/<int:pk>/update/', GroupUpdateView.as_view(), name='group_update'),
    path('groups/<int:pk>/delete/', GroupDeleteView.as_view(), name='group_delete'),
   
]