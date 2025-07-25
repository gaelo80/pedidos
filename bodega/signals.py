from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction # Sigue siendo bueno para la atomicidad de la creación del movimiento
from .models import MovimientoInventario, DetalleIngresoBodega, ComprobanteDespacho
# La importación de Producto desde productos.models es correcta según tu archivo
from productos.models import Producto
from django.contrib.auth.models import Group
from notificaciones.models import Notificacion
from django.urls import reverse, NoReverseMatch
from django.contrib.auth import get_user_model
import logging



User = get_user_model()
logger = logging.getLogger(__name__)

@receiver(post_save, sender=DetalleIngresoBodega)
def crear_movimiento_para_ingreso_detalle(sender, instance, created, **kwargs):
    """
    Se activa después de guardar un DetalleIngresoBodega.
    Si es una nueva creación (created=True):
    1. Crea un movimiento de inventario de ENTRADA.
    El stock_actual del Producto se actualizará automáticamente porque
    es una @property que suma los movimientos.
    """
    print(f"DEBUG SEÑAL INGRESO DETALLE: Recibida para DetalleIngresoBodega #{instance.pk}. Creado: {created}")

    if created: 
        try:

            with transaction.atomic():
                
                doc_ref_movimiento = f'ING_DET_{instance.pk}'

                existe_movimiento_previo = MovimientoInventario.objects.filter(
                    empresa=instance.producto.empresa,
                    documento_referencia=doc_ref_movimiento,
                    producto=instance.producto,
                    tipo_movimiento='ENTRADA_COMPRA' # Asegúrate que este sea el tipo correcto
                ).exists()

                if not existe_movimiento_previo:
                    movimiento = MovimientoInventario.objects.create(
                        producto=instance.producto,
                        cantidad=instance.cantidad, # Cantidad positiva para un ingreso
                        tipo_movimiento='ENTRADA_COMPRA', # Ajusta si usas otro tipo para ingresos desde el admin
                        fecha_hora=instance.ingreso.fecha_hora, # Fecha/hora de la cabecera del ingreso
                        usuario=instance.ingreso.usuario, # Usuario que registró el ingreso
                        documento_referencia=doc_ref_movimiento,
                        notas=f"Entrada automática por Ingreso Bodega #{instance.ingreso.pk} (Detalle ID: {instance.pk}). Ref. Doc. Ingreso: {instance.ingreso.documento_referencia or '-'}"
                    )
                    print(f"DEBUG SEÑAL INGRESO DETALLE: Movimiento de inventario #{movimiento.pk} (ENTRADA_COMPRA) CREADO para DetalleIngresoBodega #{instance.pk}")
                else:
                    print(f"DEBUG SEÑAL INGRESO DETALLE: Movimiento de inventario para DetalleIngresoBodega #{instance.pk} (doc_ref: {doc_ref_movimiento}) YA EXISTÍA. No se creó uno nuevo.")


                producto_obj = instance.producto
                print(f"DEBUG SEÑAL INGRESO DETALLE: Producto afectado: '{producto_obj}'. Stock actual (calculado por @property): {producto_obj.stock_actual}")

        except Exception as e:
            print(f"ERROR CRÍTICO INESPERADO en señal 'crear_movimiento_para_ingreso_detalle' para DetalleIngresoBodega #{instance.pk}: {type(e).__name__} - {e}")
            import traceback
            traceback.print_exc()

    else:
        print(f"DEBUG SEÑAL INGRESO DETALLE: Ignorada para DetalleIngresoBodega #{instance.pk} (no fue una creación, created=False).")
        
        
