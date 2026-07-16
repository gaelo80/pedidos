# puntoventa/views.py
import json
import openpyxl
from decimal import Decimal, InvalidOperation

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.utils import timezone

from core.auth_utils import es_cajero, es_administracion
from core.utils import render_pdf_weasyprint, get_logo_base_64_despacho
from bodega.models import Bodega, MovimientoInventario, SalidaInternaCabecera, SalidaInternaDetalle
from productos.models import Producto
from clientes.models import Cliente, Ciudad

from .models import (
    TurnoCaja, VentaPOS, DetalleVentaPOS, PagoVentaPOS, PrecioEspecialPOS,
    DevolucionCambioPOS, DetalleDevolucionPOS, DetalleEntregaCambioPOS,
)
from .forms import AbrirTurnoForm, CerrarTurnoForm

CARRITO_SESSION_KEY = 'carrito_pos'


def _puede_usar_pos(user):
    return es_cajero(user) or es_administracion(user)


def _solo_administracion(user):
    return es_administracion(user)


def _turno_abierto_del_usuario(request, empresa_actual):
    return TurnoCaja.objects.filter(
        empresa=empresa_actual, usuario_cajero=request.user, estado=TurnoCaja.EstadoTurno.ABIERTO
    ).select_related('bodega').first()


def _bloqueo_sin_turno(request, empresa_actual):
    """
    Para reportes/consultas operativas: un cajero debe tener un turno abierto
    para verlas (evita entrar a Historial/Salidas sin haber abierto caja). Un
    administrador puede consultarlas siempre, sin necesidad de operar una caja.
    Retorna un redirect si debe bloquear el acceso, o None si puede continuar.
    """
    if es_administracion(request.user):
        return None
    if _turno_abierto_del_usuario(request, empresa_actual):
        return None
    messages.warning(request, "Debes abrir un turno de caja para acceder a esta pantalla.")
    return redirect('puntoventa:abrir_turno')


def _get_carrito(request):
    return request.session.setdefault(CARRITO_SESSION_KEY, {})


def _guardar_carrito(request, carrito):
    request.session[CARRITO_SESSION_KEY] = carrito
    request.session.modified = True


def _precio_para_bodega(producto, bodega):
    """Precio a usar para este producto en esta bodega: precio de saldo si existe, si no el de catálogo."""
    especial = PrecioEspecialPOS.objects.filter(bodega=bodega, producto=producto).first()
    return especial.precio_especial if especial else producto.precio_venta


# ============================================================
# Apertura / Cierre de turno
# ============================================================

@login_required
@user_passes_test(_puede_usar_pos, login_url='core:acceso_denegado')
def abrir_turno(request):
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')

    if _turno_abierto_del_usuario(request, empresa_actual):
        return redirect('puntoventa:vender')

    if request.method == 'POST':
        form = AbrirTurnoForm(request.POST, empresa=empresa_actual)
        if form.is_valid():
            bodega = form.cleaned_data['bodega']
            if TurnoCaja.objects.filter(bodega=bodega, estado=TurnoCaja.EstadoTurno.ABIERTO).exists():
                messages.error(request, f"La bodega '{bodega.nombre}' ya tiene un turno abierto.")
            else:
                turno = TurnoCaja.objects.create(
                    empresa=empresa_actual,
                    bodega=bodega,
                    usuario_cajero=request.user,
                    saldo_inicial=form.cleaned_data['saldo_inicial'],
                )
                messages.success(request, f"Turno #{turno.pk} abierto en '{bodega.nombre}'.")
                return redirect('puntoventa:vender')
    else:
        form = AbrirTurnoForm(empresa=empresa_actual)

    context = {'form': form, 'titulo': 'Abrir Turno de Caja'}
    return render(request, 'puntoventa/abrir_turno.html', context)


@login_required
@user_passes_test(_puede_usar_pos, login_url='core:acceso_denegado')
def cerrar_turno(request):
    empresa_actual = getattr(request, 'tenant', None)
    turno = _turno_abierto_del_usuario(request, empresa_actual)
    if not turno:
        messages.warning(request, "No tienes ningún turno abierto para cerrar.")
        return redirect('puntoventa:abrir_turno')

    if request.method == 'POST':
        form = CerrarTurnoForm(request.POST)
        if form.is_valid():
            saldo_contado = form.cleaned_data['saldo_final_contado']
            saldo_esperado = turno.saldo_esperado()
            turno.saldo_final_contado = saldo_contado
            turno.diferencia = saldo_contado - saldo_esperado
            turno.fecha_cierre = timezone.now()
            turno.estado = TurnoCaja.EstadoTurno.CERRADO
            turno.save()
            request.session.pop(CARRITO_SESSION_KEY, None)
            messages.success(request, f"Turno #{turno.pk} cerrado. Diferencia: ${turno.diferencia}")
            return redirect('puntoventa:detalle_turno', pk=turno.pk)
    else:
        form = CerrarTurnoForm()

    context = {
        'form': form,
        'turno': turno,
        'saldo_esperado': turno.saldo_esperado(),
        'total_ventas': turno.total_ventas(),
        'totales_por_metodo': turno.totales_por_metodo_pago(),
        'total_reembolsos_efectivo': turno.total_reembolsos_efectivo(),
        'total_cobros_adicionales_efectivo': turno.total_cobros_adicionales_efectivo(),
        'titulo': f'Cerrar Turno #{turno.pk}',
    }
    return render(request, 'puntoventa/cerrar_turno.html', context)


@login_required
@user_passes_test(_puede_usar_pos, login_url='core:acceso_denegado')
def detalle_turno(request, pk):
    empresa_actual = getattr(request, 'tenant', None)
    turno = get_object_or_404(TurnoCaja.objects.select_related('bodega', 'usuario_cajero'), pk=pk, empresa=empresa_actual)
    ventas = turno.ventas.filter(estado=VentaPOS.EstadoVenta.COMPLETADA).prefetch_related('pagos').order_by('-fecha_hora')
    devoluciones = turno.devoluciones_cambios.select_related('venta_original').prefetch_related(
        'detalles_devueltos__detalle_venta_original__producto', 'detalles_entregados__producto'
    ).order_by('-fecha_hora')

    context = {
        'turno': turno,
        'ventas': ventas,
        'devoluciones': devoluciones,
        'totales_por_metodo': turno.totales_por_metodo_pago(),
        'total_reembolsos_efectivo': turno.total_reembolsos_efectivo(),
        'total_cobros_adicionales_efectivo': turno.total_cobros_adicionales_efectivo(),
        'saldo_esperado': turno.saldo_esperado(),
        'titulo': f'Turno #{turno.pk}',
    }
    return render(request, 'puntoventa/detalle_turno.html', context)


