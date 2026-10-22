"""
Operaciones del módulo de producción. Toda la lógica que mueve unidades
vive aquí (no en las vistas) para que cada operación sea atómica y quede
registrada en el kardex del lote con su duración.

Reglas de negocio (ver decisiones del 21/10/2026):
- Un lote (una talla de una OP) se reparte en partidas que avanzan por separado.
- Las etapas externas (talleres) se mueven con remisión y recepción; a los
  talleres se les paga por todas las unidades recibidas, los faltantes no.
- Remisiones y recepciones no se editan: se corrigen con CorreccionProduccion.
- El descuento por segundas/terceras lo decide Administración caso a caso,
  siempre con motivo (DecisionDefecto).
"""
from django.db import transaction
from django.utils import timezone

from .models import (
    CorreccionProduccion, DecisionDefecto, DefectoCalidad, LoteProduccion,
    MovimientoLoteProduccion as Mov, PartidaLote, RecepcionLinea, RecepcionTaller,
    RemisionLinea, RemisionTaller,
)


class ErrorProduccion(ValueError):
    """Error de negocio con un mensaje para mostrarle al usuario."""


# ------------------------------------------------------------------
# Utilidades internas
# ------------------------------------------------------------------

def _bloquear(partida):
    return PartidaLote.objects.select_for_update(of=('self',)).select_related('lote__orden', 'etapa', 'taller').get(pk=partida.pk)


def _descontar(partida, cantidad):
    if cantidad > partida.cantidad:
        raise ErrorProduccion(f"La partida {partida.numero} solo tiene {partida.cantidad} unidad(es).")
    partida.cantidad -= cantidad
    if partida.cantidad == 0:
        partida.estado = PartidaLote.Estado.CERRADA
        partida.fecha_cierre = timezone.now()
    partida.save(update_fields=['cantidad', 'estado', 'fecha_cierre'])


def _nueva_partida(lote, etapa, cantidad, *, origen=None, taller=None, remision_linea=None, usuario=None, documento=''):
    estado = PartidaLote.Estado.EN_TALLER if taller else PartidaLote.Estado.EN_ETAPA
    # Bloquea el lote para que el consecutivo de la partida (…-P1, -P2) no se repita.
    list(LoteProduccion.objects.select_for_update().filter(pk=lote.pk).values_list('pk', flat=True))
    partida = PartidaLote.objects.create(
        lote=lote, etapa=etapa, cantidad=cantidad, cantidad_inicial=cantidad, estado=estado,
        origen=origen, taller=taller, remision_linea=remision_linea,
    )
    if not taller:
        Mov.objects.create(
            lote=lote, partida=partida, etapa=etapa, tipo=Mov.TipoMovimiento.INGRESO,
            cantidad=cantidad, usuario=usuario, documento=documento,
        )
    return partida


def _ingresar_a_bodega(partida, cantidad, usuario, observaciones=''):
    from bodega.models import Bodega, MovimientoInventario

    lote = partida.lote
    producto = lote.producto_real()
    if not producto:
        raise ErrorProduccion(f"No existe en el catálogo la talla {lote.talla} de {lote.orden.referencia_color}; no se puede ingresar a bodega.")
    MovimientoInventario.objects.create(
        empresa=lote.orden.empresa, producto=producto, bodega=Bodega.objects.principal(lote.orden.empresa),
        cantidad=cantidad, tipo_movimiento='ENTRADA_PRODUCCION', documento_referencia=partida.numero,
        usuario=usuario, notas=f"Ingreso a bodega desde {lote.orden.numero_orden} ({partida.numero}).",
    )
    if producto.permitir_preventa:
        producto.permitir_preventa = False
        producto.save(update_fields=['permitir_preventa'])
    Mov.objects.create(
        lote=lote, partida=partida, etapa=partida.etapa, tipo=Mov.TipoMovimiento.INGRESO_BODEGA,
        cantidad=cantidad, cantidad_buena=cantidad, inicio_etapa=partida.fecha_ingreso,
        usuario=usuario, observaciones=observaciones or None, documento=partida.numero,
    )


