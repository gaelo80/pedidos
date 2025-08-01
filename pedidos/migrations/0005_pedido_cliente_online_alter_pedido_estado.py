# Generated by Django 5.2.1 on 2025-07-23 20:43

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pedidos', '0004_alter_pedido_estado'),
        ('pedidos_online', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='pedido',
            name='cliente_online',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='pedidos', to='pedidos_online.clienteonline', verbose_name='Cliente Online'),
        ),
        migrations.AlterField(
            model_name='pedido',
            name='estado',
            field=models.CharField(choices=[('PENDIENTE_CLIENTE', 'Pendiente por Aprobación de Cliente'), ('BORRADOR', 'Borrador'), ('PENDIENTE_APROBACION_CARTERA', 'Pendiente Aprobación Cartera'), ('RECHAZADO_CARTERA', 'Rechazado por Cartera'), ('PENDIENTE_APROBACION_ADMIN', 'Pendiente Aprobación Administración'), ('RECHAZADO_ADMIN', 'Rechazado por Administración'), ('APROBADO_ADMIN', 'Aprobado por Administración (Listo Bodega)'), ('PROCESANDO', 'Procesando en Bodega'), ('COMPLETADO', 'Completado en Bodega'), ('ENVIADO_INCOMPLETO', 'Enviado Incompleto'), ('LISTO_BODEGA_DIRECTO', 'Listo para Bodega (Directo)'), ('ENVIADO', 'Enviado'), ('ENTREGADO', 'Entregado'), ('CANCELADO', 'Cancelado')], default='BORRADOR', max_length=35, verbose_name='Estado del Pedido'),
        ),
    ]
