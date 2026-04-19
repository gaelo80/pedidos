from django.core.management.base import BaseCommand
from pedidos.models import Pedido
from bodega.models import MovimientoInventario

class Command(BaseCommand):
    help = 'Repara los movimientos de inventario omitidos en pedidos antiguos (Inflado de matriz)'

    def handle(self, *args, **kwargs):
        estados_con_reserva = ['PENDIENTE_APROBACION_CARTERA', 'PENDIENTE_APROBACION_ADMIN', 'APROBADO_ADMIN']
        pedidos = Pedido.objects.filter(estado__in=estados_con_reserva).exclude(tipo_pedido='ONLINE')
        
        movimientos_creados = 0
        pedidos_revisados = 0

        self.stdout.write(self.style.WARNING("Iniciando auditoría y reparación de inventario..."))

        for pedido in pedidos:
            pedidos_revisados += 1
            for detalle in pedido.detalles.all():
                producto = detalle.producto
                
                existe_movimiento = MovimientoInventario.objects.filter(
                    empresa=pedido.empresa,
                    producto=producto,
                    documento_referencia__contains=f'Pedido #{pedido.numero_pedido_empresa}'
                ).exists()

                if not existe_movimiento:
                    cantidad_a_descontar = -detalle.cantidad
                    talla_display = producto.talla if hasattr(producto, 'talla') else producto.id
                    doc_ref = f'Pedido #{pedido.numero_pedido_empresa} (Reserva) - {producto.referencia} T-{talla_display}'

                    MovimientoInventario.objects.create(
                        empresa=pedido.empresa,
                        tipo_movimiento='SALIDA_VENTA_PENDIENTE',
                        documento_referencia=doc_ref,
                        producto=producto,
                        cantidad=cantidad_a_descontar,
                        usuario=pedido.vendedor.user if pedido.vendedor else None
                    )
                    movimientos_creados += 1
                    self.stdout.write(self.style.SUCCESS(f"Corregido: Pedido #{pedido.numero_pedido_empresa} | {producto.referencia} Talla {talla_display} | Cantidad: {cantidad_a_descontar}"))

        self.stdout.write("-" * 50)
        self.stdout.write(self.style.SUCCESS(f"Auditoría finalizada. Pedidos revisados: {pedidos_revisados}"))
        self.stdout.write(self.style.SUCCESS(f"Movimientos creados (Inventario descontado): {movimientos_creados}"))