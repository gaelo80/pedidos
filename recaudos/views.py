# recaudos/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test, permission_required
from django.contrib import messages
from django.db.models import Sum, Q
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import os
import base64
from django.conf import settings # Importar settings

# --- Importaciones de tus modelos ---
from .models import Recaudo, Consignacion
from .forms import RecaudoForm, ConsignacionForm
from vendedores.models import Vendedor # Importar Vendedor
from clientes.models import Empresa # Asegúrate de importar tu modelo Empresa (ej. de clientes.models)
from core.auth_utils import es_vendedor, es_administracion, es_cartera # Funciones de permisos personalizadas


# --- Función Auxiliar para el Logo Base64 (consolidada y robusta) ---
def get_logo_base_64_despacho(empresa):
    """
    Obtiene el logo de la empresa codificado en Base64 para incrustar en PDFs.
    """
    if not empresa or not empresa.logo:
        # print("Advertencia: No hay empresa o logo definido para codificar.") # Solo para depuración
        return None
    try:
        logo_path = os.path.join(settings.MEDIA_ROOT, empresa.logo.name)
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                ext = os.path.splitext(empresa.logo.name)[1].lower()
                mime_type = "image/png" # Default
                if ext == ".jpg" or ext == ".jpeg":
                    mime_type = "image/jpeg"
                elif ext == ".gif":
                    mime_type = "image/gif"
                return f"data:{mime_type};base64,{encoded_string}"
        else:
            print(f"Advertencia: Archivo de logo no encontrado en la ruta: {logo_path} para la empresa {empresa.nombre}.")
            return None
    except Exception as e:
        print(f"ERROR: Falló al codificar el logo para {empresa.nombre}: {e}")
        return None


# --- Vistas para Vendedores ---

@login_required
@user_passes_test(es_vendedor, login_url='core:acceso_denegado')
def crear_recaudo(request):
    empresa_actual = getattr(request.user, 'empresa', None) # Asumimos que el usuario tiene un campo 'empresa' o es un tenant
    if not empresa_actual:
        messages.error(request, "Su usuario no tiene una empresa asignada. Contacta al administrador.")
        return redirect('core:acceso_denegado')

    try:
        vendedor_actual = request.user.perfil_vendedor
    except Vendedor.DoesNotExist:
        messages.error(request, "Tu usuario no tiene un perfil de vendedor asociado. Contacta al administrador.")
        return redirect('core:acceso_denegado') # Redirige a acceso_denegado en lugar de index

    if request.method == 'POST':
        form = RecaudoForm(request.POST, empresa=empresa_actual)
        if form.is_valid():
            with transaction.atomic(): # Asegurar atomicidad
                recaudo = form.save(commit=False)
                recaudo.empresa = empresa_actual
                recaudo.vendedor = vendedor_actual
                recaudo.save()
            messages.success(request, f"Recaudo No. {recaudo.id} creado exitosamente.")
            return redirect('recaudos:detalle_recibo', pk=recaudo.pk)
        else:
            messages.error(request, "Por favor, corrige los errores en el formulario.") # Mensaje genérico para errores del form
    else:
        form = RecaudoForm(empresa=empresa_actual)
    context = {'form': form, 'titulo': f'Registrar Nuevo Recaudo ({empresa_actual.nombre})'}
    return render(request, 'recaudos/crear_recaudo.html', context)


@login_required
@user_passes_test(es_vendedor, login_url='core:acceso_denegado')
def lista_recaudos_vendedor(request):
    empresa_actual = getattr(request.user, 'empresa', None)
    if not empresa_actual:
        messages.error(request, "Su usuario no tiene una empresa asignada. Contacta al administrador.")
        return redirect('core:acceso_denegado')

    try:
        vendedor_actual = request.user.perfil_vendedor
    except Vendedor.DoesNotExist:
        messages.error(request, "Tu usuario no tiene un perfil de vendedor asociado. Contacta al administrador.")
        return redirect('core:acceso_denegado')

    recaudos_list = Recaudo.objects.filter(vendedor=vendedor_actual, empresa=empresa_actual).select_related('cliente', 'consignacion')
    total_en_manos = recaudos_list.filter(estado=Recaudo.Estado.EN_MANOS_DEL_VENDEDOR).aggregate(total=Sum('monto_recibido'))['total'] or Decimal('0.00')
    
    context = {
        'recaudos': recaudos_list,
        'total_en_manos': total_en_manos,
        'titulo': f'Mis Recaudos - {vendedor_actual.user.get_full_name() or vendedor_actual.user.username}',
        'empresa_nombre': empresa_actual.nombre
    }
    return render(request, 'recaudos/lista_recaudos.html', context)


