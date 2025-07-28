# informes/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test, permission_required
from django.db.models import Sum, Count, F, ExpressionWrapper, fields, DecimalField, Case, When, Value, Q, Min
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import timedelta, datetime as dt
from decimal import Decimal, ROUND_HALF_UP
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from core.auth_utils import es_administracion, es_bodega, es_vendedor, es_diseno, es_cartera, es_factura # Asegúrate de que todas estas funciones están disponibles
from bodega.models import IngresoBodega, ComprobanteDespacho, DetalleComprobanteDespacho # AÑADIDO DetalleComprobanteDespacho
from pedidos.models import Pedido, DetallePedido
from vendedores.models import Vendedor
from django.contrib.auth import get_user_model
from django.contrib import messages
from devoluciones.models import DevolucionCliente
from core.mixins import TenantAwareMixin # Asegúrate de que este mixin esté disponible
from django.core.exceptions import PermissionDenied
from django.db.models import Subquery, OuterRef # AÑADIDO para las subconsultas


ESTADOS_PEDIDO_REPORTEABLES = [
    'PENDIENTE_APROBACION_CARTERA',
    'PENDIENTE_APROBACION_ADMIN',
    'APROBADO_ADMIN',
    'PROCESANDO',
    'COMPLETADO',
    'ENVIADO',
    'ENTREGADO'
]

# Función auxiliar para parsear rango de fechas (asumo que está completa y funciona bien)
def _parse_date_range_from_request(request):
    current_tz = timezone.get_current_timezone()
    
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')

    # Valores por defecto: últimos 30 días
    fecha_fin_dt = timezone.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    fecha_inicio_dt = (timezone.now() - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)

    if fecha_inicio_str:
        try:
            fecha_inicio_dt_naive = dt.strptime(fecha_inicio_str, '%Y-%m-%d')
            fecha_inicio_dt = timezone.make_aware(fecha_inicio_dt_naive.replace(hour=0, minute=0, second=0, microsecond=0), current_tz)
        except ValueError:
            messages.error(request, "Formato de fecha de inicio inválido.")

    if fecha_fin_str:
        try:
            fecha_fin_dt_naive = dt.strptime(fecha_fin_str, '%Y-%m-%d')
            fecha_fin_dt = timezone.make_aware(fecha_fin_dt_naive.replace(hour=23, minute=59, second=59, microsecond=999999), current_tz)
        except ValueError:
            messages.error(request, "Formato de fecha de fin inválido.")
            
    return fecha_inicio_dt, fecha_fin_dt


