# productos/migrations/0004_poblar_referencia_color_y_reasignar_fotos.py
from django.db import migrations

def migrar_datos_a_referencia_color(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    ReferenciaColor = apps.get_model('productos', 'ReferenciaColor')
    FotoProducto = apps.get_model('productos', 'FotoProducto') # Modelo FotoProducto
    db_alias = schema_editor.connection.alias

    print("\n   [MIGRACION DE DATOS INICIADA]")
    # --- Paso 1: Crear/Obtener ReferenciaColor y asignar a Productos (variantes) ---
    print("   Paso 1: Creando/Obteniendo instancias de ReferenciaColor y asignándolas a los Productos (variantes)...")
    
    ref_color_cache = {} # Caché para evitar lookups/creaciones repetidas de ReferenciaColor
    productos_actualizados_count = 0
    referencias_color_creadas_count = 0
    productos_sin_ref_o_color_count = 0

    for producto_variante in Producto.objects.using(db_alias).select_related('articulo_color_fotos').all():
        # Usar producto_variante.referencia y producto_variante.color para la agrupación
        ref_base_val = producto_variante.referencia
        color_val = producto_variante.color # Puede ser None o ''

        if not ref_base_val: # Si la variante no tiene una referencia base, no podemos agruparla bien
            print(f"      ADVERTENCIA: Producto (variante) ID {producto_variante.pk} no tiene 'referencia'. Se omitirá para ReferenciaColor.")
            productos_sin_ref_o_color_count +=1
            continue

        # Normalizar color vacío a None para consistencia en la clave de caché y get_or_create
        color_val_normalizado = color_val if color_val and color_val.strip() != "" else None
        
        cache_key = (ref_base_val, color_val_normalizado)
        
        ref_color_obj = None
        if cache_key in ref_color_cache:
            ref_color_obj = ref_color_cache[cache_key]
        else:
            try:
                ref_color_obj, created = ReferenciaColor.objects.using(db_alias).get_or_create(
                    referencia_base=ref_base_val,
                    color=color_val_normalizado # Usar el valor normalizado
                )
                if created:
                    print(f"      Creada ReferenciaColor: REF='{ref_base_val}', Color='{color_val_normalizado}'")
                    referencias_color_creadas_count += 1
                ref_color_cache[cache_key] = ref_color_obj
            except Exception as e:
                print(f"      ERROR creando/obteniendo ReferenciaColor para REF='{ref_base_val}', Color='{color_val_normalizado}': {e}")
                continue # Saltar este producto si no se puede crear/obtener su ReferenciaColor
        
        # Asignar al producto variante si no es el mismo objeto o si es None
        if producto_variante.articulo_color_fotos_id != ref_color_obj.id:
             producto_variante.articulo_color_fotos = ref_color_obj
             producto_variante.save(update_fields=['articulo_color_fotos'])
             productos_actualizados_count += 1

    print(f"   - Fin Paso 1: {productos_actualizados_count} Productos (variantes) actualizados con ReferenciaColor.")
    print(f"                  {referencias_color_creadas_count} nuevas ReferenciaColor creadas.")
    if productos_sin_ref_o_color_count > 0:
        print(f"                  {productos_sin_ref_o_color_count} Productos (variantes) omitidos por falta de 'referencia'.")

    # --- Paso 2: Reasignar FotoProducto existentes (SI ES POSIBLE Y DESEADO) ---
    print("\n   Paso 2: Reasignación de FotoProducto existentes...")
    print("   ADVERTENCIA: La migración de esquema anterior (0003) eliminó la FK original de FotoProducto a Producto.")
    print("   Por lo tanto, las FotoProducto existentes NO PUEDEN SER REASIGNADAS AUTOMÁTICAMENTE a ReferenciaColor en este script")
    print("   porque han perdido su vínculo original con la variante Producto de la cual se derivaría la ReferenciaColor.")
    print("   - Si no tenías fotos antes de la migración 0003, no hay problema.")
    print("   - Si tenías fotos, estas tendrán 'articulo_agrupador_id = NULL'.")
    print("   Deberás resubir las fotos usando el nuevo sistema que las asociará a ReferenciaColor,")
    print("   o realizar una restauración de base de datos y una estrategia de migración de esquema más compleja")
    print("   que preserve el enlace original de FotoProducto a Producto (variante) temporalmente.")
    
    # Si en el futuro implementas una forma de reasignar (ej. con un campo legacy_fk temporal):
    # fotos_reasignadas_count = 0
    # for foto in FotoProducto.objects.using(db_alias).filter(articulo_agrupador__isnull=True):
    #     # ... tu lógica para encontrar la ReferenciaColor para 'foto' ...
    #     # foto.articulo_agrupador = la_referencia_color_correcta
    #     # foto.save(update_fields=['articulo_agrupador'])
    #     # fotos_reasignadas_count += 1
    # print(f"   - {fotos_reasignadas_count} FotoProducto reasignadas (ejemplo, adaptar lógica).")
    print("   [MIGRACION DE DATOS FINALIZADA]")


def revert_migrar_datos_a_referencia_color(apps, schema_editor):
    # Revertir esto es complejo: implicaría poner Producto.articulo_color_fotos a NULL.
    # Las ReferenciaColor creadas podrían quedarse o eliminarse si no tienen variantes.
    # No se pueden "des-reasignar" fácilmente las FotoProducto si la FK original se fue.
    print("\n   [REVERSION DE MIGRACION DE DATOS INICIADA]")
    Producto = apps.get_model('productos', 'Producto')
    db_alias = schema_editor.connection.alias
    updated_count = Producto.objects.using(db_alias).filter(articulo_color_fotos__isnull=False).update(articulo_color_fotos=None)
    print(f"   - {updated_count} Productos (variantes) tuvieron articulo_color_fotos puesto a NULL.")
    print("   - Las ReferenciaColor creadas no se eliminan automáticamente en esta reversión.")
    print("   - Las FotoProducto no se revierten a su estado anterior (si la FK original fue eliminada).")
    print("   [REVERSION DE MIGRACION DE DATOS FINALIZADA]")


class Migration(migrations.Migration):

    dependencies = [
        # Asegúrate de que esta sea la migración anterior correcta (la 0003 que acabas de aplicar)
        ('productos', '0003_referenciacolor_alter_fotoproducto_options_and_more'),
    ]

    operations = [
        migrations.RunPython(migrar_datos_a_referencia_color, reverse_code=revert_migrar_datos_a_referencia_color),
    ]