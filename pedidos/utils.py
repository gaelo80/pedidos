# pedidos/utils.py
from decimal import Decimal, InvalidOperation
import logging

# Configura un logger para este módulo
logger = logging.getLogger(__name__)

def preparar_datos_seccion(items_seccion, tallas_columnas_definidas=None): # El segundo argumento ahora es opcional
    """
    Agrupa los detalles de un pedido por referencia y color para su visualización.
    Ahora descubre dinámicamente las tallas presentes en los items.
    """
    grupos = {} 
    tallas_presentes_en_seccion = set()

    for item in items_seccion:
        try:
            ref = item.producto.referencia
            color = item.producto.color 
            talla_actual = item.producto.talla
            cantidad_actual = item.cantidad
            
            precio_unitario = Decimal(item.precio_unitario or '0.00')
            subtotal_linea = Decimal(item.subtotal or '0.00')

        except AttributeError as e:
            logger.error(f"Error de atributo en DetallePedido {item.pk}: {e}. Revisar modelos.")
            continue 
        except (InvalidOperation, TypeError) as e_conv:
            logger.error(f"Error convirtiendo a Decimal para item {item.pk}. Error: {e_conv}")
            continue

        clave = (ref, color) 

        if clave not in grupos:
            grupos[clave] = {
                'ref': ref, 'color': color, 
                'tallas_cantidades': {}, 
                'cantidad_total': 0,
                'subtotal_total': Decimal('0.00'), 
                'precio_unitario': precio_unitario
            }

        grupos[clave]['tallas_cantidades'][talla_actual] = grupos[clave]['tallas_cantidades'].get(talla_actual, 0) + cantidad_actual
        grupos[clave]['cantidad_total'] += cantidad_actual
        grupos[clave]['subtotal_total'] += subtotal_linea

        # --- LÓGICA CORREGIDA ---
        # Simplemente añadimos la talla si existe en el producto.
        # Ya no la comparamos con una lista maestra.
        if talla_actual:
            tallas_presentes_en_seccion.add(talla_actual)

    # Función para ordenar tallas numéricamente primero, luego alfabéticamente
    def ordenar_tallas_llave(talla):
        try:
            return (0, int(talla))
        except (ValueError, TypeError):
            return (1, talla)

    tallas_columnas_finales = sorted(list(tallas_presentes_en_seccion), key=ordenar_tallas_llave)
    lista_grupos_ordenada = sorted(grupos.values(), key=lambda g: (g['ref'], g['color']))
    
    return lista_grupos_ordenada, tallas_columnas_finales