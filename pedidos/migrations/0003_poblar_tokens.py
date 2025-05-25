# pedidos/migrations/0003_poblar_tokens.py (o como se llame el tuyo)
from django.db import migrations
import uuid

def generar_uuids_para_pedidos(apps, schema_editor):
    Pedido = apps.get_model('pedidos', 'Pedido') # Cambia 'pedidos' si tu app se llama diferente
    for pedido_obj in Pedido.objects.all():
        pedido_obj.token_descarga_fotos = uuid.uuid4()
        pedido_obj.save(update_fields=['token_descarga_fotos'])

class Migration(migrations.Migration):

    dependencies = [
        ('pedidos', '0002_pedido_token_descarga_fotos'), # USA AQUÍ EL NOMBRE DEL ARCHIVO DEL PASO C.2
    ]

    operations = [
        migrations.RunPython(generar_uuids_para_pedidos, reverse_code=migrations.RunPython.noop),
    ]