@login_required
@user_passes_test(_puede_usar_pos, login_url='core:acceso_denegado')
def informe_cierre_turno(request, pk):
    """Informe imprimible (PDF) de lo que se deja en caja: desglose completo del turno."""
    empresa_actual = getattr(request, 'tenant', None)
    turno = get_object_or_404(
        TurnoCaja.objects.select_related('bodega', 'usuario_cajero'), pk=pk, empresa=empresa_actual
    )
    ventas = turno.ventas.filter(estado=VentaPOS.EstadoVenta.COMPLETADA).prefetch_related('pagos').order_by('fecha_hora')
    devoluciones = turno.devoluciones_cambios.select_related('venta_original').order_by('fecha_hora')

    context = {
        'turno': turno,
        'ventas': ventas,
        'devoluciones': devoluciones,
        'totales_por_metodo': turno.totales_por_metodo_pago(),
        'total_reembolsos_efectivo': turno.total_reembolsos_efectivo(),
        'total_cobros_adicionales_efectivo': turno.total_cobros_adicionales_efectivo(),
        'saldo_esperado': turno.saldo_esperado(),
        'empresa': empresa_actual,
        'logo_base64': get_logo_base_64_despacho(empresa=empresa_actual),
        'fecha_generacion': timezone.now(),
    }
    return render_pdf_weasyprint(request, 'puntoventa/informe_cierre_turno.html', context, filename_prefix=f"Cierre_Turno_{turno.pk}")


# ============================================================
# Pantalla de venta
# ============================================================

@login_required
@user_passes_test(_puede_usar_pos, login_url='core:acceso_denegado')
def vista_venta(request):
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')

    turno = _turno_abierto_del_usuario(request, empresa_actual)
    if not turno:
        messages.warning(request, "Debes abrir un turno de caja antes de vender.")
        return redirect('puntoventa:abrir_turno')

    context = {
        'turno': turno,
        'metodos_pago': PagoVentaPOS.MetodoPago.choices,
        'titulo': 'Punto de Venta',
    }
    return render(request, 'puntoventa/vender.html', context)


@login_required
@user_passes_test(_puede_usar_pos, login_url='core:acceso_denegado')
def api_buscar_producto_venta(request):
    """Busca productos con stock en la bodega del turno abierto del cajero."""
    empresa_actual = getattr(request, 'tenant', None)
    turno = _turno_abierto_del_usuario(request, empresa_actual)
    if not turno:
        return JsonResponse({'productos': []})

    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'productos': []})

    productos = Producto.objects.filter(
        empresa=empresa_actual, activo=True
    ).filter(
        Q(referencia__icontains=query) | Q(nombre__icontains=query) | Q(codigo_barras__icontains=query)
    ).annotate(
        stock_bodega=Coalesce(Sum('movimientos__cantidad', filter=Q(movimientos__bodega=turno.bodega)), 0)
    ).filter(stock_bodega__gt=0).order_by('referencia', 'color', 'talla')[:20]

    resultados = []
    for p in productos:
        resultados.append({
            'id': p.pk,
            'label': f"{p.referencia} - {p.nombre} ({p.color or '-'} - Talla {p.talla or '-'})",
            'precio': str(_precio_para_bodega(p, turno.bodega)),
            'stock': p.stock_bodega,
        })

    return JsonResponse({'productos': resultados})


@login_required
@user_passes_test(_puede_usar_pos, login_url='core:acceso_denegado')
def api_buscar_cliente_venta(request):
    empresa_actual = getattr(request, 'tenant', None)
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'clientes': []})

    clientes = Cliente.objects.filter(
        empresa=empresa_actual, activo=True
    ).filter(
        Q(nombre_completo__icontains=query) | Q(identificacion__icontains=query)
    ).order_by('nombre_completo')[:20]

    return JsonResponse({'clientes': [{'id': c.pk, 'label': f"{c.nombre_completo} ({c.identificacion})"} for c in clientes]})


@login_required
@user_passes_test(_puede_usar_pos, login_url='core:acceso_denegado')
@require_POST
def api_cliente_rapido(request):
    """
    Crea un cliente al vuelo con datos mínimos cuando no está registrado.
    Todos los campos son opcionales salvo el nombre.
    """
    empresa_actual = getattr(request, 'tenant', None)
    try:
        data = json.loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({'status': 'error', 'msg': 'Datos inválidos.'}, status=400)

    nombre = (data.get('nombre_completo') or '').strip()
    if not nombre:
        return JsonResponse({'status': 'error', 'msg': 'El nombre del cliente es obligatorio.'}, status=400)

    identificacion = (data.get('identificacion') or '').strip() or None
    telefono = (data.get('telefono') or '').strip() or None
    direccion = (data.get('direccion') or '').strip() or None
    email = (data.get('email') or '').strip() or None

    if identificacion:
        existente = Cliente.objects.filter(empresa=empresa_actual, identificacion=identificacion).first()
        if existente:
            return JsonResponse({
                'status': 'ok',
                'cliente': {'id': existente.pk, 'label': f"{existente.nombre_completo} ({existente.identificacion})"},
                'msg': 'Ya existía un cliente con esa identificación; se usó el registro existente.',
            })

    # Cliente.ciudad es obligatorio a nivel de modelo/BD, pero en una venta de mostrador
    # no tiene sentido pedirle la ciudad al cajero. Se usa una ciudad genérica placeholder.
    ciudad_generica, _ = Ciudad.objects.get_or_create(nombre='Sin Especificar')

    cliente = Cliente.objects.create(
        empresa=empresa_actual,
        nombre_completo=nombre,
        identificacion=identificacion,
        telefono=telefono,
        direccion=direccion,
        email=email,
        ciudad=ciudad_generica,
    )
    return JsonResponse({
        'status': 'ok',
        'cliente': {'id': cliente.pk, 'label': f"{cliente.nombre_completo} ({cliente.identificacion or 'Sin ID'})"},
    })