def _avanzar(partida, cantidad, usuario, observaciones=''):
    """Saca 'cantidad' unidades de una partida en planta hacia la siguiente etapa de la ruta (o a bodega)."""
    lote = partida.lote
    _descontar(partida, cantidad)
    if partida.etapa.es_ingreso_bodega:
        _ingresar_a_bodega(partida, cantidad, usuario, observaciones)
        return None
    Mov.objects.create(
        lote=lote, partida=partida, etapa=partida.etapa, tipo=Mov.TipoMovimiento.SALIDA,
        cantidad=cantidad, cantidad_buena=cantidad, inicio_etapa=partida.fecha_ingreso,
        usuario=usuario, observaciones=observaciones or None,
    )
    siguiente = lote.etapa_siguiente_de(partida.etapa)
    if siguiente is None:
        return None
    return _nueva_partida(lote, siguiente, cantidad, origen=partida, usuario=usuario)


def _validar_cantidad(cantidad, nombre="La cantidad"):
    if cantidad is None or cantidad < 0:
        raise ErrorProduccion(f"{nombre} no es válida.")


# ------------------------------------------------------------------
# Operaciones en planta
# ------------------------------------------------------------------

@transaction.atomic
def registrar_corte(lote, cantidad, usuario, observaciones=''):
    """Fija cuántas unidades salieron de corte y las pone en la siguiente etapa."""
    lote = LoteProduccion.objects.select_for_update().get(pk=lote.pk)
    if not lote.por_cortar:
        raise ErrorProduccion(f"El lote {lote.numero_lote} ya tiene registrado el corte.")
    if not cantidad or cantidad <= 0:
        raise ErrorProduccion("La cantidad cortada debe ser mayor que cero.")
    primera = lote.primera_etapa()
    if primera is None:
        raise ErrorProduccion("La orden no tiene ruta de etapas.")

    lote.cantidad_inicial = cantidad
    lote.cantidad_actual = cantidad
    lote.etapa_actual = None
    lote.fecha_ultimo_movimiento = timezone.now()
    lote.save(update_fields=['cantidad_inicial', 'cantidad_actual', 'etapa_actual', 'fecha_ultimo_movimiento'])

    if primera.es_externa:
        # Si la ruta arranca en un taller, el corte solo define la cantidad
        # que queda lista para enviarse con remisión.
        return _nueva_partida(lote, primera, cantidad, usuario=usuario)

    Mov.objects.create(
        lote=lote, etapa=primera, tipo=Mov.TipoMovimiento.CORTE, cantidad=cantidad, cantidad_buena=cantidad,
        inicio_etapa=lote.fecha_creacion, usuario=usuario, observaciones=observaciones or None,
    )
    siguiente = lote.etapa_siguiente_de(primera)
    if siguiente is None:
        raise ErrorProduccion("La ruta solo tiene una etapa; agrega las demás etapas a la orden.")
    return _nueva_partida(lote, siguiente, cantidad, usuario=usuario)


@transaction.atomic
def pasar_partida(partida, cantidad, usuario, perdidas=0, motivo_perdida='', observaciones=''):
    """Saca unidades de una partida en planta (etapa interna) hacia la siguiente etapa."""
    partida = _bloquear(partida)
    _validar_cantidad(cantidad)
    _validar_cantidad(perdidas, "La cantidad perdida")
    if partida.estado != PartidaLote.Estado.EN_ETAPA:
        raise ErrorProduccion(f"La partida {partida.numero} no está en planta.")
    if partida.etapa.es_externa:
        raise ErrorProduccion(f"{partida.etapa.nombre} es una etapa externa: las unidades salen con remisión a un taller.")
    if partida.etapa.es_control_calidad and cantidad:
        # En Calidad se usa registrar_calidad, que además separa segundas/terceras.
        return registrar_calidad(partida, cantidad, 0, 0, None, None, usuario, observaciones=observaciones,
                                 perdidas=perdidas, motivo_perdida=motivo_perdida)
    if cantidad + perdidas == 0:
        raise ErrorProduccion("No hay unidades para registrar.")
    if cantidad + perdidas > partida.cantidad:
        raise ErrorProduccion(f"La partida {partida.numero} solo tiene {partida.cantidad} unidad(es).")
    if perdidas:
        _registrar_perdida(partida, perdidas, motivo_perdida, usuario)
    nueva = _avanzar(partida, cantidad, usuario, observaciones) if cantidad else None
    partida.lote.actualizar_estado()
    return nueva


