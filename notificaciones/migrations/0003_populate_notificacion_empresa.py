from django.db import migrations
from django.conf import settings

def populate_empresa(apps, schema_editor):
    """
    Asigna la empresa correcta a cada notificación existente,
    basándose en la empresa del usuario destinatario.
    """
    Notificacion = apps.get_model('notificaciones', 'Notificacion')

    # Iteramos solo sobre las que acabamos de añadir (empresa=NULL)
    print("\nIniciando migración de datos de empresa en Notificaciones...")
    for notif in Notificacion.objects.filter(empresa__isnull=True).iterator():
        try:
            # Buscamos al usuario destinatario
            destinatario = notif.destinatario

            # Verificamos que el usuario exista y tenga una empresa
            if destinatario and hasattr(destinatario, 'empresa') and destinatario.empresa:
                notif.empresa = destinatario.empresa
                notif.save(update_fields=['empresa'])
            else:
                # Si el destinatario no existe o no tiene empresa, la notificación
                # está huérfana. Es seguro eliminarla.
                print(f"Eliminando notificación huérfana {notif.pk}")
                notif.delete()
        except Exception as e:
            # Si el usuario ya no existe (p.ej. User.DoesNotExist)
            print(f"Error migrando notif {notif.pk}, eliminando: {e}")
            try:
                notif.delete()
            except:
                pass # Si falla la eliminación, simplemente continuamos
    print("Migración de datos de empresa finalizada.")

class Migration(migrations.Migration):

    dependencies = [
        ('notificaciones', '0002_notificacion_empresa'), # El nombre de tu migración ANTERIOR
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('clientes', '0001_initial'), # <-- ASÍ QUEDA CORREGIDO
    ]

    operations = [
        migrations.RunPython(populate_empresa, migrations.RunPython.noop),
    ]