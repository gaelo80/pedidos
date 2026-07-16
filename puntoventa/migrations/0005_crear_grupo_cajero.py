from django.db import migrations


def crear_grupo_cajero(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name='Cajero')


def eliminar_grupo_cajero(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name='Cajero').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('puntoventa', '0004_ventapos_notas_devolucioncambiopos_and_more'),
    ]

    operations = [
        migrations.RunPython(crear_grupo_cajero, eliminar_grupo_cajero),
    ]
