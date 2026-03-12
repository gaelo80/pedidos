from rest_framework import serializers
from django.db import transaction
from .models import InventarioAlmacen, FacturaAlmacen, DetalleFacturaAlmacen
from bodega.models import MovimientoInventario

class InventarioAlmacenSerializer(serializers.ModelSerializer):
    # Extraemos campos específicos del Producto original (la Bodega)
    # NOTA: Cambia 'referencia' y 'descripcion' si tus campos en el modelo Producto se llaman diferente (ej. 'codigo', 'nombre')
    codigo_barras = serializers.CharField(source='producto.referencia')
    nombre = serializers.CharField(source='producto.descripcion')

    class Meta:
        model = InventarioAlmacen
        fields = ['id', 'codigo_barras', 'nombre', 'precio_detal', 'stock_actual']


class DetalleFacturaAlmacenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DetalleFacturaAlmacen
        fields = ['producto', 'cantidad', 'precio_unitario', 'subtotal']


class FacturaAlmacenSerializer(serializers.ModelSerializer):
    detalles = DetalleFacturaAlmacenSerializer(many=True, write_only=True)

    class Meta:
        model = FacturaAlmacen
        fields = ['id', 'consecutivo_local', 'fecha_venta', 'total_venta',
                  'metodo_pago', 'detalles', 'sincronizado_el']
        read_only_fields = ['sincronizado_el']

    def create(self, validated_data):
        """
        Crea una factura con sus detalles y registra MovimientoInventario.

        Flujo:
        1. Crear FacturaAlmacen
        2. Crear DetalleFacturaAlmacen para cada producto
        3. Crear MovimientoInventario (SALIDA_VENTA) para contabilizar la venta
        4. Signal almacen/signals.py decrementará automáticamente InventarioAlmacen
        """
        detalles_data = validated_data.pop('detalles', [])
        validated_data['vendedor'] = self.context['request'].user

        with transaction.atomic():
            factura = FacturaAlmacen.objects.create(**validated_data)

            for detalle in detalles_data:
                detalle_obj = DetalleFacturaAlmacen.objects.create(
                    factura=factura,
                    **detalle
                )

                # Crear MovimientoInventario para registrar la venta
                # El signal almacen/signals.py también decrementará InventarioAlmacen
                MovimientoInventario.objects.create(
                    empresa=validated_data.get('vendedor').empresa if hasattr(validated_data.get('vendedor'), 'empresa') else None,
                    producto=detalle_obj.producto,
                    cantidad=-detalle_obj.cantidad,  # Negativo para salida
                    tipo_movimiento='SALIDA_VENTA_ALMACEN',
                    documento_referencia=f"FacturaAlmacen #{factura.pk}",
                    usuario=validated_data.get('vendedor'),
                    notas=f"Venta en almacén - Método: {factura.metodo_pago}"
                )

        return factura