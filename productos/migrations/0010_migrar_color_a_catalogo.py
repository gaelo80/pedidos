import unicodedata
from django.db import migrations


def _normalizar_nombre_color(nombre):
    if not nombre:
        return nombre
    sin_tildes = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode('ascii')
    return sin_tildes.strip().upper()


def poblar_color_temp(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Color = apps.get_model('productos', 'Color')

    cache_colores = {}  # (empresa_id, nombre_normalizado) -> Color instance

    productos_con_color = Producto.objects.exclude(color__isnull=True).exclude(color='').select_related(None)
    for producto in productos_con_color.iterator():
        nombre_normalizado = _normalizar_nombre_color(producto.color)
        if not nombre_normalizado:
            continue
        clave = (producto.empresa_id, nombre_normalizado)
        color_obj = cache_colores.get(clave)
        if color_obj is None:
            color_obj, _ = Color.objects.get_or_create(
                empresa_id=producto.empresa_id,
                nombre=nombre_normalizado,
            )
            cache_colores[clave] = color_obj
        producto.color_temp_id = color_obj.pk
        producto.save(update_fields=['color_temp'])


def revertir(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.update(color_temp=None)
    Color = apps.get_model('productos', 'Color')
    Color.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('productos', '0009_color_producto_color_temp_and_more'),
    ]

    operations = [
        migrations.RunPython(poblar_color_temp, revertir),
    ]
