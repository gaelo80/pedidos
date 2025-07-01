# pedidos/utils.py
from decimal import Decimal, InvalidOperation
import logging

# Configura un logger para este módulo
logger = logging.getLogger(__name__)

def preparar_datos_seccion(items_seccion, tallas_columnas_definidas):
    """
    Agrupa los detalles de un pedido por referencia y color para su visualización.

    Args:
        items_seccion (iterable): Una lista o queryset de objetos DetallePedido.
            -! SEGURIDAD !- Es responsabilidad de la vista que llama a esta función
            asegurarse de que este iterable ya esté filtrado por la empresa (tenant)
            correcta para evitar la fuga de datos.
        tallas_columnas_definidas (set): Un conjunto de todas las tallas posibles
            que deberían considerarse como columnas.

    Returns:
        tuple: Una tupla conteniendo:
            - lista_grupos_ordenada (list): Una lista de diccionarios, donde cada
              diccionario representa una fila (ref+color) con sus totales.
            - tallas_columnas_finales (list): Una lista ordenada de las tallas
              que realmente se encontraron en los items.
    """
    grupos = {} 
    tallas_presentes_en_seccion = set()

    for item in items_seccion:
        try:
            ref = item.producto.referencia
            color = item.producto.color 
            talla_actual = item.producto.talla
            cantidad_actual = item.cantidad
            
            # Asegura que los valores monetarios sean Decimal para cálculos precisos
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

        if talla_actual in tallas_columnas_definidas:
            tallas_presentes_en_seccion.add(talla_actual)

    # Función para ordenar tallas numéricamente primero, luego alfabéticamente
    def ordenar_tallas_llave(talla):
        try:
            # Prioriza los números, devolviendo una tupla (prioridad, valor)
            return (0, int(talla))
        except (ValueError, TypeError):
            # Las tallas no numéricas van después
            return (1, talla)

    tallas_columnas_finales = sorted(list(tallas_presentes_en_seccion), key=ordenar_tallas_llave)
    lista_grupos_ordenada = sorted(grupos.values(), key=lambda g: (g['ref'], g['color']))
    
    return lista_grupos_ordenada, tallas_columnas_finales