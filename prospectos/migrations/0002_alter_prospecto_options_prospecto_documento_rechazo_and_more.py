# Generated by Django 5.2.1 on 2025-07-25 11:15

import django.db.models.deletion
import prospectos.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prospectos', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='prospecto',
            options={'permissions': [('aprobar_prospecto_cartera', 'Puede aprobar solicitudes de prospectos (Cartera)'), ('rechazar_prospecto_cartera', 'Puede rechazar solicitudes de prospectos (Cartera)')], 'verbose_name': 'Prospecto', 'verbose_name_plural': 'Prospectos'},
        ),
        migrations.AddField(
            model_name='prospecto',
            name='documento_rechazo',
            field=models.FileField(blank=True, null=True, upload_to=prospectos.models.ruta_guardado_documento_rechazo, verbose_name='Documento de Rechazo (Opcional)'),
        ),
        migrations.AlterField(
            model_name='prospecto',
            name='vendedor_asignado',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='prospectos_asignados', to=settings.AUTH_USER_MODEL, verbose_name='Vendedor Asignado'),
        ),
    ]
