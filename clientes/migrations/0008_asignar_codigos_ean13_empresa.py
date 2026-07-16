import re
from django.db import migrations


def _digito_verificador_ean13(cuerpo_12_digitos):
    total = sum(
        int(digito) * (1 if (indice + 1) % 2 == 1 else 3)
        for indice, digito in enumerate(cuerpo_12_digitos)
    )
    return (10 - (total % 10)) % 10


# Esquema viejo (sin identificador de empresa): '20' + 10 dígitos de
# consecutivo + dígito verificador = 13 caracteres. Ya se verificó antes de
# implementar el generador automático que ningún código digitado a mano por
# los usuarios coincide con este patrón, así que todo lo que calce aquí fue
# generado por el sistema y es seguro renumerar.
PATRON_EAN13_ESQUEMA_VIEJO = re.compile(r'^20\d{11}$')


def asignar_codigos_y_renumerar(apps, schema_editor):
    Empresa = apps.get_model('clientes', 'Empresa')
    Producto = apps.get_model('productos', 'Producto')

    # 1. Asignar a cada empresa su bloque de 3 dígitos, por orden alfabético.
    empresas = list(Empresa.objects.order_by('nombre'))
    for indice, empresa in enumerate(empresas, start=1):
        empresa.codigo_ean13_empresa = indice
        empresa.save(update_fields=['codigo_ean13_empresa'])

    # 2. Renumerar los códigos ya generados con el esquema viejo para que
    #    incluyan el identificador de empresa. Los códigos digitados a mano
    #    (que no calzan con el patrón viejo) no se tocan.
    for empresa in empresas:
        productos_a_renumerar = [
            p for p in Producto.objects.filter(empresa=empresa).order_by('fecha_creacion', 'pk')
            if p.codigo_barras and PATRON_EAN13_ESQUEMA_VIEJO.match(p.codigo_barras)
        ]

        if not productos_a_renumerar:
            continue

        # Paso 1: liberar los códigos viejos primero, para no chocar
        # transitoriamente con la restricción única mientras se reasignan
        # (la restricción es condicional: solo aplica si codigo_barras no es nulo).
        ids = [p.pk for p in productos_a_renumerar]
        Producto.objects.filter(pk__in=ids).update(codigo_barras=None)

        # Paso 2: reasignar códigos nuevos y consecutivos con el identificador
        # de empresa incluido, en el mismo orden en que se habían creado.
        consecutivo = 0
        for producto in productos_a_renumerar:
            consecutivo += 1
            cuerpo = f"20{empresa.codigo_ean13_empresa:03d}{consecutivo:07d}"
            producto.codigo_barras = cuerpo + str(_digito_verificador_ean13(cuerpo))
            producto.save(update_fields=['codigo_barras'])

        empresa.ultimo_consecutivo_ean13 = consecutivo
        empresa.save(update_fields=['ultimo_consecutivo_ean13'])


def revertir(apps, schema_editor):
    # No es posible reconstruir el esquema viejo exacto (se perdería el orden
    # de emisión original), así que revertir solo limpia el código de empresa.
    Empresa = apps.get_model('clientes', 'Empresa')
    Empresa.objects.update(codigo_ean13_empresa=None)


class Migration(migrations.Migration):

    dependencies = [
        ('clientes', '0007_empresa_codigo_ean13_empresa'),
        ('productos', '0012_alter_producto_options'),
    ]

    operations = [
        migrations.RunPython(asignar_codigos_y_renumerar, revertir),
    ]
