# pedidos/utils.py
from decimal import Decimal, InvalidOperation
import logging
from itertools import groupby
from operator import attrgetter

# Configura un logger para este módulo
logger = logging.getLogger(__name__)

def preparar_datos_seccion(items_genero, columnas_fijas):
    """
    Prepara los datos para una sección del PDF (ej. Dama, Caballero)
    usando una lista de columnas de tallas FIJA.
    """
    # Si no hay items o no se definieron columnas, no hay nada que hacer.
    if not items_genero or not columnas_fijas:
        return [], []

    # Define la función 'key' para agrupar por referencia y color
    keyfunc = attrgetter('producto.referencia', 'producto.color')
    
    items_ordenados = sorted(items_genero, key=keyfunc)
    
    grupos_procesados = []
    # Usamos el mismo keyfunc para el groupby
    for (ref, color), grupo_iter in groupby(items_ordenados, key=keyfunc):
        
        detalles_grupo = list(grupo_iter)
        
        tallas_cantidades = {
            str(d.producto.talla): d.cantidad 
            for d in detalles_grupo if d.producto and d.producto.talla
        }

        grupo_data = {
            'ref': ref,
            'color': color,
            'tallas_cantidades': tallas_cantidades,
            'cantidad_total': sum(d.cantidad for d in detalles_grupo),
            'precio_unitario': detalles_grupo[0].precio_unitario,
            'subtotal_total': sum(d.subtotal for d in detalles_grupo),
        }
        grupos_procesados.append(grupo_data)

    return grupos_procesados, columnas_fijas