@login_required
@permission_required('informes.view_reporte_ventas_general', login_url='core:acceso_denegado')
def reporte_ventas_general(request):
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')

    fecha_inicio_dt_aware, fecha_fin_dt_aware = _parse_date_range_from_request(request)
    
    # Subconsulta para sumar las cantidades REALMENTE despachadas (de los comprobantes) para cada pedido
    total_unidades_despachadas_subquery = Subquery(
        DetalleComprobanteDespacho.objects.filter(
            comprobante_despacho__pedido_id=OuterRef('pk') 
        )
        .values('comprobante_despacho__pedido_id') 
        .annotate(total_despachado=Coalesce(Sum('cantidad_despachada'), Value(0)))
        .values('total_despachado')[:1], 
        output_field=fields.IntegerField() 
    )

    pedidos_para_lista_general_qs = Pedido.objects.filter(
        empresa=empresa_actual,
        estado__in=ESTADOS_PEDIDO_REPORTEABLES,
        fecha_hora__range=(fecha_inicio_dt_aware, fecha_fin_dt_aware)
    ).select_related('cliente', 'vendedor__user').annotate(
        unidades_solicitadas_en_pedido=Coalesce(Sum('detalles__cantidad'), Value(0)),
        total_unidades_despachadas_en_pedido=Coalesce(total_unidades_despachadas_subquery, Value(0)) 
    )
    
    # === AÑADIR ESTE BLOQUE DE DEPURACIÓN ===
    print("\n--- DEBUG: Valores de Unidades Despachadas por Pedido (Informe General) ---")
    for pedido_debug in pedidos_para_lista_general_qs:
        print(f"Pedido #{pedido_debug.pk}:")
        print(f"  Unid. Solicitadas: {pedido_debug.unidades_solicitadas_en_pedido}")
        print(f"  Unid. Despachadas (anotado): {pedido_debug.total_unidades_despachadas_en_pedido}")
        # Verificación directa de comprobantes para el pedido
        comprobantes_directos = ComprobanteDespacho.objects.filter(pedido=pedido_debug).annotate(
            sum_comp_detalles=Coalesce(Sum('detalles__cantidad_despachada'), Value(0))
        )
        if comprobantes_directos.exists():
            total_sum_directa_comp = sum(c.sum_comp_detalles for c in comprobantes_directos)
            print(f"  Suma directa de comprobantes: {total_sum_directa_comp} (Comprobantes: {', '.join([str(c.pk) for c in comprobantes_directos])})")
        else:
            print("  No hay comprobantes de despacho para este pedido.")
    print("----------------------------------------------------------------------\n")
    # === FIN DEL BLOQUE DE DEPURACIÓN ===

    # Para los agregados generales (tarjetas de resumen), sumamos de los Pedidos ya anotados
    agregados_generales = pedidos_para_lista_general_qs.aggregate(
        total_unidades_solicitadas_general=Coalesce(Sum('unidades_solicitadas_en_pedido'), Value(0)),
        total_unidades_despachadas_general=Coalesce(Sum('total_unidades_despachadas_en_pedido'), Value(0))
    )
    
    total_unidades_solicitadas_general = agregados_generales['total_unidades_solicitadas_general']
    total_unidades_despachadas_general = agregados_generales['total_unidades_despachadas_general']
    
    porcentaje_despacho_general = Decimal('0.00')
    if total_unidades_solicitadas_general > 0:
        porcentaje_despacho_general = (Decimal(total_unidades_despachadas_general) / Decimal(total_unidades_solicitadas_general) * Decimal('100.00'))
        porcentaje_despacho_general = porcentaje_despacho_general.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    cantidad_pedidos_considerados_venta = pedidos_para_lista_general_qs.count()
    
    # Ventas por Producto
    ventas_por_producto = DetalleComprobanteDespacho.objects.filter(
        comprobante_despacho__pedido__in=pedidos_para_lista_general_qs.values('pk')
    ).values(
        'producto__referencia',  
        'producto__color'        
    ).annotate(
        cantidad_total_vendida=Coalesce(Sum('cantidad_despachada'), Value(0)),
        nombre_producto_display=Min('producto__nombre')
    ).order_by('producto__referencia', 'producto__color')
    
    context = {
        'titulo': f'Informe General de Ventas para {empresa_actual.nombre}',
        'pedidos_list': pedidos_para_lista_general_qs,
        'total_unidades_solicitadas_general': total_unidades_solicitadas_general,
        'total_unidades_despachadas_general': total_unidades_despachadas_general,
        'porcentaje_despacho_general': porcentaje_despacho_general,
        'cantidad_pedidos': cantidad_pedidos_considerados_venta,
        'ventas_por_producto': ventas_por_producto,
        'fecha_inicio': fecha_inicio_dt_aware.strftime('%Y-%m-%d'),
        'fecha_fin': fecha_fin_dt_aware.strftime('%Y-%m-%d'),
        'app_name': 'Informes'
    }
    return render(request, 'informes/reporte_ventas_general.html', context)


