# pedidos_web/signals.py
"""
Sincronización de inventario con Shopify EN TIEMPO REAL: cada vez que se crea
un MovimientoInventario (venta, despacho, ajuste, traslado, devolución...)
en cualquier parte del sistema, se agenda una actualización automática del
stock en Shopify -- sin que nadie tenga que entrar a la pantalla de
sincronización y darle clic.

Los movimientos de una misma transacción (ej. un ajuste masivo con 50 líneas)
se agrupan y se sincronizan en UN solo lote cuando la transacción termina de
guardarse (transaction.on_commit), en vez de mandar una sincronización por
cada movimiento individual.
"""
import logging
import threading

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from bodega.models import MovimientoInventario

logger = logging.getLogger(__name__)

# Almacenamiento por hilo: cada request de Django corre en un solo hilo bajo
# gunicorn (workers síncronos), así que esto agrupa correctamente todos los
# movimientos creados dentro de una misma transacción/petición.
_pendientes = threading.local()


def _programar_sincronizacion(producto):
    if not producto.empresa_id:
        return

    ids_pendientes = getattr(_pendientes, 'ids_por_empresa', None)
    if ids_pendientes is None:
        ids_pendientes = {}
        _pendientes.ids_por_empresa = ids_pendientes

    es_primero_de_la_empresa = producto.empresa_id not in ids_pendientes
    ids_pendientes.setdefault(producto.empresa_id, set()).add(producto.pk)

    if es_primero_de_la_empresa:
        transaction.on_commit(lambda: _disparar_sincronizacion(producto.empresa_id))


def _disparar_sincronizacion(empresa_id):
    ids_pendientes = getattr(_pendientes, 'ids_por_empresa', None)
    if not ids_pendientes or empresa_id not in ids_pendientes:
        return
    producto_ids = ids_pendientes.pop(empresa_id)
    if not producto_ids:
        return

    hilo = threading.Thread(
        target=_hilo_sincronizar_productos, args=(list(producto_ids), empresa_id), daemon=True
    )
    hilo.start()


def _hilo_sincronizar_productos(producto_ids, empresa_id):
    from clientes.models import Empresa
    from productos.models import Producto
    from pedidos_web import shopify_api

    try:
        empresa = Empresa.objects.filter(pk=empresa_id, usa_shopify=True).first()
        if not empresa:
            return  # esta empresa no usa Shopify, no hay nada que sincronizar

        location_id = shopify_api.obtener_location_id()
        if not location_id:
            return

        productos = list(
            Producto.objects.filter(pk__in=producto_ids, shopify_inventory_item_id__isnull=False)
        )
        if not productos:
            return  # ninguno de estos productos está subido a Shopify todavía

        exitosos, errores = shopify_api.sincronizar_inventario_lote(productos, location_id)
        logger.info(
            f"Sincronización en tiempo real con Shopify: {exitosos} variante(s) actualizadas, "
            f"{errores} con error (empresa {empresa_id})."
        )
    except Exception as e:
        logger.error(f"Error en sincronización en tiempo real con Shopify: {e}")


@receiver(post_save, sender=MovimientoInventario)
def sincronizar_shopify_en_tiempo_real(sender, instance, created, **kwargs):
    if not created:
        return
    _programar_sincronizacion(instance.producto)
