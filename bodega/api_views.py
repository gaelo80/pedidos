# bodega/api_views.py
import json
import logging
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from pedidos.models import Pedido, DetallePedido
from bodega.models import BorradorDespacho, DetalleBorradorDespacho, ComprobanteDespacho, DetalleComprobanteDespacho, MovimientoInventario
from factura.models import EstadoFacturaDespacho
from .api_serializers import PedidoBodegaListSerializer, PedidoBodegaDetalleSerializer, ComprobanteDespachoSerializer

logger = logging.getLogger(__name__)


class PedidoBodegaListAPIView(APIView):
    """
    GET /api/bodega/pedidos/ - Lista pedidos pendientes para bodega
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            empresa_actual = getattr(request, 'tenant', None)
            if not empresa_actual:
                return Response(
                    {'error': 'Empresa no identificada'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Estados que bodega puede ver por defecto
            estados_permitidos = ['APROBADO_ADMIN', 'PROCESANDO', 'LISTO_BODEGA_DIRECTO']

            # Parámetros opcionales
            estado = request.query_params.get('estado', None)
            cliente = request.query_params.get('cliente', None)
            referencia = request.query_params.get('referencia', None)

            pedidos = Pedido.objects.filter(
                empresa=empresa_actual,
                estado__in=estados_permitidos
            ).prefetch_related('detalles__producto').select_related('cliente', 'vendedor', 'cliente_online')

            # Filtros adicionales
            if estado and estado in [s[0] for s in Pedido.ESTADO_PEDIDO_CHOICES]:
                pedidos = pedidos.filter(estado=estado)

            if cliente:
                pedidos = pedidos.filter(
                    cliente__nombre_completo__icontains=cliente
                ) | pedidos.filter(
                    cliente_online__nombre__icontains=cliente
                )

            if referencia:
                pedidos = pedidos.filter(
                    detalles__producto__referencia__icontains=referencia
                ).distinct()

            serializer = PedidoBodegaListSerializer(pedidos, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error en PedidoBodegaListAPIView: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Error interno: {str(e)[:100]}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PedidoBodegaDetalleAPIView(APIView):
    """
    GET /api/bodega/pedidos/{pk}/ - Detalle de pedido con info de despacho
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        empresa_actual = getattr(request, 'tenant', None)
        if not empresa_actual:
            return Response(
                {'error': 'Empresa no identificada'},
                status=status.HTTP_400_BAD_REQUEST
            )

        pedido = get_object_or_404(
            Pedido.objects.prefetch_related('detalles__producto'),
            pk=pk,
            empresa=empresa_actual
        )

        serializer = PedidoBodegaDetalleSerializer(pedido)
        return Response(serializer.data)