@login_required
@permission_required('informes.view_reporte_ventas_vendedor', login_url='core:acceso_denied')
def reporte_ventas_vendedor(request):
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')
    
    usuario_actual = request.user
    es_administracion_rol_actual = es_administracion(usuario_actual)
    es_vendedor_rol_actual = es_vendedor(usuario_actual)

    fecha_inicio_dt_aware, fecha_fin_dt_aware = _parse_date_range_from_request(request)

    # Queryset base para pedidos dentro del rango de fechas Y EMPRESA
    pedidos_base_qs = Pedido.objects.filter(
        empresa=empresa_actual,
        fecha_hora__range=(fecha_inicio_dt_aware, fecha_fin_dt_aware)
    )

    vendedores_list_for_dropdown = None
    vendedor_objeto_contexto = None   
    pedidos_filtrados_final_qs = Pedido.objects.none() # Empezar con queryset vacío para el filtro de vendedor

    # Lógica de filtro por vendedor
    if es_administracion_rol_actual:
        vendedores_list_for_dropdown = Vendedor.objects.filter(
            empresa=empresa_actual, 
            activo=True
        ).select_related('user').order_by('user__first_name', 'user__last_name')
        
        vendedor_seleccionado_id_str = request.GET.get('vendedor_id')
        if vendedor_seleccionado_id_str:
            try:
                vendedor_id_int = int(vendedor_seleccionado_id_str)
                # Aplicar el filtro de vendedor aquí mismo para que pedidos_filtrados_final_qs contenga solo los pedidos relevantes
                pedidos_filtrados_final_qs = pedidos_base_qs.filter(vendedor_id=vendedor_id_int)
                vendedor_objeto_contexto = Vendedor.objects.get(pk=vendedor_id_int, empresa=empresa_actual)
            except (ValueError, Vendedor.DoesNotExist):
                messages.error(request, "El vendedor seleccionado no es válido o no pertenece a esta empresa.")
                return redirect(f"{request.path}?fecha_inicio={fecha_inicio_dt_aware.strftime('%Y-%m-%d')}&fecha_fin={fecha_fin_dt_aware.strftime('%Y-%m-%d')}")
        else:
            # Si es admin y NO selecciona vendedor, mostrar TODOS los pedidos de la empresa en el rango de fechas
            pedidos_filtrados_final_qs = pedidos_base_qs 
            
    elif es_vendedor_rol_actual:
        try:
            vendedor_objeto_contexto = Vendedor.objects.get(user=usuario_actual)
            if vendedor_objeto_contexto.user.empresa != empresa_actual:
                raise PermissionDenied("Este vendedor no pertenece a tu empresa.")
            # Aplicar filtro de vendedor para el vendedor logueado
            pedidos_filtrados_final_qs = pedidos_base_qs.filter(vendedor=vendedor_objeto_contexto)
        except Vendedor.DoesNotExist:
            messages.error(request, "No se encontró un perfil de vendedor activo para su cuenta en esta empresa.")
            return redirect(f"{request.path}?fecha_inicio={fecha_inicio_dt_aware.strftime('%Y-%m-%d')}&fecha_fin={fecha_fin_dt_aware.strftime('%Y-%m-%d')}")
        except PermissionDenied as e:
            messages.error(request, str(e))
            return redirect('core:acceso_denegado')

    # Subconsulta para sumar las cantidades REALMENTE despachadas para cada pedido
    # Se asegura que la subconsulta también filtre por el pedido principal
    total_unidades_despachadas_subquery = Subquery(
        DetalleComprobanteDespacho.objects.filter(
            comprobante_despacho__pedido_id=OuterRef('pk'), # Filtra por el PK del pedido principal
            # Opcional: Si quieres que las unidades despachadas solo cuenten si el comprobante
            # fue generado dentro del rango de fechas del informe.
            # comprobante_despacho__fecha_hora_despacho__range=(fecha_inicio_dt_aware, fecha_fin_dt_aware) 
        )
        .values('comprobante_despacho__pedido_id') # Agrupa por el ID del pedido del comprobante
        .annotate(total_desp=Coalesce(Sum('cantidad_despachada'), Value(0)))
        .values('total_desp')[:1],
        output_field=fields.IntegerField()
    )

    # Filtrar por estados de venta solicitada y anotar
    # pedidos_para_lista_y_agregados contendrá solo los pedidos que cumplen todos los filtros (empresa, fecha, vendedor)
    pedidos_para_lista_y_agregados = pedidos_filtrados_final_qs.filter(
        estado__in=ESTADOS_PEDIDO_REPORTEABLES
    ).select_related('cliente', 'vendedor__user').annotate(
        unidades_solicitadas_en_pedido=Coalesce(Sum('detalles__cantidad'), Value(0)),
        # La subconsulta ya está relacionada con el pedido a través de OuterRef('pk')
        total_unidades_despachadas_pedido=Coalesce(total_unidades_despachadas_subquery, Value(0)) 
    )

    # Calcular agregados solicitados
    agregados_solicitados_vendedor = DetallePedido.objects.filter(
        pedido__in=pedidos_para_lista_y_agregados # Asegura que solo se consideran los pedidos ya filtrados
    ).aggregate(
        total_unidades=Coalesce(Sum('cantidad'), Value(0)),
        valor_total=Coalesce(Sum(F('cantidad') * F('precio_unitario'), output_field=DecimalField()), Value(Decimal('0.00')))
    )
    total_unidades_solicitadas_vendedor = agregados_solicitados_vendedor['total_unidades']
    valor_total_ventas_solicitadas_vendedor = agregados_solicitados_vendedor['valor_total']

    # Agregados de unidades despachadas basados en DetalleComprobanteDespacho
    # Aquí sumamos las unidades despachadas SÓLO para los pedidos que YA ESTÁN en pedidos_para_lista_y_agregados
    agregados_despachados_vendedor = DetalleComprobanteDespacho.objects.filter(
        comprobante_despacho__pedido__in=pedidos_para_lista_y_agregados.values('pk') # Filtra por los IDs de los pedidos válidos
    ).aggregate(
        total_unidades=Coalesce(Sum('cantidad_despachada'), Value(0))
    )
    total_unidades_despachadas_vendedor = agregados_despachados_vendedor['total_unidades']

    porcentaje_despacho_vendedor = Decimal('0.00')
    if total_unidades_solicitadas_vendedor > 0:
        porcentaje_despacho_vendedor = (Decimal(total_unidades_despachadas_vendedor) / Decimal(total_unidades_solicitadas_vendedor) * Decimal('100.00'))
        porcentaje_despacho_vendedor = porcentaje_despacho_vendedor.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    cantidad_pedidos_del_vendedor = pedidos_para_lista_y_agregados.count()

    # Lógica para el título del informe
    titulo_informe = "Informe de Ventas"
    vendedor_seleccionado_id_str = request.GET.get('vendedor_id') 
    if es_administracion_rol_actual:
        if vendedor_objeto_contexto:
            titulo_informe = f"Unidades Vendidas de: {vendedor_objeto_contexto.user.get_full_name() or vendedor_objeto_contexto.user.username}"
        elif vendedor_seleccionado_id_str:
            titulo_informe = f"Informe para Vendedor ID: {vendedor_seleccionado_id_str} (No encontrado)"
        else:
            titulo_informe = "Informe General por Vendedor" # Título por defecto si admin no selecciona
    elif vendedor_objeto_contexto:
         titulo_informe = f"Mis Unidades Vendidas ({vendedor_objeto_contexto.user.get_full_name() or vendedor_objeto_contexto.user.username})"
    else: # Si no es admin y no es vendedor logueado o no se encontró perfil
        titulo_informe = "Informe de Ventas por Vendedor (Acceso Restringido)"

    context = {
        'titulo': titulo_informe,
        'pedidos_list': pedidos_para_lista_y_agregados, # Contiene los pedidos con sus unidades despachadas anotadas
        'total_unidades_solicitadas_vendedor': total_unidades_solicitadas_vendedor,
        'valor_total_ventas_solicitadas_vendedor': valor_total_ventas_solicitadas_vendedor,
        'total_unidades_despachadas_vendedor': total_unidades_despachadas_vendedor,
        'porcentaje_despacho_vendedor': porcentaje_despacho_vendedor,
        'cantidad_pedidos_vendedor': cantidad_pedidos_del_vendedor,
        'fecha_inicio': fecha_inicio_dt_aware.strftime('%Y-%m-%d'),
        'fecha_fin': fecha_fin_dt_aware.strftime('%Y-%m-%d'),
        'vendedores_list': vendedores_list_for_dropdown, 
        'vendedor_id_seleccionado': int(vendedor_seleccionado_id_str) if vendedor_seleccionado_id_str and vendedor_seleccionado_id_str.isdigit() else None,
        'es_administracion': es_administracion_rol_actual, 
        'app_name': 'Informes'
    }
    return render(request, 'informes/reporte_ventas_vendedor.html', context)


