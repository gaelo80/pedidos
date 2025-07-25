# Generated by Django 5.2.1 on 2025-07-10 23:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('costeo_jeans', '0008_alter_detalleproceso_cantidad'),
    ]

    operations = [
        migrations.AddField(
            model_name='detalleinsumo',
            name='consumo_unitario',
            field=models.DecimalField(decimal_places=4, default=0, help_text='Cantidad o metros necesarios para UNA SOLA UNIDAD del producto.', max_digits=10),
        ),
        migrations.AlterField(
            model_name='detalleinsumo',
            name='cantidad',
            field=models.DecimalField(decimal_places=2, editable=False, help_text='Cantidad total calculada para toda la producción.', max_digits=10),
        ),
    ]