@login_required
@user_passes_test(_puede_usar_pos, login_url='core:acceso_denegado')
@require_POST
def api_carrito_agregar(request):
    empresa_actual = getattr(request, 'tenant', None)
    turno = _turno_abierto_del_usuario(request, empresa_actual)
    if not turno:
        return JsonResponse({'status': 'error', 'msg': 'No tienes un turno abierto.'}, status=400)

    try:
        data = json.loads(request.body)
        producto_id = int(data['producto_id'])
        cantidad = int(data.get('cantidad', 1))
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'status': 'error', 'msg': 'Datos inválidos.'}, status=400)

    if cantidad <= 0:
        return JsonResponse({'status': 'error', 'msg': 'La cantidad debe ser mayor a cero.'}, status=400)

    producto = get_object_or_404(Producto, pk=producto_id, empresa=empresa_actual, activo=True)

    carrito = _get_carrito(request)
    linea = carrito.get(str(producto_id), {'cantidad': 0, 'precio_unitario': None})
    carrito[str(producto_id)] = {
        'cantidad': linea['cantidad'] + cantidad,
        'precio_unitario': linea.get('precio_unitario') or str(_precio_para_bodega(producto, turno.bodega)),
        'precio_override': linea.get('precio_override'),
        'motivo_override': linea.get('motivo_override'),
    }
    _guardar_carrito(request, carrito)

    return JsonResponse({'status': 'ok', 'carrito': _resumen_carrito(carrito)})


@login_required
@user_passes_test(_puede_usar_pos, login_url='core:acceso_denegado')
@require_POST
def api_carrito_ajustar_precio(request):
    """Ajuste manual de precio para una línea del carrito. Requiere motivo obligatorio."""
    try:
        data = json.loads(request.body)
        producto_id = str(int(data['producto_id']))
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'status': 'error', 'msg': 'Datos inválidos.'}, status=400)

    carrito = _get_carrito(request)
    if producto_id not in carrito:
        return JsonResponse({'status': 'error', 'msg': 'Ese producto no está en el carrito.'}, status=404)

    precio_nuevo_raw = data.get('precio_nuevo')
    if precio_nuevo_raw in (None, ''):
        # Quitar el ajuste y volver al precio original (catálogo o saldo).
        carrito[producto_id]['precio_override'] = None
        carrito[producto_id]['motivo_override'] = None
    else:
        try:
            precio_nuevo = Decimal(str(precio_nuevo_raw))
        except InvalidOperation:
            return JsonResponse({'status': 'error', 'msg': 'Precio inválido.'}, status=400)
        motivo = (data.get('motivo') or '').strip()
        if precio_nuevo <= 0:
            return JsonResponse({'status': 'error', 'msg': 'El precio debe ser mayor a cero.'}, status=400)
        if not motivo:
            return JsonResponse({'status': 'error', 'msg': 'Debes indicar un motivo para ajustar el precio.'}, status=400)
        carrito[producto_id]['precio_override'] = str(precio_nuevo)
        carrito[producto_id]['motivo_override'] = motivo

    _guardar_carrito(request, carrito)
    return JsonResponse({'status': 'ok', 'carrito': _resumen_carrito(carrito)})


@login_required
@user_passes_test(_puede_usar_pos, login_url='core:acceso_denegado')
@require_POST
def api_carrito_actualizar(request):
    try:
        data = json.loads(request.body)
        producto_id = str(int(data['producto_id']))
        cantidad = int(data.get('cantidad', 0))
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'status': 'error', 'msg': 'Datos inválidos.'}, status=400)

    carrito = _get_carrito(request)
    if producto_id not in carrito:
        return JsonResponse({'status': 'error', 'msg': 'Ese producto no está en el carrito.'}, status=404)

    if cantidad <= 0:
        del carrito[producto_id]
    else:
        carrito[producto_id]['cantidad'] = cantidad
    _guardar_carrito(request, carrito)

    return JsonResponse({'status': 'ok', 'carrito': _resumen_carrito(carrito)})


@login_required
@user_passes_test(_puede_usar_pos, login_url='core:acceso_denegado')
@require_POST
def api_carrito_vaciar(request):
    _guardar_carrito(request, {})
    return JsonResponse({'status': 'ok', 'carrito': _resumen_carrito({})})


def _resumen_carrito(carrito):
    if not carrito:
        return {'lineas': [], 'total': '0.00'}

    productos_map = {p.pk: p for p in Producto.objects.filter(pk__in=[int(k) for k in carrito.keys()])}
    lineas = []
    total = Decimal('0.00')
    for producto_id, datos in carrito.items():
        producto = productos_map.get(int(producto_id))
        if not producto:
            continue
        precio_original = Decimal(datos['precio_unitario'])
        override = datos.get('precio_override')
        precio_final = Decimal(override) if override is not None else precio_original
        cantidad = datos['cantidad']
        subtotal = precio_final * cantidad
        total += subtotal
        lineas.append({
            'producto_id': producto.pk,
            'label': f"{producto.referencia} - {producto.nombre} ({producto.color or '-'} - Talla {producto.talla or '-'})",
            'cantidad': cantidad,
            'precio_unitario': str(precio_original),
            'precio_override': str(override) if override is not None else None,
            'motivo_override': datos.get('motivo_override'),
            'precio_final': str(precio_final),
            'subtotal': str(subtotal),
        })
    return {'lineas': lineas, 'total': str(total)}


@login_required
@user_passes_test(_puede_usar_pos, login_url='core:acceso_denegado')
def api_carrito_estado(request):
    return JsonResponse({'status': 'ok', 'carrito': _resumen_carrito(_get_carrito(request))})