@login_required
@user_passes_test(lambda u: es_vendedor(u) or es_administracion(u))
def reporte_cumplimiento_despachos(request):
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')
    
    fecha_inicio_dt, fecha_fin_dt = _parse_date_range_from_request(request) # Usar la función auxiliar

    vendedor_filtro_id = request.GET.get('vendedor_id')

    # Consulta base para pedidos
    pedidos_qs = Pedido.objects.filter(
        empresa=empresa_actual,
        fecha_hora__range=(fecha_inicio_dt, fecha_fin_dt)
    )

    # Subconsulta para sumar las cantidades REALMENTE despachadas para cada pedido
    total_unidades_despachadas_subquery = Subquery(
        DetalleComprobanteDespacho.objects.filter(
            comprobante_despacho__pedido=OuterRef('pk')
        ).values('comprobante_despacho__pedido')
        .annotate(total_desp=Coalesce(Sum('cantidad_despachada'), Value(0)))
        .values('total_desp')[:1],
        output_field=fields.IntegerField()
    )

    pedidos_qs = pedidos_qs.annotate(
        total_unidades_solicitadas=Coalesce(Sum('detalles__cantidad'), 0),
        # Usamos la subconsulta para las unidades REALMENTE despachadas
        total_unidades_despachadas=Coalesce(total_unidades_despachadas_subquery, 0)
    ).annotate(
        porcentaje_cumplimiento=Case(
            When(total_unidades_solicitadas__gt=0,
                 then=ExpressionWrapper(
                    (F('total_unidades_despachadas') * 100.0 / F('total_unidades_solicitadas')),
                    output_field=DecimalField(max_digits=5, decimal_places=2)
                 )
            ),
            default=Value(Decimal('0.00')),
            output_field=DecimalField(max_digits=5, decimal_places=2)
        )
    ).select_related('cliente', 'vendedor__user').order_by('-fecha_hora')

    usuario_actual = request.user
    es_administracion_actual = es_administracion(usuario_actual)
    vendedores_list = None

    if es_administracion_actual:
        vendedores_list = Vendedor.objects.filter(
            empresa=empresa_actual, 
            activo=True
        ).select_related('user').order_by('user__first_name', 'user__last_name')
        
    if vendedor_filtro_id:
        try:
            vendedor_obj = Vendedor.objects.get(pk=vendedor_filtro_id, empresa=empresa_actual)
            pedidos_qs = pedidos_qs.filter(vendedor=vendedor_obj)
        except (ValueError, Vendedor.DoesNotExist):
            messages.error(request, "El vendedor seleccionado no es válido o no pertenece a esta empresa.")
            pedidos_qs = Pedido.objects.none()           
            
    elif es_vendedor(usuario_actual):
        try:
            vendedor_actual = Vendedor.objects.get(user=usuario_actual, empresa=empresa_actual)
            pedidos_qs = pedidos_qs.filter(vendedor=vendedor_actual)
        except Vendedor.DoesNotExist:
            pedidos_qs = Pedido.objects.none()
    else:
        pedidos_qs = Pedido.objects.none()

    agregados_generales = pedidos_qs.aggregate(
        sum_solicitado=Sum('total_unidades_solicitadas'),
        sum_despachado=Sum('total_unidades_despachadas')
    )
    sum_solicitado_general = agregados_generales['sum_solicitado'] or 0
    sum_despachado_general = agregados_generales['sum_despachado'] or 0

    porcentaje_cumplimiento_general = Decimal('0.00')
    if sum_solicitado_general > 0:
        porcentaje_cumplimiento_general = (Decimal(sum_despachado_general) * Decimal('100.0')) / Decimal(sum_solicitado_general)
        porcentaje_cumplimiento_general = porcentaje_cumplimiento_general.quantize(Decimal('0.01'))


    context = {
        'titulo': f'Cumplimiento de Despachos para {empresa_actual.nombre}',
        'pedidos_list': pedidos_qs,
        'fecha_inicio': fecha_inicio_dt.strftime('%Y-%m-%d'),
        'fecha_fin': fecha_fin_dt.strftime('%Y-%m-%d'),
        'vendedores_list': vendedores_list,
        'vendedor_seleccionado_id': int(vendedor_filtro_id) if vendedor_filtro_id else None,
        'es_administracion': es_administracion_actual,
        'sum_solicitado_general': sum_solicitado_general,
        'sum_despachado_general': sum_despachado_general,
        'porcentaje_cumplimiento_general': porcentaje_cumplimiento_general,
        'app_name': 'Informes'
    }
    return render(request, 'informes/reporte_cumplimiento_despachos.html', context)