@login_required
@permission_required('recaudos.view_recaudo', login_url='core:acceso_denegado')
def detalle_recibo(request, pk):
    empresa_actual = getattr(request, 'tenant', None) # Idealmente, empresa_actual viene del middleware de tenant

    # 1. Validación inicial de empresa
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa o su usuario no está asociado a una.")
        return redirect('core:acceso_denegado')

    # 2. Obtener el Recaudo (filtrando por empresa, si no es superusuario)
    # Superusuarios pueden ver cualquier recaudo (asumiendo que tiene sentido en tu modelo de negocio)
    recaudo_qs = Recaudo.objects.select_related('cliente', 'vendedor__user', 'empresa').filter(empresa=empresa_actual)
    if request.user.is_superuser:
        recaudo_qs = Recaudo.objects.select_related('cliente', 'vendedor__user', 'empresa') # Superuser ve de todas las empresas
    
    recaudo = get_object_or_404(recaudo_qs, pk=pk)

    # 3. Lógica de Permisos de Acceso al Contenido (más granular)
    user = request.user
    es_admin_o_superuser = user.is_superuser or es_administracion(user)
    es_vendedor_del_recaudo = hasattr(user, 'perfil_vendedor') and recaudo.vendedor == user.perfil_vendedor
    es_cartera_rol = es_cartera(user) # Asumo que es_cartera existe

    tiene_permiso_ver_recaudo = False
    if es_admin_o_superuser:
        tiene_permiso_ver_recaudo = True
    elif es_vendedor_del_recaudo: # Si es el vendedor que creó el recaudo
        tiene_permiso_ver_recaudo = True
    elif es_cartera_rol: # Si es de cartera, asumo que puede ver todos los recibos de su empresa
        tiene_permiso_ver_recaudo = True
    
    if not tiene_permiso_ver_recaudo:
        messages.error(request, "No tienes permiso para ver este recibo.")
        return redirect('core:acceso_denegado')

    # 4. Lógica para el Logo Base64
    logo_base64_final = None
    try:
        logo_base64_final = get_logo_base_64_despacho(recaudo.empresa) # Usamos recaudo.empresa para asegurar el logo correcto
        if not logo_base64_final:
            print(f"Advertencia: Logo no disponible para la empresa {recaudo.empresa.nombre} en el recibo {recaudo.id}.")
    except Exception as e:
        print(f"Error al codificar el logo para el recibo {recaudo.id}: {e}")

    context = {
        'recaudo': recaudo,
        'titulo': f"Detalle Recibo de Caja No. {recaudo.id}",
        'empresa_actual': recaudo.empresa, # Asegúrate de pasar el objeto Empresa del recaudo
        'logo_base64': logo_base64_final,
    }
    return render(request, 'recaudos/detalle_recibo.html', context)


@login_required
@user_passes_test(es_vendedor, login_url='core:acceso_denegado')
def crear_consignacion(request):
    empresa_actual = getattr(request.user, 'empresa', None)
    if not empresa_actual:
        messages.error(request, "Su usuario no tiene una empresa asignada. Contacta al administrador.")
        return redirect('core:acceso_denegado')
        
    try:
        vendedor_actual = request.user.perfil_vendedor
    except Vendedor.DoesNotExist:
        messages.error(request, "Tu usuario no tiene un perfil de vendedor asociado.")
        return redirect('core:acceso_denegado')
    
    recaudos_pendientes = Recaudo.objects.filter(vendedor=vendedor_actual, empresa=empresa_actual, estado=Recaudo.Estado.EN_MANOS_DEL_VENDEDOR)
    
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
            messages.error(request, "Por favor, corrige los errores en el formulario.")
    else:
        form = ConsignacionForm(vendedor=vendedor_actual, empresa=empresa_actual)
    
    context = {
        'form': form,
        'recaudos_pendientes': recaudos_pendientes,
        'titulo': f'Registrar Nueva Consignación ({empresa_actual.nombre})'
    }
    return render(request, 'recaudos/crear_consignacion.html', context)


