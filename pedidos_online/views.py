# pedidos_online/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Sum, Max, F, ExpressionWrapper, DurationField
from django.db.models.functions import Coalesce
from django.utils import timezone
import json
from decimal import Decimal, InvalidOperation
import traceback

# Django Rest Framework imports
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

# Existing app imports
from pedidos.models import Pedido, DetallePedido
from productos.models import Producto
from vendedores.models import Vendedor
from clientes.models import Cliente
from bodega.models import MovimientoInventario
from core.auth_utils import es_admin_sistema, es_vendedor

# New app imports
from .models import ClienteOnline, PrecioEspecial
from .forms import PedidoOnlineForm, ClienteOnlineForm

# --- Existing views (keeping them for context, no changes needed here) ---

@login_required
@permission_required('pedidos.add_pedido', login_url='core:acceso_denegado')
def crear_pedido_online(request, pk=None):
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Invalid access. Company could not be identified.")
        return redirect('core:acceso_denied')

    pedido_instance = None
    if pk:
        # Ensure only online drafts belonging to the current company can be edited
        pedido_instance = get_object_or_404(
            Pedido, pk=pk, empresa=empresa_actual,
            estado='BORRADOR', tipo_pedido='ONLINE'
        )

    if request.method == 'POST':
        # --- KEY MODIFICATION: Pass request.FILES to the form ---
        form = PedidoOnlineForm(request.POST, request.FILES, instance=pedido_instance, empresa=empresa_actual)
        # --- END MODIFICATION ---
        accion = request.POST.get('accion')

        detalles_para_crear = []
        errores_stock = []
        errores_generales = []
        al_menos_un_detalle = False

        # Collect product and quantity details from hidden inputs
        for key, value in request.POST.items():
            if key.startswith('cantidad_') and value:
                try:
                    producto_id = int(key.split('_')[1])
                    cantidad_pedida = int(value)

                    # Retrieve unit price from the corresponding hidden input
                    precio_unitario_str = request.POST.get(f'precio_{producto_id}')
                    precio_unitario = Decimal(precio_unitario_str) if precio_unitario_str else Decimal('0.00')

                    if cantidad_pedida > 0:
                        al_menos_un_detalle = True
                        try:
                            # Ensure the product belongs to the current company
                            producto_variante = Producto.objects.get(pk=producto_id, activo=True, empresa=empresa_actual)
                            detalles_para_crear.append({
                                'producto': producto_variante,
                                'cantidad': cantidad_pedida,
                                'precio_unitario': precio_unitario,
                                'stock_disponible': producto_variante.stock_actual
                            })
                        except Producto.DoesNotExist:
                            errores_generales.append(f"Product ID {producto_id} not found, inactive, or does not belong to your company.")
                    elif cantidad_pedida < 0:
                        errores_generales.append(f"Negative quantity not allowed for product ID {producto_id}.")
                except (ValueError, TypeError, IndexError, InvalidOperation):
                    errores_generales.append(f"Invalid data in field '{key}' (value: '{value}').")

        if errores_generales:
            for error in errores_generales: messages.error(request, error)

        # Now, form.is_valid() will also execute the form's clean method,
        # which will assign online_client and order_type to the instance.
        if form.is_valid() and not errores_generales:
            try:
                with transaction.atomic():
                    pedido = form.save(commit=False) # online_client and order_type are already assigned here
                    pedido.empresa = empresa_actual

                    # Assign the current seller (the logged-in user creating the online order)
                    try:
                        # CORRECTED: Filter Vendedor by user__empresa
                        pedido.vendedor = Vendedor.objects.get(user=request.user, user__empresa=empresa_actual)
                    except Vendedor.DoesNotExist:
                        messages.error(request, "No seller profile found for your user in this company.")
                        raise Exception("Seller not assigned.")

                    if accion == 'crear_definitivo':
                        # Validate stock only if creating definitively
                        stock_suficiente_para_crear = True
                        if not al_menos_un_detalle:
                            messages.error(request, "You must add at least one product to create the definitive order.")
                            stock_suficiente_para_crear = False
                        else:
                            for detalle_data_check in detalles_para_crear:
                                if detalle_data_check['cantidad'] > detalle_data_check['producto'].stock_actual:
                                    stock_suficiente_para_crear = False
                                    errores_stock.append(f"Insufficient stock for '{detalle_data_check['producto'].referencia} ({detalle_data_check['producto'].talla})'. Ordered: {detalle_data_check['cantidad']}, Available: {detalle_data_check['producto'].stock_actual}")

                        if not stock_suficiente_para_crear:
                            for error in errores_stock: messages.error(request, error)
                            # If there are stock errors, we don't save and re-render the form
                            context = {
                                'titulo': f'Edit Online Draft #{pk}' if pk else 'Create Online Order',
                                'form': form,
                                'cliente_form': ClienteOnlineForm(),
                                'pedido_instance': pedido_instance,
                                'detalles_existentes_json': json.dumps([
                                    {
                                        'producto_id': d['producto'].id, 'ref': d['producto'].referencia,
                                        'nombre': d['producto'].nombre, 'color': d['producto'].color or '-',
                                        'talla': d.producto.talla, 'cantidad': d['cantidad'],
                                        'precio_unitario': float(d['precio_unitario'])
                                    } for d in detalles_para_crear
                                ]),
                                'IVA_RATE': Pedido.IVA_RATE
                            }
                            return render(request, 'pedidos_online/crear_pedido_online.html', context)


                        pedido.estado = 'LISTO_BODEGA_DIRECTO'
                        pedido.save() # Save the order with online_client and order_type assigned

                        # Delete existing details if it's an edit
                        if pedido_instance:
                            pedido_instance.detalles.all().delete()

                        productos_con_movimiento_ids = set()
                        for detalle_data in detalles_para_crear:
                            DetallePedido.objects.create(
                                pedido=pedido,
                                producto=detalle_data['producto'],
                                cantidad=detalle_data['cantidad'],
                                precio_unitario=detalle_data['precio_unitario']
                            )
                            # Register inventory movement only if not already done for this product
                            if detalle_data['producto'].id not in productos_con_movimiento_ids:
                                MovimientoInventario.objects.create(
                                    empresa=empresa_actual,
                                    producto=detalle_data['producto'],
                                    cantidad=-detalle_data['cantidad'],
                                    tipo_movimiento='SALIDA_VENTA_DIRECTA',
                                    documento_referencia=f'Online Order #{pedido.pk}',
                                    usuario=request.user,
                                    notas=f'Automatic exit for Online Order creation #{pedido.pk}'
                                )
                                productos_con_movimiento_ids.add(detalle_data['producto'].id)

                        messages.success(request, f"Online Order #{pedido.pk} created and sent to warehouse.")
                        return redirect('pedidos:pedido_creado_exito', pk=pedido.pk)

                    elif accion == 'guardar_borrador':
                        pedido.estado = 'BORRADOR'
                        pedido.save()

                        # Delete existing details if it's an edit
                        if pedido_instance:
                            pedido_instance.detalles.all().delete()

                        for detalle_data in detalles_para_crear:
                            DetallePedido.objects.create(
                                pedido=pedido,
                                producto=detalle_data['producto'],
                                cantidad=detalle_data['cantidad'],
                                precio_unitario=detalle_data['precio_unitario']
                            )
                        messages.success(request, f"Online Order Draft #{pedido.pk} saved.")
                        return redirect('pedidos_online:editar_pedido_online', pk=pedido.pk)

            except Exception as e:
                messages.error(request, f"Error processing the order: {e}")
        else:
            # If the form is not valid, form validation errors (including online_client)
            # will be automatically displayed in the template.
            messages.error(request, "Please correct the errors in the form.")

    # If the method is GET or if there were errors in POST and no redirect occurred
    # Prepare the form and context for rendering the page
    form = PedidoOnlineForm(instance=pedido_instance, empresa=empresa_actual)

    # Prepare existing details for JS if it's an existing pedido_instance
    detalles_existentes_json = '[]'
    if pedido_instance:
        detalles_data = []
        for d in pedido_instance.detalles.select_related('producto').all():
            detalles_data.append({
                'producto_id': d.producto.id,
                'ref': d.producto.referencia,
                'nombre': d.producto.nombre,
                'color': d.producto.color or '-',
                'talla': d.producto.talla,
                'cantidad': d.cantidad,
                'precio_unitario': float(d.precio_unitario)
            })
        detalles_existentes_json = json.dumps(detalles_data)

    context = {
        'titulo': f'Edit Online Draft #{pk}' if pk else 'Create Online Order',
        'form': form,
        'cliente_form': ClienteOnlineForm(),
        'pedido_instance': pedido_instance,
        'detalles_existentes_json': detalles_existentes_json,
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

    # Filter by seller if the user is a seller and not an admin/superuser
    if es_vendedor(user) and not (user.is_staff or es_admin_sistema(user)):
        queryset = base_queryset.filter(vendedor__user=user)
        titulo = 'Mis Pedidos Borrador Online'
    else:
        # Admins and superusers see all online draft orders for their company
        queryset = base_queryset
        titulo = 'Todos los Pedidos Borrador Online'

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

    form = PedidoOnlineForm(request.POST)
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
    ).values_list('color', flat=True).distinct().order_by('color')

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
    color_filter = None if color_slug == '-' else color_slug

    variantes = Producto.objects.filter(
        empresa=empresa_actual,
        referencia=ref,
        color=color_filter,
        activo=True
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
            'stock_actual': variante.stock_actual,
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


# --- NUEVAS VISTAS DE REPORTES PARA PEDIDOS ONLINE ---

@login_required
@permission_required('pedidos.view_pedido', login_url='core:acceso_denegado')
def reporte_ventas_vendedor_online(request):
    """
    Genera un informe de ventas por vendedor para pedidos ONLINE.
    Permite filtrar por rango de fechas y por vendedor (si el usuario es admin).
    """
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:acceso_denegado')

    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    vendedor_id_seleccionado = request.GET.get('vendedor_id')

    # Convertir fechas a objetos datetime
    fecha_inicio = None
    if fecha_inicio_str:
        try:
            fecha_inicio = timezone.datetime.strptime(fecha_inicio_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        except ValueError:
            messages.error(request, "Formato de fecha de inicio inválido.")

    fecha_fin = None
    if fecha_fin_str:
        try:
            # Add one day to include the entire end day
            fecha_fin = timezone.datetime.strptime(fecha_fin_str, '%Y-%m-%d').replace(tzinfo=timezone.utc) + timezone.timedelta(days=1)
        except ValueError:
            messages.error(request, "Formato de fecha de fin inválido.")

    # Base queryset for ONLINE orders
    pedidos_qs = Pedido.objects.filter(
        empresa=empresa_actual,
        tipo_pedido='ONLINE',
        estado__in=['LISTO_BODEGA_DIRECTO', 'DESPACHADO', 'ENTREGADO', 'FACTURADO'] # Consider only completed sales
    ).select_related('cliente_online', 'vendedor__user')

    # Apply date filters
    if fecha_inicio:
        pedidos_qs = pedidos_qs.filter(fecha_hora__gte=fecha_inicio)
    if fecha_fin:
        pedidos_qs = pedidos_qs.filter(fecha_hora__lt=fecha_fin)

    # Filter by seller based on user permissions
    user = request.user
    vendedores_list = Vendedor.objects.filter(user__empresa=empresa_actual).select_related('user').order_by('user__first_name')
    es_admin = es_admin_sistema(user) or user.is_superuser

    if es_admin:
        if vendedor_id_seleccionado:
            pedidos_qs = pedidos_qs.filter(vendedor__pk=vendedor_id_seleccionado)
        titulo = "Informe de Ventas Online por Vendedor"
    elif es_vendedor(user):
        pedidos_qs = pedidos_qs.filter(vendedor__user=user)
        titulo = f"Mis Ventas Online ({user.get_full_name()})"
    else:
        messages.warning(request, "No tiene permisos para ver este informe.")
        return redirect('core:acceso_denegado')

    # Annotate pedidos with total requested and dispatched units
    pedidos_list = pedidos_qs.annotate(
        unidades_solicitadas_en_pedido=Coalesce(Sum('detalles__cantidad'), 0),
        total_unidades_despachadas_pedido=Coalesce(Sum('detalles__cantidad_verificada'), 0)
    ).order_by('-fecha_hora')

    # Calculate totals for the selected seller (or all if admin and no specific seller selected)
    total_unidades_solicitadas_vendedor = pedidos_qs.aggregate(
        total=Coalesce(Sum('detalles__cantidad'), 0)
    )['total']
    valor_total_ventas_solicitadas_vendedor = pedidos_qs.aggregate(
        total=Coalesce(Sum(F('detalles__cantidad') * F('detalles__precio_unitario')), Decimal('0.00'))
    )['total']
    total_unidades_despachadas_vendedor = pedidos_qs.aggregate(
        total=Coalesce(Sum('detalles__cantidad_verificada'), 0)
    )['total']
    cantidad_pedidos_vendedor = pedidos_qs.count()

    porcentaje_despacho_vendedor = 0
    if total_unidades_solicitadas_vendedor > 0:
        porcentaje_despacho_vendedor = (total_unidades_despachadas_vendedor / total_unidades_solicitadas_vendedor) * 100

    context = {
        'titulo': titulo,
        'fecha_inicio': fecha_inicio_str,
        'fecha_fin': fecha_fin_str,
        'vendedores_list': vendedores_list if es_admin else [],
        'vendedor_id_seleccionado': int(vendedor_id_seleccionado) if vendedor_id_seleccionado else None,
        'es_admin_sistema': es_admin,
        'pedidos_list': pedidos_list,
        'total_unidades_solicitadas_vendedor': total_unidades_solicitadas_vendedor,
        'valor_total_ventas_solicitadas_vendedor': valor_total_ventas_solicitadas_vendedor,
        'total_unidades_despachadas_vendedor': total_unidades_despachadas_vendedor,
        'cantidad_pedidos_vendedor': cantidad_pedidos_vendedor,
        'porcentaje_despacho_vendedor': porcentaje_despacho_vendedor,
    }
    return render(request, 'pedidos_online/reporte_ventas_vendedor_online.html', context)


@login_required
@permission_required('pedidos.view_pedido', login_url='core:acceso_denegado')
def reporte_ventas_general_online(request):
    """
    Genera un informe general de ventas para pedidos ONLINE,
    resumiendo cantidades vendidas y despachadas por producto.
    """
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:acceso_denegado')

    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    vendedor_id_seleccionado = request.GET.get('vendedor_id') # Get selected seller ID

    fecha_inicio = None
    if fecha_inicio_str:
        try:
            fecha_inicio = timezone.datetime.strptime(fecha_inicio_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        except ValueError:
            messages.error(request, "Formato de fecha de inicio inválido.")

    fecha_fin = None
    if fecha_fin_str:
        try:
            fecha_fin = timezone.datetime.strptime(fecha_fin_str, '%Y-%m-%d').replace(tzinfo=timezone.utc) + timezone.timedelta(days=1)
        except ValueError:
            messages.error(request, "Formato de fecha de fin inválido.")

    # Base queryset for ONLINE orders
    pedidos_qs = Pedido.objects.filter(
        empresa=empresa_actual,
        tipo_pedido='ONLINE',
        estado__in=['LISTO_BODEGA_DIRECTO', 'DESPACHADO', 'ENTREGADO', 'FACTURADO'] # Only consider completed sales
    )

    if fecha_inicio:
        pedidos_qs = pedidos_qs.filter(fecha_hora__gte=fecha_inicio)
    if fecha_fin:
        pedidos_qs = pedidos_qs.filter(fecha_hora__lt=fecha_fin)

    # Filter by seller based on user permissions (similar to reporte_ventas_vendedor_online)
    user = request.user
    vendedores_list = Vendedor.objects.filter(user__empresa=empresa_actual).select_related('user').order_by('user__first_name')
    es_admin = es_admin_sistema(user) or user.is_superuser

    if es_admin:
        if vendedor_id_seleccionado:
            pedidos_qs = pedidos_qs.filter(vendedor__pk=vendedor_id_seleccionado)
    elif es_vendedor(user):
        pedidos_qs = pedidos_qs.filter(vendedor__user=user)
        # If a seller is logged in, they only see their own sales,
        # so the seller filter dropdown might not be necessary for them in the template.
        # However, we still pass vendedores_list for consistency if needed for other logic.


    # General totals for all online sales
    total_unidades_solicitadas_general = pedidos_qs.aggregate(
        total=Coalesce(Sum('detalles__cantidad'), 0)
    )['total']
    total_unidades_despachadas_general = pedidos_qs.aggregate(
        total=Coalesce(Sum('detalles__cantidad_verificada'), 0)
    )['total']
    cantidad_pedidos = pedidos_qs.count()

    # Sales by product
    ventas_por_producto = DetallePedido.objects.filter(
        pedido__in=pedidos_qs
    ).values(
        'producto__referencia',
        'producto__color',
        'producto__nombre'
    ).annotate(
        cantidad_total_vendida=Coalesce(Sum('cantidad'), 0)
    ).order_by('producto__referencia', 'producto__color')

    # Add a display name for the product
    for item in ventas_por_producto:
        item['nombre_producto_display'] = f"{item['producto__nombre']} ({item['producto__referencia']})"

    # Annotate pedidos_list for the table
    pedidos_list = pedidos_qs.select_related('cliente_online', 'vendedor__user').annotate(
        unidades_solicitadas_en_pedido=Coalesce(Sum('detalles__cantidad'), 0),
        total_unidades_despachadas_pedido=Coalesce(Sum('detalles__cantidad_verificada'), 0)
    ).order_by('-fecha_hora')

    context = {
        'titulo': "Informe General de Ventas Online",
        'fecha_inicio': fecha_inicio_str,
        'fecha_fin': fecha_fin_str,
        'vendedores_list': vendedores_list if es_admin else [],
        'vendedor_id_seleccionado': int(vendedor_id_seleccionado) if vendedor_id_seleccionado else None,
        'es_admin_sistema': es_admin,
        'total_unidades_solicitadas_general': total_unidades_solicitadas_general,
        'total_unidades_despachadas_general': total_unidades_despachadas_general,
        'cantidad_pedidos': cantidad_pedidos,
        'pedidos_list': pedidos_list,
        'ventas_por_producto': ventas_por_producto,
    }
    return render(request, 'pedidos_online/reporte_ventas_general_online.html', context)


# --- NUEVA VISTA PARA REGISTRAR CAMBIOS ONLINE ---
@login_required
@permission_required('pedidos.add_pedido', login_url='core:acceso_denegado') # Assuming 'add_pedido' permission covers this
def registrar_cambio_online(request, pedido_id=None):
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:acceso_denegado')

    original_pedido = None
    cliente_online_data = None
    detalles_devueltos_json = '[]' # Initialize for GET requests
    detalles_enviados_json = '[]' # Initialize for GET requests
    notas_cambio = '' # Initialize for GET requests
    cliente_online_id = '' # Initialize for GET requests

    if pedido_id:
        try:
            original_pedido = Pedido.objects.select_related('cliente_online').get(
                pk=pedido_id,
                empresa=empresa_actual,
                tipo_pedido='ONLINE'
            )
            cliente_online_data = {
                'id': original_pedido.cliente_online.pk,
                'nombre_completo': original_pedido.cliente_online.nombre_completo,
                'identificacion': original_pedido.cliente_online.identificacion,
                'telefono': original_pedido.cliente_online.telefono,
                'email': original_pedido.cliente_online.email,
                'direccion': original_pedido.cliente_online.direccion,
            }
            messages.info(request, f"Cargando cambio para el Pedido Online #{original_pedido.pk}.")

            returned_items_from_original = []
            for detalle in original_pedido.detalles.select_related('producto').all():
                returned_items_from_original.append({
                    'producto_id': detalle.producto.id,
                    'referencia': detalle.producto.referencia,
                    'color': detalle.producto.color or '-',
                    'talla': detalle.producto.talla,
                    'cantidad': detalle.cantidad,
                    'precio_unitario': float(detalle.precio_unitario)
                })
            detalles_devueltos_json = json.dumps(returned_items_from_original)

        except Pedido.DoesNotExist:
            messages.error(request, f"El Pedido Online #{pedido_id} no existe o no pertenece a su empresa.")
            return redirect('pedidos_online:registrar_cambio_online') # Redirect to empty form

    if request.method == 'POST':
        # Get data from POST request
        returned_products_json = request.POST.get('returned_products_data', '[]')
        returned_products_data = json.loads(returned_products_json)

        new_products_json = request.POST.get('new_products_data', '[]')
        new_products_data = json.loads(new_products_json)

        notas_cambio = request.POST.get('notas_cambio', '')
        cliente_online_id = request.POST.get('cliente_online_id')
        
        # Guardar el ID del pedido original si viene del formulario para re-renderizar
        original_pedido_pk_from_post = request.POST.get('original_pedido_pk') 
        if original_pedido_pk_from_post:
            try:
                original_pedido = Pedido.objects.select_related('cliente_online').get(
                    pk=int(original_pedido_pk_from_post),
                    empresa=empresa_actual,
                    tipo_pedido='ONLINE'
                )
                cliente_online_data = {
                    'id': original_pedido.cliente_online.pk,
                    'nombre_completo': original_pedido.cliente_online.nombre_completo,
                    'identificacion': original_pedido.cliente_online.identificacion,
                    'telefono': original_pedido.cliente_online.telefono,
                    'email': original_pedido.cliente_online.email,
                    'direccion': original_pedido.cliente_online.direccion,
                }
            except Pedido.DoesNotExist:
                original_pedido = None
                cliente_online_data = None # Clear data if original pedido is not found
            except ValueError:
                original_pedido = None
                cliente_online_data = None


        errores_generales = []
        if not cliente_online_id:
            errores_generales.append("Debe seleccionar un cliente online para registrar el cambio.")

        if not returned_products_data and not new_products_data:
            errores_generales.append("Debe especificar al menos un producto devuelto o un producto a enviar.")

        if errores_generales:
            for error in errores_generales:
                messages.error(request, error)
            # Re-render form with current data and messages
            context = {
                'titulo': 'Registrar Cambio de Producto Online',
                'original_pedido': original_pedido, # Usar el objeto ya cargado/manejado
                'cliente_online_data': cliente_online_data, # Usar el objeto ya cargado/manejado
                'detalles_devueltos_json': returned_products_json,
                'detalles_enviados_json': new_products_json,
                'notas_cambio': notas_cambio,
                'cliente_online_id': cliente_online_id,
            }
            return render(request, 'pedidos_online/crear_cambio_online.html', context)

        try:
            with transaction.atomic():
                vendedor = get_object_or_404(Vendedor, user=request.user, user__empresa=empresa_actual)
                cliente_online_obj = get_object_or_404(ClienteOnline, pk=int(cliente_online_id), empresa=empresa_actual)

                cambio_pedido = Pedido.objects.create(
                    empresa=empresa_actual,
                    vendedor=vendedor,
                    fecha_hora=timezone.now(),
                    estado='CAMBIO_REGISTRADO',
                    notas=f"Registro de cambio: {notas_cambio}",
                    tipo_pedido='ONLINE',
                    cliente_online=cliente_online_obj
                )

                # Process returned products (increase stock)
                for item in returned_products_data:
                    producto = get_object_or_404(Producto, pk=item['producto_id'], empresa=empresa_actual)
                    cantidad = item['cantidad']
                    if cantidad > 0:
                        MovimientoInventario.objects.create(
                            empresa=empresa_actual,
                            producto=producto,
                            cantidad=cantidad,
                            tipo_movimiento='ENTRADA_CAMBIO',
                            documento_referencia=f'Cambio Online #{cambio_pedido.pk}',
                            usuario=request.user,
                            notas=f'Entrada por cambio de cliente. Cambio #{cambio_pedido.pk}. Producto devuelto: {producto.referencia}'
                        )
                        DetallePedido.objects.create(
                            pedido=cambio_pedido,
                            producto=producto,
                            cantidad=cantidad,
                            precio_unitario=item['precio_unitario'],
                            tipo_detalle='DEVOLUCION'
                        )

                # Process new products to be sent (decrease stock)
                for item in new_products_data:
                    producto = get_object_or_404(Producto, pk=item['producto_id'], empresa=empresa_actual)
                    cantidad = item['cantidad']
                    if cantidad > 0:
                        if producto.stock_actual < cantidad:
                            raise ValueError(f"Stock insuficiente para el producto a enviar '{producto.referencia} ({producto.talla})'. Disponible: {producto.stock_actual}, Solicitado: {cantidad}")

                        MovimientoInventario.objects.create(
                            empresa=empresa_actual,
                            producto=producto,
                            cantidad=-cantidad,
                            tipo_movimiento='SALIDA_CAMBIO',
                            documento_referencia=f'Cambio Online #{cambio_pedido.pk}',
                            usuario=request.user,
                            notas=f'Salida por cambio de cliente. Cambio #{cambio_pedido.pk}. Producto enviado: {producto.referencia}'
                        )
                        DetallePedido.objects.create(
                            pedido=cambio_pedido,
                            producto=producto,
                            cantidad=cantidad,
                            precio_unitario=item['precio_unitario'],
                            tipo_detalle='ENVIO'
                        )
                
                messages.success(request, f"Cambio de producto registrado exitosamente con referencia #{cambio_pedido.pk}.")
                # CAMBIO CLAVE: Esta redirección solo se ejecuta si la transacción es exitosa
                return redirect('pedidos_online:comprobante_cambio_online', pk=cambio_pedido.pk)

        except Vendedor.DoesNotExist:
            messages.error(request, "No se encontró un perfil de vendedor para su usuario en esta empresa.")
        except ClienteOnline.DoesNotExist:
            messages.error(request, "El cliente online seleccionado no es válido o no existe.")
        except ValueError as ve:
            messages.error(request, f"Error de stock o validación: {ve}")
        except Exception as e:
            # Fallback for any other unexpected errors
            traceback.print_exc()
            messages.error(request, f"Ocurrió un error inesperado al registrar el cambio: {e}")

        # If any exception occurred, the flow reaches here.
        # Re-render the form with existing data (retrieved from POST or re-loaded for original_pedido if it was set)
        context = {
            'titulo': 'Registrar Cambio de Producto Online',
            'original_pedido': original_pedido, # Usar el objeto ya cargado/manejado
            'cliente_online_data': cliente_online_data, # Usar el objeto ya cargado/manejado
            'detalles_devueltos_json': returned_products_json,
            'detalles_enviados_json': new_products_json,
            'notas_cambio': notas_cambio,
            'cliente_online_id': cliente_online_id,
        }
        return render(request, 'pedidos_online/crear_cambio_online.html', context)

    # GET request logic
    context = {
        'titulo': 'Registrar Cambio de Producto Online',
        'original_pedido': original_pedido,
        'cliente_online_data': cliente_online_data,
        'detalles_devueltos_json': detalles_devueltos_json,
        'detalles_enviados_json': '[]', # Always empty for GET unless pre-filled for editing a change
        'notas_cambio': '',
        'cliente_online_id': original_pedido.cliente_online.pk if original_pedido and original_pedido.cliente_online else '',
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
        for detalle in pedido.detalles.select_related('producto').all():
            detalles_data.append({
                'producto_id': detalle.producto.id,
                'referencia': detalle.producto.referencia,
                'color': detalle.producto.color or '-',
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