#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


@login_required
@permission_required('informes.view_pedidos_rechazados', login_url='core:acceso_denegado')
def informe_pedidos_rechazados(request):
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')
    
    pedidos_rechazados_list = Pedido.objects.filter(        
        Q(estado='RECHAZADO_CARTERA') | Q(estado='RECHAZADO_ADMIN'),
        empresa=empresa_actual
    ).select_related(
        'cliente',
        'vendedor__user',
        'usuario_decision_cartera',
        'usuario_decision_admin'
    ).order_by('-fecha_hora')


    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    current_tz = timezone.get_current_timezone()

    q_date_filter = Q()

    if fecha_inicio_str:
        try:
            fecha_inicio_dt_naive = dt.strptime(fecha_inicio_str, '%Y-%m-%d')
            fecha_inicio_dt_aware = timezone.make_aware(fecha_inicio_dt_naive.replace(hour=0, minute=0, second=0, microsecond=0), current_tz)
            q_date_filter &= (Q(fecha_decision_cartera__gte=fecha_inicio_dt_aware) | Q(fecha_decision_admin__gte=fecha_inicio_dt_aware))
        except ValueError:
            pass

    if fecha_fin_str:
        try:
            fecha_fin_dt_naive = dt.strptime(fecha_fin_str, '%Y-%m-%d')
            fecha_fin_dt_aware = timezone.make_aware(fecha_fin_dt_naive.replace(hour=23, minute=59, second=59, microsecond=999999), current_tz)
            q_date_filter &= (Q(fecha_decision_cartera__lte=fecha_fin_dt_aware) | Q(fecha_decision_admin__lte=fecha_fin_dt_aware))
        except ValueError:
            pass

    if q_date_filter:
        pedidos_rechazados_list = pedidos_rechazados_list.filter(q_date_filter)

    context = {
        'pedidos_list': pedidos_rechazados_list,
        'titulo': f'Informe de Pedidos Rechazados para {empresa_actual.nombre}',
        'fecha_inicio': fecha_inicio_str,
        'fecha_fin': fecha_fin_str,
        'app_name': 'Informes' 
    }
    return render(request, 'informes/informe_pedidos_rechazados.html', context)

