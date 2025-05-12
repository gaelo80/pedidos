# inventario/templatetags/inventario_extras.py
from django import template
from django.contrib.auth.models import Group

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Permite acceder a un valor de diccionario usando una variable como clave.
    Uso en plantilla: {{ mi_diccionario|get_item:mi_variable_clave }}
    Devuelve el valor asociado a la clave, o None si no la encuentra o si
    el primer argumento no es un diccionario.
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key) # Usamos .get() que devuelve None si la clave no existe
    return None


@register.filter(name='has_group')
def has_group(user, group_name):
    """
    Verifica si un usuario pertenece a un grupo específico.
    Uso en plantilla: {{ user|has_group:"NombreDelGrupo" }}
    """
    # Asegurarse que el usuario esté autenticado podría ser buena idea aquí,
    # aunque usualmente se usa dentro de {% if user.is_authenticated %}
    if not user.is_authenticated:
        return False
    try:
        # Comprueba si existe un grupo con ese nombre y si el usuario pertenece a él
        group = Group.objects.get(name=group_name)
        return group in user.groups.all()
    except Group.DoesNotExist:
        # Si el grupo no existe en la BD, el usuario no puede pertenecer a él
        print(f"Advertencia: El grupo '{group_name}' referenciado en la plantilla no existe en la base de datos.")
        return False
    except Exception as e:
        # Captura otros posibles errores (ej: si 'user' no es un objeto User válido)
        print(f"Error inesperado en el filtro has_group para usuario '{user}' y grupo '{group_name}': {e}")
        return False
    
@register.filter(name='get_item') # Registra la función como un filtro llamado 'get_item'
def get_item(dictionary, key):
    """
    Permite acceder a un item de diccionario usando una variable como llave en plantillas Django.
    Uso: {{ mi_diccionario|get_item:mi_variable_llave }}
    Devuelve '' si no es un diccionario o la llave no existe, para evitar errores.
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key, '') # Usamos get() para devolver '' si no existe
    return ''

# Puedes tener otros tags/filtros aquí debajo o arriba...