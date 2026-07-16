import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('productos', '0010_migrar_color_a_catalogo'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='producto',
            name='color',
        ),
        migrations.RenameField(
            model_name='producto',
            old_name='color_temp',
            new_name='color',
        ),
        migrations.AlterField(
            model_name='producto',
            name='color',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='productos',
                to='productos.color',
                verbose_name='Color',
            ),
        ),
    ]