# --- Informe de Pedidos Aprobados para Bodega ---
@login_required
@permission_required('informes.view_pedidos_aprobados', login_url='core:acceso_denegado')
def informe_pedidos_aprobados_bodega(request):
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')
    
    pedidos_aprobados_list = Pedido.objects.filter(
        empresa=empresa_actual,
        estado='APROBADO_ADMIN'
    ).select_related(
        'cliente',
        'vendedor__user',
        'usuario_decision_cartera',
        'usuario_decision_admin'
    ).order_by('-fecha_decision_admin')

    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    current_tz = timezone.get_current_timezone()

    if fecha_inicio_str:
        try:
            fecha_inicio_dt_naive = dt.strptime(fecha_inicio_str, '%Y-%m-%d')
            fecha_inicio_dt_aware = timezone.make_aware(fecha_inicio_dt_naive.replace(hour=0, minute=0, second=0, microsecond=0), current_tz)
            pedidos_aprobados_list = pedidos_aprobados_list.filter(fecha_decision_admin__gte=fecha_inicio_dt_aware)
        except ValueError:
            pass

    if fecha_fin_str:
        try:
            fecha_fin_dt_naive = dt.strptime(fecha_fin_str, '%Y-%m-%d')
            fecha_fin_dt_aware = timezone.make_aware(fecha_fin_dt_naive.replace(hour=23, minute=59, second=59, microsecond=999999), current_tz)
            pedidos_aprobados_list = pedidos_aprobados_list.filter(fecha_decision_admin__lte=fecha_fin_dt_aware)
        except ValueError:
            pass

    context = {
        'pedidos_list': pedidos_aprobados_list,
        'titulo': f'Pedidos Aprobados para Bodega ({empresa_actual.nombre})',
        'fecha_inicio': fecha_inicio_str,
        'fecha_fin': fecha_fin_str,
        'app_name': 'Informes'
    }
    return render(request, 'informes/informe_pedidos_aprobados_bodega.html', context)

@login_required
@user_passes_test(lambda u: es_bodega(u) or es_administracion(u) or es_factura(u) or es_cartera(u) or es_diseno(u), login_url='core:acceso_denegado')
def informe_ingresos_bodega(request):
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')
    
    ingresos_list = IngresoBodega.objects.filter(
        empresa=empresa_actual
    ).select_related(
        'usuario'
    ).annotate(
        numero_items=Count('detalles'), 
        cantidad_total_productos=Coalesce(Sum('detalles__cantidad'), 0) 
    ).order_by('-fecha_hora')

    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    usuario_id_str = request.GET.get('usuario_id') 
    current_tz = timezone.get_current_timezone()

    if fecha_inicio_str:
        try:
            fecha_inicio_dt_naive = dt.strptime(fecha_inicio_str, '%Y-%m-%d')
            fecha_inicio_dt_aware = timezone.make_aware(fecha_inicio_dt_naive.replace(hour=0, minute=0, second=0, microsecond=0), current_tz)
            ingresos_list = ingresos_list.filter(fecha_hora__gte=fecha_inicio_dt_aware)
        except ValueError:
            pass

    if fecha_fin_str:
        try:
            fecha_fin_dt_naive = dt.strptime(fecha_fin_str, '%Y-%m-%d')
            fecha_fin_dt_aware = timezone.make_aware(fecha_fin_dt_naive.replace(hour=23, minute=59, second=59, microsecond=999999), current_tz)
            ingresos_list = ingresos_list.filter(fecha_hora__lte=fecha_fin_dt_aware)
        except ValueError:
            pass

    if usuario_id_str:
        try:
            usuario_id = int(usuario_id_str)
            ingresos_list = ingresos_list.filter(usuario_id=usuario_id)
        except ValueError:
            pass

    User = get_user_model()
    usuarios_con_ingresos = User.objects.filter(
        ingresos_registrados__empresa=empresa_actual
    ).distinct().order_by('username')


    context = {
        'ingresos_list': ingresos_list,
        'titulo': f'Informe de Ingresos a Bodega ({empresa_actual.nombre})',
        'fecha_inicio': fecha_inicio_str,
        'fecha_fin': fecha_fin_str,
        'usuarios_filtro': usuarios_con_ingresos,
        'usuario_id_seleccionado': usuario_id_str,
        'app_name': 'Informes'
    }
    return render(request, 'informes/informe_ingresos_bodega.html', context)

