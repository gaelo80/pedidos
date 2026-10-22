from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from clientes.models import Empresa


class EtapaProduccion(models.Model):
    """
    Catálogo de etapas del proceso productivo (Corte, Confección, Lavandería,
    Control de Calidad, Empaque, Bodega...). Editable por empresa -- si mañana
    se necesita agregar "Bordado" o "Estampado", se hace aquí sin tocar código.
    """
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='etapas_produccion')
    nombre = models.CharField(max_length=100)
    orden = models.PositiveIntegerField(
        default=0, help_text="Orden sugerido al armar la ruta de una nueva orden de producción."
    )
    es_control_calidad = models.BooleanField(
        default=False,
        help_text="Marca la etapa donde se clasifican las unidades en buenas/segunda/tercera. Las segundas/terceras salen de la ruta normal hacia la bodega de Calidad."
    )
    es_ingreso_bodega = models.BooleanField(
        default=False,
        help_text="Marca la etapa donde el lote entra de verdad al inventario de bodega (crea el movimiento real y habilita la venta)."
    )
    es_externa = models.BooleanField(
        default=False,
        help_text="La hace un taller externo (ej. Confección, Lavandería): las unidades salen con remisión y vuelven con comprobante de recepción."
    )
    dias_alerta = models.PositiveIntegerField(
        default=2,
        help_text="Días que una partida puede estar en esta etapa antes de marcarse como atrasada en el tablero."
    )
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Etapa de Producción"
        verbose_name_plural = "Etapas de Producción"
        ordering = ['orden', 'nombre']
        unique_together = ('empresa', 'nombre')

    def __str__(self):
        return self.nombre


