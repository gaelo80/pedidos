# pedidos_online/views.py

from django.shortcuts import render, redirect, get_object_or_404, HttpResponse
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Sum, Max, F, ExpressionWrapper, DurationField, DecimalField, Case, When, Value, Min, fields
from django.db.models.functions import Coalesce
from django.utils import timezone
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import traceback
from django.template.loader import get_template
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Subquery, OuterRef
from django.contrib.auth.models import Group
import uuid
from datetime import datetime, timezone, timedelta
from core.utils import get_logo_base_64_despacho
from pedidos.models import Pedido, DetallePedido
from pedidos.utils import preparar_datos_seccion
from productos.models import Producto
from vendedores.models import Vendedor
from clientes.models import Cliente
from bodega.models import MovimientoInventario, ComprobanteDespacho, DetalleComprobanteDespacho, Bodega
from core.auth_utils import es_administracion, es_bodega, es_online, es_vendedor
from django.core.exceptions import ValidationError

# New app imports
from .models import ClienteOnline, PrecioEspecial
from .forms import PedidoOnlineForm, ClienteOnlineForm

logger = logging.getLogger(__name__)


def _stock_para_venta_online(producto, usuario):
    """
    Administración y Bodega ven el stock real total; un vendedor Online solo
    debe ver/reservar lo que está en bodegas habilitadas para el canal Online
    (o que tenga como excepción individual vía AccesoBodega).
    """
    if es_administracion(usuario) or es_bodega(usuario):
        return producto.stock_actual
    return producto.stock_disponible_para_canal('ONLINE', usuario=usuario)

@login_required
# El permiso debería ser para pedidos_online, o un permiso más genérico si aplica
@permission_required('pedidos.add_pedido', login_url='core:acceso_denegado')
def crear_pedido_online(request, pk=None):
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso inválido. No se pudo identificar la empresa.")
        return redirect('core:acceso_denegado')

    pedido_instance = None
    # ✅ CORREGIDO #1: Definir el título por defecto y actualizarlo después si es una edición
    titulo = "Crear nuevo pedido online"

    if pk:
        pedido_instance = get_object_or_404(
            Pedido, pk=pk, empresa=empresa_actual,
            estado='BORRADOR', tipo_pedido='ONLINE'
        )
        # ✅ CORREGIDO #1: El título ahora usa el número de pedido correcto
        titulo = f"Editar Borrador Online #{pedido_instance.numero_pedido_empresa}"

    if request.method == 'POST':
        form = PedidoOnlineForm(request.POST, request.FILES, instance=pedido_instance, empresa=empresa_actual)
        accion = request.POST.get('accion')

        # La lógica para recolectar detalles está bien, la mantenemos
        detalles_para_crear = []
        # ... (el bucle para parsear 'cantidad_' y 'precio_' se mantiene igual que en tu código) ...
        # (Este bloque no necesita cambios)
        for key, value in request.POST.items():
            if key.startswith('cantidad_') and value:
                try:
                    producto_id = int(key.split('_')[1])
                    cantidad_pedida = int(value)
                    precio_unitario_str = request.POST.get(f'precio_{producto_id}')
                    precio_unitario = Decimal(precio_unitario_str) if precio_unitario_str else Decimal('0.00')

                    if cantidad_pedida > 0:
                        producto_variante = Producto.objects.get(pk=producto_id, activo=True, empresa=empresa_actual)
                        detalles_para_crear.append({
                            'producto': producto_variante,
                            'cantidad': cantidad_pedida,
                            'precio_unitario': precio_unitario
                        })
                except (Producto.DoesNotExist, ValueError, TypeError, IndexError, InvalidOperation):
                    # Simplificamos el manejo de errores
                    messages.error(request, f"Se encontró un dato inválido en los productos del pedido. Por favor, verifica los detalles.")
                    # Redirigir o renderizar de nuevo es una opción aquí
                    # Por ahora, dejaremos que continúe al render final
                    pass

        if form.is_valid():
            try:
                with transaction.atomic():
                    pedido = form.save(commit=False)
                    pedido.empresa = empresa_actual
                    try:
                        pedido.vendedor = Vendedor.objects.get(user=request.user, user__empresa=empresa_actual)
                    except Vendedor.DoesNotExist:
                        messages.error(request, "No se encontró un perfil de vendedor para tu usuario.")
                        raise Exception("Vendedor no asignado.")

                    # Lógica para procesar las acciones
                    if accion == 'crear_definitivo':
                        # Validar stock
