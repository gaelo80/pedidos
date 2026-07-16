# Crea la Bodega Principal de cada empresa existente y asigna a ella
# todo el inventario/movimientos/ingresos/salidas que ya existían antes
# de que el sistema de bodegas múltiples existiera.

from django.db import migrations


def crear_principales_y_backfill(apps, schema_editor):
    Empresa = apps.get_model('clientes', 'Empresa')
    Bodega = apps.get_model('bodega', 'Bodega')
    MovimientoInventario = apps.get_model('bodega', 'MovimientoInventario')
    IngresoBodega = apps.get_model('bodega', 'IngresoBodega')
    SalidaInternaCabecera = apps.get_model('bodega', 'SalidaInternaCabecera')
    Producto = apps.get_model('productos', 'Producto')

    for empresa in Empresa.objects.all():
        principal, _ = Bodega.objects.get_or_create(
            empresa=empresa,
            es_principal=True,
            defaults={
                'nombre': 'Principal',
                'codigo': 'PRINCIPAL',
                'tipo': 'PRINCIPAL',
                'activa': True,
            }
        )

        MovimientoInventario.objects.filter(empresa=empresa, bodega__isnull=True).update(bodega=principal)
        IngresoBodega.objects.filter(empresa=empresa, bodega__isnull=True).update(bodega=principal)
        SalidaInternaCabecera.objects.filter(empresa=empresa, bodega_origen__isnull=True).update(bodega_origen=principal)
        Producto.objects.filter(empresa=empresa, ubicacion__isnull=True).update(ubicacion=principal)


def revertir(apps, schema_editor):
    # No se elimina nada al revertir: los datos backfilleados se quedan como
    # historial válido (apuntando a una bodega Principal que seguiría existiendo
    # si la migración de creación de modelos también se revierte).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('bodega', '0007_alter_personalbodega_options_and_more'),
        ('productos', '0008_alter_producto_ubicacion'),
    ]

    operations = [
        migrations.RunPython(crear_principales_y_backfill, revertir),
    ]
