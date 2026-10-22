from collections import defaultdict
from datetime import datetime, time, timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from bodega.models import Bodega, MovimientoInventario
from core.auth_utils import es_administracion, es_bodega, es_diseno, es_patinador
from core.models import ModuloEmpresa
from productos.models import Producto

from . import services
from .forms import (
    CalidadForm, CorreccionForm, CorteForm, DecisionDefectoForm, EtapaProduccionForm,
    OrdenProduccionForm, PasarPartidaForm, TallerExternoForm,
)
from .models import (
    CorreccionProduccion, DefectoCalidad, EtapaProduccion, LoteProduccion, MovimientoLoteProduccion,
    OrdenProduccion, PartidaLote, RecepcionLinea, RecepcionTaller, RemisionLinea, RemisionTaller,
    RutaOrdenProduccion, TallerExterno,
)


MODULO_CATEGORIA = 'Producción'


def requiere_modulo(view_func):
    """
    Bloqueo real (no solo del menú): la empresa debe tener contratado el
    módulo de Producción, que es opcional y viene apagado. El superusuario
    siempre pasa. Se aplica a todas las rutas en produccion/urls.py.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_superuser:
            if MODULO_CATEGORIA in ModuloEmpresa.categorias_desactivadas(_empresa(request)):
                messages.error(request, "Tu empresa no tiene habilitado el módulo de Producción.")
                return redirect('core:index')
        return view_func(request, *args, **kwargs)
    return _wrapped


def _puede_crear_orden(user):
    return es_diseno(user) or es_administracion(user)


def _puede_operar_lotes(user):
    return es_patinador(user) or es_bodega(user) or es_administracion(user) or es_diseno(user)


def _puede_administrar(user):
    return es_administracion(user)


_rol_crear_orden = user_passes_test(_puede_crear_orden, login_url='core:acceso_denegado')
_rol_operar_lotes = user_passes_test(_puede_operar_lotes, login_url='core:acceso_denegado')
_rol_administrar = user_passes_test(_puede_administrar, login_url='core:acceso_denegado')


class RolCrearOrdenMixin(UserPassesTestMixin):
    def test_func(self):
        return _puede_crear_orden(self.request.user)

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para acceder a esta sección de Producción.")
        return redirect('core:index')


class RolAdministrarMixin(UserPassesTestMixin):
    def test_func(self):
        return _puede_administrar(self.request.user)

    def handle_no_permission(self):
        messages.error(self.request, "Solo Administración puede acceder a esta sección.")
        return redirect('core:index')


def _empresa(request):
    return getattr(request, 'tenant', None)


def _volver(request, por_defecto):
    """Vuelve a la página desde donde se envió el formulario (tablero o detalle), si es de este sitio."""
    siguiente = request.POST.get('next') or request.GET.get('next')
    if siguiente and siguiente.startswith('/'):
        return redirect(siguiente)
    return redirect(por_defecto)


class PanelProduccionView(LoginRequiredMixin, TemplateView):
    template_name = 'produccion/panel_produccion.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        empresa = _empresa(self.request)
        usuario = self.request.user
        context['puede_crear_orden'] = _puede_crear_orden(usuario)
        context['puede_administrar'] = _puede_administrar(usuario)
        context['falta_bodega_calidad'] = not Bodega.objects.filter(
            empresa=empresa, tipo=Bodega.TipoBodega.CALIDAD, activa=True
        ).exists()
        context['sin_talleres'] = not TallerExterno.objects.filter(empresa=empresa, activo=True).exists()
        context['defectos_pendientes'] = DefectoCalidad.objects.filter(
            empresa=empresa, decision=DefectoCalidad.Decision.PENDIENTE
        ).count()
        context['remisiones_abiertas'] = sum(
            1 for r in RemisionTaller.objects.filter(empresa=empresa).prefetch_related('lineas') if r.abierta
        )
        return context


# ============================================================
# Catálogo de Etapas
# ============================================================

class EtapaProduccionListView(LoginRequiredMixin, RolAdministrarMixin, ListView):
    model = EtapaProduccion
    template_name = 'produccion/etapa_list.html'
    context_object_name = 'etapas'

    def get_queryset(self):
        return EtapaProduccion.objects.filter(empresa=_empresa(self.request)).order_by('orden', 'nombre')


class EtapaProduccionCreateView(LoginRequiredMixin, RolAdministrarMixin, CreateView):
    model = EtapaProduccion
    form_class = EtapaProduccionForm
    template_name = 'produccion/etapa_form.html'
    success_url = reverse_lazy('produccion:etapa_list')

    def form_valid(self, form):
        form.instance.empresa = _empresa(self.request)
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Añadir Nueva Etapa'
        return context


class EtapaProduccionUpdateView(LoginRequiredMixin, RolAdministrarMixin, UpdateView):
    model = EtapaProduccion
    form_class = EtapaProduccionForm
    template_name = 'produccion/etapa_form.html'
    success_url = reverse_lazy('produccion:etapa_list')

    def get_queryset(self):
        return EtapaProduccion.objects.filter(empresa=_empresa(self.request))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar Etapa'
        return context


class EtapaProduccionDeleteView(LoginRequiredMixin, RolAdministrarMixin, DeleteView):
    model = EtapaProduccion
    template_name = 'produccion/etapa_confirm_delete.html'
    success_url = reverse_lazy('produccion:etapa_list')

    def get_queryset(self):
        return EtapaProduccion.objects.filter(empresa=_empresa(self.request))


# ============================================================
# Talleres externos
# ============================================================

class TallerListView(LoginRequiredMixin, RolAdministrarMixin, ListView):
    model = TallerExterno
    template_name = 'produccion/taller_list.html'
    context_object_name = 'talleres'

    def get_queryset(self):
        return TallerExterno.objects.filter(empresa=_empresa(self.request)).prefetch_related('etapas')


class _TallerFormMixin:
    model = TallerExterno
    form_class = TallerExternoForm
    template_name = 'produccion/taller_form.html'
    success_url = reverse_lazy('produccion:taller_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['empresa'] = _empresa(self.request)
        return kwargs


class TallerCreateView(LoginRequiredMixin, RolAdministrarMixin, _TallerFormMixin, CreateView):
    def form_valid(self, form):
        form.instance.empresa = _empresa(self.request)
        return super().form_valid(form)


class TallerUpdateView(LoginRequiredMixin, RolAdministrarMixin, _TallerFormMixin, UpdateView):
    def get_queryset(self):
        return TallerExterno.objects.filter(empresa=_empresa(self.request))


# ============================================================
# Órdenes de Producción
# ============================================================

@login_required
@_rol_crear_orden
def api_tallas_de_referencia(request):
    """Tallas reales (con su EAN13 ya asignado) de una ReferenciaColor, para
    poblar el checklist de 'Producción por Talla' -- igual que al crear un
    producto nuevo, se elige de una lista real, no se escribe a mano."""
    empresa_actual = _empresa(request)
    referencia_color_id = request.GET.get('referencia_color_id')
    if not empresa_actual or not referencia_color_id:
        return JsonResponse({'tallas': []})

    productos = Producto.objects.filter(
        articulo_color_fotos_id=referencia_color_id,
        articulo_color_fotos__empresa=empresa_actual,
        activo=True,
    ).order_by('talla')

    return JsonResponse({'tallas': [
        {'talla': str(p.talla) if p.talla is not None else '', 'codigo_barras': p.codigo_barras or 'Sin EAN asignado'}
        for p in productos
    ]})


@login_required
@_rol_crear_orden
def crear_orden_produccion(request):
    empresa_actual = _empresa(request)
    etapas_disponibles = EtapaProduccion.objects.filter(empresa=empresa_actual, activa=True).order_by('orden', 'nombre')

    if request.method == 'POST':
        form = OrdenProduccionForm(request.POST, empresa=empresa_actual)
        etapas_seleccionadas_ids = request.POST.getlist('etapas')
        tallas_seleccionadas = request.POST.getlist('tallas')

        if not etapas_seleccionadas_ids:
            messages.error(request, "Selecciona al menos una etapa para la ruta de esta orden.")
        elif not tallas_seleccionadas:
            messages.error(request, "Selecciona al menos una talla para producir.")
        elif form.is_valid():
            with transaction.atomic():
                orden = form.save(commit=False)
                orden.empresa = empresa_actual
                orden.creado_por = request.user
                orden.estado = OrdenProduccion.EstadoOrden.EN_PROCESO
                orden.save()

                etapas_ruta = list(
                    etapas_disponibles.filter(pk__in=etapas_seleccionadas_ids).order_by('orden', 'nombre')
                )
                for secuencia, etapa in enumerate(etapas_ruta, start=1):
                    RutaOrdenProduccion.objects.create(orden=orden, etapa=etapa, secuencia=secuencia)

                primera_etapa = etapas_ruta[0] if etapas_ruta else None

                # La orden solo define QUÉ tallas se producen, no cuánto -- la
                # cantidad real de cada lote la registra Corte (services.registrar_corte).
                for talla in tallas_seleccionadas:
                    LoteProduccion.objects.create(
                        orden=orden, talla=talla,
                        cantidad_inicial=0, cantidad_actual=0,
                        etapa_actual=primera_etapa,
                    )

                if orden.permitir_venta_sin_stock:
                    orden.referencia_color.variantes.filter(activo=True).update(permitir_preventa=True)

            messages.success(request, f"Orden de Producción {orden.numero_orden} creada con {len(tallas_seleccionadas)} lote(s).")
            return redirect('produccion:detalle_orden', pk=orden.pk)
        else:
            messages.error(request, "Por favor corrige los errores en el formulario.")
    else:
        form = OrdenProduccionForm(empresa=empresa_actual)

    return render(request, 'produccion/orden_form.html', {'form': form, 'etapas_disponibles': etapas_disponibles})


def _resumen_lote(lote):
    """Totales de un lote a partir de su kardex y sus partidas abiertas."""
    movs = lote.movimientos.all()
    sumar = lambda tipo: sum((m.cantidad or 0) for m in movs if m.tipo == tipo)
    return {
        'en_proceso': sum(p.cantidad for p in lote.partidas.all() if p.estado != PartidaLote.Estado.CERRADA),
        'en_bodega': sumar(MovimientoLoteProduccion.TipoMovimiento.INGRESO_BODEGA),
        'defectuosas': sumar(MovimientoLoteProduccion.TipoMovimiento.CALIDAD),
        'faltantes': sumar(MovimientoLoteProduccion.TipoMovimiento.FALTANTE),
        'perdidas': sumar(MovimientoLoteProduccion.TipoMovimiento.PERDIDA),
    }


@login_required
@_rol_operar_lotes
def detalle_orden_produccion(request, pk):
    orden = get_object_or_404(
        OrdenProduccion.objects.select_related('referencia_color', 'creado_por').prefetch_related(
            'ruta__etapa', 'lotes__partidas__etapa', 'lotes__partidas__taller', 'lotes__movimientos',
        ),
        pk=pk, empresa=_empresa(request),
    )
    lotes = []
    for lote in orden.lotes.all():
        abiertas = [p for p in lote.partidas.all() if p.estado != PartidaLote.Estado.CERRADA]
        lotes.append({'lote': lote, 'partidas': abiertas, 'resumen': _resumen_lote(lote)})
    atrasada = bool(
        orden.fecha_estimada_entrega and orden.estado == OrdenProduccion.EstadoOrden.EN_PROCESO
        and orden.fecha_estimada_entrega < timezone.localdate()
    )
    return render(request, 'produccion/orden_detalle.html', {
        'orden': orden, 'lotes': lotes, 'atrasada': atrasada, 'corte_form': CorteForm(),
        'puede_anular': _puede_crear_orden(request.user) and orden.estado == OrdenProduccion.EstadoOrden.EN_PROCESO,
    })


@login_required
@_rol_crear_orden
@require_POST
def anular_orden(request, pk):
    orden = get_object_or_404(OrdenProduccion, pk=pk, empresa=_empresa(request))
    try:
        services.anular_orden(orden, request.POST.get('motivo', ''), request.user)
        messages.success(request, f"Orden {orden.numero_orden} anulada.")
    except services.ErrorProduccion as e:
        messages.error(request, str(e))
    return redirect('produccion:detalle_orden', pk=orden.pk)


@login_required
@_rol_administrar
@require_POST
def crear_bodega_calidad(request):
    """Crea la bodega 'Calidad / Segundas' sin habilitarla para ningún canal de venta."""
    empresa = _empresa(request)
    if Bodega.objects.filter(empresa=empresa, tipo=Bodega.TipoBodega.CALIDAD, activa=True).exists():
        messages.info(request, "Ya existe una bodega de Calidad activa.")
    else:
        codigo, n = 'CALIDAD', 1
        while Bodega.objects.filter(empresa=empresa, codigo=codigo).exists():
            n += 1
            codigo = f'CALIDAD{n}'
        Bodega.objects.create(
            empresa=empresa, nombre='Calidad / Segundas', codigo=codigo, tipo=Bodega.TipoBodega.CALIDAD,
            disponible_venta_estandar=False, disponible_venta_online=False,
            disponible_venta_web=False, disponible_venta_puntoventa=False,
            notas='Creada desde Producción. Recibe las segundas y terceras de Control de Calidad; no está habilitada para la venta.',
        )
        messages.success(request, "Bodega 'Calidad / Segundas' creada (no habilitada para la venta).")
    return redirect('produccion:panel_produccion')


class RolOperarMixin(UserPassesTestMixin):
    def test_func(self):
        return _puede_operar_lotes(self.request.user)

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para acceder a esta sección de Producción.")
        return redirect('core:index')


class OrdenProduccionListView(LoginRequiredMixin, RolOperarMixin, ListView):
    model = OrdenProduccion
    template_name = 'produccion/orden_list.html'
    context_object_name = 'ordenes'
    paginate_by = 20

    def get_queryset(self):
        qs = OrdenProduccion.objects.filter(empresa=_empresa(self.request)).select_related('referencia_color')
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(numero_orden__icontains=q) | Q(referencia_color__referencia_base__icontains=q))
        estado = self.request.GET.get('estado', '')
        if estado:
            qs = qs.filter(estado=estado)
        return qs.order_by('-fecha_creacion')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q', '')
        context['estado'] = self.request.GET.get('estado', '')
        context['estados'] = OrdenProduccion.EstadoOrden.choices
        context['hoy'] = timezone.localdate()
        context['puede_crear_orden'] = _puede_crear_orden(self.request.user)
        return context


# ============================================================
# Tablero (operación diaria de la patinadora)
# ============================================================

@login_required
@_rol_operar_lotes
def tablero_lotes(request):
    """
    Una columna por etapa y una tarjeta por partida (lo que hay en cada sitio),
    con su tiempo ahí. Los lotes que aún no se cortan aparecen en la primera
    etapa de su ruta.
    """
    empresa = _empresa(request)
    q = request.GET.get('q', '').strip()
    taller_id = request.GET.get('taller', '')

    partidas = PartidaLote.objects.filter(
        lote__orden__empresa=empresa, lote__orden__estado=OrdenProduccion.EstadoOrden.EN_PROCESO,
    ).exclude(estado=PartidaLote.Estado.CERRADA).select_related(
        'lote__orden__referencia_color', 'etapa', 'taller', 'remision_linea__remision',
    ).order_by('fecha_ingreso')
    por_cortar = LoteProduccion.objects.filter(
        orden__empresa=empresa, orden__estado=OrdenProduccion.EstadoOrden.EN_PROCESO,
        estado=LoteProduccion.EstadoLote.EN_PROCESO, partidas__isnull=True,
    ).select_related('orden__referencia_color', 'etapa_actual').order_by('fecha_creacion')

    if q:
        filtro = (Q(lote__numero_lote__icontains=q) | Q(lote__orden__numero_orden__icontains=q)
                  | Q(lote__orden__referencia_color__referencia_base__icontains=q) | Q(numero__icontains=q))
        partidas = partidas.filter(filtro)
        por_cortar = por_cortar.filter(
            Q(numero_lote__icontains=q) | Q(orden__numero_orden__icontains=q)
            | Q(orden__referencia_color__referencia_base__icontains=q)
        )
    if taller_id:
        partidas = partidas.filter(taller_id=taller_id)
        por_cortar = por_cortar.none()

    etapas = list(EtapaProduccion.objects.filter(empresa=empresa, activa=True).order_by('orden', 'nombre'))
    tarjetas = defaultdict(list)
    for partida in partidas:
        tarjetas[partida.etapa_id].append({'partida': partida})
    cortes = defaultdict(list)
    for lote in por_cortar:
        cortes[lote.etapa_actual_id].append({'lote': lote, 'tiempo': timezone.now() - lote.fecha_creacion})

    columnas = []
    for etapa in etapas:
        filas = tarjetas.get(etapa.pk, [])
        columnas.append({
            'etapa': etapa,
            'filas': filas,
            'por_cortar': cortes.get(etapa.pk, []),
            'unidades': sum(f['partida'].cantidad for f in filas),
            'atrasadas': sum(1 for f in filas if f['partida'].atrasada),
        })

    empresa_etapas = EtapaProduccion.objects.filter(empresa=empresa, activa=True)
    return render(request, 'produccion/tablero_lotes.html', {
        'columnas': columnas,
        'q': q,
        'taller_id': taller_id,
        'talleres': TallerExterno.objects.filter(empresa=empresa, activo=True),
        'pasar_form': PasarPartidaForm(),
        'calidad_form': CalidadForm(empresa=empresa),
        'corte_form': CorteForm(),
        'etapas_causa': empresa_etapas,
    })


@login_required
@_rol_operar_lotes
@require_POST
def registrar_corte(request, pk):
    lote = get_object_or_404(LoteProduccion, pk=pk, orden__empresa=_empresa(request))
    form = CorteForm(request.POST)
    if not form.is_valid():
        messages.error(request, f"Revisa el corte de {lote.numero_lote}: {form.errors.as_text()}")
    else:
        try:
            services.registrar_corte(lote, form.cleaned_data['cantidad'], request.user, form.cleaned_data['observaciones'])
            messages.success(request, f"Corte registrado: {lote.numero_lote}, {form.cleaned_data['cantidad']} unidad(es).")
        except services.ErrorProduccion as e:
            messages.error(request, str(e))
    return _volver(request, 'produccion:tablero_lotes')


@login_required
@_rol_operar_lotes
@require_POST
def registrar_partida(request, pk):
    """Salida de una partida en planta: a la siguiente etapa (o clasificación en Calidad)."""
    empresa = _empresa(request)
    partida = get_object_or_404(PartidaLote.objects.select_related('etapa', 'lote'), pk=pk, lote__orden__empresa=empresa)
    try:
        if partida.etapa.es_control_calidad:
            form = CalidadForm(request.POST, empresa=empresa)
            if not form.is_valid():
                raise services.ErrorProduccion(form.errors.as_text())
            d = form.cleaned_data
            services.registrar_calidad(
                partida, d['buenas'], d['segundas'] or 0, d['terceras'] or 0, d['causa'] or None, d['etapa_causa'],
                request.user, observaciones=d['observaciones'], perdidas=d['perdidas'] or 0, motivo_perdida=d['motivo_perdida'],
            )
        else:
            form = PasarPartidaForm(request.POST)
            if not form.is_valid():
                raise services.ErrorProduccion(form.errors.as_text())
            d = form.cleaned_data
            services.pasar_partida(
                partida, d['cantidad'], request.user, perdidas=d['perdidas'] or 0,
                motivo_perdida=d['motivo_perdida'], observaciones=d['observaciones'],
            )
        messages.success(request, f"Movimiento registrado para {partida.numero}.")
    except services.ErrorProduccion as e:
        messages.error(request, f"{partida.numero}: {e}")
    return _volver(request, 'produccion:tablero_lotes')


@login_required
@_rol_operar_lotes
def detalle_lote(request, pk):
    lote = get_object_or_404(
        LoteProduccion.objects.select_related('orden__referencia_color').prefetch_related(
            'partidas__etapa', 'partidas__taller', 'movimientos__etapa', 'movimientos__taller', 'movimientos__usuario',
        ),
        pk=pk, orden__empresa=_empresa(request),
    )
    # Tiempo total por etapa (suma de lo que duraron todas sus partidas ahí).
    tiempos = defaultdict(timedelta)
    for mov in lote.movimientos.all():
        if mov.duracion is not None and mov.tipo != MovimientoLoteProduccion.TipoMovimiento.FALTANTE:
            tiempos[mov.etapa.nombre] += mov.duracion
    return render(request, 'produccion/lote_detalle.html', {
        'lote': lote,
        'partidas_abiertas': [p for p in lote.partidas.all() if p.estado != PartidaLote.Estado.CERRADA],
        'resumen': _resumen_lote(lote),
        'tiempos_por_etapa': list(tiempos.items()),
        'corte_form': CorteForm(),
    })


# ============================================================
# Remisiones a talleres y recepciones
# ============================================================

@login_required
@_rol_operar_lotes
def remision_list(request):
    empresa = _empresa(request)
    remisiones = RemisionTaller.objects.filter(empresa=empresa).select_related('taller', 'etapa', 'usuario').prefetch_related(
        'lineas__recepciones', 'lineas__correcciones',
    )
    taller_id = request.GET.get('taller', '')
    if taller_id:
        remisiones = remisiones.filter(taller_id=taller_id)
    solo_abiertas = request.GET.get('abiertas') == '1'
    filas = [r for r in remisiones[:300] if (r.abierta or not solo_abiertas)]
    return render(request, 'produccion/remision_list.html', {
        'remisiones': filas, 'talleres': TallerExterno.objects.filter(empresa=empresa),
        'taller_id': taller_id, 'solo_abiertas': solo_abiertas,
    })


@login_required
@_rol_operar_lotes
def remision_crear(request):
    """Elegir etapa externa y taller, y cuántas unidades de cada partida en planta salen."""
    empresa = _empresa(request)
    etapas = EtapaProduccion.objects.filter(empresa=empresa, es_externa=True, activa=True)
    etapa = etapas.filter(pk=request.GET.get('etapa') or request.POST.get('etapa')).first() if (request.GET.get('etapa') or request.POST.get('etapa')) else None
    talleres = TallerExterno.objects.filter(empresa=empresa, activo=True, etapas=etapa) if etapa else TallerExterno.objects.none()
    partidas = PartidaLote.objects.filter(
        lote__orden__empresa=empresa, etapa=etapa, estado=PartidaLote.Estado.EN_ETAPA,
        lote__orden__estado=OrdenProduccion.EstadoOrden.EN_PROCESO,
    ).select_related('lote__orden__referencia_color').order_by('fecha_ingreso') if etapa else PartidaLote.objects.none()

    if request.method == 'POST' and etapa:
        taller = talleres.filter(pk=request.POST.get('taller')).first()
        items = []
        try:
            if not taller:
                raise services.ErrorProduccion("Elige el taller.")
            for partida in partidas:
                valor = request.POST.get(f'cantidad_{partida.pk}', '').strip()
                if valor:
                    items.append((partida, int(valor)))
            remision = services.enviar_a_taller(
                empresa, etapa, taller, items, request.user, request.POST.get('observaciones', '').strip(),
            )
            messages.success(request, f"Remisión {remision.numero} creada. Imprímela para que el taller la firme.")
            return redirect('produccion:remision_detalle', pk=remision.pk)
        except ValueError as e:
            messages.error(request, str(e) if isinstance(e, services.ErrorProduccion) else "Revisa las cantidades.")

    return render(request, 'produccion/remision_form.html', {
        'etapas': etapas, 'etapa': etapa, 'talleres': talleres, 'partidas': partidas,
        'preseleccion': request.GET.get('partida', ''),
    })


@login_required
@_rol_operar_lotes
def remision_detalle(request, pk):
    remision = get_object_or_404(
        RemisionTaller.objects.select_related('taller', 'etapa', 'usuario').prefetch_related(
            'lineas__lote__orden__referencia_color', 'lineas__recepciones__recepcion', 'lineas__correcciones__usuario',
            'recepciones__usuario',
        ),
        pk=pk, empresa=_empresa(request),
    )
    return render(request, 'produccion/remision_detalle.html', {
        'remision': remision, 'correccion_form': CorreccionForm(),
        'imprimir': request.GET.get('imprimir') == '1',
    })


@login_required
@_rol_operar_lotes
def recepcion_crear(request, remision_pk):
    remision = get_object_or_404(
        RemisionTaller.objects.select_related('taller', 'etapa').prefetch_related('lineas__lote__orden__referencia_color'),
        pk=remision_pk, empresa=_empresa(request),
    )
    lineas = [l for l in remision.lineas.all() if l.pendiente > 0]
    if request.method == 'POST':
        items = []
        try:
            for linea in lineas:
                valor = request.POST.get(f'recibida_{linea.pk}', '').strip()
                cerrar = request.POST.get(f'cerrar_{linea.pk}') == '1'
                items.append((linea, int(valor) if valor else 0, cerrar))
            recepcion = services.recibir_de_taller(remision, items, request.user, request.POST.get('observaciones', '').strip())
            messages.success(request, f"Recepción {recepcion.numero} registrada. Imprímela para que el taller la firme.")
            return redirect('produccion:recepcion_detalle', pk=recepcion.pk)
        except ValueError as e:
            messages.error(request, str(e) if isinstance(e, services.ErrorProduccion) else "Revisa las cantidades.")
    return render(request, 'produccion/recepcion_form.html', {'remision': remision, 'lineas': lineas})


@login_required
@_rol_operar_lotes
def recepcion_detalle(request, pk):
    recepcion = get_object_or_404(
        RecepcionTaller.objects.select_related('remision__taller', 'remision__etapa', 'usuario').prefetch_related(
            'lineas__remision_linea__lote__orden__referencia_color',
        ),
        pk=pk, empresa=_empresa(request),
    )
    return render(request, 'produccion/recepcion_detalle.html', {
        'recepcion': recepcion, 'imprimir': request.GET.get('imprimir') == '1',
    })


@login_required
@_rol_administrar
@require_POST
def corregir_linea(request, pk, tipo):
    """Corrección de lo enviado o recibido en una línea de remisión (solo Administración)."""
    linea = get_object_or_404(RemisionLinea.objects.select_related('remision'), pk=pk, remision__empresa=_empresa(request))
    if tipo not in ('envio', 'recepcion'):
        messages.error(request, "Tipo de corrección no válido.")
        return redirect('produccion:remision_detalle', pk=linea.remision_id)
    form = CorreccionForm(request.POST)
    if not form.is_valid():
        messages.error(request, f"Revisa la corrección: {form.errors.as_text()}")
    else:
        funcion = services.corregir_envio if tipo == 'envio' else services.corregir_recepcion
        try:
            funcion(linea, form.cleaned_data['cantidad'], form.cleaned_data['motivo'], request.user)
            messages.success(request, "Corrección registrada. El documento original no se modificó.")
        except services.ErrorProduccion as e:
            messages.error(request, str(e))
    return redirect('produccion:remision_detalle', pk=linea.remision_id)


# ============================================================
# Defectos de calidad (decisión de descuento)
# ============================================================

@login_required
@_rol_operar_lotes
def defecto_list(request):
    empresa = _empresa(request)
    defectos = DefectoCalidad.objects.filter(empresa=empresa).select_related(
        'lote__orden__referencia_color', 'etapa_causa', 'taller_responsable', 'usuario',
    ).prefetch_related('decisiones__usuario', 'decisiones__taller_responsable')
    decision = request.GET.get('decision', DefectoCalidad.Decision.PENDIENTE)
    if decision:
        defectos = defectos.filter(decision=decision)
    puede_decidir = _puede_administrar(request.user)
    filas = []
    for defecto in defectos[:300]:
        form = None
        if puede_decidir:
            posibles = list(defecto.talleres_posibles())
            form = DecisionDefectoForm(empresa=empresa, initial={
                'taller': posibles[0].pk if len(posibles) == 1 else None,
            })
        filas.append({'defecto': defecto, 'form': form, 'posibles': defecto.talleres_posibles()})
    return render(request, 'produccion/defecto_list.html', {
        'filas': filas, 'decision': decision, 'decisiones': DefectoCalidad.Decision.choices, 'puede_decidir': puede_decidir,
    })


@login_required
@_rol_administrar
@require_POST
def defecto_decidir(request, pk):
    empresa = _empresa(request)
    defecto = get_object_or_404(DefectoCalidad, pk=pk, empresa=empresa)
    form = DecisionDefectoForm(request.POST, empresa=empresa)
    if not form.is_valid():
        messages.error(request, f"Revisa la decisión: {form.errors.as_text()}")
    else:
        try:
            services.decidir_defecto(defecto, form.cleaned_data['decision'], form.cleaned_data['taller'],
                                     form.cleaned_data['motivo'], request.user)
            messages.success(request, "Decisión registrada.")
        except services.ErrorProduccion as e:
            messages.error(request, str(e))
    return _volver(request, 'produccion:defecto_list')


# ============================================================
# Informes
# ============================================================

def _rango_fechas(request):
    """(inicio, fin_exclusivo, texto_inicio, texto_fin) en hora local; por defecto el mes actual."""
    hoy = timezone.localdate()
    try:
        inicio = datetime.strptime(request.GET.get('fecha_inicio', ''), '%Y-%m-%d').date()
    except ValueError:
        inicio = hoy.replace(day=1)
    try:
        fin = datetime.strptime(request.GET.get('fecha_fin', ''), '%Y-%m-%d').date()
    except ValueError:
        fin = hoy
    a_dt = lambda d: timezone.make_aware(datetime.combine(d, time.min))
    return a_dt(inicio), a_dt(fin + timedelta(days=1)), inicio, fin


@login_required
@_rol_administrar
def informe_taller(request):
    """
    Lo que tiene cada taller hoy y, para el periodo, lo enviado, recibido (base
    de pago), faltantes y defectos con su decisión. Solo cantidades.
    """
    empresa = _empresa(request)
    talleres = TallerExterno.objects.filter(empresa=empresa)
    taller = talleres.filter(pk=request.GET.get('taller')).first() if request.GET.get('taller') else None
    inicio, fin, fecha_inicio, fecha_fin = _rango_fechas(request)
    contexto = {'talleres': talleres, 'taller': taller, 'fecha_inicio': fecha_inicio, 'fecha_fin': fecha_fin}

    if taller:
        en_taller = PartidaLote.objects.filter(taller=taller, estado=PartidaLote.Estado.EN_TALLER).select_related(
            'lote__orden__referencia_color', 'etapa', 'remision_linea__remision',
        ).order_by('fecha_ingreso')

        enviados = RemisionLinea.objects.filter(
            remision__taller=taller, remision__fecha_hora__gte=inicio, remision__fecha_hora__lt=fin,
        ).select_related('remision', 'lote__orden__referencia_color').order_by('remision__fecha_hora')
        recibidos = RecepcionLinea.objects.filter(
            recepcion__remision__taller=taller, recepcion__fecha_hora__gte=inicio, recepcion__fecha_hora__lt=fin,
        ).select_related('recepcion__remision', 'remision_linea__lote__orden__referencia_color').order_by('recepcion__fecha_hora')
        correcciones = CorreccionProduccion.objects.filter(
            remision_linea__remision__taller=taller, fecha_hora__gte=inicio, fecha_hora__lt=fin,
        ).select_related('remision_linea__remision', 'remision_linea__lote', 'usuario')
        defectos = DefectoCalidad.objects.filter(
            taller_responsable=taller, decision=DefectoCalidad.Decision.DESCONTAR,
        ).prefetch_related('decisiones').select_related('lote__orden__referencia_color')
        defectos = [d for d in defectos if inicio <= d.decisiones.first().fecha_hora < fin]

        corr_recepcion = sum(c.cantidad for c in correcciones if c.tipo == CorreccionProduccion.Tipo.RECEPCION)
        corr_envio = sum(c.cantidad for c in correcciones if c.tipo == CorreccionProduccion.Tipo.ENVIO)
        contexto.update({
            'en_taller': en_taller,
            'en_taller_total': sum(p.cantidad for p in en_taller),
            'enviados': enviados,
            'recibidos': recibidos,
            'correcciones': correcciones,
            'defectos': defectos,
            'total_enviado': sum(l.cantidad_enviada for l in enviados) + corr_envio,
            'total_recibido': sum(l.cantidad_recibida for l in recibidos) + corr_recepcion,
            'total_faltante': sum(l.cantidad_faltante for l in recibidos),
            'total_descontar': sum(d.total for d in defectos),
        })
    return render(request, 'produccion/informe_taller.html', contexto)


@login_required
@_rol_administrar
def informe_segundas_terceras(request):
    empresa_actual = _empresa(request)
    movimientos = MovimientoInventario.objects.filter(
        empresa=empresa_actual, tipo_movimiento='ENTRADA_PRODUCCION_SEGUNDA'
    ).select_related('producto', 'producto__articulo_color_fotos').order_by('-fecha_hora')

    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    if fecha_inicio:
        movimientos = movimientos.filter(fecha_hora__date__gte=fecha_inicio)
    if fecha_fin:
        movimientos = movimientos.filter(fecha_hora__date__lte=fecha_fin)

    total_unidades = movimientos.aggregate(total=Sum('cantidad'))['total'] or 0
    por_referencia = movimientos.values('producto__referencia').annotate(total=Sum('cantidad')).order_by('-total')

    return render(request, 'produccion/informe_segundas_terceras.html', {
        'movimientos': movimientos[:200],
        'total_unidades': total_unidades,
        'por_referencia': por_referencia,
        'fecha_inicio': fecha_inicio or '',
        'fecha_fin': fecha_fin or '',
    })
