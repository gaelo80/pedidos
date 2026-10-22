from django.db import migrations

# Valores iniciales; cada empresa los ajusta en Producción > Etapas.
ETAPAS_EXTERNAS = {'Confección': 8, 'Lavandería': 5}


def marcar_externas(apps, schema_editor):
    EtapaProduccion = apps.get_model('produccion', 'EtapaProduccion')
    for nombre, dias in ETAPAS_EXTERNAS.items():
        EtapaProduccion.objects.filter(nombre=nombre).update(es_externa=True, dias_alerta=dias)


def desmarcar_externas(apps, schema_editor):
    EtapaProduccion = apps.get_model('produccion', 'EtapaProduccion')
    EtapaProduccion.objects.filter(nombre__in=ETAPAS_EXTERNAS).update(es_externa=False, dias_alerta=2)


class Migration(migrations.Migration):

    dependencies = [
        ('produccion', '0006_partidas_talleres_remisiones'),
    ]

    operations = [
        migrations.RunPython(marcar_externas, desmarcar_externas),
    ]