@login_required
@user_passes_test(_puede_usar_pos, login_url='core:acceso_denegado')
@require_POST
def api_checkout(request):
    empresa_actual = getattr(request, 'tenant', None)
    turno = _turno_abierto_del_usuario(request, empresa_actual)
    if not turno:
        return JsonResponse({'status': 'error', 'msg': 'No tienes un turno abierto.'}, status=400)

    carrito = _get_carrito(request)
    if not carrito:
        return JsonResponse({'status': 'error', 'msg': 'El carrito está vacío.'}, status=400)

    try:
        data = json.loads(request.body)
        cliente_id = data.get('cliente_id')
        pagos_data = data['pagos']
        notas = (data.get('notas') or '').strip()
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'status': 'error', 'msg': 'Datos de pago inválidos.'}, status=400)

    if not pagos_data:
        return JsonResponse({'status': 'error', 'msg': 'Debes indicar al menos un método de pago.'}, status=400)

    metodos_validos = {c[0] for c in PagoVentaPOS.MetodoPago.choices}
    total_pagado = Decimal('0.00')
    pagos_limpios = []
    for pago in pagos_data:
        metodo = pago.get('metodo_pago')
        try:
            monto = Decimal(str(pago.get('monto', '0')))
        except InvalidOperation:
            return JsonResponse({'status': 'error', 'msg': 'Monto de pago inválido.'}, status=400)
        if metodo not in metodos_validos or monto <= 0:
            return JsonResponse({'status': 'error', 'msg': 'Método o monto de pago inválido.'}, status=400)

        monto_recibido = None
        recibido_raw = pago.get('monto_recibido')
        if recibido_raw not in (None, ''):
            try:
                monto_recibido = Decimal(str(recibido_raw))
            except InvalidOperation:
                return JsonResponse({'status': 'error', 'msg': 'Monto recibido inválido.'}, status=400)
            if metodo != PagoVentaPOS.MetodoPago.EFECTIVO:
                return JsonResponse({'status': 'error', 'msg': 'El monto recibido solo aplica a pagos en efectivo.'}, status=400)
            if monto_recibido < monto:
                return JsonResponse({'status': 'error', 'msg': 'El monto recibido no puede ser menor al monto del pago.'}, status=400)

        total_pagado += monto
        pagos_limpios.append({'metodo_pago': metodo, 'monto': monto, 'monto_recibido': monto_recibido})

    cliente = None
    if cliente_id:
        cliente = get_object_or_404(Cliente, pk=cliente_id, empresa=empresa_actual)

    productos_map = {p.pk: p for p in Producto.objects.filter(pk__in=[int(k) for k in carrito.keys()], empresa=empresa_actual)}

    total_carrito = Decimal('0.00')
    for producto_id, datos in carrito.items():
        producto = productos_map.get(int(producto_id))
        if not producto:
            return JsonResponse({'status': 'error', 'msg': 'Uno de los productos del carrito ya no existe.'}, status=400)
        override = datos.get('precio_override')
        precio_final = Decimal(override) if override is not None else Decimal(datos['precio_unitario'])
        total_carrito += precio_final * datos['cantidad']

    if total_pagado != total_carrito:
        return JsonResponse({
            'status': 'error',
            'msg': f"La suma de los pagos (${total_pagado}) no coincide con el total de la venta (${total_carrito})."
        }, status=400)

    # Validar stock disponible en la bodega del turno para cada línea
    errores_stock = []
    for producto_id, datos in carrito.items():
        producto = productos_map[int(producto_id)]
        stock_en_bodega = MovimientoInventario.objects.filter(
            producto=producto, bodega=turno.bodega
        ).aggregate(total=Sum('cantidad'))['total'] or 0
        if stock_en_bodega < datos['cantidad']:
            errores_stock.append(f"'{producto}': disponible {stock_en_bodega}, solicitado {datos['cantidad']}.")

    if errores_stock:
        return JsonResponse({'status': 'error', 'msg': 'Stock insuficiente: ' + ' | '.join(errores_stock)}, status=400)

    with transaction.atomic():
        venta = VentaPOS.objects.create(
            empresa=empresa_actual,
            turno=turno,
            cliente=cliente,
            total_venta=total_carrito,
            notas=notas or None,
        )

        for producto_id, datos in carrito.items():
            producto = productos_map[int(producto_id)]
            cantidad = datos['cantidad']
            precio_unitario = Decimal(datos['precio_unitario'])
            override = datos.get('precio_override')
            precio_override = Decimal(override) if override is not None else None
            precio_final = precio_override if precio_override is not None else precio_unitario

            DetalleVentaPOS.objects.create(
                venta=venta,
                producto=producto,
                cantidad=cantidad,
                precio_unitario=precio_unitario,
                precio_override=precio_override,
                motivo_override=datos.get('motivo_override') if precio_override is not None else None,
                subtotal=precio_final * cantidad,
            )

            MovimientoInventario.objects.create(
                empresa=empresa_actual,
                producto=producto,
                bodega=turno.bodega,
                cantidad=-cantidad,
                tipo_movimiento='SALIDA_VENTA_POS',
                documento_referencia=f"VentaPOS #{venta.consecutivo}",
                usuario=request.user,
                notas=f"Venta de mostrador #{venta.consecutivo} - Turno #{turno.pk}",
            )

        pagos_creados = []
        for pago in pagos_limpios:
            pago_obj = PagoVentaPOS.objects.create(
                venta=venta, metodo_pago=pago['metodo_pago'], monto=pago['monto'],
                monto_recibido=pago['monto_recibido'],
            )
            pagos_creados.append({'pago_id': pago_obj.pk, 'metodo_pago': pago_obj.metodo_pago})

    _guardar_carrito(request, {})

    return JsonResponse({
        'status': 'ok',
        'venta_id': venta.pk,
        'consecutivo': venta.consecutivo,
        'recibo_url': reverse('puntoventa:recibo_venta', kwargs={'pk': venta.pk}),
        'pagos_creados': pagos_creados,
    })


# ============================================================
# Recibo
# ============================================================

@login_required
@user_passes_test(_puede_usar_pos, login_url='core:acceso_denegado')
def recibo_venta(request, pk):
    empresa_actual = getattr(request, 'tenant', None)
    venta = get_object_or_404(
        VentaPOS.objects.select_related('cliente', 'turno', 'turno__bodega', 'turno__usuario_cajero'),
        pk=pk, empresa=empresa_actual
    )
    detalles = venta.detalles.select_related('producto').all()
    pagos = venta.pagos.all()

    formato = request.GET.get('formato', 'termico')
    template = 'puntoventa/recibo_termico.html' if formato == 'termico' else 'puntoventa/recibo_estandar.html'

    context = {
        'venta': venta,
        'detalles': detalles,
        'pagos': pagos,
        'empresa': empresa_actual,
        'logo_base64': get_logo_base_64_despacho(empresa=empresa_actual),
        'fecha_generacion': timezone.now(),
    }
    return render_pdf_weasyprint(request, template, context, filename_prefix=f"Recibo_POS_{venta.consecutivo}")


