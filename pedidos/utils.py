from decimal import Decimal, InvalidOperation


def preparar_datos_seccion(items_seccion, tallas_columnas_definidas):
    grupos = {} 
    tallas_presentes_en_seccion = set()
    print(f"Preparando sección con {len(items_seccion)} items y tallas definidas: {tallas_columnas_definidas}") # Debug

    for item in items_seccion:
        try:
            # !!! Sigue verificando que estos nombres de campo sean correctos !!!
            ref = item.producto.referencia
            color = item.producto.color 
            talla_actual = item.producto.talla
            cantidad_actual = item.cantidad

            # Asegurarnos que los valores monetarios sean Decimal
            # Si ya vienen como Decimal del modelo, está bien. 
            # Si pudieran ser None o float, los convertimos.
            precio_unitario_val = item.precio_unitario
            subtotal_linea_val = item.subtotal
            print(f"    ---> Procesando Detalle PK={item.pk}: Ref='{ref}', Color='{color}', Talla='{talla_actual}', Qty={cantidad_actual}")


            precio_unitario = Decimal(str(precio_unitario_val)) if precio_unitario_val is not None else Decimal('0.00')
            subtotal_linea = Decimal(str(subtotal_linea_val)) if subtotal_linea_val is not None else Decimal('0.00')

        except AttributeError as e:
             print(f"Error! Campo no encontrado en 'item.producto'. Verifica 'models.py'. Error: {e}")
             continue 
        except (TypeError, ValueError) as e_conv: # Captura error si no se puede convertir a Decimal
             print(f"Error convirtiendo a Decimal para item {item.pk}. Precio='{precio_unitario_val}', Subtotal='{subtotal_linea_val}'. Error: {e_conv}")
             continue # Saltar este item si hay problemas con los valores

        clave = (ref, color) 

        if clave not in grupos:
            grupos[clave] = {
                'ref': ref, 'color': color, 
                'tallas_cantidades': {}, 'cantidad_total': 0,
                # <<< CAMBIO: Inicializar como Decimal >>>
                'subtotal_total': Decimal('0.00'), 
                'precio_unitario': precio_unitario # Guardar como Decimal
            }

        grupos[clave]['tallas_cantidades'][talla_actual] = grupos[clave]['tallas_cantidades'].get(talla_actual, 0) + cantidad_actual
        grupos[clave]['cantidad_total'] += cantidad_actual

        # <<< CORRECCIÓN: Ahora la suma es Decimal += Decimal >>>
        grupos[clave]['subtotal_total'] += subtotal_linea

        if talla_actual in tallas_columnas_definidas:
             tallas_presentes_en_seccion.add(talla_actual)

    # --- Resto de la función (ordenar tallas y grupos) sin cambios ---
    def ordenar_tallas_llave(talla):
        try: return int(talla)
        except ValueError: return float('inf') 

    tallas_columnas_finales = sorted(list(tallas_presentes_en_seccion), key=ordenar_tallas_llave)
    lista_grupos_ordenada = sorted(grupos.values(), key=lambda g: (g['ref'], g['color']))
    print(f"Sección preparada: {len(lista_grupos_ordenada)} grupos. Columnas de talla a mostrar: {tallas_columnas_finales}") # Debug
    return lista_grupos_ordenada, tallas_columnas_finales