# Validar stock de forma inteligente
                        cantidades_originales = {}
                        if pedido_instance: # Si estamos editando un borrador existente
                            # Guardamos las cantidades que el borrador ya tenía reservadas
                            cantidades_originales = {d.producto_id: d.cantidad for d in pedido_instance.detalles.all()}

                        for detalle in detalles_para_crear:
                            producto = detalle['producto']
                            cantidad_solicitada = detalle['cantidad']

                            # Obtenemos la cantidad que este borrador ya tenía reservada para este producto
                            cantidad_ya_reservada = cantidades_originales.get(producto.id, 0)

                            # El stock real disponible para ESTE pedido es el stock actual + lo que ya habíamos reservado
                            stock_libre = _stock_para_venta_online(producto, request.user)
                            stock_disponible_para_este_pedido = stock_libre + cantidad_ya_reservada

                            if cantidad_solicitada > stock_disponible_para_este_pedido:
                                messages.error(
                                    request,
                                    f"Stock insuficiente para '{producto.referencia}'. "
                                    f"Solicitado: {cantidad_solicitada}, "
                                    f"Disponible en total: {stock_disponible_para_este_pedido} "
                                    f"(Stock libre: {stock_libre} + Reservado por este borrador: {cantidad_ya_reservada})"
                                )
                                raise ValidationError("Fallo de stock")

                        pedido.estado = 'LISTO_BODEGA_DIRECTO'

                    elif accion == 'guardar_borrador':
                        pedido.estado = 'BORRADOR'
                    
                    pedido.save() # Guardamos la cabecera del pedido

                    # ✅ CORREGIDO #4: Lógica de actualización de detalles más eficiente y segura
                    productos_enviados_ids = {d['producto'].id for d in detalles_para_crear}
                    
                    # Eliminar detalles que ya no están en el formulario
                    if pedido_instance:
                        pedido.detalles.exclude(producto_id__in=productos_enviados_ids).delete()

                    # Actualizar o crear los detalles enviados
                    for detalle_data in detalles_para_crear:
                        DetallePedido.objects.update_or_create(
                            pedido=pedido,
                            producto=detalle_data['producto'],
                            defaults={
                                'cantidad': detalle_data['cantidad'],
                                'precio_unitario': detalle_data['precio_unitario']
                            }
                        )

                    # ✅ CORRECCIÓN #2: RE-IMPLEMENTACIÓN DE LÓGICA DE INVENTARIO
                    # La señal post_save en Pedido no funciona para este caso,
                    # porque se ejecuta ANTES de que los DetallePedido se guarden.
                    # La lógica debe vivir aquí, después de guardar los detalles.

                    # FIX: Usar update_or_create() en lugar de delete() + get_or_create()
                    # para evitar race conditions cuando el usuario intenta guardar rápidamente.
                    # El documento_referencia es consistente, sin incluir el estado (Borrador/Definitivo).

                    doc_ref_base = f'Pedido #{pedido.numero_pedido_empresa} (Reserva Online)'

                    # Obtener los IDs de productos en el pedido actual
                    productos_actuales_ids = set(pedido.detalles.values_list('producto_id', flat=True))

                    # Eliminar movimientos de productos que ya NO están en el pedido
                    # (el usuario quitó esos ítems)
                    MovimientoInventario.objects.filter(
                        empresa=pedido.empresa,
                        tipo_movimiento='SALIDA_VENTA_PENDIENTE',
                        documento_referencia=doc_ref_base
                    ).exclude(
                        producto_id__in=productos_actuales_ids
                    ).delete()

                    # Crear o actualizar movimientos para todos los detalles actuales
                    bodega_principal = Bodega.objects.principal(pedido.empresa)
                    for detalle in pedido.detalles.all():
                        if detalle.cantidad > 0:
                            MovimientoInventario.objects.update_or_create(
                                empresa=pedido.empresa,
                                producto=detalle.producto,
                                tipo_movimiento='SALIDA_VENTA_PENDIENTE',
                                documento_referencia=doc_ref_base,
                                defaults={
                                    'cantidad': -detalle.cantidad,
                                    'usuario': pedido.vendedor.user if pedido.vendedor else None,
                                    'bodega': bodega_principal,
                                }
                            )
                    logger.info(f"Movimientos de inventario actualizados para Pedido #{pedido.numero_pedido_empresa}.")
                    
                    # --- FIN DE LA LÓGICA DE INVENTARIO ---

                    if accion == 'crear_definitivo':
                        # ✅ CORREGIDO #3: Mensaje de éxito correcto
                        messages.success(request, f'Pedido Online #{pedido.numero_pedido_empresa} creado y enviado a bodega.')
                        return redirect('pedidos:pedido_creado_exito', pk=pedido.pk)
                    
                    elif accion == 'guardar_borrador':
                       
                        # ✅ CORREGIDO #3: Mensaje de éxito correcto
                        messages.success(request, f"Borrador de Pedido Online #{pedido.numero_pedido_empresa} guardado.")
                        return redirect('pedidos_online:editar_pedido_online', pk=pedido.pk)

            except Exception as e:
                # Evita mostrar errores técnicos al usuario
                if not isinstance(e, ValidationError):
                    messages.error(request, f"Ocurrió un error inesperado al procesar el pedido: {e}")

    # --- Lógica de renderizado para GET o si POST falla ---
    # ✅ CORREGIDO #5: El contexto siempre se crea de forma consistente al final
    detalles_existentes_json = '[]'
    if pedido_instance:
        detalles_data = [{
            'producto_id': d.producto.id, 'ref': d.producto.referencia, 'nombre': d.producto.nombre,
            'color': d.producto.color.nombre if d.producto.color_id else '-', 'talla': d.producto.talla, 'cantidad': d.cantidad,
            'precio_unitario': float(d.precio_unitario)
        } for d in pedido_instance.detalles.select_related('producto', 'producto__color').all()]
        detalles_existentes_json = json.dumps(detalles_data)
    elif request.method == 'POST' and 'detalles_para_crear' in locals() and detalles_para_crear:
        # Caso POST FALLIDO en pedido NUEVO (p. ej. stock insuficiente):
        # reconstruimos los detalles desde lo que el usuario acababa de enviar,
        # para que el JavaScript vuelva a pintar la tabla y no se pierda el trabajo.
        detalles_data = [{
            'producto_id': d['producto'].id, 'ref': d['producto'].referencia, 'nombre': d['producto'].nombre,
            'color': d['producto'].color.nombre if d['producto'].color_id else '-', 'talla': d['producto'].talla, 'cantidad': d['cantidad'],
            'precio_unitario': float(d['precio_unitario'])
        } for d in detalles_para_crear]
        detalles_existentes_json = json.dumps(detalles_data)

    # Cliente y descuento seleccionados (para repintarlos tras un POST fallido)
    cliente_post_pk = ''
    cliente_post_text = ''
    descuento_post = ''
    if request.method == 'POST':
        cliente_post_pk = request.POST.get('cliente_online', '')
        descuento_post = request.POST.get('porcentaje_descuento', '')
        if cliente_post_pk:
            try:
                _cli = ClienteOnline.objects.get(pk=cliente_post_pk, empresa=empresa_actual)
                cliente_post_text = f"[Online] {_cli.nombre_completo} ({_cli.identificacion})"
            except (ClienteOnline.DoesNotExist, ValueError, TypeError):
                cliente_post_text = ''

    context = {
        'titulo': titulo, # La variable 'titulo' ya tiene el valor correcto
        'form': form if request.method == 'POST' else PedidoOnlineForm(instance=pedido_instance, empresa=empresa_actual),
        'cliente_form': ClienteOnlineForm(),
        'pedido_instance': pedido_instance,
        'detalles_existentes_json': detalles_existentes_json,
        'cliente_post_pk': cliente_post_pk,
        'cliente_post_text': cliente_post_text,
        'descuento_post': descuento_post,
        'IVA_RATE': Pedido.IVA_RATE
    }
    return render(request, 'pedidos_online/crear_pedido_online.html', context)