class TallerExterno(models.Model):
    """Taller satélite (confección, lavandería...) al que se envían unidades con remisión."""
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='talleres_externos')
    nombre = models.CharField(max_length=150)
    nit = models.CharField(max_length=30, blank=True, verbose_name="NIT / Cédula")
    telefono = models.CharField(max_length=30, blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    contacto = models.CharField(max_length=150, blank=True, verbose_name="Persona de contacto")
    etapas = models.ManyToManyField(
        EtapaProduccion, related_name='talleres', blank=True,
        help_text="Etapas externas que atiende este taller (ej. Confección)."
    )
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Taller Externo"
        verbose_name_plural = "Talleres Externos"
        ordering = ['nombre']
        unique_together = ('empresa', 'nombre')

    def __str__(self):
        return self.nombre


def _siguiente_consecutivo(modelo, empresa, campo, prefijo):
    """Consecutivo por empresa (PREFIJO-00001...), mismo patrón que OrdenProduccion/TrasladoBodega."""
    ultimo = (
        modelo.objects.filter(empresa=empresa).select_for_update()
        .order_by(f'-{campo}').values_list(campo, flat=True).first()
    )
    siguiente = 1
    if ultimo:
        try:
            siguiente = int(ultimo.split('-')[1]) + 1
        except (IndexError, ValueError):
            siguiente = modelo.objects.filter(empresa=empresa).count() + 1
    return f"{prefijo}-{siguiente:05d}"


class OrdenProduccion(models.Model):
    class EstadoOrden(models.TextChoices):
        BORRADOR = 'BORRADOR', 'Borrador'
        EN_PROCESO = 'EN_PROCESO', 'En Proceso'
        TERMINADA = 'TERMINADA', 'Terminada'
        ANULADA = 'ANULADA', 'Anulada'

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='ordenes_produccion', db_index=True)
    numero_orden = models.CharField(max_length=20, blank=True, editable=False, help_text="Se genera solo (ej. OP-00001).")
    referencia_color = models.ForeignKey(
        'productos.ReferenciaColor', on_delete=models.PROTECT, related_name='ordenes_produccion',
        help_text="La referencia+color debe existir ya en el catálogo -- esta orden solo arranca su producción."
    )
    permitir_venta_sin_stock = models.BooleanField(
        default=False,
        verbose_name="¿Se puede vender mientras está en producción?",
        help_text="Si se marca, las tallas de esta referencia quedan disponibles para la venta (preventa) aunque todavía no haya stock físico."
    )
    estado = models.CharField(max_length=20, choices=EstadoOrden.choices, default=EstadoOrden.BORRADOR)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ordenes_produccion_creadas'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_estimada_entrega = models.DateField(null=True, blank=True)
    notas = models.TextField(blank=True, null=True)
    motivo_anulacion = models.TextField(blank=True)
    anulada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    fecha_anulacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Orden de Producción"
        verbose_name_plural = "Órdenes de Producción"
        ordering = ['-fecha_creacion']
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'numero_orden'], name='numero_orden_unico_por_empresa')
        ]

    def save(self, *args, **kwargs):
        # Numeración consecutiva por empresa (OP-00001...), mismo patrón que
        # TrasladoBodega.save() en la app bodega.
        if self.pk is None and not self.numero_orden:
            with transaction.atomic():
                ultimo = (
                    OrdenProduccion.objects.filter(empresa=self.empresa)
                    .select_for_update()
                    .order_by('-numero_orden')
                    .first()
                )
                siguiente = 1
                if ultimo and ultimo.numero_orden:
                    try:
                        siguiente = int(ultimo.numero_orden.split('-')[1]) + 1
                    except (IndexError, ValueError):
                        siguiente = OrdenProduccion.objects.filter(empresa=self.empresa).count() + 1
                self.numero_orden = f"OP-{siguiente:05d}"
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

    @property
    def total_tallas(self):
        return self.lotes.count()

    def apagar_preventa(self):
        """
        Al terminar o anular una orden que habilitó la preventa, la apaga en
        las tallas de su referencia+color, salvo que otra orden en proceso de
        la misma referencia+color también la tenga habilitada.
        """
        if not self.permitir_venta_sin_stock:
            return
        otra_activa = OrdenProduccion.objects.filter(
            referencia_color_id=self.referencia_color_id, estado=self.EstadoOrden.EN_PROCESO,
            permitir_venta_sin_stock=True,
        ).exclude(pk=self.pk).exists()
        if not otra_activa:
            self.referencia_color.variantes.filter(permitir_preventa=True).update(permitir_preventa=False)

    def __str__(self):
        return f"{self.numero_orden} - {self.referencia_color}"


class RutaOrdenProduccion(models.Model):
    """La secuencia de etapas que ESTA orden en particular debe recorrer -- permite saltarse o agregar etapas sin tocar código."""
    orden = models.ForeignKey(OrdenProduccion, on_delete=models.CASCADE, related_name='ruta')
    etapa = models.ForeignKey(EtapaProduccion, on_delete=models.PROTECT, related_name='+')
    secuencia = models.PositiveIntegerField()

    class Meta:
        verbose_name = "Paso de Ruta (Orden de Producción)"
        verbose_name_plural = "Pasos de Ruta (Orden de Producción)"
        unique_together = (('orden', 'secuencia'), ('orden', 'etapa'))
        ordering = ['secuencia']

    def __str__(self):
        return f"{self.secuencia}. {self.etapa.nombre}"