def _registrar_perdida(partida, perdidas, motivo, usuario):
    if not (motivo or '').strip():
        raise ErrorProduccion("Indica el motivo de las unidades perdidas.")
    _descontar(partida, perdidas)
    Mov.objects.create(
        lote=partida.lote, partida=partida, etapa=partida.etapa, tipo=Mov.TipoMovimiento.PERDIDA,
        cantidad=perdidas, usuario=usuario, observaciones=motivo.strip(),
    )


@transaction.atomic
def registrar_calidad(partida, buenas, segundas, terceras, causa, etapa_causa, usuario,
                      observaciones='', perdidas=0, motivo_perdida=''):
    """Clasifica en Control de Calidad: las buenas siguen, segundas/terceras van a la bodega de Calidad."""
    from bodega.models import Bodega, MovimientoInventario

    partida = _bloquear(partida)
    for valor, nombre in ((buenas, "Las buenas"), (segundas, "Las segundas"), (terceras, "Las terceras"), (perdidas, "Las perdidas")):
        _validar_cantidad(valor, nombre)
    if not partida.etapa.es_control_calidad:
        raise ErrorProduccion(f"{partida.etapa.nombre} no es la etapa de Control de Calidad.")
    if partida.estado != PartidaLote.Estado.EN_ETAPA:
        raise ErrorProduccion(f"La partida {partida.numero} no está en planta.")
    defectuosas = segundas + terceras
    if buenas + defectuosas + perdidas == 0:
        raise ErrorProduccion("No hay unidades para registrar.")
    if buenas + defectuosas + perdidas > partida.cantidad:
        raise ErrorProduccion(f"La partida {partida.numero} solo tiene {partida.cantidad} unidad(es).")

    lote = partida.lote
    if defectuosas:
        if causa not in DefectoCalidad.Causa.values:
            raise ErrorProduccion("Indica la causa de las segundas/terceras.")
        if causa == DefectoCalidad.Causa.PROCESO and etapa_causa is None:
            raise ErrorProduccion("Indica en qué etapa se originó el defecto.")
        producto = lote.producto_real()
        if not producto:
            raise ErrorProduccion(f"No existe en el catálogo la talla {lote.talla}; no se pueden registrar segundas/terceras.")
        bodega_calidad = Bodega.objects.filter(empresa=lote.orden.empresa, tipo=Bodega.TipoBodega.CALIDAD, activa=True).first()
        if not bodega_calidad:
            raise ErrorProduccion("No existe una bodega de tipo 'Calidad / Segundas' activa. Créala primero en Bodegas.")
        _descontar(partida, defectuosas)
        defecto = DefectoCalidad.objects.create(
            empresa=lote.orden.empresa, lote=lote, partida=partida, etapa=partida.etapa,
            cantidad_segunda=segundas, cantidad_tercera=terceras, causa=causa,
            etapa_causa=etapa_causa if causa == DefectoCalidad.Causa.PROCESO else None,
            observaciones=observaciones, usuario=usuario,
        )
        MovimientoInventario.objects.create(
            empresa=lote.orden.empresa, producto=producto, bodega=bodega_calidad, cantidad=defectuosas,
            tipo_movimiento='ENTRADA_PRODUCCION_SEGUNDA', documento_referencia=f"{partida.numero}-D{defecto.pk}",
            usuario=usuario, notas=f"{segundas} segunda(s), {terceras} tercera(s) de {lote.orden.referencia_color} talla {lote.talla}.",
        )
        Mov.objects.create(
            lote=lote, partida=partida, etapa=partida.etapa, tipo=Mov.TipoMovimiento.CALIDAD, cantidad=defectuosas,
            cantidad_segunda=segundas, cantidad_tercera=terceras, usuario=usuario,
            observaciones=f"Causa: {defecto.get_causa_display()}" + (f" ({etapa_causa.nombre})" if defecto.etapa_causa else ''),
        )
    if perdidas:
        _registrar_perdida(partida, perdidas, motivo_perdida, usuario)
    nueva = _avanzar(partida, buenas, usuario, observaciones) if buenas else None
    lote.actualizar_estado()
    return nueva


# ------------------------------------------------------------------
# Talleres externos
# ------------------------------------------------------------------

