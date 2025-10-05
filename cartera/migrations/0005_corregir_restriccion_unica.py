# cartera/migrations/XXXX_corregir_restriccion_unica.py
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    # IMPORTANTE: Busca el nombre de tu última migración REAL y ponlo aquí.
    # Por ejemplo, si el archivo anterior a este se llama '0015_auto_....py',
    # la línea de abajo debe decir ('cartera', '0015_auto_....'),
    dependencies = [
        ('cartera', '0004_documentocartera_restriccion_factura_unica_por_cliente'), # AJUSTA ESTE NOMBRE
    ]

    operations = [
        # Hemos eliminado la operación 'RemoveConstraint' que causaba el error.
        # Ahora solo se ejecutará la creación de la nueva restricción.
        migrations.AddConstraint(
            model_name='documentocartera',
            constraint=models.UniqueConstraint(
                fields=('empresa', 'cliente', 'tipo_documento', 'numero_documento'), 
                name='restriccion_doc_unico_por_cliente'
            ),
        ),
    ]