class LoteProduccion(models.Model):
    """
    Un lote = una talla de una Orden de Producción, trazada por etapa.
    Se hace 1 lote por talla (no una mezcla) para poder atribuir sin
    ambigüedad las segundas/terceras al Producto (SKU) real que les
    corresponde cuando pasan por Control de Calidad.
    """
    class EstadoLote(models.TextChoices):
        EN_PROCESO = 'EN_PROCESO', 'En Proceso'
        TERMINADO = 'TERMINADO', 'Terminado'
        ANULADO = 'ANULADO', 'Anulado'

    orden = models.ForeignKey(OrdenProduccion, on_delete=models.CASCADE, related_name='lotes')
    numero_lote = models.CharField(max_length=40, blank=True, editable=False)
    talla = models.CharField(max_length=20)
    cantidad_inicial = models.PositiveIntegerField()
    cantidad_actual = models.PositiveIntegerField(
        help_text="Unidades buenas que siguen vivas en este lote (se reduce con cada merma/segunda/tercera)."
    )
    etapa_actual = models.ForeignKey(EtapaProduccion, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    estado = models.CharField(max_length=20, choices=EstadoLote.choices, default=EstadoLote.EN_PROCESO)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_ultimo_movimiento = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Lote de Producción"
        verbose_name_plural = "Lotes de Producción"
        unique_together = ('orden', 'talla')
        ordering = ['numero_lote']

    def save(self, *args, **kwargs):
        if self.pk is None and not self.numero_lote:
            self.numero_lote = f"{self.orden.numero_orden}-T{self.talla}"
        super().save(*args, **kwargs)


    def etapa_siguiente_de(self, etapa):
        """Etapa después de 'etapa' en la ruta de la orden, o None si es la última."""
        ruta = [r.etapa for r in self.orden.ruta.select_related('etapa').order_by('secuencia')]
        ids = [e.pk for e in ruta]
        if etapa.pk not in ids:
            return None
        idx = ids.index(etapa.pk)
        return ruta[idx + 1] if idx + 1 < len(ruta) else None

    def primera_etapa(self):
        paso = self.orden.ruta.select_related('etapa').order_by('secuencia').first()
        return paso.etapa if paso else None

    def producto_real(self):
        """El Producto (SKU) real del catálogo que corresponde a este lote (misma referencia+color+talla)."""
        return self.orden.referencia_color.variantes.filter(activo=True, talla=self.talla).first()

    @property
    def por_cortar(self):
        """Todavía no se ha registrado cuántas unidades salieron de corte."""
        return self.estado == self.EstadoLote.EN_PROCESO and not self.partidas.exists()

    def actualizar_estado(self):
        """Termina el lote cuando ya no le queda ninguna partida abierta; y la orden cuando no le queda ningún lote vivo."""
        if self.partidas.exists() and not self.partidas.exclude(estado=PartidaLote.Estado.CERRADA).exists():
            self.estado = self.EstadoLote.TERMINADO
            self.etapa_actual = None
            self.save(update_fields=['estado', 'etapa_actual'])
        orden = self.orden
        if orden.estado == OrdenProduccion.EstadoOrden.EN_PROCESO and not orden.lotes.filter(
            estado=self.EstadoLote.EN_PROCESO
        ).exists():
            orden.estado = OrdenProduccion.EstadoOrden.TERMINADA
            orden.save(update_fields=['estado'])
            orden.apagar_preventa()

    def __str__(self):
        return self.numero_lote


class PartidaLote(models.Model):
    """
    Una parte de un lote que está en un mismo sitio: N unidades en una etapa
    (y, si la etapa es externa, en un taller). Un lote se puede repartir en
    varias partidas que avanzan por separado; cada una lleva su propio reloj
    desde que llegó a donde está.
    """
    class Estado(models.TextChoices):
        EN_ETAPA = 'EN_ETAPA', 'En planta'
        EN_TALLER = 'EN_TALLER', 'En taller externo'
        CERRADA = 'CERRADA', 'Cerrada'

    lote = models.ForeignKey(LoteProduccion, on_delete=models.CASCADE, related_name='partidas')
    numero = models.CharField(max_length=50, editable=False)
    etapa = models.ForeignKey(EtapaProduccion, on_delete=models.PROTECT, related_name='+')
    taller = models.ForeignKey(TallerExterno, on_delete=models.PROTECT, null=True, blank=True, related_name='partidas')
    cantidad = models.PositiveIntegerField(help_text="Unidades que siguen en esta partida.")
    cantidad_inicial = models.PositiveIntegerField(help_text="Unidades con que nació esta partida.")
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.EN_ETAPA)
    origen = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='derivadas')
    remision_linea = models.ForeignKey(
        'RemisionLinea', on_delete=models.PROTECT, null=True, blank=True, related_name='partidas',
        help_text="Línea de remisión con la que esta partida salió al taller."
    )
    fecha_ingreso = models.DateTimeField(default=timezone.now, help_text="Desde cuándo está donde está.")
    fecha_cierre = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Partida de Lote"
        verbose_name_plural = "Partidas de Lote"
        ordering = ['fecha_ingreso']

    def save(self, *args, **kwargs):
        if self.pk is None and not self.numero:
            self.numero = f"{self.lote.numero_lote}-P{self.lote.partidas.count() + 1}"
        super().save(*args, **kwargs)

    @property
    def tiempo_aqui(self):
        fin = self.fecha_cierre or timezone.now()
        return fin - self.fecha_ingreso

    @property
    def atrasada(self):
        return self.estado != self.Estado.CERRADA and self.tiempo_aqui.days >= self.etapa.dias_alerta

    def __str__(self):
        return f"{self.numero} ({self.cantidad} u.)"