@transaction.atomic
def enviar_a_taller(empresa, etapa, taller, items, usuario, observaciones=''):
    """
    Crea una remisión: 'items' es una lista de (partida_en_planta, cantidad).
    Cada cantidad sale de su partida y queda como una partida nueva en el taller.
    """
    if not etapa.es_externa:
        raise ErrorProduccion(f"{etapa.nombre} no es una etapa externa.")
    if not taller.activo or not taller.etapas.filter(pk=etapa.pk).exists():
        raise ErrorProduccion(f"El taller {taller} no está habilitado para {etapa.nombre}.")
    items = [(p, c) for p, c in items if c]
    if not items:
        raise ErrorProduccion("Indica al menos una cantidad a enviar.")

    remision = RemisionTaller.objects.create(
        empresa=empresa, taller=taller, etapa=etapa, usuario=usuario, observaciones=observaciones,
    )
    for partida, cantidad in items:
        partida = _bloquear(partida)
        _validar_cantidad(cantidad)
        if partida.lote.orden.empresa_id != empresa.pk or partida.etapa_id != etapa.pk or partida.estado != PartidaLote.Estado.EN_ETAPA:
            raise ErrorProduccion(f"La partida {partida.numero} no está en planta en {etapa.nombre}.")
        _descontar(partida, cantidad)
        linea = RemisionLinea.objects.create(remision=remision, lote=partida.lote, cantidad_enviada=cantidad)
        en_taller = _nueva_partida(partida.lote, etapa, cantidad, origen=partida, taller=taller, remision_linea=linea)
        Mov.objects.create(
            lote=partida.lote, partida=en_taller, etapa=etapa, taller=taller, tipo=Mov.TipoMovimiento.ENVIO_TALLER,
            cantidad=cantidad, inicio_etapa=partida.fecha_ingreso, usuario=usuario, documento=remision.numero,
            observaciones=observaciones or None,
        )
    return remision


def _partidas_en_taller(linea):
    return list(
        PartidaLote.objects.select_for_update()
        .filter(remision_linea=linea, estado=PartidaLote.Estado.EN_TALLER)
        .order_by('fecha_ingreso')
    )


def _sacar_del_taller(linea, cantidad):
    """Descuenta 'cantidad' de las partidas abiertas en el taller para esta línea (la más antigua primero)."""
    restante = cantidad
    inicio = None
    for partida in _partidas_en_taller(linea):
        if restante == 0:
            break
        tomar = min(restante, partida.cantidad)
        inicio = inicio or partida.fecha_ingreso
        _descontar(partida, tomar)
        restante -= tomar
    if restante:
        raise ErrorProduccion(f"El taller no tiene tantas unidades pendientes en {linea}.")
    return inicio


@transaction.atomic
def recibir_de_taller(remision, items, usuario, observaciones=''):
    """
    Crea un comprobante de recepción: 'items' es una lista de
    (linea_remision, cantidad_recibida, cerrar_con_faltante). Lo recibido pasa
    a la siguiente etapa; si se cierra con faltante, lo que siga pendiente se
    da por no devuelto (no se le paga al taller).
    """
    remision = RemisionTaller.objects.select_for_update().get(pk=remision.pk)
    items = [(l, r or 0, cerrar) for l, r, cerrar in items if (r or cerrar)]
    if not items:
        raise ErrorProduccion("Indica al menos una cantidad recibida o una línea a cerrar.")

    recepcion = RecepcionTaller.objects.create(
        empresa=remision.empresa, remision=remision, usuario=usuario, observaciones=observaciones,
    )
    lotes = set()
    for linea, recibida, cerrar in items:
        if linea.remision_id != remision.pk:
            raise ErrorProduccion("Una de las líneas no pertenece a esta remisión.")
        _validar_cantidad(recibida, "La cantidad recibida")
        pendiente = linea.pendiente
        if recibida > pendiente:
            raise ErrorProduccion(f"{linea.lote.numero_lote}: se recibieron {recibida} pero solo hay {pendiente} pendiente(s) en el taller.")
        destino = None
        if recibida:
            inicio = _sacar_del_taller(linea, recibida)
            Mov.objects.create(
                lote=linea.lote, etapa=remision.etapa, taller=remision.taller, tipo=Mov.TipoMovimiento.RECEPCION_TALLER,
                cantidad=recibida, cantidad_buena=recibida, inicio_etapa=inicio, usuario=usuario,
                documento=recepcion.numero, observaciones=observaciones or None,
            )
            siguiente = linea.lote.etapa_siguiente_de(remision.etapa)
            if siguiente is not None:
                destino = _nueva_partida(linea.lote, siguiente, recibida, usuario=usuario, documento=recepcion.numero)
        faltante = 0
        if cerrar:
            faltante = pendiente - recibida
            if faltante:
                inicio = _sacar_del_taller(linea, faltante)
                Mov.objects.create(
                    lote=linea.lote, etapa=remision.etapa, taller=remision.taller, tipo=Mov.TipoMovimiento.FALTANTE,
                    cantidad=faltante, inicio_etapa=inicio, usuario=usuario, documento=recepcion.numero,
                    observaciones=observaciones or None,
                )
        RecepcionLinea.objects.create(
            recepcion=recepcion, remision_linea=linea, cantidad_recibida=recibida,
            cantidad_faltante=faltante, partida_destino=destino,
        )
        lotes.add(linea.lote)
    for lote in lotes:
        lote.actualizar_estado()
    return recepcion


