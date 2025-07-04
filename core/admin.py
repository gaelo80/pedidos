# usuarios/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

class CustomUserAdmin(UserAdmin):
    # Añadimos 'empresa' directamente al formulario de edición
    fieldsets = (
        *UserAdmin.fieldsets, # Mantenemos los fieldsets originales
        ('Asignación de Empresa', {'fields': ('empresa',)}), # Añadimos nuestra sección
    )
    # Y a la lista
    list_display = ('username', 'email', 'is_staff', 'empresa')

admin.site.register(User, CustomUserAdmin)