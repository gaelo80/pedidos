from django.db import migrations


def _digito_verificador_ean13(cuerpo_12_digitos):
    total = sum(
        int(digito) * (1 if (indice + 1) % 2 == 1 else 3)
        for indice, digito in enumerate(cuerpo_12_digitos)
    )
    return (10 - (total % 10)) % 10


def regenerar_todos_los_codigos(apps, schema_editor):
    """
    Reemplaza TODOS los códigos de barras existentes (incluidos los
    digitados a mano antes de que existiera el generador automático) por el
    esquema nuevo (empresa + consecutivo). Decisión explícita del usuario,
    a sabiendas de que invalida cualquier etiqueta física ya impresa con
    los códigos viejos.
    """
    Empresa = apps.get_model('clientes', 'Empresa')
    Producto = apps.get_model('productos', 'Producto')

    for empresa in Empresa.objects.all():
        productos = list(
            Producto.objects.filter(empresa=empresa)
            .order_by('referencia', 'color_id', 'talla', 'pk')
        )

        if not productos:
            continue

        # Paso 1: liberar todos los códigos actuales de esta empresa antes de
        # reasignar, para no chocar transitoriamente con la restricción única
        # (la restricción es condicional: solo aplica si codigo_barras no es nulo).
        Producto.objects.filter(empresa=empresa).update(codigo_barras=None)

        # Paso 2: asignar códigos nuevos y consecutivos a todos, con el
        # identificador de empresa incluido.
        consecutivo = 0
        for producto in productos:
            consecutivo += 1
            cuerpo = f"20{empresa.codigo_ean13_empresa:03d}{consecutivo:07d}"
            producto.codigo_barras = cuerpo + str(_digito_verificador_ean13(cuerpo))
            producto.save(update_fields=['codigo_barras'])

        empresa.ultimo_consecutivo_ean13 = consecutivo
        empresa.save(update_fields=['ultimo_consecutivo_ean13'])


def revertir(apps, schema_editor):
    # No es reversible: se perdieron los códigos originales al sobrescribirlos.
    raise migrations.exceptions.IrreversibleError(
        "Esta migración no se puede revertir: los códigos de barras originales "
        "ya fueron reemplazados y no quedaron guardados en ningún lado."
    )


class Migration(migrations.Migration):

    dependencies = [
        ('clientes', '0008_asignar_codigos_ean13_empresa'),
        ('productos', '0012_alter_producto_options'),
    ]

    operations = [
        migrations.RunPython(regenerar_todos_los_codigos, revertir),
    ]