# --- NEW VIEW: List Online Draft Orders ---
@login_required
@permission_required('pedidos.view_pedido', login_url='core:acceso_denegado')
def lista_pedidos_borrador_online(request):
    """
    Lista los pedidos en estado de borrador del canal ONLINE,
    filtrando por la empresa actual y por el vendedor si corresponde.
    """
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:acceso_denegado')

    user = request.user
    search_query = request.GET.get('q', None)

    # Base queryset for online draft orders within the current company
    base_queryset = Pedido.objects.filter(
        empresa=empresa_actual,
        estado='BORRADOR',
        tipo_pedido='ONLINE' # Filter specifically for ONLINE orders
    )

    # --- INICIO DE LA CORRECCIÓN DE SEGURIDAD ---

    # Comprobamos si el usuario es Admin o Staff
    es_admin = user.is_staff or es_administracion(user)
    
    # Comprobamos si el usuario pertenece al grupo 'es_online'
    es_vendedor_online = es_online(user)

    # Aplicamos la lógica de filtrado
    if es_vendedor_online and not es_admin:
        # Si es un vendedor ONLINE y NO es admin, filtra solo por su usuario
        queryset = base_queryset.filter(vendedor__user=user)
        titulo = 'Mis Pedidos Borrador Online'
    elif es_admin:
        # Si es Admin, ve todos los borradores ONLINE de la empresa
        queryset = base_queryset
        titulo = 'Todos los Pedidos Borrador Online'
    else:
        # Si no es ni Admin ni Vendedor Online (ej. un vendedor estándar), no ve nada.
        queryset = base_queryset.none()
        titulo = 'Mis Pedidos Borrador Online'
        
    # --- FIN DE LA CORRECCIÓN DE SEGURIDAD ---

    if search_query:
        queryset = queryset.filter(
            Q(pk__icontains=search_query) |
            Q(cliente_online__nombre_completo__icontains=search_query) | # Search by online client name
            Q(cliente_online__identificacion__icontains=search_query) # Search by online client identification
        ).distinct()

    pedidos_list = queryset.select_related('cliente_online', 'vendedor__user').order_by('-fecha_hora')

    context = {
        'pedidos_list': pedidos_list,
        'titulo': titulo,
        'search_query': search_query
    }
    return render(request, 'pedidos_online/lista_pedidos_borrador_online.html', context)