class MovimientoLoteProduccion(models.Model):
    """Kardex de trazabilidad del lote: cada paso de cada partida, con su duración."""
    class TipoMovimiento(models.TextChoices):
        INGRESO = 'INGRESO', 'Ingreso a la etapa'
        SALIDA = 'SALIDA', 'Salida de la etapa'
        CORTE = 'CORTE', 'Corte (cantidad inicial)'
        ENVIO_TALLER = 'ENVIO_TALLER', 'Envío a taller'
        RECEPCION_TALLER = 'RECEPCION_TALLER', 'Recepción de taller'
        FALTANTE = 'FALTANTE', 'Faltante de taller'
        PERDIDA = 'PERDIDA', 'Pérdida en planta'
        CALIDAD = 'CALIDAD', 'Segundas/terceras'
        INGRESO_BODEGA = 'INGRESO_BODEGA', 'Ingreso a bodega'
        CORRECCION = 'CORRECCION', 'Corrección'
        ANULACION = 'ANULACION', 'Anulación de la orden'

    lote = models.ForeignKey(LoteProduccion, on_delete=models.CASCADE, related_name='movimientos')
    partida = models.ForeignKey(PartidaLote, on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos')
    etapa = models.ForeignKey(EtapaProduccion, on_delete=models.PROTECT, related_name='+')
    taller = models.ForeignKey(TallerExterno, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    tipo = models.CharField(max_length=20, choices=TipoMovimiento.choices)
    cantidad = models.IntegerField(null=True, blank=True)
    cantidad_buena = models.PositiveIntegerField(null=True, blank=True)
    cantidad_segunda = models.PositiveIntegerField(null=True, blank=True, default=0)
    cantidad_tercera = models.PositiveIntegerField(null=True, blank=True, default=0)
    inicio_etapa = models.DateTimeField(
        null=True, blank=True, help_text="Desde cuándo estaban estas unidades en la etapa (para medir cuánto duraron)."
    )
    documento = models.CharField(max_length=40, blank=True, help_text="Remisión, recepción u otro documento asociado.")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    fecha_hora = models.DateTimeField(auto_now_add=True)
    observaciones = models.TextField(blank=True, null=True, help_text="Novedades para que administración tome acción.")

    class Meta:
        verbose_name = "Movimiento de Lote"
        verbose_name_plural = "Movimientos de Lote"
        ordering = ['-fecha_hora', '-pk']

    @property
    def duracion(self):
        if self.inicio_etapa and self.fecha_hora:
            return self.fecha_hora - self.inicio_etapa
        return None

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.lote.numero_lote} - {self.etapa.nombre}"


# ============================================================
# Remisiones y recepciones de talleres externos
# ============================================================
# Estos documentos sustentan lo que se le paga a cada taller, por eso NO se
# editan ni se borran: un error se corrige con una CorreccionProduccion que
# deja motivo, usuario y fecha.

class RemisionTaller(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='remisiones_taller')
    numero = models.CharField(max_length=20, editable=False)
    taller = models.ForeignKey(TallerExterno, on_delete=models.PROTECT, related_name='remisiones')
    etapa = models.ForeignKey(EtapaProduccion, on_delete=models.PROTECT, related_name='+')
    fecha_hora = models.DateTimeField(default=timezone.now)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Remisión a Taller"
        verbose_name_plural = "Remisiones a Talleres"
        ordering = ['-fecha_hora']
        constraints = [models.UniqueConstraint(fields=['empresa', 'numero'], name='remision_taller_numero_unico')]

    def save(self, *args, **kwargs):
        if self.pk is None and not self.numero:
            with transaction.atomic():
                self.numero = _siguiente_consecutivo(RemisionTaller, self.empresa, 'numero', 'REM')
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

    @property
    def total_enviado(self):
        return sum(l.cantidad_enviada_total for l in self.lineas.all())

    @property
    def total_pendiente(self):
        return sum(l.pendiente for l in self.lineas.all())

    @property
    def abierta(self):
        return self.total_pendiente > 0

    def __str__(self):
        return f"{self.numero} - {self.taller}"


class RemisionLinea(models.Model):
    remision = models.ForeignKey(RemisionTaller, on_delete=models.PROTECT, related_name='lineas')
    lote = models.ForeignKey(LoteProduccion, on_delete=models.PROTECT, related_name='+')
    cantidad_enviada = models.PositiveIntegerField()

    class Meta:
        verbose_name = "Línea de Remisión"
        verbose_name_plural = "Líneas de Remisión"

    def _suma_correcciones(self, tipo):
        return self.correcciones.filter(tipo=tipo).aggregate(t=models.Sum('cantidad'))['t'] or 0

    @property
    def cantidad_enviada_total(self):
        return self.cantidad_enviada + self._suma_correcciones(CorreccionProduccion.Tipo.ENVIO)

    @property
    def cantidad_recibida(self):
        recibido = self.recepciones.aggregate(t=models.Sum('cantidad_recibida'))['t'] or 0
        return recibido + self._suma_correcciones(CorreccionProduccion.Tipo.RECEPCION)

    @property
    def cantidad_faltante(self):
        return self.recepciones.aggregate(t=models.Sum('cantidad_faltante'))['t'] or 0

    @property
    def pendiente(self):
        return max(self.cantidad_enviada_total - self.cantidad_recibida - self.cantidad_faltante, 0)

    def __str__(self):
        return f"{self.remision.numero} / {self.lote.numero_lote}"


class RecepcionTaller(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='recepciones_taller')
    numero = models.CharField(max_length=20, editable=False)
    remision = models.ForeignKey(RemisionTaller, on_delete=models.PROTECT, related_name='recepciones')
    fecha_hora = models.DateTimeField(default=timezone.now)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Recepción de Taller"
        verbose_name_plural = "Recepciones de Talleres"
        ordering = ['-fecha_hora']
        constraints = [models.UniqueConstraint(fields=['empresa', 'numero'], name='recepcion_taller_numero_unico')]

    def save(self, *args, **kwargs):
        if self.pk is None and not self.numero:
            with transaction.atomic():
                self.numero = _siguiente_consecutivo(RecepcionTaller, self.empresa, 'numero', 'REC')
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.numero} ({self.remision.numero})"


