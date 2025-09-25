
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('bodega', '0001_initial'),
        ('clientes', '0001_initial'),
        ('pedidos', '0001_initial'),
        ('productos', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='borradordespacho',
            name='pedido',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='borradores_despacho', to='pedidos.pedido', verbose_name='Pedido'),
        ),
        migrations.AddField(
            model_name='borradordespacho',
            name='usuario',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Usuario Responsable'),
        ),
        migrations.AddField(
            model_name='cabeceraconteo',
            name='empresa',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conteos_inventario', to='clientes.empresa', verbose_name='Empresa'),
        ),
        migrations.AddField(
            model_name='cabeceraconteo',
            name='usuario_registro',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Usuario que Registró'),
        ),
        migrations.AddField(
            model_name='comprobantedespacho',
            name='empresa',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comprobantes_despacho', to='clientes.empresa', verbose_name='Empresa'),
        ),
        migrations.AddField(
            model_name='comprobantedespacho',
            name='pedido',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='comprobantes_despacho', to='pedidos.pedido', verbose_name='Pedido Asociado'),
        ),
        migrations.AddField(
            model_name='comprobantedespacho',
            name='usuario_responsable',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='comprobantes_despachados', to=settings.AUTH_USER_MODEL, verbose_name='Usuario Responsable (Bodega)'),
        ),
        migrations.AddField(
            model_name='conteoinventario',
            name='cabecera_conteo',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='detalles_conteo', to='bodega.cabeceraconteo', verbose_name='Cabecera del Conteo'),
        ),
        migrations.AddField(
            model_name='conteoinventario',
            name='empresa',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='detalles_conteo_inventario', to='clientes.empresa', verbose_name='Empresa'),
        ),
        migrations.AddField(
            model_name='conteoinventario',
            name='producto',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='conteos_inventario', to='productos.producto', verbose_name='Producto Contado'),
        ),
        migrations.AddField(
            model_name='conteoinventario',
            name='usuario_conteo',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Usuario que Contó'),
        ),
        migrations.AddField(
            model_name='detalleborradordespacho',
            name='borrador_despacho',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='detalles_borrador', to='bodega.borradordespacho', verbose_name='Borrador de Despacho'),
        ),
        migrations.AddField(
            model_name='detalleborradordespacho',
            name='detalle_pedido_origen',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='detalles_borrador_asociados', to='pedidos.detallepedido', verbose_name='Detalle Pedido Original'),
        ),
        migrations.AddField(
            model_name='detalleborradordespacho',
            name='producto',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='productos.producto', verbose_name='Producto'),
        ),
        migrations.AddField(
            model_name='detallecomprobantedespacho',
            name='comprobante_despacho',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='detalles', to='bodega.comprobantedespacho', verbose_name='Comprobante de Despacho'),
        ),
        migrations.AddField(
            model_name='detallecomprobantedespacho',
            name='detalle_pedido_origen',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='items_despachados', to='pedidos.detallepedido', verbose_name='Línea del Pedido Original'),
        ),
        migrations.AddField(
            model_name='detallecomprobantedespacho',
            name='producto',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='en_despachos', to='productos.producto', verbose_name='Producto Despachado'),
        ),
        migrations.AddField(
            model_name='detalleingresobodega',
            name='producto',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='detalles_ingreso', to='productos.producto', verbose_name='Producto Ingresado'),
        ),
        migrations.AddField(
            model_name='ingresobodega',
            name='empresa',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ingresos_bodega', to='clientes.empresa', verbose_name='Empresa'),
        ),
        migrations.AddField(
            model_name='ingresobodega',
            name='usuario',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ingresos_registrados', to=settings.AUTH_USER_MODEL, verbose_name='Usuario Registrador'),
        ),
        migrations.AddField(
            model_name='detalleingresobodega',
            name='ingreso',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='detalles', to='bodega.ingresobodega', verbose_name='Ingreso Asociado'),
        ),
        migrations.AddField(
            model_name='movimientoinventario',
            name='empresa',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='movimientos_inventario', to='clientes.empresa', verbose_name='Empresa'),
        ),
        migrations.AddField(
            model_name='movimientoinventario',
            name='producto',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='movimientos', to='productos.producto', verbose_name='Producto'),
        ),
        migrations.AddField(
            model_name='movimientoinventario',
            name='usuario',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='movimientos_registrados', to=settings.AUTH_USER_MODEL, verbose_name='Usuario Registrador'),
        ),
        migrations.AddField(
            model_name='personalbodega',
            name='user',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='perfil_bodega', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='salidainternacabecera',
            name='empresa',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='salidas_internas', to='clientes.empresa', verbose_name='Empresa'),
        ),
        migrations.AddField(
            model_name='salidainternacabecera',
            name='responsable_entrega',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='salidas_internas_entregadas', to=settings.AUTH_USER_MODEL, verbose_name='Responsable de Entrega (Bodega)'),
        ),
        migrations.AddField(
            model_name='salidainternadetalle',
            name='cabecera_salida',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='detalles', to='bodega.salidainternacabecera', verbose_name='Cabecera de Salida Interna'),
        ),
        migrations.AddField(
            model_name='salidainternadetalle',
            name='producto',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='productos.producto', verbose_name='Producto'),
        ),
        migrations.AlterUniqueTogether(
            name='borradordespacho',
            unique_together={('pedido', 'empresa')},
        ),
        migrations.AlterUniqueTogether(
            name='detalleborradordespacho',
            unique_together={('borrador_despacho', 'detalle_pedido_origen')},
        ),
        migrations.AlterUniqueTogether(
            name='detallecomprobantedespacho',
            unique_together={('comprobante_despacho', 'producto', 'detalle_pedido_origen')},
        ),
        migrations.AlterUniqueTogether(
            name='detalleingresobodega',
            unique_together={('ingreso', 'producto')},
        ),
        migrations.AlterUniqueTogether(
            name='salidainternadetalle',
            unique_together={('cabecera_salida', 'producto')},
        ),
    ]
