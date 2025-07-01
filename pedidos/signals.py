# pedidos/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from bodega.models import MovimientoInventario
import logging

# Configura un logger para este módulo
logger = logging.getLogger(__name__)

@receiver(post_save, sender='pedidos.Pedido')
def registrar_salida_venta_pedido(sender, instance, created, **kwargs):
    """
    Señal que se activa después de guardar un Pedido.
    Si el estado es 'ENVIADO', crea los movimientos de inventario correspondientes,
    asegurándose de que pertenezcan a la misma empresa que el pedido.
    """
    ESTADO_GATILLO_SALIDA = 'ENVIADO'

    if instance.estado == ESTADO_GATILLO_SALIDA:
        
        # 1. --- CORRECCIÓN DE SEGURIDAD: Usar la empresa del pedido ---
        empresa_del_pedido = instance.empresa
        
        # Si por alguna razón el pedido no tiene empresa, no podemos continuar.
        if not empresa_del_pedido:
            logger.error(f"Pedido #{instance.pk} no tiene una empresa asociada. No se puede crear movimiento de inventario.")
            return

        # 2. --- CORRECCIÓN DE SEGURIDAD: Añadir filtro por empresa ---
        existe_movimiento = MovimientoInventario.objects.filter(
            empresa=empresa_del_pedido, 
            tipo_movimiento='SALIDA_VENTA',
            documento_referencia=f'PEDIDO_{instance.pk}'
        ).exists()

        if not existe_movimiento:
            logger.info(f"Registrando salida de inventario para Pedido #{instance.pk} de la empresa {empresa_del_pedido.nombre}.")
            try:
                for detalle in instance.detalles.all():
                    # 3. --- CORRECCIÓN DE SEGURIDAD: Asignar la empresa al crear ---
                    MovimientoInventario.objects.create(
                        empresa=empresa_del_pedido,
                        producto=detalle.producto,
                        cantidad=-detalle.cantidad,
                        tipo_movimiento='SALIDA_VENTA',
                        fecha_hora=timezone.now(),
                        usuario=instance.vendedor.user if instance.vendedor else None,
                        documento_referencia=f'PEDIDO_{instance.pk}',
                        notas=f"Salida automática por {ESTADO_GATILLO_SALIDA} de Pedido #{instance.pk}"
                    )
                logger.info(f"Movimientos de SALIDA_VENTA creados para Pedido #{instance.pk}")
            except Exception as e:
                logger.error(f"ERROR al crear movimientos para Pedido #{instance.pk}: {e}")
        else:
            logger.warning(f"Ya existen movimientos de SALIDA_VENTA para Pedido #{instance.pk}. No se crean nuevos.")