class RecepcionLinea(models.Model):
    recepcion = models.ForeignKey(RecepcionTaller, on_delete=models.PROTECT, related_name='lineas')
    remision_linea = models.ForeignKey(RemisionLinea, on_delete=models.PROTECT, related_name='recepciones')
    cantidad_recibida = models.PositiveIntegerField(default=0)
    cantidad_faltante = models.PositiveIntegerField(
        default=0, help_text="Unidades que el taller no devolvió y se dan por perdidas al cerrar la línea."
    )
    partida_destino = models.ForeignKey(PartidaLote, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        verbose_name = "Línea de Recepción"
        verbose_name_plural = "Líneas de Recepción"


class CorreccionProduccion(models.Model):
    """Corrige una cantidad ya registrada en una remisión o recepción sin borrar el original."""
    class Tipo(models.TextChoices):
        ENVIO = 'ENVIO', 'Corrección de cantidad enviada'
        RECEPCION = 'RECEPCION', 'Corrección de cantidad recibida'

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='+')
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    remision_linea = models.ForeignKey(RemisionLinea, on_delete=models.PROTECT, related_name='correcciones')
    cantidad = models.IntegerField(help_text="Positivo suma, negativo resta.")
    motivo = models.TextField()
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    fecha_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Corrección de Producción"
        verbose_name_plural = "Correcciones de Producción"
        ordering = ['-fecha_hora']


