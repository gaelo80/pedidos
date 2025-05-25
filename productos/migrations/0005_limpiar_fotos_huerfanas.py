# productos/migrations/000X_limpiar_fotos_huerfanas.py
from django.db import migrations

def eliminar_fotos_sin_agrupador(apps, schema_editor):
    FotoProducto = apps.get_model('productos', 'FotoProducto')
    db_alias = schema_editor.connection.alias

    fotos_a_eliminar = FotoProducto.objects.using(db_alias).filter(articulo_agrupador__isnull=True)
    count = fotos_a_eliminar.count()

    if count > 0:
        print(f"\n   Eliminando {count} FotoProducto(s) con articulo_agrupador nulo...")
        fotos_a_eliminar.delete()
        print(f"   - {count} FotoProducto(s) huérfanas eliminadas.")
    else:
        print("\n   No se encontraron FotoProducto(s) huérfanas para eliminar.")

class Migration(migrations.Migration):
    dependencies = [
        # La migración anterior (la de poblar_referencia_color_y_reasignar_fotos, ej. 0004_...)
        ('productos', '0004_poblar_referencia_color_y_reasignar_fotos'), # AJUSTA ESTE NOMBRE
    ]
    operations = [
        migrations.RunPython(eliminar_fotos_sin_agrupador, reverse_code=migrations.RunPython.noop),
    ]