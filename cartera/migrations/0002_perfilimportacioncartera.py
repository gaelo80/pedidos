# Generated by Django 5.2.1 on 2025-07-07 04:45

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cartera', '0001_initial'),
        ('clientes', '0003_empresa_ciudad_empresa_correo_electronico_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='PerfilImportacionCartera',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre_perfil', models.CharField(help_text="Nombre único para identificar este perfil (ej: 'Formato Contable S.A.S.')", max_length=100, unique=True)),
                ('fila_inicio_header', models.PositiveIntegerField(default=3, help_text='Número de la fila en Excel donde comienzan los datos (ej: si los datos empiezan en la fila 4, poner 3).')),
                ('columna_id_cliente', models.CharField(default='CODIGO', max_length=50)),
                ('columna_numero_documento', models.CharField(default='DOCUMENTO', max_length=50)),
                ('columna_fecha_documento', models.CharField(default='FECHADOC', max_length=50)),
                ('columna_fecha_vencimiento', models.CharField(default='FECHAVEN', max_length=50)),
                ('columna_saldo', models.CharField(default='SALDOACT', max_length=50)),
                ('columna_nombre_vendedor', models.CharField(default='NOMVENDEDOR', max_length=50)),
                ('columna_codigo_vendedor', models.CharField(default='VENDEDOR', max_length=50)),
                ('empresa', models.ForeignKey(help_text='Empresa a la que pertenece este formato de archivo.', on_delete=django.db.models.deletion.CASCADE, related_name='perfiles_importacion', to='clientes.empresa')),
            ],
            options={
                'verbose_name': 'Perfil de Importación de Cartera',
                'verbose_name_plural': 'Perfiles de Importación de Cartera',
                'unique_together': {('empresa', 'nombre_perfil')},
            },
        ),
    ]
