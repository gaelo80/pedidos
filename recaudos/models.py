# recaudos/models.py
import os
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError

# --- IMPORTACIONES VALIDADAS ---
# Se importan los modelos de tus apps existentes
from clientes.models import Empresa, Cliente
from vendedores.models import Vendedor

def ruta_comprobante_consignacion(instance, filename):
    """
    Genera una ruta única para guardar el comprobante de consignación.
    Ej: media/empresa_1/consignaciones/2025/vendedor_5_comprobante.pdf
    """
    # Asegurarse de que la instancia y las relaciones no son None
    empresa_id = instance.empresa.id if instance.empresa else 'sin_empresa'
    vendedor_id = instance.vendedor.id if instance.vendedor else 'sin_vendedor'
    
    return os.path.join(
        f'empresa_{empresa_id}',
        'consignaciones',
        str(timezone.now().year),
        f'vendedor_{vendedor_id}_{filename}'
    )

class Recaudo(models.Model):
    """
    Registra un pago individual recibido por un vendedor de un cliente.
    """
    class Estado(models.TextChoices):
        EN_MANOS_DEL_VENDEDOR = 'EN_MANOS', 'En Manos del Vendedor'
        DEPOSITADO = 'DEPOSITADO', 'Depositado (Pend. Verificar)'
        VERIFICADO = 'VERIFICADO', 'Verificado y Cerrado'

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='recaudos')
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='pagos_realizados')
    vendedor = models.ForeignKey(Vendedor, on_delete=models.PROTECT, related_name='recaudos_realizados')
    
    monto_recibido = models.DecimalField(max_digits=15, decimal_places=2)
    fecha_recaudo = models.DateTimeField(default=timezone.now)
    concepto = models.TextField(blank=True, help_text="Ej: Abono a factura F-123, F-124. Pago total remisión R-55.")
    
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.EN_MANOS_DEL_VENDEDOR, db_index=True)
    
    # Relación con la consignación
    consignacion = models.ForeignKey(
        'Consignacion', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='recaudos_incluidos'
    )

    class Meta:
        verbose_name = "Recaudo de Dinero"
        verbose_name_plural = "Recaudos de Dinero"
        ordering = ['-fecha_recaudo']

    def __str__(self):
        return f"Recaudo #{self.id} de {self.cliente} por ${self.monto_recibido:,.2f}"

class Consignacion(models.Model):
    """
    Agrupa uno o más recaudos que han sido depositados en el banco.
    """
    class Estado(models.TextChoices):
        PENDIENTE_VERIFICACION = 'PENDIENTE', 'Pendiente de Verificación'
        VERIFICADA = 'VERIFICADA', 'Verificada'
        RECHAZADA = 'RECHAZADA', 'Rechazada'

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='consignaciones')
    vendedor = models.ForeignKey(Vendedor, on_delete=models.PROTECT, related_name='consignaciones_realizadas')
    
    fecha_consignacion = models.DateField(help_text="Fecha en que se realizó el depósito en el banco.")
    monto_total = models.DecimalField(max_digits=15, decimal_places=2, help_text="Monto total que figura en el comprobante de depósito.")
    numero_referencia = models.CharField(max_length=100, help_text="Número de la transacción o referencia del depósito.")
    
    comprobante_adjunto = models.FileField(
        upload_to=ruta_comprobante_consignacion,
        help_text="Foto o PDF del recibo de consignación."
    )
    
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE_VERIFICACION, db_index=True)
    notas_verificacion = models.TextField(blank=True, help_text="Notas del administrador al verificar o rechazar (ej: 'El valor no coincide').")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_verificacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Consignación"
        verbose_name_plural = "Consignaciones"
        ordering = ['-fecha_consignacion']

    def __str__(self):
        return f"Consignación de {self.vendedor} por ${self.monto_total:,.2f} ({self.fecha_consignacion})"

    def clean(self):
        # Validación para asegurar que el monto de la consignación coincida con los recaudos asociados
        if self.pk: # Solo si el objeto ya está guardado y tiene recaudos
            total_recaudos = self.recaudos_incluidos.aggregate(total=models.Sum('monto_recibido'))['total'] or 0
            if self.monto_total != total_recaudos:
                raise ValidationError(
                    f"El monto total de la consignación (${self.monto_total:,.2f}) no coincide "
                    f"con la suma de los recaudos incluidos (${total_recaudos:,.2f})."
                )