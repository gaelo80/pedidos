from django import template

register = template.Library()


@register.filter
def duracion(td):
    """timedelta -> '3 d 4 h' / '5 h 12 min' / '8 min'."""
    if td is None:
        return '-'
    minutos = int(td.total_seconds() // 60)
    dias, resto = divmod(minutos, 60 * 24)
    horas, mins = divmod(resto, 60)
    if dias:
        return f"{dias} d {horas} h"
    if horas:
        return f"{horas} h {mins} min"
    return f"{mins} min"