# --- NEW API VIEW: Get Client Summary ---
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_get_cliente_summary(request, client_type, client_pk):
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        return Response({'error': 'Empresa no identificada'}, status=403)

    client_data = {}
    last_order_info = None
    order_history = []
    total_discounts_given = Decimal('0.00')

    try:
        if client_type == 'online':
            client_obj = get_object_or_404(ClienteOnline, pk=client_pk, empresa=empresa_actual)
            client_data = {
                'id': client_obj.pk,
                'type': 'Online',
                'nombre_completo': client_obj.nombre_completo,
                'identificacion': client_obj.identificacion,
                'telefono': client_obj.telefono,
                'email': client_obj.email,
                'direccion': client_obj.direccion,
                'tipo_cliente_display': client_obj.get_tipo_cliente_display(),
                'forma_pago_preferida_display': client_obj.get_forma_pago_preferida_display(),
                'fecha_creacion': client_obj.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
            }
            # Get orders for this online client
            orders = Pedido.objects.filter(
                cliente_online=client_obj, # Argumento posicional primero
                empresa=empresa_actual # Argumento de palabra clave después
            ).order_by('-fecha_hora').select_related('vendedor__user')

        elif client_type == 'estandar':
            client_obj = get_object_or_404(Cliente, pk=client_pk, empresa=empresa_actual)
            client_data = {
                'id': client_obj.pk,
                'type': 'Estándar',
                'nombre_completo': client_obj.nombre_completo,
                'identificacion': client_obj.identificacion,
                'telefono': client_obj.telefono,
                'email': client_obj.email,
                'direccion': client_obj.direccion,
                'tipo_cliente_display': client_obj.get_tipo_cliente_display() if hasattr(client_obj, 'get_tipo_cliente_display') else 'N/A',
                'forma_pago_preferida_display': client_obj.get_forma_pago_preferida_display() if hasattr(client_obj, 'get_forma_pago_preferida_display') else 'N/A',
                'fecha_creacion': client_obj.fecha_creacion.strftime('%d/%m/%Y %H:%M') if hasattr(client_obj, 'fecha_creacion') else 'N/A',
            }
            # Get orders for this standard client
            orders = Pedido.objects.filter(
                cliente=client_obj, # Argumento posicional primero
                empresa=empresa_actual # Argumento de palabra clave después
            ).order_by('-fecha_hora').select_related('vendedor__user')
        else:
            return Response({'error': 'Tipo de cliente no válido'}, status=400)

        # Process order history
        if orders.exists():
            # Last order info
            last_order = orders.first()
            last_order_info = {
                'id': last_order.pk,
                'fecha_hora': last_order.fecha_hora.strftime('%d/%m/%Y %H:%M'),
                'estado': last_order.get_estado_display(),
                'total_a_pagar': float(last_order.total_a_pagar),
                'vendedor': last_order.vendedor.user.get_full_name() if last_order.vendedor and last_order.vendedor.user else 'N/A',
            }

            # Detailed order history (e.g., last 5 orders)
            for order in orders[:5]: # Limit to last 5 orders for summary
                order_history.append({
                    'id': order.pk,
                    'fecha_hora': order.fecha_hora.strftime('%d/%m/%Y'),
                    'estado': order.get_estado_display(),
                    'total_a_pagar': float(order.total_a_pagar),
                    'descuento_aplicado': float(order.porcentaje_descuento),
                    'valor_descuento_total': float(order.valor_total_descuento),
                    'vendedor': order.vendedor.user.get_full_name() if order.vendedor and order.vendedor.user else 'N/A',
                })
                total_discounts_given += order.valor_total_descuento

        # Cartera (assuming you have a DocumentoCliente model for this)
        cartera_info = {
            'saldo_total': 0.0,
            'saldo_vencido': 0.0,
            'max_dias_mora': 0,
            'documentos': []
        }
        # This part requires your DocumentoCliente model and its relation to Cliente/ClienteOnline
        # Example (adjust according to your actual DocumentoCliente model):
        # from datetime import timedelta # Import timedelta
        # from django.db.models import F, ExpressionWrapper, DurationField # Import necessary for date calculations
        #
        # if hasattr(client_obj, 'documentos_cliente'): # Assuming a related_name 'documentos_cliente'
        #     # Use Coalesce to treat None as 0 in sums
        #     documentos_qs = client_obj.documentos_cliente.filter(empresa=empresa_actual) # Filter by company too
        #     cartera_info['saldo_total'] = float(documentos_qs.aggregate(total=Coalesce(Sum('saldo_pendiente'), Decimal('0.00')))['total'])
        #     cartera_info['saldo_vencido'] = float(documentos_qs.filter(
        #         fecha_vencimiento__lt=timezone.now()
        #     ).aggregate(vencido=Coalesce(Sum('saldo_pendiente'), Decimal('0.00')))['vencido'])
        #
        #     max_mora_doc = documentos_qs.filter(
        #         fecha_vencimiento__lt=timezone.now()
        #     ).annotate(
        #         dias_mora_calc=ExpressionWrapper(timezone.now() - F('fecha_vencimiento'), output_field=DurationField())
        #     ).aggregate(max_dias=Max('dias_mora_calc'))
        #
        #     cartera_info['max_dias_mora'] = max_mora_doc['max_dias'].days if max_mora_doc['max_dias'] else 0
        #
        #     for doc in documentos_qs[:5]: # Last 5 documents
        #         dias_mora = (timezone.now() - doc.fecha_vencimiento).days if doc.fecha_vencimiento < timezone.now() else 0
        #         cartera_info['documentos'].append({
        #             'tipo': doc.tipo_documento, 'numero': doc.numero_documento,
        #             'fecha_doc': doc.fecha_documento.strftime('%d/%m/%Y'),
        #             'fecha_ven': doc.fecha_vencimiento.strftime('%d/%m/%Y'),
        #             'saldo': float(doc.saldo_pendiente),
        #             'esta_vencido': doc.fecha_vencimiento < timezone.now(),
        #             'dias_mora': dias_mora,
        #             'vendedor': doc.vendedor.user.get_full_name() if doc.vendedor and doc.vendedor.user else 'N/A', # Assuming DocumentoCliente has a seller
        #         })

        # You might also have a 'descuentos' field on the client model directly
        # client_data['descuento_fijo'] = float(client_obj.descuento_fijo) if hasattr(client_obj, 'descuento_fijo') else 0.0

        summary_data = {
            'client_info': client_data,
            'last_order': last_order_info,
            'order_history': order_history,
            'total_discounts_given': float(total_discounts_given),
            'cartera_info': cartera_info, # Placeholder, implement if you have DocumentoCliente
            # Add more fields as needed, e.g., 'client_obj.credito_disponible'
        }

        return Response(summary_data)

    except ClienteOnline.DoesNotExist:
        return Response({'error': 'Cliente Online no encontrado'}, status=404)
    except Cliente.DoesNotExist:
        return Response({'error': 'Cliente Estándar no encontrado'}, status=404)
    except Exception as e:
        traceback.print_exc() # For debugging purposes: prints full traceback to server console
        return Response({'error': f'Error interno al obtener el resumen del cliente: {str(e)}'}, status=500)