@login_required
@user_passes_test(lambda u: es_factura(u) or es_bodega(u) or es_vendedor(u) or es_cartera(u) or u.is_superuser or es_administracion(u), login_url='core:acceso_denegado')
def informe_comprobantes_despacho(request):
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')
    
    
    comprobantes_list = ComprobanteDespacho.objects.filter(
        pedido__empresa=empresa_actual    
    ).select_related(
        'pedido__cliente',
        'usuario_responsable'
    ).annotate(
        numero_items_despachados=Count('detalles'), 
        cantidad_total_despachada=Coalesce(Sum('detalles__cantidad_despachada'), Value(0))
    ).order_by('-fecha_hora_despacho')

    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    usuario_id_str = request.GET.get('usuario_id') 
    pedido_id_str = request.GET.get('pedido_id')
    current_tz = timezone.get_current_timezone()

    if fecha_inicio_str:
        try:
            fecha_inicio_dt_naive = dt.strptime(fecha_inicio_str, '%Y-%m-%d')
            fecha_inicio_dt_aware = timezone.make_aware(fecha_inicio_dt_naive.replace(hour=0, minute=0, second=0, microsecond=0), current_tz)
            comprobantes_list = comprobantes_list.filter(fecha_hora_despacho__gte=fecha_inicio_dt_aware)
        except ValueError:
            messages.error(request, "Formato de fecha de inicio inválido.")

    if fecha_fin_str:
        try:
            fecha_fin_dt_naive = dt.strptime(fecha_fin_str, '%Y-%m-%d')
            fecha_fin_dt_aware = timezone.make_aware(fecha_fin_dt_naive.replace(hour=23, minute=59, second=59, microsecond=999999), current_tz)
            comprobantes_list = comprobantes_list.filter(fecha_hora_despacho__lte=fecha_fin_dt_aware)
        except ValueError:
            messages.error(request, "Formato de fecha de fin inválido.")

    if usuario_id_str:
        try:
            usuario_id = int(usuario_id_str)
            comprobantes_list = comprobantes_list.filter(usuario_responsable_id=usuario_id)
        except ValueError:
            messages.error(request, "ID de usuario inválido.")

    if pedido_id_str:
        try:
            pedido_id = int(pedido_id_str)
            comprobantes_list = comprobantes_list.filter(pedido_id=pedido_id)
        except ValueError:
            messages.error(request, "ID de pedido inválido.")

    User = get_user_model()
    usuarios_bodega = User.objects.filter(
        comprobantes_despachados__pedido__empresa=empresa_actual
    ).distinct().order_by('username')

    context = {
        'comprobantes_list': comprobantes_list,
        'titulo': f'Informe de Comprobantes de Despacho ({empresa_actual.nombre})',
        'fecha_inicio': fecha_inicio_str,
        'fecha_fin': fecha_fin_str,
        'usuarios_filtro': usuarios_bodega,
        'usuario_id_seleccionado': usuario_id_str,
        'pedido_id_seleccionado': pedido_id_str,
        'app_name': 'Informes'
    }
    return render(request, 'informes/informe_comprobantes_despacho.html', context)


