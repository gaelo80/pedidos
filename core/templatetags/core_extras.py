# core/templatetags/core_extras.py
from django import template
from django.contrib.auth.models import Group

register = template.Library()

@register.simple_tag(takes_context=True)
def query_transform(context, **kwargs):
    """
    Actualiza o añade parámetros GET a la URL actual.
    Útil para construir enlaces de paginación y ordenamiento.
    """
    # Asegúrate de que 'request' esté en el contexto. Puede fallar en algunos casos si no.
    request = context.get('request')
    if request is None:
        print("Advertencia: 'request' no encontrado en el contexto para query_transform.")
        return ""
        
    query = request.GET.copy()
    for k, v in kwargs.items():
        query[k] = v
    return query.urlencode()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Permite acceder a un item de diccionario usando una variable como clave en las plantillas.
    Uso: {{ mi_diccionario|get_item:mi_variable_clave }}
    Devuelve None si no es un diccionario o la clave no existe.
    """
    # Manejar el caso donde la clave podría ser None o no existir
    if not isinstance(dictionary, dict) or key is None:
        return None
    return dictionary.get(key) # .get() devuelve None si la clave no existe

@register.simple_tag(takes_context=True)
def update_context(context, **kwargs):
    """
    Actualiza el contexto de la plantilla actual.
    Necesario para el cálculo dinámico del colspan en el reporte.
    """
    context.update(kwargs)
    return "" # Los simple_tag deben devolver algo (aunque sea vacío)

@register.filter(name='has_group')
def has_group(user, group_name):
    """
    Verifica si un usuario pertenece a un grupo específico.
    Uso en plantilla: {{ user|has_group:"NombreDelGrupo" }}
    """
    if not user or not user.is_authenticated:
        return False
    try:
        # Comprueba si existe un grupo con ese nombre y si el usuario pertenece a él
        group = Group.objects.get(name=group_name)
        # Usamos user.groups.filter() que es más eficiente que user.groups.all()
        return user.groups.filter(name=group_name).exists() 
    except Group.DoesNotExist:
        # Si el grupo no existe en la BD, el usuario no puede pertenecer a él
        print(f"Advertencia: El grupo '{group_name}' referenciado en la plantilla no existe en la base de datos.")
        return False
    except Exception as e:
        # Captura otros posibles errores
        print(f"Error inesperado en el filtro has_group para usuario '{user}' y grupo '{group_name}': {e}")
        return False