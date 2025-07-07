# recaudos/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Sum, Q
from django.db import transaction
from django.utils import timezone
from decimal import Decimal

# --- Importaciones de tus apps ---
from .models import Recaudo, Consignacion
from .forms import RecaudoForm, ConsignacionForm
from vendedores.models import Vendedor
# Usamos tus funciones de permisos
from core.auth_utils import es_vendedor, es_admin_sistema, es_cartera

# (Las vistas para vendedores no cambian...)
@login_required
@user_passes_test(es_vendedor, login_url='core:acceso_denegado')
def crear_recaudo(request):
    empresa_actual = request.user.empresa
    if request.method == 'POST':
        form = RecaudoForm(request.POST, empresa=empresa_actual)
        if form.is_valid():
            try:
                vendedor_actual = request.user.perfil_vendedor
                recaudo = form.save(commit=False)
                recaudo.empresa = empresa_actual
                recaudo.vendedor = vendedor_actual
                recaudo.save()
                messages.success(request, f"Recaudo No. {recaudo.id} creado exitosamente.")
                return redirect('recaudos:detalle_recibo', pk=recaudo.pk)
            except Vendedor.DoesNotExist:
                messages.error(request, "Tu usuario no tiene un perfil de vendedor asociado. Contacta al administrador.")
            except Exception as e:
                messages.error(request, f"Ocurrió un error inesperado: {e}")
    else:
        form = RecaudoForm(empresa=empresa_actual)
    context = {'form': form, 'titulo': f'Registrar Nuevo Recaudo ({empresa_actual.nombre})'}
    return render(request, 'recaudos/crear_recaudo.html', context)

@login_required
@user_passes_test(es_vendedor, login_url='core:acceso_denegado')
def lista_recaudos_vendedor(request):
    try:
        vendedor_actual = request.user.perfil_vendedor
        empresa_actual = request.user.empresa
        recaudos_list = Recaudo.objects.filter(vendedor=vendedor_actual).select_related('cliente', 'consignacion')
        total_en_manos = recaudos_list.filter(estado=Recaudo.Estado.EN_MANOS_DEL_VENDEDOR).aggregate(total=Sum('monto_recibido'))['total'] or Decimal('0.00')
        context = {'recaudos': recaudos_list, 'total_en_manos': total_en_manos, 'titulo': f'Mis Recaudos - {vendedor_actual}', 'empresa_nombre': empresa_actual.nombre}
        return render(request, 'recaudos/lista_recaudos.html', context)
    except Vendedor.DoesNotExist:
        messages.error(request, "Tu usuario no tiene un perfil de vendedor asociado.")
        return redirect('core:index')

@login_required
@user_passes_test(es_vendedor, login_url='core:acceso_denegado')
def detalle_recibo(request, pk):
    try:
        vendedor_actual = request.user.perfil_vendedor
        recaudo = get_object_or_404(Recaudo, pk=pk, vendedor=vendedor_actual)
        context = {'recaudo': recaudo, 'titulo': f"Detalle Recibo de Caja No. {recaudo.id}"}
        return render(request, 'recaudos/detalle_recibo.html', context)
    except Vendedor.DoesNotExist:
        messages.error(request, "Tu usuario no tiene un perfil de vendedor asociado.")
        return redirect('core:index')

@login_required
@user_passes_test(es_vendedor, login_url='core:acceso_denegado')
def crear_consignacion(request):
    empresa_actual = request.user.empresa
    try:
        vendedor_actual = request.user.perfil_vendedor
    except Vendedor.DoesNotExist:
        messages.error(request, "Tu usuario no tiene un perfil de vendedor asociado.")
        return redirect('core:index')
    recaudos_pendientes = Recaudo.objects.filter(vendedor=vendedor_actual, estado=Recaudo.Estado.EN_MANOS_DEL_VENDEDOR)
    if request.method == 'POST':
        form = ConsignacionForm(request.POST, request.FILES, vendedor=vendedor_actual, empresa=empresa_actual)
        if form.is_valid():
            try:
                with transaction.atomic():
                    recaudos_seleccionados_qs = form.cleaned_data['recaudos']
                    monto_calculado = recaudos_seleccionados_qs.aggregate(total=Sum('monto_recibido'))['total'] or Decimal('0.00')
                    consignacion = form.save(commit=False)
                    consignacion.vendedor = vendedor_actual
                    consignacion.empresa = empresa_actual
                    consignacion.monto_total = monto_calculado
                    consignacion.save()
                    recaudos_seleccionados_qs.update(estado=Recaudo.Estado.DEPOSITADO, consignacion=consignacion)
                messages.success(request, f"Consignación No. {consignacion.id} registrada exitosamente.")
                return redirect('recaudos:lista_recaudos')
            except Exception as e:
                messages.error(request, f"Ocurrió un error al guardar la consignación: {e}")
    else:
        form = ConsignacionForm(vendedor=vendedor_actual, empresa=empresa_actual)
    context = {'form': form, 'recaudos_pendientes': recaudos_pendientes, 'titulo': f'Registrar Nueva Consignación ({empresa_actual.nombre})'}
    return render(request, 'recaudos/crear_consignacion.html', context)

# --- VISTAS DE ADMINISTRACIÓN CORREGIDAS ---

def es_admin_o_cartera(user):
    """Función de permiso para chequear si el usuario es Admin o de Cartera."""
    return es_admin_sistema(user) or es_cartera(user)

