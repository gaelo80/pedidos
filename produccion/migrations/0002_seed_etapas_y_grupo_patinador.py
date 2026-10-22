from django.db import migrations

ETAPAS_NUCLEO = [
    ('Corte', 1, False, False),
    ('Confección', 2, False, False),
    ('Lavandería', 3, False, False),
    ('Control de Calidad', 4, True, False),
    ('Empaque', 5, False, False),
    ('Bodega', 6, False, True),
]


def crear_grupo_patinador(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name='Patinador')


def eliminar_grupo_patinador(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name='Patinador').delete()


def seed_etapas(apps, schema_editor):
    Empresa = apps.get_model('clientes', 'Empresa')
    EtapaProduccion = apps.get_model('produccion', 'EtapaProduccion')
    for empresa in Empresa.objects.all():
        for nombre, orden, es_calidad, es_bodega in ETAPAS_NUCLEO:
            EtapaProduccion.objects.get_or_create(
                empresa=empresa, nombre=nombre,
                defaults={'orden': orden, 'es_control_calidad': es_calidad, 'es_ingreso_bodega': es_bodega, 'activa': True}
            )


def eliminar_etapas_nucleo(apps, schema_editor):
    EtapaProduccion = apps.get_model('produccion', 'EtapaProduccion')
    EtapaProduccion.objects.filter(nombre__in=[e[0] for e in ETAPAS_NUCLEO]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('produccion', '0001_initial'),
        ('clientes', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(crear_grupo_patinador, eliminar_grupo_patinador),
        migrations.RunPython(seed_etapas, eliminar_etapas_nucleo),
    ]