# --- Existing API Views (no significant changes, just for context) ---

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_buscar_clientes_unificado(request):
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        return Response({'error': 'Company not identified'}, status=403)

    term = request.GET.get('term', '')
    results = []

    # Search in ClienteOnline
    clientes_online = ClienteOnline.objects.filter(
        Q(nombre_completo__icontains=term) | Q(identificacion__icontains=term), # Argumento posicional primero
        empresa=empresa_actual # Argumento de palabra clave después
    )[:10]
    for c in clientes_online:
        results.append({
            'id': f'online_{c.pk}',
            'text': f'[Online] {c.nombre_completo} ({c.identificacion})',
            'type': 'online',
            'data': {
                'tipo_cliente': c.tipo_cliente,
                'identificacion': c.identificacion,
                'telefono': c.telefono,
                'email': c.email,
                'direccion': c.direccion,
                'forma_pago_preferida': c.forma_pago_preferida,
            }
        })

    # Search in Cliente (standard)
    clientes_estandar = Cliente.objects.filter(
        Q(nombre_completo__icontains=term) | Q(identificacion__icontains=term), # Argumento posicional primero
        empresa=empresa_actual # Argumento de palabra clave después
    )[:10]
    for c in clientes_estandar:
        results.append({
            'id': f'std_{c.pk}',
            'text': f'[Standard] {c.nombre_completo} ({c.identificacion})',
            'type': 'estandar',
            'data': {
                'tipo_cliente': 'DETAL',
                'identificacion': c.identificacion,
                'telefono': c.telefono,
                'email': c.email,
                'direccion': c.direccion,
            }
        })

    return Response({'results': results})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_crear_cliente_online(request):
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        return Response({'success': False, 'error': 'Company not identified'}, status=403)

    form = ClienteOnlineForm(request.POST)
    if form.is_valid():
        try:
            cliente = form.save(commit=False)
            cliente.empresa = empresa_actual
            cliente.save()
            return Response({
                'success': True,
                'cliente': {
                    'id': f'online_{cliente.pk}',
                    'text': f'[Online] {cliente.nombre_completo} ({cliente.identificacion})',
                    'data': {
                        'tipo_cliente': cliente.tipo_cliente,
                        'identificacion': cliente.identificacion,
                        'telefono': cliente.telefono,
                        'email': cliente.email,
                        'direccion': cliente.direccion,
                        'forma_pago_preferida': cliente.forma_pago_preferida,
                    }
                }
            })
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=400)
    else:
        return Response({'success': False, 'errors': form.errors}, status=400)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_editar_cliente_online(request):
    """Actualiza los datos de un cliente online existente"""
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        return Response({'success': False, 'error': 'Company not identified'}, status=403)

    cliente_id = request.POST.get('cliente_id')
    if not cliente_id:
        return Response({'success': False, 'error': 'Cliente ID requerido'}, status=400)

    try:
        cliente = ClienteOnline.objects.get(pk=cliente_id, empresa=empresa_actual)

        # Actualizar solo los campos editables
        if request.POST.get('telefono') is not None:
            cliente.telefono = request.POST.get('telefono', '')
        if request.POST.get('email') is not None:
            cliente.email = request.POST.get('email', '')
        if request.POST.get('direccion') is not None:
            cliente.direccion = request.POST.get('direccion', '')

        cliente.save()

        return Response({
            'success': True,
            'message': 'Cliente actualizado exitosamente',
            'cliente': {
                'id': f'online_{cliente.pk}',
                'text': f'[Online] {cliente.nombre_completo} ({cliente.identificacion})',
                'data': {
                    'tipo_cliente': cliente.tipo_cliente,
                    'identificacion': cliente.identificacion,
                    'telefono': cliente.telefono,
                    'email': cliente.email,
                    'direccion': cliente.direccion,
                    'forma_pago_preferida': cliente.forma_pago_preferida,
                }
            }
        })
    except ClienteOnline.DoesNotExist:
        return Response({'success': False, 'error': 'Cliente no encontrado'}, status=404)
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_get_colores_for_referencia(request, ref):
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        return Response({'error': 'Company not identified'}, status=403)

    # Get unique colors for the reference and company
    colores = Producto.objects.filter(
        empresa=empresa_actual,
        referencia=ref,
        activo=True
    ).values_list('color__nombre', flat=True).distinct().order_by('color__nombre')

    results = []
    for color in colores:
        if color:
            results.append({'valor': color, 'display': color})
        else:
            results.append({'valor': '-', 'display': 'No Color'}) # For products without color

    return Response(results)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_get_tallas_for_color(request, ref, color_slug):
    empresa_actual = getattr(request, 'tenant', None)
    filtro_color = {'color__isnull': True} if color_slug == '-' else {'color__nombre': color_slug}

    variantes = Producto.objects.filter(
        empresa=empresa_actual,
        referencia=ref,
        activo=True,
        **filtro_color
    ).order_by('talla')

    if not variantes.exists():
        return Response({'error': 'No variants found for the specified reference and color'}, status=404)

    tipo_cliente_online = request.GET.get('tipo_cliente')
    variantes_data = []
    for variante in variantes:
        precio_final = variante.precio_venta # Default price

        # Apply special price if it exists and the client type matches
        if tipo_cliente_online:
            precio_esp = PrecioEspecial.objects.filter(
                producto=variante,
                tipo_cliente=tipo_cliente_online,
                # Consider adding date logic if your special prices have validity
            ).first()
            if precio_esp:
                precio_final = precio_esp.precio_especial

        variantes_data.append({
            'id': variante.id,
            'talla': variante.talla,
            'stock_actual': _stock_para_venta_online(variante, request.user),
            'precio_venta': float(precio_final)
        })
    return Response({'variantes': variantes_data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_get_cliente_estandar_data(request, cliente_id):
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        return Response({'error': 'Company not identified'}, status=403)

    cliente = get_object_or_404(Cliente, pk=cliente_id, empresa=empresa_actual)

    data = {
        'nombre_completo': cliente.nombre_completo,
        'identificacion': cliente.identificacion,
        'telefono': cliente.telefono,
        'email': cliente.email,
        'direccion': cliente.direccion,
        # You can add other fields if they are relevant for ClienteOnlineForm
    }
    return Response(data)


# --- NUEVA VISTA PARA REGISTRAR CAMBIOS ONLINE ---
@login_required
@permission_required('pedidos.add_pedido', login_url='core:acceso_denegado')
def registrar_cambio_online(request):
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso inválido. No se pudo identificar la empresa.")
        return redirect('core:acceso_denegado')

    if request.method == 'POST':
        try:
            # 1. Recibir y decodificar los datos del formulario
            cliente_online_id = request.POST.get('cliente_online_id')
            returned_products_data = json.loads(request.POST.get('returned_products_data', '[]'))
            new_products_data = json.loads(request.POST.get('new_products_data', '[]'))
            notas_cambio = request.POST.get('notas_cambio', '')

            # Validaciones básicas
            if not cliente_online_id:
                messages.error(request, "Se requiere un cliente para registrar el cambio.")
                return redirect('pedidos_online:registrar_cambio_online')

            if not returned_products_data and not new_products_data:
                messages.error(request, "Debe agregar al menos un producto devuelto o a enviar.")
                return redirect('pedidos_online:registrar_cambio_online')

            cliente = get_object_or_404(ClienteOnline, pk=cliente_online_id, empresa=empresa_actual)
            vendedor = get_object_or_404(Vendedor, user=request.user, user__empresa=empresa_actual)

            with transaction.atomic():
                # 2. Crear el pedido "contenedor" del cambio
                cambio_pedido = Pedido.objects.create(
                    empresa=empresa_actual,
                    cliente_online=cliente,
                    vendedor=vendedor,
                    tipo_pedido='ONLINE',
                    estado='CAMBIO_REGISTRADO',
                    notas=notas_cambio,
                    # Los cambios no suelen tener descuentos aplicados en la cabecera
                    porcentaje_descuento=Decimal('0.00')
                )

                # 3. Procesar productos DEVUELTOS (Entrada a bodega)
                for item in returned_products_data:
                    producto = get_object_or_404(Producto, pk=item.get('producto_id'), empresa=empresa_actual)
                    cantidad = int(item.get('cantidad', 0))
                    precio = Decimal(item.get('precio_unitario', '0.00'))

                    if cantidad > 0:
                        DetallePedido.objects.create(
                            pedido=cambio_pedido,
                            producto=producto,
                            cantidad=cantidad,
                            precio_unitario=precio,
                            tipo_detalle='DEVOLUCION'  # <-- USO DEL NUEVO CAMPO
                        )
                        MovimientoInventario.objects.get_or_create(
                            empresa=empresa_actual,
                            producto=producto,
                            bodega=Bodega.objects.principal(empresa_actual),
                            tipo_movimiento='ENTRADA_CAMBIO',
                            documento_referencia=f'Cambio Pedido #{cambio_pedido.numero_pedido_empresa} - {producto.referencia}',
                            defaults={
                                'cantidad': cantidad,
                                'usuario': request.user
                            }
                        )

                # 4. Procesar productos A ENVIAR (Salida de bodega)
                for item in new_products_data:
                    producto = get_object_or_404(Producto, pk=item.get('producto_id'), empresa=empresa_actual)
                    cantidad = int(item.get('cantidad', 0))
                    precio = Decimal(item.get('precio_unitario', '0.00'))

                    if cantidad > 0:
                        # Verificar stock antes de descontar
                        stock_disponible = _stock_para_venta_online(producto, request.user)
                        if cantidad > stock_disponible:
                            raise Exception(f"Stock insuficiente para '{producto.referencia}'. Solicitado: {cantidad}, Disponible: {stock_disponible}")

                        DetallePedido.objects.create(
                            pedido=cambio_pedido,
                            producto=producto,
                            cantidad=cantidad,
                            precio_unitario=precio,
                            tipo_detalle='ENVIO'  # <-- USO DEL NUEVO CAMPO
                        )
                        MovimientoInventario.objects.get_or_create(
                            empresa=empresa_actual,
                            producto=producto,
                            bodega=Bodega.objects.principal(empresa_actual),
                            tipo_movimiento='SALIDA_CAMBIO',
                            documento_referencia=f'Cambio Pedido #{cambio_pedido.numero_pedido_empresa} - {producto.referencia}',
                            defaults={
                                'cantidad': -cantidad,
                                'usuario': request.user
                            }
                        )
            
            messages.success(request, f"El cambio #{cambio_pedido.numero_pedido_empresa} ha sido registrado exitosamente.")
            # 5. Redirigir al comprobante
            return redirect('pedidos_online:comprobante_cambio_online', pk=cambio_pedido.pk)

        except Exception as e:
            messages.error(request, f"Ocurrió un error al registrar el cambio: {e}")
            return redirect('pedidos_online:registrar_cambio_online')

    # Si el método es GET, simplemente renderiza la página
    context = {
        'titulo': "Registrar Cambio de Producto Online",
        # ✅ CORREGIDO: Inicializamos las variables como un string de array JSON vacío
        'detalles_devueltos_json': '[]',
        'detalles_enviados_json': '[]',
    }
    return render(request, 'pedidos_online/crear_cambio_online.html', context)


# --- NUEVA API: Buscar Pedidos (para el selector en la vista de cambios) ---
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_buscar_pedidos(request):
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        return Response({'error': 'Empresa no identificada'}, status=403)

    term = request.GET.get('term', '')
    results = []

    # Search for ONLINE orders only
    pedidos = Pedido.objects.filter(
        empresa=empresa_actual,
        tipo_pedido='ONLINE'
    ).filter( # Encadenar filter para evitar el error de Pylance con Q objects
        Q(pk__icontains=term) |
        Q(cliente_online__nombre_completo__icontains=term) |
        Q(cliente_online__identificacion__icontains=term)
    ).select_related('cliente_online').order_by('-fecha_hora')[:10] # Limit results

    for p in pedidos:
        cliente_nombre = p.cliente_online.nombre_completo if p.cliente_online else "Cliente Desconocido"
        results.append({
            'id': p.pk,
            'text': f'Pedido #{p.pk} - {cliente_nombre} ({p.fecha_hora.strftime("%Y-%m-%d")})',
            'cliente_online_id': p.cliente_online.pk if p.cliente_online else None,
            'cliente_online_nombre': cliente_nombre,
            'cliente_online_identificacion': p.cliente_online.identificacion if p.cliente_online else None,
            'cliente_online_telefono': p.cliente_online.telefono if p.cliente_online else None,
            'cliente_online_email': p.cliente_online.email if p.cliente_online else None,
            'cliente_online_direccion': p.cliente_online.direccion if p.cliente_online else (p.cliente.direccion if p.cliente else None), # Corrected: Use p.cliente_online.direccion or p.cliente.direccion
        })

    return Response({'results': results})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_get_pedido_detalles(request, pedido_id):
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        return Response({'error': 'Empresa no identificada'}, status=403)

    try:
        pedido = Pedido.objects.get(pk=pedido_id, empresa=empresa_actual, tipo_pedido='ONLINE')
        detalles_data = []
        for detalle in pedido.detalles.select_related('producto', 'producto__color').all():
            detalles_data.append({
                'producto_id': detalle.producto.id,
                'referencia': detalle.producto.referencia,
                'color': detalle.producto.color.nombre if detalle.producto.color_id else '-',
                'talla': detalle.producto.talla,
                'cantidad': detalle.cantidad,
                'precio_unitario': float(detalle.precio_unitario)
            })
        return Response({'detalles': detalles_data})
    except Pedido.DoesNotExist:
        return Response({'error': 'Pedido no encontrado o no pertenece a su empresa'}, status=404)
    except Exception as e:
        traceback.print_exc()
        return Response({'error': f'Error interno al obtener los detalles del pedido: {str(e)}'}, status=500)


@login_required
@permission_required('pedidos.view_pedido', login_url='core:acceso_denegado') # O un permiso más específico si lo creas
def comprobante_cambio_online(request, pk):
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:acceso_denegado')

    # Obtener el pedido de cambio
    cambio_pedido = get_object_or_404(
        Pedido.objects.select_related('cliente_online', 'vendedor__user'),
        pk=pk,
        empresa=empresa_actual,
        estado='CAMBIO_REGISTRADO', # Asegurarse de que sea un pedido de cambio
        tipo_pedido='ONLINE'
    )

    # Filtrar los detalles entre devueltos y enviados
    productos_devueltos = []
    productos_enviados = []




    for detalle in cambio_pedido.detalles.select_related('producto').all():
        if detalle.tipo_detalle == 'DEVOLUCION': # CAMBIO: Usar el nuevo campo
            productos_devueltos.append({
                'referencia': detalle.producto.referencia,
                'nombre': detalle.producto.nombre, # Asegúrate de que tu Producto tenga un campo 'nombre'
                'color': detalle.producto.color or '-',
                'talla': detalle.producto.talla,
                'cantidad': detalle.cantidad, # Cantidad ya es positiva
                'precio_unitario': detalle.precio_unitario,
                'subtotal': detalle.cantidad * detalle.precio_unitario
            })
        elif detalle.tipo_detalle == 'ENVIO': # CAMBIO: Usar el nuevo campo
            productos_enviados.append({
                'referencia': detalle.producto.referencia,
                'nombre': detalle.producto.nombre, # Asegúrate de que tu Producto tenga un campo 'nombre'
                'color': detalle.producto.color or '-',
                'talla': detalle.producto.talla,
                'cantidad': detalle.cantidad,
                'precio_unitario': detalle.precio_unitario,
                'subtotal': detalle.cantidad * detalle.precio_unitario
            })
            
            
            
    
    # Calcular totales si es necesario (diferencia de precios)
    total_valor_devuelto = sum(item['subtotal'] for item in productos_devueltos)
    total_valor_enviado = sum(item['subtotal'] for item in productos_enviados)
    diferencia_valor = total_valor_enviado - total_valor_devuelto

    context = {
        'cambio_pedido': cambio_pedido,
        'productos_devueltos': productos_devueltos,
        'productos_enviados': productos_enviados,
        'total_valor_devuelto': total_valor_devuelto,
        'total_valor_enviado': total_valor_enviado,
        'diferencia_valor': diferencia_valor,
        'titulo': f'Comprobante de Cambio #{cambio_pedido.pk}',
    }
    return render(request, 'pedidos_online/comprobante_cambio_online.html', context)


@login_required
@permission_required('pedidos.view_pedido', login_url='core:acceso_denegado')
def generar_borrador_online_pdf(request, pk):
    """
    Genera un PDF para un pedido en estado BORRADOR (ONLINE) específico,
    asegurando que pertenezca al inquilino actual y que el usuario
    tenga permisos para verlo.
    """
    empresa_actual = getattr(request, 'tenant', None)

    # Lógica de acceso y filtrado del pedido borrador online
    query_params = {'pk': pk, 'estado': 'BORRADOR', 'tipo_pedido': 'ONLINE'}

    if not request.user.is_superuser:
        if not empresa_actual:
            messages.error(request, "Acceso no válido. Su usuario no está asociado a ninguna empresa.")
            return redirect('core:acceso_denegado')
        query_params['empresa'] = empresa_actual

    # Filtro adicional para vendedores (solo pueden ver sus borradores)
    if es_vendedor(request.user) and not (request.user.is_superuser or es_administracion(request.user)):
        try:
            # CORRECCIÓN: Filtrar Vendedor por user__empresa
            vendedor_obj = Vendedor.objects.get(user=request.user, user__empresa=empresa_actual)
            query_params['vendedor'] = vendedor_obj
        except Vendedor.DoesNotExist:
            messages.error(request, "Su perfil de vendedor no está asociado a esta empresa.")
            return redirect('core:acceso_denegado')

    # Obtener el pedido borrador online
    pedido = get_object_or_404(
        Pedido.objects.select_related('cliente_online', 'prospecto', 'vendedor__user', 'empresa'), 
        **query_params
    )

    # --- Obtener logo de la empresa ---
    logo_para_pdf = None
    try:
        logo_para_pdf = get_logo_base_64_despacho(empresa_actual)
    except Exception as e: 
        logger.warning(f"Advertencia PDF Borrador Online: Excepción al llamar get_logo_base_64_despacho(): {e}")

    # --- INICIO: LÓGICA DINÁMICA DE CATEGORÍAS Y TALLAS (PDF) ---
    # Esta lógica es idéntica a la de pedidos/views.py
    
    empresa_obj = pedido.empresa
    
    # 1. Cargar la configuración de categorías desde la BD.
    categorias_config = empresa_obj.categorias_tallas or {
        # Default por si la empresa no tiene nada configurado
        'DAMA': ['6', '8', '10', '12', '14', '16'],
        'CABALLERO': ['28', '30', '32', '34', '36', '38'],
        'NIÑO': ['4', '6', '8', '10', '12', '14', '16'],
        'NIÑA': ['4', '6', '8', '10', '12', '14', '16'],
        'UNISEX': ['S', 'M', 'L', 'XL']
    }
    
    # 2. Cargar el mapeo de tallas (Ej: {"6": "3"})
    TALLAS_MAPEO = empresa_obj.talla_mapeo or {}

    # 3. Agrupar detalles por su categoría (género)
    # Usamos defaultdict para crear listas vacías automáticamente
    from collections import defaultdict
    detalles_por_categoria = defaultdict(list)
    
    for detalle in pedido.detalles.select_related('producto').all():
        
        # --- INICIO: CORRECCIÓN DE TIPO DE DATO (Integer vs String) ---
        talla_normalizada = ""
        # 
        # ESTE ES EL IF IMPORTANTE
        #
        if hasattr(detalle.producto, 'talla') and detalle.producto.talla is not None:
            # Normalización robusta: str -> strip -> split on . -> take first part
            talla_normalizada = str(detalle.producto.talla).strip().split('.')[0].split(',')[0]

            # Aplicar el mapeo de tallas SI EXISTE (para Louis Ferry)
            if TALLAS_MAPEO and talla_normalizada in TALLAS_MAPEO:
                # Traduce la talla (ej: "6" -> "3")
                detalle.producto.talla = TALLAS_MAPEO[talla_normalizada]
            
            else:
                # NO hay mapeo (AMERICAN JEANS)
                # Asignamos la talla normalizada (ej: "16.0" -> "16")
                detalle.producto.talla = talla_normalizada
            # --- FIN: CORRECCIÓN ---
        
        # 
        # ESTAS LÍNEAS ESTÁN FUERA DEL IF (¡Correcto!)
        #
        # Asignar a la categoría correcta (ej: "DAMA", "NIÑO", etc.)
        categoria_producto = getattr(detalle.producto, 'genero', 'NIÑO').upper()
        detalles_por_categoria[categoria_producto].append(detalle) 
    
    # 4. Procesar cada sección definida en la configuración
    secciones_procesadas = []
    # Iteramos sobre la configuración de la empresa (ej: "DAMA", "NIÑO", etc.)
    for categoria, tallas_lista in categorias_config.items():
        # Solo procesamos la categoría si hay productos de ese tipo en el pedido
        if categoria in detalles_por_categoria:
            items_de_categoria = detalles_por_categoria[categoria]

            # --- INICIO DE LA CORRECCIÓN ---
            # Normalización robusta de la lista de columnas
            tallas_columnas_normalizadas_y_mapeadas = []
            for t in tallas_lista:
                # 1. Normalizar la columna (ej: 16.0 -> "16")
                col_normalizada = str(t).strip().split('.')[0].split(',')[0]
                # 2. Mapear la columna normalizada (ej: "6" -> "3")
                col_mapeada = TALLAS_MAPEO.get(col_normalizada, col_normalizada)
                tallas_columnas_normalizadas_y_mapeadas.append(col_mapeada)

            # Pasamos la lista de columnas YA NORMALIZADA Y MAPEADA a la utilidad
            grupos, tallas_cols = preparar_datos_seccion(items_de_categoria, tallas_columnas_normalizadas_y_mapeadas)
            # --- FIN DE LA CORRECCIÓN ---
            
            if grupos: # Solo añadir si hay productos
                secciones_procesadas.append({
                    'titulo': f"PEDIDO {categoria.replace('_', ' ')}",
                    'grupos': grupos,
                    'tallas_cols': tallas_cols
                })
    # --- FIN: LÓGICA DINÁMICA ---


    # --- INICIO: DICCIONARIO DE CONTEXTO CORREGIDO ---
    context = {
        'pedido': pedido,
        'empresa_actual': empresa_actual,
        'logo_base64': logo_para_pdf,
        'tasa_iva_pct': int(pedido.IVA_RATE * 100),
        'secciones_procesadas': secciones_procesadas,  # <-- ¡AQUÍ ESTÁ LA CORRECCIÓN!
        'incluir_color': True,
        'incluir_vr_unit': pedido.mostrar_precios_pdf, # <-- ¡AQUÍ ESTÁ LA OTRA CORRECCIÓN!
        'enlace_descarga_fotos_pdf': pedido.get_enlace_descarga_fotos(request),
    }
    # --- FIN: DICCIONARIO DE CONTEXTO CORREGIDO ---

    template = get_template('pedidos/pedido_pdf.html') # Reutilizamos la misma plantilla PDF
    html = template.render(context)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="pedido_borrador_online_{pedido.pk}.pdf"'

    # Uso de xhtml2pdf
    from xhtml2pdf import pisa
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        logger.error(f"Error al generar PDF de borrador ONLINE para pedido #{pedido.numero_pedido_empresa}: {pisa_status.err}")
        return HttpResponse('Ocurrió un error al generar el PDF.', status=500)
    return response

@login_required
def eliminar_borrador_online(request, pk):
    empresa_actual = getattr(request, 'tenant', None)
    
    borrador = get_object_or_404(
        Pedido, 
        pk=pk, 
        empresa=empresa_actual, 
        estado='BORRADOR', 
        tipo_pedido='ONLINE'
    )

    if request.method == 'POST':
        try:
            # Guardamos el número antes de que el objeto se elimine
            numero_borrador = borrador.numero_pedido_empresa
            
            # La única acción necesaria. La señal se encargará del stock.
            borrador.delete()
            
            messages.success(request, f"El borrador #{numero_borrador} ha sido eliminado y el stock liberado.")
        
        except Exception as e:
            messages.error(request, f"Ocurrió un error durante la eliminación: {e}")

        # Redirigir siempre fuera del bloque try/except
        return redirect('pedidos_online:lista_pedidos_borrador_online')

    # El contexto para la página de confirmación (GET request)
    context = {
        'borrador': borrador
    }
    return render(request, 'pedidos_online/borrador_confirm_delete.html', context)