# factura/models.py
from django.db import models
from django.conf import settings 
from django.utils import timezone


class Factura(models.Model):

    ESTADO_CHOICES = [
        ('PENDIENTE_FACTURAR', 'Pendiente por Facturar'),
        ('FACTURADO', 'Facturado'),
        ('ANULADO', 'Factura Anulada'),
    ]

    pedido = models.OneToOneField(
        'pedidos.Pedido',
        on_delete=models.CASCADE,
        related_name='registro_factura',
        verbose_name="Pedido Asociado"
    )
    estado_facturacion = models.CharField(
        max_length=25,
        choices=ESTADO_CHOICES,
        default='PENDIENTE_FACTURAR',
        verbose_name="Estado de Facturación"
    )
    numero_factura = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Número de Factura/Documento"
    )
    fecha_facturacion = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Fecha y Hora de Facturación"
    )
    usuario_accion = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='facturas_gestionadas_%(app_label)s_factura_model',
        verbose_name="Usuario (Acción Factura)"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    notas = models.TextField(blank=True, null=True, verbose_name="Notas Adicionales de Facturación")

    def __str__(self):
        return f"Facturación Pedido #{self.pedido.pk} - {self.get_estado_facturacion_display()}"

    class Meta:
        verbose_name = "Registro de Facturación de Pedido" # Ajustado para diferenciar
        verbose_name_plural = "Registros de Facturación de Pedidos"
        ordering = ['-pedido__fecha_hora']


class EstadoFacturaDespacho(models.Model):

    ESTADO_CHOICES = [
        ('POR_FACTURAR', 'Por Facturar'),
        ('FACTURADO', 'Facturado'),
    ]

    despacho = models.OneToOneField(
        'bodega.ComprobanteDespacho',
        on_delete=models.PROTECT,
        primary_key=True,
        related_name='estado_facturacion_info',
        verbose_name="Comprobante de Despacho Asociado"
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='POR_FACTURAR',
        db_index=True,
        verbose_name="Estado de Facturación"
    )
    fecha_hora_facturado_sistema = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha/Hora Marcado como Facturado (Sistema)",
        help_text="Fecha y hora en que se actualizó el estado a FACTURADO en esta aplicación."
    )
    usuario_responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='despachos_facturados_gestionados_por_usuario',
        verbose_name="Usuario Responsable (Facturación)"
    )
    referencia_factura_externa = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Referencia Factura Externa",
        help_text="Número o ID de la factura en el sistema contable externo."
    )
    notas_facturacion = models.TextField(
        blank=True,
        null=True,
        verbose_name="Notas Adicionales de Facturación"
    )
    fecha_creacion_registro = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación del Registro")
    fecha_ultima_modificacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de Última Modificación")

    def __str__(self):
        return f"Facturación para Despacho Bodega ID: {self.despacho_id} - Estado: {self.get_estado_display()}"

    class Meta:
        verbose_name = "Estado de Facturación de Despacho"
        verbose_name_plural = "Estados de Facturación de Despachos"
        ordering = ['despacho__fecha_hora_despacho']
        permissions = [

            ("view_despachos_a_facturar", "Puede ver lista de despachos por facturar"),
            ("can_mark_despacho_facturado", "Puede marcar un despacho como facturado"),
            ("view_informe_facturados_fecha", "Puede ver informe de facturados por fecha"),
            ("view_informe_despachos_cliente", "Puede ver informe de despachos por cliente (factura)"),
            ("view_informe_despachos_estado", "Puede ver informe de despachos por estado (factura)"),
            ("view_informe_despachos_pedido", "Puede ver informe de despachos por pedido (factura)"),
        ]