@login_required
@user_passes_test(lambda u: es_factura(u) or es_cartera(u) or u.is_superuser or es_administracion(u), login_url='core:acceso_denegado')
def informe_total_pedidos(request):

    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')

    pedidos_qs = Pedido.objects.filter(
        empresa=empresa_actual
    ).select_related(
        'cliente',
        'vendedor__user'
    ).order_by('-fecha_hora')
    
    pedidos_qs = pedidos_qs.exclude(estado='BORRADOR')

    # Filtros
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    estado_query = request.GET.get('estado')
    cliente_query = request.GET.get('cliente_q')
    vendedor_id_str = request.GET.get('vendedor_id')
    current_tz = timezone.get_current_timezone()

    # Aplicar filtros al queryset
    if fecha_inicio_str:
        try:
            fecha_inicio_dt_naive = dt.strptime(fecha_inicio_str, '%Y-%m-%d')
            fecha_inicio_dt_aware = timezone.make_aware(fecha_inicio_dt_naive.replace(hour=0, minute=0, second=0, microsecond=0), current_tz)
            pedidos_qs = pedidos_qs.filter(fecha_hora__gte=fecha_inicio_dt_aware)
        except ValueError:
            messages.error(request, "Formato de fecha de inicio inválido.")

    if fecha_fin_str:
        try:
            fecha_fin_dt_naive = dt.strptime(fecha_fin_str, '%Y-%m-%d')
            fecha_fin_dt_aware = timezone.make_aware(fecha_fin_dt_naive.replace(hour=23, minute=59, second=59, microsecond=999999), current_tz)
            pedidos_qs = pedidos_qs.filter(fecha_hora__lte=fecha_fin_dt_aware)
        except ValueError:
            messages.error(request, "Formato de fecha de fin inválido.")

    if estado_query:
        pedidos_qs = pedidos_qs.filter(estado=estado_query)

    if cliente_query:
        pedidos_qs = pedidos_qs.filter(
            Q(cliente__nombre_completo__icontains=cliente_query) |
            Q(cliente__identificacion__icontains=cliente_query)
        )

    if vendedor_id_str:
        try:
            vendedor_id = int(vendedor_id_str)
            pedidos_qs = pedidos_qs.filter(vendedor_id=vendedor_id)
        except ValueError:
            messages.error(request, "ID de vendedor inválido.")


   # Anotamos el subtotal (antes de descuento) para cada pedido
    pedidos_qs = pedidos_qs.annotate(
        subtotal=Coalesce(Sum(
            F('detalles__cantidad') * F('detalles__precio_unitario'),
            output_field=DecimalField()
        ), Value(Decimal('0.00'))) # Añadido Coalesce para subtotal
    ).annotate(
        total_calculado=ExpressionWrapper(
            F('subtotal') * (Decimal('1.0') - F('porcentaje_descuento') / Decimal('100.0')),
            output_field=DecimalField()
        )
    )
    
    # Agregamos el valor total de todos los pedidos filtrados
    agregados = pedidos_qs.aggregate(
        total_valor=Coalesce(Sum('total_calculado'), Value(Decimal('0.00'))) # Añadido Coalesce
    )
    total_pedidos_valor = agregados['total_valor']
    
    # Ordenamos el queryset ANOTADO
    pedidos_ordenados = pedidos_qs.order_by('-fecha_hora')
    
    cantidad_total_pedidos = pedidos_ordenados.count()   

    # --- Paginación y Contexto (se mantienen igual) ---
    paginator = Paginator(pedidos_qs, 30)
    page_number = request.GET.get('page')
    pedidos_page_obj = paginator.get_page(page_number)    

    # Lista de vendedores y estados para los desplegables de filtro.
    lista_vendedores = Vendedor.objects.filter(
        user__empresa=empresa_actual,
        activo=True
    ).select_related('user').order_by('user__first_name')
    lista_estados_filtrada = [estado for estado in Pedido.ESTADO_PEDIDO_CHOICES if estado[0] != 'BORRADOR']

    context = {
        'pedidos_list': pedidos_page_obj,
        'titulo': f'Informe Total de Pedidos ({empresa_actual.nombre})',
        'fecha_inicio': fecha_inicio_str, 
        'fecha_fin': fecha_fin_str, 
        'estado_seleccionado': estado_query, 
        'cliente_query': cliente_query, 
        'vendedor_id_seleccionado': vendedor_id_str,         
        'lista_vendedores': lista_vendedores, 
        'lista_estados': lista_estados_filtrada,        
        'cantidad_total_pedidos': cantidad_total_pedidos, 
        'total_pedidos_valor': total_pedidos_valor,
        'app_name': 'Informes' 
    }
    return render(request, 'informes/informe_total_pedidos.html', context)

@login_required 
def informe_lista_devoluciones(request):

    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')

    devoluciones_list = DevolucionCliente.objects.filter(
        empresa=empresa_actual        
    ).select_related( 
        'cliente', 
        'usuario'
    ).all() 

    context = {
        'titulo': f'Informe de Devoluciones de Clientes ({empresa_actual.nombre})',
        'devoluciones_list': devoluciones_list, 
        'app_name': 'Informes'
    }
    return render(request, 'informes/lista_devoluciones_reporte.html', context)