@receiver(post_save, sender=ComprobanteDespacho)
def crear_notificacion_despacho_listo(sender, instance, created, **kwargs):
    """
    Crea una notificación cuando se CREA un nuevo Comprobante de Despacho.
    """
    # La señal ahora se dispara solo en la creación del comprobante (created=True)
    if not created:
        return

    grupo_destino = 'Factura'
    url_destino = None
    
    try:
        # El mensaje se genera siempre que se crea un comprobante
        mensaje = f"El despacho #{instance.id} para el cliente {instance.pedido.destinatario.nombre_completo} está listo para facturar."
        
        # Se intenta obtener la URL para la lista de despachos a facturar
        url_destino = reverse('factura:lista_despachos_a_facturar')
    except NoReverseMatch:
        logger.warning("No se encontró la URL 'factura:lista_despachos_a_facturar'.")
    except Exception as e:
        logger.error(f"Error al generar mensaje o URL para despacho #{instance.id}: {e}")
        return

    try:
        if not hasattr(instance, 'empresa'):
             logger.error(f"El ComprobanteDespacho #{instance.id} no tiene un campo 'empresa'. No se puede notificar.")
             return

        usuarios_a_notificar = User.objects.filter(
            groups__name=grupo_destino,
            empresa=instance.empresa,
            is_active=True
        )
        
        for usuario in usuarios_a_notificar:
            if not Notificacion.objects.filter(destinatario=usuario, mensaje=mensaje, leido=False).exists():
                Notificacion.objects.create(
                    destinatario=usuario,
                    mensaje=mensaje,
                    url=url_destino
                )
    except Group.DoesNotExist:
        logger.warning(f"El grupo '{grupo_destino}' no existe. No se pudo notificar.")
    except Exception as e:
        logger.error(f"Error creando notificación para despacho #{instance.id}: {e}")
        
@receiver(post_save, sender=MovimientoInventario)
def notificar_entrada_stock_a_vendedores(sender, instance, created, **kwargs):

    if created and instance.cantidad > 0:

        tipos_entrada_relevantes_para_vendedores = [
            'ENTRADA_COMPRA', 'ENTRADA_AJUSTE', 'ENTRADA_DEVOLUCION_CLIENTE',
            'ENTRADA_OTRO', 'ENTRADA_RECHAZO_CARTERA', 'ENTRADA_RECHAZO_ADMIN',
            'ENTRADA_DEV_MUESTRARIO', 'ENTRADA_DEV_EXHIBIDOR', 'ENTRADA_DEV_TRASLADO',
            'ENTRADA_DEV_PRESTAMO', 'ENTRADA_DEV_INTERNA_OTRA', 'ENTRADA_CAMBIO',
        ]

        if instance.tipo_movimiento in tipos_entrada_relevantes_para_vendedores:
            producto = instance.producto
            empresa = instance.empresa

            try:
                producto.refresh_from_db() 
            except Producto.DoesNotExist:
                logger.error(f"Error en señal notificar_entrada_stock_a_vendedores: Producto ID {instance.producto.pk} no encontrado.")
                return # No continuar si el producto no existe



            if producto.stock_actual > 0: # Solo si el stock está realmente disponible ahora
                mensaje_notificacion = (
                    f"¡Stock Disponible! La referencia '{producto.referencia} "
                    f"({producto.color} - Talla {producto.talla})' "
                    f"ha ingresado a bodega por '{instance.get_tipo_movimiento_display()}'. "
                    f"Stock actual: {producto.stock_actual} unidades."
                )
                
                url_producto = None
                try:
 
                    url_producto = reverse('productos:detalle_producto', args=[producto.pk]) 
                except NoReverseMatch:
                    logger.warning(f"No se encontró la URL 'productos:detalle_producto' para producto ID {producto.pk}.")
                    
                    
                vendedores_a_notificar = User.objects.filter(
                    perfil_vendedor__empresa=empresa,
                    is_active=True
                )
                with transaction.atomic(): # Asegurar que las notificaciones se creen juntas
                    for usuario_vendedor in vendedores_a_notificar:

                        if not Notificacion.objects.filter(destinatario=usuario_vendedor, mensaje=mensaje_notificacion, leido=False).exists():
                            Notificacion.objects.create(
                                destinatario=usuario_vendedor,
                                mensaje=mensaje_notificacion,
                                url=url_producto, # Opcional: URL para ir al detalle del producto
                                leido=False
                            )
                        else:
                            logger.debug(f"Notificación de stock para {producto.referencia} para {usuario_vendedor.username} ya existía o no se duplicó.")
            else:
                logger.debug(f"DEBUG: Stock de '{producto.referencia}' es 0 o negativo ({producto.stock_actual}). No se notifica a vendedores.")
    else:
        logger.debug(f"DEBUG: Movimiento Inventario #{instance.pk} ignorado (no es creación o no es entrada).")