# --- VISTAS DE ADMINISTRACIÓN Y CARTERA ---

def es_admin_o_cartera(user):
    """Función de permiso para chequear si el usuario es Admin o de Cartera."""
    return es_administracion(user) or es_cartera(user)

@login_required
@user_passes_test(es_admin_o_cartera, login_url='core:acceso_denegado')
def panel_administracion(request):
    empresa_actual = getattr(request.user, 'empresa', None)
    
    # 1. Validación inicial de empresa para usuarios no-superuser
    if not request.user.is_superuser and not empresa_actual:
        messages.error(request, "Su usuario no tiene una empresa asignada. Contacte al administrador.")
        return redirect('core:acceso_denegado')
    
    # 2. Definir el queryset base según el tipo de usuario y empresa
    consignaciones_list = Consignacion.objects.select_related('vendedor__user', 'empresa')
    if not request.user.is_superuser:
        consignaciones_list = consignaciones_list.filter(empresa=empresa_actual)
        titulo = f'Panel de Verificación ({empresa_actual.nombre})'
    else: # Superusuario
        titulo = 'Panel de Verificación (Todas las Empresas)'

    # Aplicar filtro por estado
    estado_filtro = request.GET.get('estado', Consignacion.Estado.PENDIENTE_VERIFICACION)
    if estado_filtro:
        consignaciones_list = consignaciones_list.filter(estado=estado_filtro)

    context = {
        'consignaciones': consignaciones_list,
        'titulo': titulo,
        'estado_actual': estado_filtro,
        'estados_posibles': Consignacion.Estado.choices
    }
    return render(request, 'recaudos/panel_administracion.html', context)


@login_required
@user_passes_test(es_admin_o_cartera, login_url='core:acceso_denegado')
@transaction.atomic
def verificar_consignacion(request, pk):
    # 1. Validación inicial de empresa para usuarios no-superuser
    empresa_actual = getattr(request.user, 'empresa', None)
    if not request.user.is_superuser and not empresa_actual:
        messages.error(request, "Su usuario no tiene una empresa asignada.")
        return redirect('core:acceso_denegado')

    # 2. Obtener la consignación (filtrando por empresa si no es superusuario)
    consignacion_qs = Consignacion.objects.select_related('vendedor__user', 'empresa')
    if not request.user.is_superuser:
        consignacion_qs = consignacion_qs.filter(empresa=empresa_actual)
    
    consignacion = get_object_or_404(consignacion_qs, pk=pk)

    if request.method == 'POST':
        accion = request.POST.get('accion')
        
        with transaction.atomic():
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
                # Los recaudos vuelven a EN_MANOS_DEL_VENDEDOR y se desvinculan de la consignación
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
    empresa_actual = getattr(request.user, 'empresa', None)
    
    # 1. Validación inicial de empresa para usuarios no-superuser
    if not request.user.is_superuser and not empresa_actual:
        messages.error(request, "Su usuario no tiene una empresa asignada. Contacte al administrador.")
        return redirect('core:acceso_denegado')

    # 2. Definir el queryset base según el tipo de usuario y empresa
    recaudos_list = Recaudo.objects.select_related('cliente', 'vendedor__user', 'consignacion', 'empresa')
    vendedores_list_qs = Vendedor.objects.select_related('user').filter(activo=True)

    if not request.user.is_superuser:
        recaudos_list = recaudos_list.filter(empresa=empresa_actual)
        vendedores_list_qs = vendedores_list_qs.filter(user__empresa=empresa_actual)
        titulo = f'Reporte General de Recaudos ({empresa_actual.nombre})'
    else: # Superusuario
        titulo = 'Reporte General de Recaudos (Todas las Empresas)'

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
        'recaudos': recaudos_list,
        'vendedores': vendedores_list_qs.order_by('user__first_name'), # Asegurar orden
        'estados_posibles': Recaudo.Estado.choices,
        'total_filtrado': total_filtrado,
        'titulo': titulo,
        # Mantener los valores de los filtros para mostrarlos en los dropdowns
        'estado_actual': estado_filtro,
        'vendedor_actual_id': vendedor_filtro_id,
    }
    return render(request, 'recaudos/reporte_general_recaudos.html', context)