# ============================================================
# Control de calidad: segundas/terceras y decisión de descuento
# ============================================================

class DefectoCalidad(models.Model):
    """
    Segundas/terceras detectadas en Control de Calidad. Si se le descuentan o
    no al taller lo decide Administración caso a caso; cada decisión queda en
    DecisionDefecto (con motivo, usuario y fecha) y nunca se borra.
    """
    class Causa(models.TextChoices):
        PROCESO = 'PROCESO', 'Proceso (etapa de producción)'
        TELA = 'TELA', 'Tela / material'
        OTRO = 'OTRO', 'Otro'

    class Decision(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        DESCONTAR = 'DESCONTAR', 'Descontar al taller'
        NO_DESCONTAR = 'NO_DESCONTAR', 'No descontar'

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='+')
    lote = models.ForeignKey(LoteProduccion, on_delete=models.PROTECT, related_name='defectos')
    partida = models.ForeignKey(PartidaLote, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    etapa = models.ForeignKey(EtapaProduccion, on_delete=models.PROTECT, related_name='+', help_text="Etapa donde se detectó.")
    cantidad_segunda = models.PositiveIntegerField(default=0)
    cantidad_tercera = models.PositiveIntegerField(default=0)
    causa = models.CharField(max_length=20, choices=Causa.choices)
    etapa_causa = models.ForeignKey(
        EtapaProduccion, on_delete=models.PROTECT, null=True, blank=True, related_name='+',
        help_text="Si la causa es un proceso: en qué etapa se originó el defecto."
    )
    observaciones = models.TextField(blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    fecha_hora = models.DateTimeField(auto_now_add=True)
    decision = models.CharField(max_length=20, choices=Decision.choices, default=Decision.PENDIENTE)
    taller_responsable = models.ForeignKey(TallerExterno, on_delete=models.PROTECT, null=True, blank=True, related_name='defectos')

    class Meta:
        verbose_name = "Defecto de Calidad"
        verbose_name_plural = "Defectos de Calidad"
        ordering = ['-fecha_hora']

    @property
    def total(self):
        return self.cantidad_segunda + self.cantidad_tercera

    def talleres_posibles(self):
        """Talleres que tuvieron unidades de este lote en la etapa donde se originó el defecto."""
        if not self.etapa_causa_id:
            return TallerExterno.objects.none()
        ids = RemisionLinea.objects.filter(
            lote=self.lote, remision__etapa_id=self.etapa_causa_id
        ).values_list('remision__taller_id', flat=True)
        return TallerExterno.objects.filter(pk__in=ids)


class DecisionDefecto(models.Model):
    defecto = models.ForeignKey(DefectoCalidad, on_delete=models.CASCADE, related_name='decisiones')
    decision = models.CharField(max_length=20, choices=DefectoCalidad.Decision.choices)
    taller_responsable = models.ForeignKey(TallerExterno, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    motivo = models.TextField()
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    fecha_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Decisión sobre Defecto"
        verbose_name_plural = "Decisiones sobre Defectos"
        ordering = ['-fecha_hora']
