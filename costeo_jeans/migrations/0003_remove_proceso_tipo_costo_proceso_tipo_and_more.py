# Generated by Django 5.2.1 on 2025-07-05 06:09

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clientes', '0002_alter_empresa_telefono'),
        ('costeo_jeans', '0002_costeo_costo_total'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='proceso',
            name='tipo_costo',
        ),
        migrations.AddField(
            model_name='proceso',
            name='tipo',
            field=models.CharField(choices=[('PROCESO', 'Proceso Industrial'), ('CONFECCION', 'Confección por Prenda')], default='PROCESO', max_length=20),
        ),
        migrations.CreateModel(
            name='Confeccionista',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=150)),
                ('documento_identidad', models.CharField(blank=True, max_length=20, null=True, unique=True)),
                ('telefono', models.CharField(blank=True, max_length=20)),
                ('direccion', models.CharField(blank=True, max_length=255)),
                ('aplica_iva', models.BooleanField(default=False, help_text='Marcar si este confeccionista factura con IVA')),
                ('empresa', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='clientes.empresa')),
            ],
        ),
    ]
