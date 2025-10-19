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
    if not items_genero or not columnas_fijas:
        return [], []

    keyfunc = attrgetter('producto.referencia', 'producto.color')
    items_ordenados = sorted(items_genero, key=keyfunc)
    
    grupos_procesados = []
    
    # --- INICIO DE LA CORRECCIÓN DEFINITIVA ---

    # Función helper para normalizar cualquier tipo de talla a un string simple
    def normalize_talla(t):
        if t is None:
            return ""
        # Convierte (16, 16.0, "16.0", " 16 ", "16,0") todos a "16"
        return str(t).strip().split('.')[0].split(',')[0]

    # 1. Normalizar las columnas y crear el mapa de índices
    # Ej: {"6": 0, "8": 1, "10": 2, ...}
    talla_a_indice = {normalize_talla(talla): i for i, talla in enumerate(columnas_fijas)}
    
    # 2. Preparar las columnas de cabecera (ya normalizadas) para devolver
    columnas_str = [normalize_talla(talla) for talla in columnas_fijas]

    for (ref, color), grupo_iter in groupby(items_ordenados, key=keyfunc):
        detalles_grupo = list(grupo_iter)
        
        # 3. Crear una lista de ceros, del mismo tamaño que las columnas
        # Ej: [0, 0, 0, 0, 0, 0]
        cantidades_ordenadas = [0] * len(columnas_str)
        
        # 4. Llenar la lista con las cantidades
        for d in detalles_grupo:
            # 5. Normalizar la talla del producto
            talla_producto_str = normalize_talla(d.producto.talla)
            
            # 6. Encontrar el índice de esta talla normalizada
            indice = talla_a_indice.get(talla_producto_str)
            
            # 7. Si se encontró el índice, sumar la cantidad en esa posición
            if indice is not None:
                cantidades_ordenadas[indice] += d.cantidad
            elif talla_producto_str: # Log si la talla existe pero no está en las columnas
                logger.warning(f"Talla '{talla_producto_str}' del producto {ref} no encontrada en columnas {columnas_str} (Mapa: {talla_a_indice.keys()})")
        
        # --- FIN DE LA CORRECCIÓN DEFINITIVA ---

        grupo_data = {
            'ref': ref,
            'color': color or 'SIN COLOR',
            'tallas_cantidades': cantidades_ordenadas, 
            'cantidad_total': sum(d.cantidad for d in detalles_grupo),
            'precio_unitario': detalles_grupo[0].precio_unitario,
            'subtotal_total': sum(d.subtotal for d in detalles_grupo),
        }
        grupos_procesados.append(grupo_data)

    # Devolvemos las columnas (como strings normalizados) para la cabecera
    return grupos_procesados, columnas_str