@login_required
@user_passes_test(es_admin_o_cartera, login_url='core:acceso_denegado')
def panel_administracion(request):
    """
    Muestra a los administradores una lista de consignaciones para verificar.
    """
    empresa_actual = getattr(request.user, 'empresa', None)
    
    # Superusuarios ven todo, otros usuarios ven solo su empresa.
    if request.user.is_superuser:
        consignaciones_list = Consignacion.objects.all()
        titulo = 'Panel de Verificación (Todas las Empresas)'
    elif empresa_actual:
        consignaciones_list = Consignacion.objects.filter(empresa=empresa_actual)
        titulo = f'Panel de Verificación ({empresa_actual.nombre})'
    else:
        # Si un usuario no-superuser no tiene empresa, se le niega el acceso.
        messages.error(request, "Su usuario no tiene una empresa asignada. Contacte al administrador.")
        return redirect('core:index')

    # Filtro por estado
    estado_filtro = request.GET.get('estado', Consignacion.Estado.PENDIENTE_VERIFICACION)
    if estado_filtro:
        consignaciones_list = consignaciones_list.filter(estado=estado_filtro)

    context = {
        'consignaciones': consignaciones_list.select_related('vendedor__user'),
        'titulo': titulo,
        'estado_actual': estado_filtro,
        'estados_posibles': Consignacion.Estado.choices
    }
    return render(request, 'recaudos/panel_administracion.html', context)


@login_required
@user_passes_test(es_admin_o_cartera, login_url='core:acceso_denegado')
@transaction.atomic
def verificar_consignacion(request, pk):
    """
    Permite a un administrador aprobar o rechazar una consignación.
    """
    # Un superusuario puede verificar cualquier consignación.
    if request.user.is_superuser:
        consignacion = get_object_or_404(Consignacion, pk=pk)
    # Un usuario normal solo puede verificar las de su empresa.
    else:
        empresa_actual = getattr(request.user, 'empresa', None)
        if not empresa_actual:
            messages.error(request, "Su usuario no tiene una empresa asignada.")
            return redirect('core:index')
        consignacion = get_object_or_404(Consignacion, pk=pk, empresa=empresa_actual)

    if request.method == 'POST':
        accion = request.POST.get('accion')
        
        if accion == 'aprobar':
            consignacion.estado = Consignacion.Estado.VERIFICADA
            consignacion.fecha_verificacion = timezone.now()
            consignacion.notas_verificacion = f"Aprobado por {request.user.username}."
            consignacion.save()
            consignacion.recaudos_incluidos.update(estado=Recaudo.Estado.VERIFICADO)
            messages.success(request, f"Consignación No. {consignacion.id} ha sido APROBADA.")
        
        elif accion == 'rechazar':
            notas = request.POST.get('notas_rechazo', 'Sin notas.')
            consignacion.estado = Consignacion.Estado.RECHAZADA
            consignacion.fecha_verificacion = timezone.now()
            consignacion.notas_verificacion = f"Rechazado por {request.user.username}. Motivo: {notas}"
            consignacion.save()
            consignacion.recaudos_incluidos.update(estado=Recaudo.Estado.EN_MANOS_DEL_VENDEDOR, consignacion=None)
            messages.warning(request, f"Consignación No. {consignacion.id} ha sido RECHAZADA.")
            
        return redirect('recaudos:panel_administracion')

    context = {
        'consignacion': consignacion,
        'titulo': f'Verificar Consignación No. {consignacion.id}'
    }
    return render(request, 'recaudos/verificar_consignacion.html', context)

@login_required
@user_passes_test(es_admin_o_cartera, login_url='core:acceso_denegado')
def reporte_general_recaudos(request):
    """
    Muestra a los administradores un reporte de todos los recaudos,
    con filtros por estado y vendedor.
    """
    empresa_actual = getattr(request.user, 'empresa', None)
    
    # Definir el queryset base según el tipo de usuario
    if request.user.is_superuser:
        recaudos_list = Recaudo.objects.all()
        vendedores_list = Vendedor.objects.filter(activo=True)
        titulo = 'Reporte General de Recaudos (Todas las Empresas)'
    elif empresa_actual:
        recaudos_list = Recaudo.objects.filter(empresa=empresa_actual)
        vendedores_list = Vendedor.objects.filter(user__empresa=empresa_actual, activo=True)
        titulo = f'Reporte General de Recaudos ({empresa_actual.nombre})'
    else:
        messages.error(request, "Su usuario no tiene una empresa asignada.")
        return redirect('core:index')

    # Aplicar filtros desde la URL (GET)
    estado_filtro = request.GET.get('estado', '')
    vendedor_filtro_id = request.GET.get('vendedor', '')

    if estado_filtro:
        recaudos_list = recaudos_list.filter(estado=estado_filtro)
    
    if vendedor_filtro_id:
        recaudos_list = recaudos_list.filter(vendedor_id=vendedor_filtro_id)

    # Calcular el total de los recaudos filtrados
    total_filtrado = recaudos_list.aggregate(total=Sum('monto_recibido'))['total'] or Decimal('0.00')

    context = {
        'recaudos': recaudos_list.select_related('cliente', 'vendedor__user', 'consignacion'),
        'vendedores': vendedores_list.select_related('user'),
        'estados_posibles': Recaudo.Estado.choices,
        'total_filtrado': total_filtrado,
        'titulo': titulo,
        # Mantener los valores de los filtros para mostrarlos en los dropdowns
        'estado_actual': estado_filtro,
        'vendedor_actual_id': vendedor_filtro_id,
    }
    return render(request, 'recaudos/reporte_general_recaudos.html', context)