class GuardarBorradorAPIView(APIView):
    """
    POST /api/bodega/pedidos/{pk}/guardar-borrador/
    Guarda cantidades escaneadas en BorradorDespacho (sin confirmar)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        empresa_actual = getattr(request, 'tenant', None)
        if not empresa_actual:
            return Response(
                {'error': 'Empresa no identificada'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            data = request.data
            detalles = data.get('detalles', [])

            if not detalles:
                return Response(
                    {'message': 'No se enviaron detalles'},
                    status=status.HTTP_200_OK
                )

            with transaction.atomic():
                pedido = get_object_or_404(Pedido, pk=pk, empresa=empresa_actual)

                # Obtener o crear borrador
                borrador, created = BorradorDespacho.objects.get_or_create(
                    pedido=pedido,
                    empresa=empresa_actual,
                    defaults={'usuario': request.user}
                )

                # Mapear detalles existentes
                detalles_pedido_map = {d.pk: d for d in pedido.detalles.select_for_update()}
                detalles_borrador_map = {
                    db.detalle_pedido_origen_id: db
                    for db in borrador.detalles_borrador.select_for_update()
                }

                cambios = 0
                for item_data in detalles:
                    detalle_id = item_data.get('id')
                    cantidad = item_data.get('cantidad')

                    if not detalle_id or cantidad is None:
                        continue

                    try:
                        cantidad = int(cantidad)
                        if cantidad < 0:
                            continue
                    except (ValueError, TypeError):
                        continue

                    detalle_original = detalles_pedido_map.get(detalle_id)
                    if not detalle_original:
                        continue

                    # Validar cantidad máxima
                    if cantidad > detalle_original.cantidad:
                        cantidad = detalle_original.cantidad

                    detalle_borrador = detalles_borrador_map.get(detalle_id)

                    if detalle_borrador:
                        if detalle_borrador.cantidad_escaneada_en_borrador != cantidad:
                            detalle_borrador.cantidad_escaneada_en_borrador = cantidad
                            detalle_borrador.save(update_fields=['cantidad_escaneada_en_borrador'])
                            cambios += 1
                    else:
                        DetalleBorradorDespacho.objects.create(
                            borrador_despacho=borrador,
                            detalle_pedido_origen=detalle_original,
                            producto=detalle_original.producto,
                            cantidad_escaneada_en_borrador=cantidad
                        )
                        cambios += 1

                # Actualizar estado a PROCESANDO
                if cambios > 0 and pedido.estado in ['APROBADO_ADMIN', 'PROCESANDO', 'PENDIENTE_BODEGA', 'LISTO_BODEGA_DIRECTO']:
                    pedido.estado = 'PROCESANDO'
                    pedido.save(update_fields=['estado'])

                return Response({
                    'status': 'success',
                    'message': f'{cambios} detalles guardados',
                    'cambios': cambios
                })

        except Exception as e:
            logger.error(f"Error en guardar-borrador para pedido {pk}: {e}", exc_info=True)
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class EnviarDespachoAPIView(APIView):
    """
    POST /api/bodega/pedidos/{pk}/enviar-despacho/
    Confirma despacho, crea comprobante, devuelve URL del comprobante PDF
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        empresa_actual = getattr(request, 'tenant', None)
        if not empresa_actual:
            return Response(
                {'error': 'Empresa no identificada'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                pedido = get_object_or_404(
                    Pedido.objects.select_for_update().prefetch_related('detalles'),
                    pk=pk,
                    empresa=empresa_actual
                )

                # Validar estado
                estados_permitidos = ['APROBADO_ADMIN', 'PROCESANDO', 'PENDIENTE_BODEGA', 'LISTO_BODEGA_DIRECTO']
                if pedido.estado not in estados_permitidos and not request.user.is_superuser:
                    return Response(
                        {'error': f'Pedido en estado {pedido.get_estado_display()} no puede ser despachado'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Obtener borrador
                borrador = BorradorDespacho.objects.filter(
                    pedido=pedido,
                    empresa=empresa_actual
                ).first()

                if not borrador or not borrador.detalles_borrador.exists():
                    return Response(
                        {'warning': 'No hay unidades escaneadas para enviar'},
                        status=status.HTTP_200_OK
                    )

                # Preparar items para comprobante
                items_para_comprobante = []
                detalles_actualizar = []

                for detalle_borrador in borrador.detalles_borrador.select_for_update():
                    detalle_original = detalle_borrador.detalle_pedido_origen
                    cantidad_nueva = detalle_borrador.cantidad_escaneada_en_borrador - (detalle_original.cantidad_verificada or 0)

                    if cantidad_nueva > 0:
                        items_para_comprobante.append({
                            'producto': detalle_original.producto,
                            'cantidad_despachada': cantidad_nueva,
                            'detalle_pedido_origen': detalle_original
                        })

                        detalle_original.cantidad_verificada = detalle_borrador.cantidad_escaneada_en_borrador
                        detalle_original.verificado_bodega = True
                        detalles_actualizar.append(detalle_original)

                if not items_para_comprobante:
                    return Response(
                        {'warning': 'No se detectaron nuevas unidades para despachar'},
                        status=status.HTTP_200_OK
                    )

                # Crear comprobante
                comprobante = ComprobanteDespacho.objects.create(
                    pedido=pedido,
                    empresa=empresa_actual,
                    fecha_hora_despacho=timezone.now(),
                    usuario_responsable=request.user,
                )

                # Crear detalles del comprobante
                detalles_comprobante = [
                    DetalleComprobanteDespacho(
                        comprobante_despacho=comprobante,
                        producto=item['producto'],
                        cantidad_despachada=item['cantidad_despachada'],
                        detalle_pedido_origen=item['detalle_pedido_origen']
                    ) for item in items_para_comprobante
                ]
                DetalleComprobanteDespacho.objects.bulk_create(detalles_comprobante)

                # Actualizar detalles del pedido
                if detalles_actualizar:
                    DetallePedido.objects.bulk_update(detalles_actualizar, ['cantidad_verificada', 'verificado_bodega'])

                # Eliminar borrador
                borrador.delete()

                # Actualizar estado del pedido
                pedido.refresh_from_db()
                todos_completos = all(
                    (d.cantidad_verificada or 0) >= d.cantidad for d in pedido.detalles.all()
                )

                comprobante.es_parcial = not todos_completos
                comprobante.save(update_fields=['es_parcial'])

                if todos_completos:
                    pedido.estado = 'ENVIADO'
                else:
                    pedido.estado = 'PROCESANDO'
                pedido.save(update_fields=['estado'])

                # Crear estado para facturación
                EstadoFacturaDespacho.objects.create(empresa=empresa_actual, despacho=comprobante)

                # Construir URL del comprobante (para abrir en navegador)
                comprobante_url = reverse('bodega:imprimir_comprobante_especifico', kwargs={'pk_comprobante': comprobante.pk})
                if not comprobante_url.startswith('http'):
                    # Construir URL completa si es relativa
                    comprobante_url = request.build_absolute_uri(comprobante_url)

                return Response({
                    'status': 'success',
                    'message': f'Comprobante #{comprobante.pk} generado',
                    'comprobante_id': comprobante.id,
                    'comprobante_url': comprobante_url,
                    'es_parcial': comprobante.es_parcial
                })

        except Exception as e:
            logger.error(f"Error en enviar-despacho para pedido {pk}: {e}", exc_info=True)
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class FinalizarIncompletoAPIView(APIView):
    """
    POST /api/bodega/pedidos/{pk}/finalizar-incompleto/
    Marca pedido como ENVIADO_INCOMPLETO, devuelve stock pendiente
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        empresa_actual = getattr(request, 'tenant', None)
        if not empresa_actual:
            return Response(
                {'error': 'Empresa no identificada'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                pedido = get_object_or_404(
                    Pedido.objects.select_for_update().prefetch_related('detalles'),
                    pk=pk,
                    empresa=empresa_actual
                )

                # Validar estado
                if pedido.estado in ['ENVIADO', 'ENTREGADO', 'CANCELADO']:
                    return Response(
                        {'warning': f'Pedido ya está en estado {pedido.get_estado_display()}'},
                        status=status.HTTP_200_OK
                    )

                # Eliminar borrador
                BorradorDespacho.objects.filter(pedido=pedido).delete()

                # Crear movimientos de devolución para stock pendiente
                for detalle in pedido.detalles.all():
                    cantidad_pendiente = detalle.cantidad - (detalle.cantidad_verificada or 0)
                    if cantidad_pendiente > 0:
                        MovimientoInventario.objects.get_or_create(
                            empresa=empresa_actual,
                            producto=detalle.producto,
                            tipo_movimiento='ENTRADA_CANCELACION',
                            documento_referencia=f"Devolución por Pedido Incompleto {pedido.pk}-{detalle.producto.id}",
                            defaults={
                                'cantidad': cantidad_pendiente,
                                'usuario': request.user,
                            }
                        )

                # Actualizar estado
                pedido.estado = 'ENVIADO_INCOMPLETO'
                pedido.save(update_fields=['estado'])

                return Response({
                    'status': 'success',
                    'message': 'Pedido marcado como ENVIADO_INCOMPLETO'
                })

        except Exception as e:
            logger.error(f"Error en finalizar-incompleto para pedido {pk}: {e}", exc_info=True)
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CancelarPedidoAPIView(APIView):
    """
    POST /api/bodega/pedidos/{pk}/cancelar/
    Cancela pedido, devuelve TODO el stock
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        empresa_actual = getattr(request, 'tenant', None)
        if not empresa_actual:
            return Response(
                {'error': 'Empresa no identificada'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                pedido = get_object_or_404(
                    Pedido.objects.select_for_update().prefetch_related('detalles'),
                    pk=pk,
                    empresa=empresa_actual
                )

                # Validar estado
                if pedido.estado in ['ENVIADO', 'ENTREGADO', 'CANCELADO']:
                    return Response(
                        {'warning': f'Pedido ya está en estado {pedido.get_estado_display()}'},
                        status=status.HTTP_200_OK
                    )

                # Eliminar borrador
                BorradorDespacho.objects.filter(pedido=pedido).delete()

                # Crear movimientos de devolución para TODO el stock
                for detalle in pedido.detalles.all():
                    MovimientoInventario.objects.get_or_create(
                        empresa=empresa_actual,
                        producto=detalle.producto,
                        tipo_movimiento='ENTRADA_CANCELACION',
                        documento_referencia=f"Devolución por Cancelación Pedido {pedido.pk}-{detalle.producto.id}",
                        defaults={
                            'cantidad': detalle.cantidad,
                            'usuario': request.user,
                        }
                    )
                    # Reset cantidad verificada
                    detalle.cantidad_verificada = 0
                    detalle.save(update_fields=['cantidad_verificada'])

                # Actualizar estado
                pedido.estado = 'CANCELADO'
                pedido.save(update_fields=['estado'])

                return Response({
                    'status': 'success',
                    'message': 'Pedido cancelado'
                })

        except Exception as e:
            logger.error(f"Error en cancelar para pedido {pk}: {e}", exc_info=True)
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
