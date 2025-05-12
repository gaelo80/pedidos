# inventario/templatetags/math_filters.py
from django import template

register = template.Library() # Asegúrate que esta línea exista

@register.filter # Asegúrate que el decorador esté presente
def subtract(value, arg):
    """Resta el argumento del valor."""
    try:
        val_numeric = int(value)
        arg_numeric = int(arg)
        return val_numeric - arg_numeric
    except (ValueError, TypeError):
        try:
            # Intenta restar directamente (ej. para Decimals)
            return value - arg
        except (ValueError, TypeError, Exception):
            return '' # O devuelve 0 o None si prefieres