@transaction.atomic
def corregir_envio(linea, delta, motivo, usuario):
    """Corrige la cantidad enviada en una línea de remisión (positivo: se enviaron más; negativo: menos)."""
    if not delta:
        raise ErrorProduccion("La corrección no puede ser cero.")
    if not (motivo or '').strip():
        raise ErrorProduccion("Indica el motivo de la corrección.")
    remision = linea.remision
    if delta > 0:
        # Salieron más unidades de las registradas: se toman de lo que hay en planta en esa etapa.
        restante = delta
        for partida in PartidaLote.objects.select_for_update().filter(
            lote=linea.lote, etapa=remision.etapa, estado=PartidaLote.Estado.EN_ETAPA
        ).order_by('fecha_ingreso'):
            tomar = min(restante, partida.cantidad)
            _descontar(partida, tomar)
            restante -= tomar
            if restante == 0:
                break
        if restante:
            raise ErrorProduccion(f"No hay {delta} unidad(es) en planta en {remision.etapa.nombre} para agregar a la remisión.")
        _nueva_partida(linea.lote, remision.etapa, delta, taller=remision.taller, remision_linea=linea)
    else:
        if -delta > linea.pendiente:
            raise ErrorProduccion(f"Solo hay {linea.pendiente} unidad(es) pendientes en el taller para esta línea.")
        _sacar_del_taller(linea, -delta)
        _nueva_partida(linea.lote, remision.etapa, -delta, usuario=usuario, documento=remision.numero)
    correccion = CorreccionProduccion.objects.create(
        empresa=remision.empresa, tipo=CorreccionProduccion.Tipo.ENVIO, remision_linea=linea,
        cantidad=delta, motivo=motivo.strip(), usuario=usuario,
    )
    Mov.objects.create(
        lote=linea.lote, etapa=remision.etapa, taller=remision.taller, tipo=Mov.TipoMovimiento.CORRECCION,
        cantidad=delta, usuario=usuario, documento=remision.numero, observaciones=f"Envío corregido: {motivo.strip()}",
    )
    return correccion


@transaction.atomic
def corregir_recepcion(linea, delta, motivo, usuario):
    """Corrige lo recibido de una línea (positivo: llegaron más; negativo: se registraron de más)."""
    if not delta:
        raise ErrorProduccion("La corrección no puede ser cero.")
    if not (motivo or '').strip():
        raise ErrorProduccion("Indica el motivo de la corrección.")
    remision = linea.remision
    siguiente = linea.lote.etapa_siguiente_de(remision.etapa)
    if delta > 0:
        if delta > linea.pendiente:
            raise ErrorProduccion(f"Solo hay {linea.pendiente} unidad(es) pendientes en el taller para esta línea.")
        _sacar_del_taller(linea, delta)
        if siguiente is not None:
            _nueva_partida(linea.lote, siguiente, delta, usuario=usuario, documento=remision.numero)
    else:
        # Se registraron de más: se devuelven al taller desde la partida que creó la recepción,
        # siempre que esas unidades no hayan avanzado todavía.
        restante = -delta
        destinos = PartidaLote.objects.select_for_update().filter(
            pk__in=linea.recepciones.values('partida_destino'), estado=PartidaLote.Estado.EN_ETAPA,
        ).order_by('-fecha_ingreso')
        for partida in destinos:
            tomar = min(restante, partida.cantidad)
            _descontar(partida, tomar)
            restante -= tomar
            if restante == 0:
                break
        if restante:
            raise ErrorProduccion(
                "Esas unidades ya avanzaron a otra etapa; registra la diferencia como pérdida en la etapa donde están."
            )
        _nueva_partida(linea.lote, remision.etapa, -delta, taller=remision.taller, remision_linea=linea)
    correccion = CorreccionProduccion.objects.create(
        empresa=remision.empresa, tipo=CorreccionProduccion.Tipo.RECEPCION, remision_linea=linea,
        cantidad=delta, motivo=motivo.strip(), usuario=usuario,
    )
    Mov.objects.create(
        lote=linea.lote, etapa=remision.etapa, taller=remision.taller, tipo=Mov.TipoMovimiento.CORRECCION,
        cantidad=delta, usuario=usuario, documento=remision.numero, observaciones=f"Recepción corregida: {motivo.strip()}",
    )
    linea.lote.actualizar_estado()
    return correccion