@login_required
@user_passes_test(_puede_usar_pos, login_url='core:acceso_denegado')
@require_POST
def api_pago_subir_comprobante(request):
    """Adjunta la foto del comprobante a un pago por transferencia ya registrado."""
    empresa_actual = getattr(request, 'tenant', None)
    pago_id = request.POST.get('pago_id')
    archivo = request.FILES.get('archivo')

    if not pago_id or not archivo:
        return JsonResponse({'status': 'error', 'msg': 'Falta el pago o el archivo.'}, status=400)

    pago = get_object_or_404(PagoVentaPOS, pk=pago_id, venta__empresa=empresa_actual)
    if pago.metodo_pago != PagoVentaPOS.MetodoPago.TRANSFERENCIA:
        return JsonResponse({'status': 'error', 'msg': 'Solo se puede adjuntar comprobante a pagos por transferencia.'}, status=400)

    pago.comprobante_transferencia = archivo
    pago.save(update_fields=['comprobante_transferencia'])
    return JsonResponse({'status': 'ok', 'comprobante_url': pago.comprobante_transferencia.url})


# ============================================================
# Precios de saldo (admin)
# ============================================================

@login_required
@user_passes_test(_solo_administracion, login_url='core:acceso_denegado')
def gestionar_precios_pos(request):
    empresa_actual = getattr(request, 'tenant', None)
    bodegas_pos = Bodega.objects.filter(empresa=empresa_actual, tipo=Bodega.TipoBodega.PUNTO_VENTA, activa=True).order_by('nombre')

    bodega_seleccionada = bodegas_pos.filter(pk=request.GET.get('bodega')).first() or bodegas_pos.first()

    context = {
        'bodegas_pos': bodegas_pos,
        'bodega_seleccionada': bodega_seleccionada,
        'titulo': 'Precios de Saldo (Punto de Venta)',
    }
    return render(request, 'puntoventa/gestionar_precios.html', context)


@login_required
@user_passes_test(_solo_administracion, login_url='core:acceso_denegado')
def api_buscar_producto_precios(request):
    empresa_actual = getattr(request, 'tenant', None)
    bodega = get_object_or_404(Bodega, pk=request.GET.get('bodega_id'), empresa=empresa_actual)

    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'productos': []})

    productos = Producto.objects.filter(
        empresa=empresa_actual, activo=True
    ).filter(
        Q(referencia__icontains=query) | Q(nombre__icontains=query) | Q(codigo_barras__icontains=query)
    ).annotate(
        stock_bodega=Coalesce(Sum('movimientos__cantidad', filter=Q(movimientos__bodega=bodega)), 0)
    ).filter(stock_bodega__gt=0).order_by('referencia', 'color', 'talla')[:20]

    especiales = {pe.producto_id: pe for pe in PrecioEspecialPOS.objects.filter(bodega=bodega, producto__in=productos)}

    resultados = []
    for p in productos:
        especial = especiales.get(p.pk)
        resultados.append({
            'id': p.pk,
            'label': f"{p.referencia} - {p.nombre} ({p.color or '-'} - Talla {p.talla or '-'})",
            'precio_catalogo': str(p.precio_venta),
            'precio_especial': str(especial.precio_especial) if especial else None,
            'stock': p.stock_bodega,
        })
    return JsonResponse({'productos': resultados})


@login_required
@user_passes_test(_solo_administracion, login_url='core:acceso_denegado')
@require_POST
def api_precio_especial_guardar(request):
    empresa_actual = getattr(request, 'tenant', None)
    try:
        data = json.loads(request.body)
        producto_id = int(data['producto_id'])
        bodega_id = int(data['bodega_id'])
        precio_especial = Decimal(str(data['precio_especial']))
    except (ValueError, KeyError, TypeError, InvalidOperation):
        return JsonResponse({'status': 'error', 'msg': 'Datos inválidos.'}, status=400)

    if precio_especial <= 0:
        return JsonResponse({'status': 'error', 'msg': 'El precio debe ser mayor a cero.'}, status=400)

    producto = get_object_or_404(Producto, pk=producto_id, empresa=empresa_actual)
    bodega = get_object_or_404(Bodega, pk=bodega_id, empresa=empresa_actual, tipo=Bodega.TipoBodega.PUNTO_VENTA)

    precio_obj, _creado = PrecioEspecialPOS.objects.update_or_create(
        bodega=bodega, producto=producto,
        defaults={'precio_especial': precio_especial, 'usuario_actualizacion': request.user, 'empresa': empresa_actual},
    )
    return JsonResponse({'status': 'ok', 'precio_especial': str(precio_obj.precio_especial)})


@login_required
@user_passes_test(_solo_administracion, login_url='core:acceso_denegado')
@require_POST
def api_precio_especial_eliminar(request):
    empresa_actual = getattr(request, 'tenant', None)
    try:
        data = json.loads(request.body)
        producto_id = int(data['producto_id'])
        bodega_id = int(data['bodega_id'])
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'status': 'error', 'msg': 'Datos inválidos.'}, status=400)

    PrecioEspecialPOS.objects.filter(empresa=empresa_actual, producto_id=producto_id, bodega_id=bodega_id).delete()
    return JsonResponse({'status': 'ok'})


# ============================================================
# Historial de ventas e informes
# ============================================================

def _ventas_filtradas(request, empresa_actual):
    ventas = VentaPOS.objects.filter(empresa=empresa_actual).select_related(
        'cliente', 'turno', 'turno__bodega', 'turno__usuario_cajero'
    ).prefetch_related('pagos')

    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    consecutivo = request.GET.get('consecutivo')
    cliente_q = request.GET.get('cliente')
    cajero_id = request.GET.get('cajero')
    bodega_id = request.GET.get('bodega')

    if fecha_desde:
        ventas = ventas.filter(fecha_hora__date__gte=fecha_desde)
    if fecha_hasta:
        ventas = ventas.filter(fecha_hora__date__lte=fecha_hasta)
    if consecutivo:
        ventas = ventas.filter(consecutivo=consecutivo)
    if cliente_q:
        ventas = ventas.filter(cliente__nombre_completo__icontains=cliente_q)
    if cajero_id:
        ventas = ventas.filter(turno__usuario_cajero_id=cajero_id)
    if bodega_id:
        ventas = ventas.filter(turno__bodega_id=bodega_id)

    return ventas.order_by('-fecha_hora')


