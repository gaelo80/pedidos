# informes/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test, permission_required
from django.db.models import Sum, Count, F, ExpressionWrapper, fields, DecimalField, Case, When, Value, Q, Min
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import timedelta, datetime as dt
from decimal import Decimal, ROUND_HALF_UP
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from core.auth_utils import es_admin_sistema, es_bodega, es_vendedor, es_diseno, es_cartera, es_admin_sistema, es_factura
from bodega.models import IngresoBodega
from pedidos.models import Pedido, DetallePedido
from vendedores.models import Vendedor
from django.contrib.auth import get_user_model
from django.contrib import messages
from bodega.models import ComprobanteDespacho
from devoluciones.models import DevolucionCliente
from core.mixins import TenantAwareMixin
from django.core.exceptions import PermissionDenied


ESTADOS_PEDIDO_REPORTEABLES = [
    'PENDIENTE_APROBACION_CARTERA',
    'PENDIENTE_APROBACION_ADMIN',
    'APROBADO_ADMIN',
    'PROCESANDO',
    'COMPLETADO',
    'ENVIADO',
    'ENTREGADO'
]

def _parse_date_range_from_request(request):
    # ... (código completo de la función como se mostró en la respuesta anterior) ...
    current_tz = timezone.get_current_timezone()
    fecha_fin_dt = timezone.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    fecha_inicio_dt = (timezone.now() - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
    # ... resto de la lógica ...
    return fecha_inicio_dt, fecha_fin_dt


@login_required
@permission_required('informes.view_reporte_ventas_general', login_url='core:acceso_denegado')
def reporte_ventas_general(request):
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')

    fecha_inicio_dt_aware, fecha_fin_dt_aware = _parse_date_range_from_request(request)
    
    
    

    pedidos_para_lista_general_qs = Pedido.objects.filter(
        empresa=empresa_actual,
        estado__in=ESTADOS_PEDIDO_REPORTEABLES,
        fecha_hora__range=(fecha_inicio_dt_aware, fecha_fin_dt_aware)
    ).select_related('cliente', 'vendedor__user').annotate(
        unidades_solicitadas_en_pedido=Coalesce(Sum('detalles__cantidad'), Value(0)),
        total_unidades_despachadas_pedido=Coalesce(Sum('detalles__cantidad_verificada'), Value(0))
    )
    
    
    

    agregados_generales = DetallePedido.objects.filter(
        pedido__in=pedidos_para_lista_general_qs  # Filtramos usando el queryset de pedidos ya seguro
    ).aggregate(
        total_unidades_solicitadas=Coalesce(Sum('cantidad'), Value(0)),
        total_unidades_despachadas=Coalesce(Sum('cantidad_verificada'), Value(0))
    )
    
    total_unidades_solicitadas_general = agregados_generales['total_unidades_solicitadas']
    total_unidades_despachadas_general = agregados_generales['total_unidades_despachadas']
    
    
    

    porcentaje_despacho_general = Decimal('0.00')
    if total_unidades_solicitadas_general > 0:
        porcentaje_despacho_general = (Decimal(total_unidades_despachadas_general) / Decimal(total_unidades_solicitadas_general) * Decimal('100.00'))
        porcentaje_despacho_general = porcentaje_despacho_general.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    cantidad_pedidos_considerados_venta = pedidos_para_lista_general_qs.count()
    
    
    

    ventas_por_producto = DetallePedido.objects.filter(
        pedido__empresa=empresa_actual,
        pedido__in=pedidos_para_lista_general_qs 
    ).values(
        'producto__referencia',  
        'producto__color'        
    ).annotate(
        cantidad_total_vendida=Coalesce(Sum('cantidad'), Value(0)),
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
@permission_required('informes.view_reporte_ventas_vendedor', login_url='core:acceso_denegado') # Usar las funciones de check correctas
def reporte_ventas_vendedor(request):
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')
    
    usuario_actual = request.user
    es_admin_sistema_rol_actual = es_admin_sistema(usuario_actual)
    es_vendedor_rol_actual = es_vendedor(usuario_actual)

    # Lógica de Fechas (como la tenías)
    fecha_fin_dt_aware = timezone.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    fecha_inicio_dt_aware = (timezone.now() - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
    current_tz = timezone.get_current_timezone()
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    vendedor_seleccionado_id_str = request.GET.get('vendedor_id')

    if fecha_inicio_str:
        try:
            fecha_inicio_dt_naive = dt.strptime(fecha_inicio_str, '%Y-%m-%d')
            fecha_inicio_dt_aware = timezone.make_aware(fecha_inicio_dt_naive.replace(hour=0, minute=0, second=0, microsecond=0), current_tz)
        except ValueError: pass

    if fecha_fin_str:
        try:
            fecha_fin_dt_naive = dt.strptime(fecha_fin_str, '%Y-%m-%d')
            fecha_fin_dt_aware = timezone.make_aware(fecha_fin_dt_naive.replace(hour=23, minute=59, second=59, microsecond=999999), current_tz)
        except ValueError: pass

    # Queryset base para pedidos dentro del rango de fechas
    
    pedidos_base_empresa = Pedido.objects.filter(empresa=empresa_actual)    
    pedidos_en_rango_fecha_qs = pedidos_base_empresa.filter(
        fecha_hora__range=(fecha_inicio_dt_aware, fecha_fin_dt_aware)
    )

    vendedores_list_for_dropdown = None # Para el desplegable del admin
    vendedor_objeto_contexto = None   # Vendedor para el título (ya sea el logueado o el seleccionado)
    pedidos_filtrados_final_qs = Pedido.objects.none() # Empezar con queryset vacío

    if es_admin_sistema_rol_actual:
        print("DEBUG: Usuario es Admin/Gerencia.")
        
        vendedores_list_for_dropdown = Vendedor.objects.filter(
            empresa=empresa_actual, 
            activo=True
        ).select_related('user').order_by('user__first_name', 'user__last_name')
        
        print(f"DEBUG: Admin - Lista de vendedores para dropdown: {vendedores_list_for_dropdown.count()} vendedores.")

        if vendedor_seleccionado_id_str:
            try:
                vendedor_id_int = int(vendedor_seleccionado_id_str)
                pedidos_filtrados_final_qs = pedidos_en_rango_fecha_qs.filter(vendedor_id=vendedor_id_int)
                vendedor_objeto_contexto = Vendedor.objects.get(pk=vendedor_id_int, empresa=empresa_actual)
                print(f"DEBUG: Admin - Vendedor ID {vendedor_id_int} seleccionado. Pedidos: {pedidos_filtrados_final_qs.count()}")
            except (ValueError, Vendedor.DoesNotExist):
                messages.error(request, "El vendedor seleccionado no es válido o no pertenece a esta empresa.")
                # pedidos_filtrados_final_qs permanece vacío
        # else: Admin no seleccionó vendedor, pedidos_filtrados_final_qs permanece vacío.

    elif es_vendedor_rol_actual: # No es admin, pero SÍ es vendedor
        print("DEBUG: Usuario es Vendedor.")
        try:
            vendedor_objeto_contexto = Vendedor.objects.get(user=usuario_actual)

            # Validación opcional si quieres reforzar seguridad multi-inquilino:
            if vendedor_objeto_contexto.user.empresa != empresa_actual:
                raise PermissionDenied("Este vendedor no pertenece a tu empresa.")
            pedidos_filtrados_final_qs = pedidos_en_rango_fecha_qs.filter(vendedor=vendedor_objeto_contexto)
            print(f"DEBUG: Vendedor - Perfil encontrado: {vendedor_objeto_contexto}. Pedidos: {pedidos_filtrados_final_qs.count()}")
        except Vendedor.DoesNotExist:
            messages.error(request, "No se encontró un perfil de vendedor activo para su cuenta en esta empresa.")
            print("DEBUG: Vendedor - Perfil de Vendedor NO encontrado para el usuario en esta empresa.")

    # Filtrar por estados de venta solicitada y anotar
    pedidos_para_lista_y_agregados = pedidos_filtrados_final_qs.filter(
        estado__in=ESTADOS_PEDIDO_REPORTEABLES
    ).select_related('cliente', 'vendedor__user').annotate(
        unidades_solicitadas_en_pedido=Coalesce(Sum('detalles__cantidad'), Value(0)),
        total_unidades_despachadas_pedido=Coalesce(Sum('detalles__cantidad_verificada'), Value(0))
    )

    # Calcular agregados (se calcularán sobre un queryset vacío si no hay selección/permiso)
    agregados_solicitados_vendedor = DetallePedido.objects.filter(
        pedido__in=pedidos_para_lista_y_agregados
    ).aggregate(
        total_unidades=Coalesce(Sum('cantidad'), Value(0)),
        valor_total=Coalesce(Sum(F('cantidad') * F('precio_unitario'), output_field=DecimalField()), Value(Decimal('0.00')))
    )
    total_unidades_solicitadas_vendedor = agregados_solicitados_vendedor['total_unidades']
    valor_total_ventas_solicitadas_vendedor = agregados_solicitados_vendedor['valor_total']

    agregados_despachados_vendedor = DetallePedido.objects.filter(
        pedido__in=pedidos_para_lista_y_agregados
    ).aggregate(
        total_unidades=Coalesce(Sum('cantidad_verificada'), Value(0))
    )
    total_unidades_despachadas_vendedor = agregados_despachados_vendedor['total_unidades']

    porcentaje_despacho_vendedor = Decimal('0.00')
    if total_unidades_solicitadas_vendedor > 0:
        porcentaje_despacho_vendedor = (Decimal(total_unidades_despachadas_vendedor) / Decimal(total_unidades_solicitadas_vendedor) * Decimal('100.00'))
        porcentaje_despacho_vendedor = porcentaje_despacho_vendedor.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    cantidad_pedidos_del_vendedor = pedidos_para_lista_y_agregados.count()

    # Lógica para el título del informe
    titulo_informe = "Informe de Ventas" # Título genérico por si acaso
    if es_admin_sistema_rol_actual:
        if vendedor_objeto_contexto:
            titulo_informe = f"Unidades Vendidas de: {vendedor_objeto_contexto.user.get_full_name() or vendedor_objeto_contexto.user.username}"
        elif vendedor_seleccionado_id_str: # Admin seleccionó un ID pero no se encontró el Vendedor obj
            titulo_informe = f"Informe para Vendedor ID: {vendedor_seleccionado_id_str} (No encontrado)"
        else: # Admin, y no ha seleccionado ningún vendedor
            titulo_informe = "Seleccione un Vendedor para ver el Informe"
    elif vendedor_objeto_contexto: # Es un vendedor viendo su propio informe
         titulo_informe = f"Mis Unidades Vendidas ({vendedor_objeto_contexto.user.get_full_name() or vendedor_objeto_contexto.user.username})"
    # Si no es admin y no se encontró su perfil de vendedor (ya se habrá mostrado un messages.error)
    # el título podría quedarse como "Informe de Ventas" o podrías poner "Mis Unidades Vendidas (Error de Perfil)"

    print(f"DEBUG: Título final: {titulo_informe}")
    print(f"DEBUG: Variable 'es_admin_sistema' para plantilla: {es_admin_sistema_rol_actual}")

    context = {
        'titulo': titulo_informe,
        'pedidos_list': pedidos_para_lista_y_agregados,
        'total_unidades_solicitadas_vendedor': total_unidades_solicitadas_vendedor,
        'valor_total_ventas_solicitadas_vendedor': valor_total_ventas_solicitadas_vendedor,
        'total_unidades_despachadas_vendedor': total_unidades_despachadas_vendedor,
        'porcentaje_despacho_vendedor': porcentaje_despacho_vendedor,
        'cantidad_pedidos_vendedor': cantidad_pedidos_del_vendedor,
        'fecha_inicio': fecha_inicio_dt_aware.strftime('%Y-%m-%d'),
        'fecha_fin': fecha_fin_dt_aware.strftime('%Y-%m-%d'),
        'vendedores_list': vendedores_list_for_dropdown, # Para el <select> del admin
        'vendedor_id_seleccionado': int(vendedor_seleccionado_id_str) if vendedor_seleccionado_id_str else None,
        'es_admin_sistema': es_admin_sistema_rol_actual, # Para la lógica if en la plantilla
        'app_name': 'Informes'
    }
    return render(request, 'informes/reporte_ventas_vendedor.html', context)


@login_required
@user_passes_test(lambda u: es_vendedor(u) or es_admin_sistema(u))
def reporte_cumplimiento_despachos(request):
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')
    
    fecha_fin_dt = timezone.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    fecha_inicio_dt = (timezone.now() - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)

    current_tz = timezone.get_current_timezone()
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    vendedor_filtro_id = request.GET.get('vendedor_id')

    if fecha_inicio_str:
        try:
            fecha_inicio_dt_naive = dt.strptime(fecha_inicio_str, '%Y-%m-%d')
            fecha_inicio_dt = timezone.make_aware(fecha_inicio_dt_naive.replace(hour=0, minute=0, second=0, microsecond=0), current_tz)
        except ValueError:
            pass

    if fecha_fin_str:
        try:
            fecha_fin_dt_naive = dt.strptime(fecha_fin_str, '%Y-%m-%d')
            fecha_fin_dt = timezone.make_aware(fecha_fin_dt_naive.replace(hour=23, minute=59, second=59, microsecond=999999), current_tz)
        except ValueError:
            pass

    pedidos_qs = Pedido.objects.filter(
        empresa=empresa_actual,
        fecha_hora__range=(fecha_inicio_dt, fecha_fin_dt)
    ).annotate(
        total_unidades_solicitadas=Coalesce(Sum('detalles__cantidad'), 0),
        total_unidades_despachadas=Coalesce(Sum('detalles__cantidad_verificada'), 0)
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
    es_admin_sistema_actual = es_admin_sistema(usuario_actual)
    vendedores_list = None

    if es_admin_sistema_actual:
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
        'es_admin_sistema': es_admin_sistema_actual,
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
        'app_name': 'Informes' # Coincide con tus otros informes
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
    ).order_by('-fecha_decision_admin') # Ordenar por fecha de aprobación de admin

    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    current_tz = timezone.get_current_timezone()

    if fecha_inicio_str:
        try:
            fecha_inicio_dt_naive = dt.strptime(fecha_inicio_str, '%Y-%m-%d')
            fecha_inicio_dt_aware = timezone.make_aware(fecha_inicio_dt_naive.replace(hour=0, minute=0, second=0, microsecond=0), current_tz)
            # Filtramos por fecha_decision_admin ya que es la aprobación final para bodega
            pedidos_aprobados_list = pedidos_aprobados_list.filter(fecha_decision_admin__gte=fecha_inicio_dt_aware)
        except ValueError: pass

    if fecha_fin_str:
        try:
            fecha_fin_dt_naive = dt.strptime(fecha_fin_str, '%Y-%m-%d')
            fecha_fin_dt_aware = timezone.make_aware(fecha_fin_dt_naive.replace(hour=23, minute=59, second=59, microsecond=999999), current_tz)
            pedidos_aprobados_list = pedidos_aprobados_list.filter(fecha_decision_admin__lte=fecha_fin_dt_aware)
        except ValueError: pass

    context = {
        'pedidos_list': pedidos_aprobados_list,
        'titulo': f'Pedidos Aprobados para Bodega ({empresa_actual.nombre})',
        'fecha_inicio': fecha_inicio_str,
        'fecha_fin': fecha_fin_str,
        'app_name': 'Informes'
    }
    return render(request, 'informes/informe_pedidos_aprobados_bodega.html', context)

@login_required
@user_passes_test(lambda u: es_bodega(u) or es_admin_sistema(u) or es_factura(u) or es_cartera(u) or es_diseno(u), login_url='core:acceso_denegado')
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
        numero_items=Count('detalles'), # Cuenta las líneas de detalle (productos distintos)
        cantidad_total_productos=Coalesce(Sum('detalles__cantidad'), 0) # Suma las cantidades de todos los detalles
    ).order_by('-fecha_hora')

    # Filtros
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    usuario_id_str = request.GET.get('usuario_id') # Para filtrar por usuario que registró
    current_tz = timezone.get_current_timezone()

    if fecha_inicio_str:
        try:
            fecha_inicio_dt_naive = dt.strptime(fecha_inicio_str, '%Y-%m-%d')
            fecha_inicio_dt_aware = timezone.make_aware(fecha_inicio_dt_naive.replace(hour=0, minute=0, second=0, microsecond=0), current_tz)
            ingresos_list = ingresos_list.filter(fecha_hora__gte=fecha_inicio_dt_aware)
        except ValueError:
            pass # Ignorar fecha inválida

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
            pass # Ignorar ID de usuario inválido

    User = get_user_model()
    # Obtener solo usuarios que han registrado ingresos para el dropdown del filtro
    usuarios_con_ingresos = User.objects.filter(
        ingresos_registrados__empresa=empresa_actual
    ).distinct().order_by('username')


    context = {
        'ingresos_list': ingresos_list,
        'titulo': f'Informe de Ingresos a Bodega ({empresa_actual.nombre})',
        'fecha_inicio': fecha_inicio_str,
        'fecha_fin': fecha_fin_str,
        'usuarios_filtro': usuarios_con_ingresos, # Para poblar el dropdown de filtro de usuario
        'usuario_id_seleccionado': usuario_id_str,
        'app_name': 'Informes'
    }
    return render(request, 'informes/informe_ingresos_bodega.html', context)

@login_required
@user_passes_test(lambda u: es_factura(u) or es_bodega(u) or es_vendedor(u) or es_cartera(u) or u.is_superuser or es_admin_sistema(u), login_url='core:acceso_denegado')
def informe_comprobantes_despacho(request):
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')
    
    
    comprobantes_list = ComprobanteDespacho.objects.filter(
        pedido__empresa=empresa_actual    
    ).select_related(
        'pedido__cliente',
        'usuario_responsable' # Usuario de bodega que registró el despacho
    ).annotate(
        numero_items_despachados=Count('detalles'), # Cuenta las líneas de detalle del comprobante
        cantidad_total_despachada=Coalesce(Sum('detalles__cantidad_despachada'), Value(0)) # Suma las cantidades
    ).order_by('-fecha_hora_despacho')

    # Filtros
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    usuario_id_str = request.GET.get('usuario_id') # Para filtrar por usuario responsable (bodega)
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
    # Obtener usuarios que han creado comprobantes de despacho
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
@user_passes_test(lambda u: es_factura(u) or es_cartera(u) or u.is_superuser or es_admin_sistema(u), login_url='core:acceso_denegado')
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
    fecha_inicio_str = request.GET.get('fecha_inicio') #
    fecha_fin_str = request.GET.get('fecha_fin') #
    estado_query = request.GET.get('estado') #
    cliente_query = request.GET.get('cliente_q') #
    vendedor_id_str = request.GET.get('vendedor_id') #
    current_tz = timezone.get_current_timezone() #

    # Aplicar filtros al queryset
    if fecha_inicio_str:
        try:
            fecha_inicio_dt_naive = dt.strptime(fecha_inicio_str, '%Y-%m-%d') #
            fecha_inicio_dt_aware = timezone.make_aware(fecha_inicio_dt_naive.replace(hour=0, minute=0, second=0, microsecond=0), current_tz) #
            pedidos_qs = pedidos_qs.filter(fecha_hora__gte=fecha_inicio_dt_aware) #
        except ValueError:
            messages.error(request, "Formato de fecha de inicio inválido.") #

    if fecha_fin_str:
        try:
            fecha_fin_dt_naive = dt.strptime(fecha_fin_str, '%Y-%m-%d') #
            fecha_fin_dt_aware = timezone.make_aware(fecha_fin_dt_naive.replace(hour=23, minute=59, second=59, microsecond=999999), current_tz) #
            pedidos_qs = pedidos_qs.filter(fecha_hora__lte=fecha_fin_dt_aware) #
        except ValueError:
            messages.error(request, "Formato de fecha de fin inválido.") #

    if estado_query:
        pedidos_qs = pedidos_qs.filter(estado=estado_query) #

    if cliente_query:
        pedidos_qs = pedidos_qs.filter( #
            Q(cliente__nombre_completo__icontains=cliente_query) | #
            Q(cliente__identificacion__icontains=cliente_query) #
        )

    if vendedor_id_str:
        try:
            vendedor_id = int(vendedor_id_str) #
            pedidos_qs = pedidos_qs.filter(vendedor_id=vendedor_id) #
        except ValueError:
            messages.error(request, "ID de vendedor inválido.") #


   # 1. Anotamos el subtotal (antes de descuento) para cada pedido
    pedidos_qs = pedidos_qs.annotate(
        subtotal=Sum(
            F('detalles__cantidad') * F('detalles__precio_unitario'),
            output_field=DecimalField()
        )
    ).annotate(
        total_calculado=ExpressionWrapper(
            F('subtotal') * (Decimal('1.0') - F('porcentaje_descuento') / Decimal('100.0')),
            output_field=DecimalField()
        )
    )
    
    # Agregamos el valor total de todos los pedidos filtrados
    agregados = pedidos_qs.aggregate(
        total_valor=Sum('total_calculado')
    )
    total_pedidos_valor = agregados['total_valor'] or Decimal('0.00')
    
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
    #lista_estados = Pedido.ESTADO_PEDIDO_CHOICES #

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
    return render(request, 'informes/informe_total_pedidos.html', context) #

@login_required # Puedes añadir @user_passes_test si necesitas permisos específicos
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