@transaction.atomic
def anular_orden(orden, motivo, usuario):
    """
    Anula una OP. No se permite si hay unidades en talleres (primero se reciben
    o se cierran con faltante, para no dejar abiertas las cuentas del taller).
    Lo que quede en planta se cierra con un movimiento de anulación, así queda
    rastro de cuántas unidades había y dónde.
    """
    from .models import OrdenProduccion

    orden = OrdenProduccion.objects.select_for_update().get(pk=orden.pk)
    if orden.estado not in (OrdenProduccion.EstadoOrden.EN_PROCESO, OrdenProduccion.EstadoOrden.BORRADOR):
        raise ErrorProduccion(f"La orden {orden.numero_orden} ya está {orden.get_estado_display().lower()}.")
    if not (motivo or '').strip():
        raise ErrorProduccion("Indica el motivo de la anulación.")
    en_taller = PartidaLote.objects.filter(lote__orden=orden, estado=PartidaLote.Estado.EN_TALLER).select_related(
        'taller', 'remision_linea__remision'
    )
    if en_taller.exists():
        detalle = ', '.join(f"{p.cantidad} u. en {p.taller} ({p.remision_linea.remision.numero})" for p in en_taller)
        raise ErrorProduccion(f"Hay unidades en talleres: {detalle}. Recíbelas o ciérralas con faltante antes de anular.")

    ahora = timezone.now()
    for partida in PartidaLote.objects.select_for_update().filter(lote__orden=orden, estado=PartidaLote.Estado.EN_ETAPA):
        Mov.objects.create(
            lote=partida.lote, partida=partida, etapa=partida.etapa, tipo=Mov.TipoMovimiento.ANULACION,
            cantidad=partida.cantidad, inicio_etapa=partida.fecha_ingreso, usuario=usuario, observaciones=motivo.strip(),
        )
        partida.estado = PartidaLote.Estado.CERRADA
        partida.fecha_cierre = ahora
        partida.save(update_fields=['estado', 'fecha_cierre'])
    orden.lotes.filter(estado=LoteProduccion.EstadoLote.EN_PROCESO).update(
        estado=LoteProduccion.EstadoLote.ANULADO, etapa_actual=None,
    )
    orden.estado = OrdenProduccion.EstadoOrden.ANULADA
    orden.motivo_anulacion = motivo.strip()
    orden.anulada_por = usuario
    orden.fecha_anulacion = ahora
    orden.save(update_fields=['estado', 'motivo_anulacion', 'anulada_por', 'fecha_anulacion'])
    orden.apagar_preventa()
    return orden


@transaction.atomic
def decidir_defecto(defecto, decision, taller, motivo, usuario):
    """Registra la decisión de Administración sobre un defecto. Nunca borra las anteriores."""
    if decision not in DefectoCalidad.Decision.values:
        raise ErrorProduccion("Decisión no válida.")
    if not (motivo or '').strip():
        raise ErrorProduccion("Indica el motivo de la decisión.")
    if decision == DefectoCalidad.Decision.DESCONTAR and taller is None:
        raise ErrorProduccion("Indica a qué taller se le descuenta.")
    if decision != DefectoCalidad.Decision.DESCONTAR:
        taller = None
    DecisionDefecto.objects.create(
        defecto=defecto, decision=decision, taller_responsable=taller, motivo=motivo.strip(), usuario=usuario,
    )
    defecto.decision = decision
    defecto.taller_responsable = taller
    defecto.save(update_fields=['decision', 'taller_responsable'])
    return defecto