@login_required
@user_passes_test(_puede_usar_pos, login_url='core:acceso_denegado')
def historial_ventas(request):
    empresa_actual = getattr(request, 'tenant', None)
    bloqueo = _bloqueo_sin_turno(request, empresa_actual)
    if bloqueo:
        return bloqueo
    ventas = _ventas_filtradas(request, empresa_actual)

    paginator = Paginator(ventas, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    U = get_user_model()
    context = {
        'page_obj': page_obj,
        'ventas': page_obj.object_list,
        'cajeros': U.objects.filter(turnos_caja_abiertos__empresa=empresa_actual).distinct().order_by('username'),
        'bodegas_pos': Bodega.objects.filter(empresa=empresa_actual, tipo=Bodega.TipoBodega.PUNTO_VENTA),
        'filtros': request.GET,
        'titulo': 'Historial de Ventas - Punto de Venta',
    }
    return render(request, 'puntoventa/historial_ventas.html', context)


@login_required
@user_passes_test(_solo_administracion, login_url='core:acceso_denegado')
def exportar_historial_excel(request):
    empresa_actual = getattr(request, 'tenant', None)
    ventas = _ventas_filtradas(request, empresa_actual)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Historial POS'
    ws.append(['Consecutivo', 'Fecha', 'Bodega', 'Cajero', 'Cliente', 'Total', 'Métodos de Pago', 'Estado'])

    for venta in ventas:
        metodos = ', '.join(f"{p.get_metodo_pago_display()}: ${p.monto}" for p in venta.pagos.all())
        ws.append([
            venta.consecutivo,
            venta.fecha_hora.strftime('%Y-%m-%d %H:%M'),
            venta.turno.bodega.nombre,
            venta.turno.usuario_cajero.get_full_name() or venta.turno.usuario_cajero.username,
            venta.cliente.nombre_completo if venta.cliente else 'Mostrador',
            float(venta.total_venta),
            metodos,
            venta.get_estado_display(),
        ])

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="historial_ventas_pos.xlsx"'
    wb.save(response)
    return response


# ============================================================
# Consulta de inventario (cajero)
# ============================================================

@login_required
@user_passes_test(_puede_usar_pos, login_url='core:acceso_denegado')
def consulta_inventario_pos(request):
    empresa_actual = getattr(request, 'tenant', None)
    turno = _turno_abierto_del_usuario(request, empresa_actual)
    if not turno:
        messages.warning(request, "Debes abrir un turno de caja para consultar el inventario de tu bodega.")
        return redirect('puntoventa:abrir_turno')

    query = request.GET.get('q', '').strip()
    productos = Producto.objects.filter(empresa=empresa_actual, activo=True).annotate(
        stock_bodega=Coalesce(Sum('movimientos__cantidad', filter=Q(movimientos__bodega=turno.bodega)), 0)
    ).filter(stock_bodega__gt=0)

    if query:
        productos = productos.filter(
            Q(referencia__icontains=query) | Q(nombre__icontains=query) | Q(codigo_barras__icontains=query)
        )
    productos = productos.order_by('referencia', 'color', 'talla')

    paginator = Paginator(productos, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    especiales = {
        pe.producto_id: pe.precio_especial
        for pe in PrecioEspecialPOS.objects.filter(bodega=turno.bodega, producto__in=page_obj.object_list)
    }
    filas = []
    for p in page_obj.object_list:
        filas.append({
            'producto': p,
            'stock': p.stock_bodega,
            'precio': especiales.get(p.pk, p.precio_venta),
            'es_saldo': p.pk in especiales,
        })

    context = {
        'turno': turno,
        'filas': filas,
        'page_obj': page_obj,
        'query': query,
        'titulo': 'Consulta de Inventario - Mi Bodega',
    }
    return render(request, 'puntoventa/consulta_inventario.html', context)


# ============================================================
# Salidas internas desde el Punto de Venta (préstamos, a persona/empresa, baja, etc.)
# ============================================================

@login_required
@user_passes_test(_puede_usar_pos, login_url='core:acceso_denegado')
def registrar_salida_pos(request):
    empresa_actual = getattr(request, 'tenant', None)
    turno = _turno_abierto_del_usuario(request, empresa_actual)
    if not turno:
        messages.warning(request, "Debes abrir un turno de caja para registrar una salida.")
        return redirect('puntoventa:abrir_turno')

    if request.method == 'POST':
        tipo_salida = request.POST.get('tipo_salida')
        destino_descripcion = (request.POST.get('destino_descripcion') or '').strip()
        observaciones_salida = (request.POST.get('observaciones_salida') or '').strip()

        tipos_validos = {c[0] for c in SalidaInternaCabecera.TIPO_SALIDA_CHOICES}
        if tipo_salida not in tipos_validos:
            messages.error(request, "Tipo de salida inválido.")
            return redirect('puntoventa:registrar_salida_pos')
        if not destino_descripcion:
            messages.error(request, "Debes indicar a quién / dónde va la salida.")
            return redirect('puntoventa:registrar_salida_pos')

        try:
            items = json.loads(request.POST.get('items_json', '[]'))
        except ValueError:
            items = []
        if not items:
            messages.error(request, "Debes agregar al menos un producto a la salida.")
            return redirect('puntoventa:registrar_salida_pos')

        productos_map = {p.pk: p for p in Producto.objects.filter(
            empresa=empresa_actual, pk__in=[int(i['producto_id']) for i in items]
        )}

        errores_stock = []
        for item in items:
            producto = productos_map.get(int(item['producto_id']))
            cantidad = int(item['cantidad'])
            if not producto or cantidad <= 0:
                continue
            stock_en_bodega = MovimientoInventario.objects.filter(
                producto=producto, bodega=turno.bodega
            ).aggregate(total=Sum('cantidad'))['total'] or 0
            if stock_en_bodega < cantidad:
                errores_stock.append(f"'{producto}': disponible {stock_en_bodega} en '{turno.bodega.nombre}', solicitado {cantidad}.")

        if errores_stock:
            for error in errores_stock:
                messages.error(request, error)
            return redirect('puntoventa:registrar_salida_pos')

        with transaction.atomic():
            cabecera = SalidaInternaCabecera.objects.create(
                empresa=empresa_actual,
                tipo_salida=tipo_salida,
                destino_descripcion=destino_descripcion,
                responsable_entrega=request.user,
                bodega_origen=turno.bodega,
                observaciones_salida=observaciones_salida or None,
                estado='CERRADA' if tipo_salida == 'DONACION_BAJA' else 'DESPACHADA',
            )
            tipo_mov_map = {
                'MUESTRARIO': 'SALIDA_MUESTRARIO',
                'EXHIBIDOR': 'SALIDA_EXHIBIDOR',
                'TRASLADO_INTERNO': 'SALIDA_TRASLADO',
                'PRESTAMO': 'SALIDA_PRESTAMO',
                'DONACION_BAJA': 'SALIDA_DONACION_BAJA',
                'OTRO': 'SALIDA_INTERNA_OTRA',
            }
            tipo_mov_str = tipo_mov_map.get(tipo_salida, 'SALIDA_INTERNA_OTRA')

            for item in items:
                producto = productos_map.get(int(item['producto_id']))
                cantidad = int(item['cantidad'])
                if not producto or cantidad <= 0:
                    continue
                SalidaInternaDetalle.objects.create(
                    cabecera_salida=cabecera, producto=producto, cantidad_despachada=cantidad,
                )
                MovimientoInventario.objects.get_or_create(
                    empresa=empresa_actual, producto=producto, bodega=turno.bodega,
                    tipo_movimiento=tipo_mov_str,
                    documento_referencia=f"SalidaInt #{cabecera.pk}-{producto.pk}",
                    defaults={
                        'cantidad': -cantidad,
                        'usuario': request.user,
                        'notas': f"Salida por {cabecera.get_tipo_salida_display()} a {destino_descripcion} (Punto de Venta)",
                    }
                )

        messages.success(request, f"Salida #{cabecera.pk} registrada correctamente desde '{turno.bodega.nombre}'.")
        return redirect('puntoventa:lista_salidas_pos')

    context = {
        'turno': turno,
        'tipos_salida': SalidaInternaCabecera.TIPO_SALIDA_CHOICES,
        'titulo': 'Registrar Salida (Punto de Venta)',
    }
    return render(request, 'puntoventa/registrar_salida.html', context)


@login_required
@user_passes_test(_puede_usar_pos, login_url='core:acceso_denegado')
def lista_salidas_pos(request):
    empresa_actual = getattr(request, 'tenant', None)
    bloqueo = _bloqueo_sin_turno(request, empresa_actual)
    if bloqueo:
        return bloqueo
    salidas = SalidaInternaCabecera.objects.filter(
        empresa=empresa_actual, bodega_origen__tipo=Bodega.TipoBodega.PUNTO_VENTA
    ).select_related('bodega_origen', 'responsable_entrega').prefetch_related('detalles__producto').order_by('-fecha_hora_salida')

    paginator = Paginator(salidas, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'salidas': page_obj.object_list,
        'titulo': 'Salidas Registradas - Punto de Venta',
    }
    return render(request, 'puntoventa/lista_salidas.html', context)


# ============================================================
# Devoluciones y cambios de producto en el Punto de Venta
# ============================================================

@login_required
@user_passes_test(_puede_usar_pos, login_url='core:acceso_denegado')
def api_buscar_venta_pos(request):
    """Busca una VentaPOS por su consecutivo, con el detalle de cuánto de cada línea aún se puede devolver."""
    empresa_actual = getattr(request, 'tenant', None)
    consecutivo = request.GET.get('consecutivo', '').strip()
    if not consecutivo:
        return JsonResponse({'status': 'error', 'msg': 'Indica el número de recibo.'}, status=400)

    venta = VentaPOS.objects.filter(
        empresa=empresa_actual, consecutivo=consecutivo, estado=VentaPOS.EstadoVenta.COMPLETADA
    ).select_related('cliente', 'turno__bodega').first()
    if not venta:
        return JsonResponse({'status': 'error', 'msg': f'No se encontró una venta completada con el recibo #{consecutivo}.'}, status=404)

    detalles = []
    for d in venta.detalles.select_related('producto').all():
        ya_devuelto = DetalleDevolucionPOS.objects.filter(detalle_venta_original=d).aggregate(t=Sum('cantidad'))['t'] or 0
        disponible = d.cantidad - ya_devuelto
        if disponible <= 0:
            continue
        detalles.append({
            'detalle_id': d.pk,
            'label': f"{d.producto.referencia} - {d.producto.nombre} ({d.producto.color or '-'} - Talla {d.producto.talla or '-'})",
            'cantidad_disponible': disponible,
            'precio_unitario': str(d.precio_final),
        })

    if not detalles:
        return JsonResponse({'status': 'error', 'msg': f'La venta #{consecutivo} no tiene productos disponibles para devolver (ya fueron devueltos).'}, status=400)

    return JsonResponse({
        'status': 'ok',
        'venta': {
            'id': venta.pk,
            'consecutivo': venta.consecutivo,
            'fecha_hora': venta.fecha_hora.strftime('%d/%m/%Y %H:%M'),
            'cliente': venta.cliente.nombre_completo if venta.cliente else 'Mostrador',
            'bodega': venta.turno.bodega.nombre,
        },
        'detalles': detalles,
    })


@login_required
@user_passes_test(_puede_usar_pos, login_url='core:acceso_denegado')
def vista_devolucion_cambio(request):
    empresa_actual = getattr(request, 'tenant', None)
    turno = _turno_abierto_del_usuario(request, empresa_actual)
    if not turno:
        messages.warning(request, "Debes abrir un turno de caja para registrar una devolución o cambio.")
        return redirect('puntoventa:abrir_turno')

    context = {
        'turno': turno,
        'metodos_pago': PagoVentaPOS.MetodoPago.choices,
        'titulo': 'Devolución / Cambio de Producto',
    }
    return render(request, 'puntoventa/devolucion_cambio.html', context)


@login_required
@user_passes_test(_puede_usar_pos, login_url='core:acceso_denegado')
@require_POST
def api_procesar_devolucion_cambio(request):
    empresa_actual = getattr(request, 'tenant', None)
    turno = _turno_abierto_del_usuario(request, empresa_actual)
    if not turno:
        return JsonResponse({'status': 'error', 'msg': 'No tienes un turno abierto.'}, status=400)

    try:
        data = json.loads(request.body)
        venta_id = int(data['venta_id'])
        devueltos_data = data.get('devueltos') or []
        entregados_data = data.get('entregados') or []
        motivo = (data.get('motivo') or '').strip()
        metodo_pago_adicional = data.get('metodo_pago_adicional')
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'status': 'error', 'msg': 'Datos inválidos.'}, status=400)

    if not motivo:
        return JsonResponse({'status': 'error', 'msg': 'Debes indicar un motivo.'}, status=400)
    if not devueltos_data:
        return JsonResponse({'status': 'error', 'msg': 'Debes seleccionar al menos un producto a devolver.'}, status=400)

    venta_original = get_object_or_404(VentaPOS, pk=venta_id, empresa=empresa_actual, estado=VentaPOS.EstadoVenta.COMPLETADA)

    # --- Validar y recalcular, en el servidor, cuánto vale lo devuelto ---
    total_valor_devuelto = Decimal('0.00')
    lineas_devueltas = []
    for item in devueltos_data:
        detalle = get_object_or_404(DetalleVentaPOS, pk=int(item['detalle_id']), venta=venta_original)
        cantidad = int(item['cantidad'])
        if cantidad <= 0:
            continue
        ya_devuelto = DetalleDevolucionPOS.objects.filter(detalle_venta_original=detalle).aggregate(t=Sum('cantidad'))['t'] or 0
        disponible = detalle.cantidad - ya_devuelto
        if cantidad > disponible:
            return JsonResponse({
                'status': 'error',
                'msg': f"'{detalle.producto}': solo hay {disponible} disponibles para devolver de la venta #{venta_original.consecutivo}."
            }, status=400)
        subtotal = cantidad * detalle.precio_final
        total_valor_devuelto += subtotal
        lineas_devueltas.append({'detalle': detalle, 'cantidad': cantidad, 'precio_unitario': detalle.precio_final, 'subtotal': subtotal})

    # --- Validar y recalcular lo entregado (si es un cambio) ---
    total_valor_entregado = Decimal('0.00')
    lineas_entregadas = []
    if entregados_data:
        productos_map = {p.pk: p for p in Producto.objects.filter(
            empresa=empresa_actual, pk__in=[int(i['producto_id']) for i in entregados_data]
        )}
        errores_stock = []
        for item in entregados_data:
            producto = productos_map.get(int(item['producto_id']))
            cantidad = int(item['cantidad'])
            if not producto or cantidad <= 0:
                continue
            stock_en_bodega = MovimientoInventario.objects.filter(
                producto=producto, bodega=turno.bodega
            ).aggregate(total=Sum('cantidad'))['total'] or 0
            if stock_en_bodega < cantidad:
                errores_stock.append(f"'{producto}': disponible {stock_en_bodega}, solicitado {cantidad}.")
                continue
            precio_unitario = _precio_para_bodega(producto, turno.bodega)
            subtotal = cantidad * precio_unitario
            total_valor_entregado += subtotal
            lineas_entregadas.append({'producto': producto, 'cantidad': cantidad, 'precio_unitario': precio_unitario, 'subtotal': subtotal})

        if errores_stock:
            return JsonResponse({'status': 'error', 'msg': 'Stock insuficiente: ' + ' | '.join(errores_stock)}, status=400)

    tipo = DevolucionCambioPOS.TipoDevolucion.CAMBIO if lineas_entregadas else DevolucionCambioPOS.TipoDevolucion.DEVOLUCION
    diferencia = total_valor_entregado - total_valor_devuelto  # >0: el cliente debe más; <0: se le reembolsa

    monto_reembolsado_efectivo = Decimal('0.00')
    monto_cobrado_adicional = Decimal('0.00')
    metodo_valido = None
    if diferencia < 0:
        monto_reembolsado_efectivo = -diferencia
    elif diferencia > 0:
        metodos_validos = {c[0] for c in PagoVentaPOS.MetodoPago.choices}
        if metodo_pago_adicional not in metodos_validos:
            return JsonResponse({'status': 'error', 'msg': 'Debes indicar el método de pago de la diferencia a favor de la tienda.'}, status=400)
        metodo_valido = metodo_pago_adicional
        monto_cobrado_adicional = diferencia

    with transaction.atomic():
        devolucion = DevolucionCambioPOS.objects.create(
            empresa=empresa_actual,
            venta_original=venta_original,
            turno=turno,
            usuario=request.user,
            tipo=tipo,
            motivo=motivo,
            total_valor_devuelto=total_valor_devuelto,
            total_valor_entregado=total_valor_entregado,
            monto_reembolsado_efectivo=monto_reembolsado_efectivo,
            metodo_pago_adicional=metodo_valido,
            monto_cobrado_adicional=monto_cobrado_adicional,
        )

        for linea in lineas_devueltas:
            DetalleDevolucionPOS.objects.create(
                devolucion=devolucion, detalle_venta_original=linea['detalle'],
                cantidad=linea['cantidad'], precio_unitario=linea['precio_unitario'],
            )
            MovimientoInventario.objects.create(
                empresa=empresa_actual, producto=linea['detalle'].producto, bodega=turno.bodega,
                cantidad=linea['cantidad'], tipo_movimiento='ENTRADA_DEVOLUCION_POS',
                documento_referencia=f"DevCambioPOS #{devolucion.pk}",
                usuario=request.user,
                notas=f"Devolución de la Venta POS #{venta_original.consecutivo}",
            )

        for linea in lineas_entregadas:
            DetalleEntregaCambioPOS.objects.create(
                devolucion=devolucion, producto=linea['producto'],
                cantidad=linea['cantidad'], precio_unitario=linea['precio_unitario'],
            )
            MovimientoInventario.objects.create(
                empresa=empresa_actual, producto=linea['producto'], bodega=turno.bodega,
                cantidad=-linea['cantidad'], tipo_movimiento='SALIDA_CAMBIO_POS',
                documento_referencia=f"DevCambioPOS #{devolucion.pk}",
                usuario=request.user,
                notas=f"Cambio de producto ligado a la Venta POS #{venta_original.consecutivo}",
            )

    return JsonResponse({
        'status': 'ok',
        'devolucion_id': devolucion.pk,
        'tipo': devolucion.tipo,
        'monto_reembolsado_efectivo': str(monto_reembolsado_efectivo),
        'monto_cobrado_adicional': str(monto_cobrado_adicional),
    })


@login_required
@user_passes_test(_puede_usar_pos, login_url='core:acceso_denegado')
def historial_devoluciones_cambios(request):
    empresa_actual = getattr(request, 'tenant', None)
    bloqueo = _bloqueo_sin_turno(request, empresa_actual)
    if bloqueo:
        return bloqueo
    devoluciones = DevolucionCambioPOS.objects.filter(empresa=empresa_actual).select_related(
        'venta_original', 'turno__bodega', 'usuario'
    ).prefetch_related('detalles_devueltos__detalle_venta_original__producto', 'detalles_entregados__producto').order_by('-fecha_hora')

    consecutivo = request.GET.get('consecutivo')
    if consecutivo:
        devoluciones = devoluciones.filter(venta_original__consecutivo=consecutivo)

    paginator = Paginator(devoluciones, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'devoluciones': page_obj.object_list,
        'filtros': request.GET,
        'titulo': 'Historial de Devoluciones y Cambios - Punto de Venta',
    }
    return render(request, 'puntoventa/historial_devoluciones.html', context)
