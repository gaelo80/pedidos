# bodega/api_serializers.py
from rest_framework import serializers
from django.db.models import Sum
from pedidos.models import Pedido, DetallePedido
from bodega.models import ComprobanteDespacho, DetalleComprobanteDespacho
from productos.models import Producto


class DetallePedidoBodegaSerializer(serializers.ModelSerializer):
    """Serializer para DetallesPedido con información de dispatch"""
    producto_referencia = serializers.CharField(source='producto.referencia', read_only=True)
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    producto_color = serializers.CharField(source='producto.color', read_only=True, allow_null=True)
    producto_talla = serializers.CharField(source='producto.talla', read_only=True, allow_null=True)
    codigo_barras = serializers.CharField(source='producto.codigo_barras', read_only=True, allow_null=True)
    cantidad_pendiente = serializers.SerializerMethodField()

    class Meta:
        model = DetallePedido
        fields = [
            'id', 'cantidad', 'cantidad_verificada', 'verificado_bodega',
            'producto_referencia', 'producto_nombre', 'producto_color', 'producto_talla',
            'codigo_barras', 'precio_unitario', 'cantidad_pendiente'
        ]

    def get_cantidad_pendiente(self, obj):
        """Cantidad aún sin despachar"""
        if obj.cantidad_verificada is None:
            return obj.cantidad
        return max(0, obj.cantidad - obj.cantidad_verificada)


class PedidoBodegaListSerializer(serializers.ModelSerializer):
    """Serializer para lista de pedidos en bodega"""
    numero_pedido = serializers.CharField(source='numero_pedido_empresa', read_only=True)
    cliente_nombre = serializers.SerializerMethodField()
    total_items = serializers.SerializerMethodField()
    items_pendientes = serializers.SerializerMethodField()
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)

    class Meta:
        model = Pedido
        fields = [
            'id', 'numero_pedido', 'cliente_nombre', 'fecha_hora', 'estado',
            'estado_display', 'total_items', 'items_pendientes'
        ]

    def get_cliente_nombre(self, obj):
        """Retorna nombre del cliente"""
        if obj.cliente:
            return obj.cliente.nombre_completo
        elif obj.cliente_online:
            return obj.cliente_online.nombre
        return "Cliente Online"

    def get_total_items(self, obj):
        """Suma de cantidades de todos los detalles"""
        return obj.detalles.aggregate(
            total=Sum('cantidad')
        )['total'] or 0

    def get_items_pendientes(self, obj):
        """Suma de cantidades pendientes (no verificadas)"""
        detalles = obj.detalles.all()
        pendientes = sum(
            detalle.cantidad if detalle.cantidad_verificada is None
            else max(0, detalle.cantidad - detalle.cantidad_verificada)
            for detalle in detalles
        )
        return pendientes


class PedidoBodegaDetalleSerializer(serializers.ModelSerializer):
    """Serializer detallado de pedido con detalles para despacho"""
    numero_pedido = serializers.CharField(source='numero_pedido_empresa', read_only=True)
    cliente_nombre = serializers.SerializerMethodField()
    detalles = DetallePedidoBodegaSerializer(source='detalles', many=True, read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)

    class Meta:
        model = Pedido
        fields = [
            'id', 'numero_pedido', 'cliente_nombre', 'fecha_hora', 'estado',
            'estado_display', 'notas', 'detalles'
        ]

    def get_cliente_nombre(self, obj):
        """Retorna nombre del cliente"""
        if obj.cliente:
            return obj.cliente.nombre_completo
        elif obj.cliente_online:
            return obj.cliente_online.nombre
        return "Cliente Online"


class ComprobanteDespachoSerializer(serializers.ModelSerializer):
    """Serializer para comprobante de despacho"""
    usuario_nombre = serializers.CharField(source='usuario_responsable.get_full_name', read_only=True)
    detalles = serializers.SerializerMethodField()

    class Meta:
        model = ComprobanteDespacho
        fields = [
            'id', 'pedido', 'fecha_hora_despacho', 'usuario_nombre',
            'es_parcial', 'notas', 'detalles'
        ]

    def get_detalles(self, obj):
        """Retorna detalles del comprobante"""
        detalles = obj.detalles_comprobante.all()
        return [
            {
                'id': d.id,
                'producto_referencia': d.producto.referencia,
                'producto_nombre': d.producto.nombre,
                'cantidad_despachada': d.cantidad_despachada,
            }
            for d in detalles
        ]
