# cartera/models.py
from django.db import models
from django.utils import timezone
from clientes.models import Cliente # Asumiendo que tienes una app clientes con el modelo Cliente
from decimal import Decimal

class DocumentoCartera(models.Model):
    """Guarda la información de una Factura o Remisión pendiente de un cliente."""
    
    TIPO_DOCUMENTO_CHOICES = [
        ('LF', 'Factura Oficial'),  # Viene de LF.xlsx
        ('FYN', 'Remisión'),       # Viene de FYN.xlsx
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='documentos_cartera') 
    tipo_documento = models.CharField(max_length=3, choices=TIPO_DOCUMENTO_CHOICES, db_index=True) 
    numero_documento = models.CharField(max_length=50, db_index=True) 
    fecha_documento = models.DateField(null=True, blank=True)
    fecha_vencimiento = models.DateField(null=True, blank=True, db_index=True)
    saldo_actual = models.DecimalField(max_digits=15, decimal_places=2, default=0.00) 
    nombre_vendedor_cartera = models.CharField(max_length=150, null=True, blank=True, help_text="Nombre del vendedor según el archivo de cartera (columna NOMVENDEDOR)")
    codigo_vendedor_cartera = models.CharField(max_length=20, null=True, blank=True, db_index=True, help_text="Código del vendedor según el archivo de cartera (VENDEDOR)")
    ultima_actualizacion_carga = models.DateTimeField(auto_now=True) 

    class Meta:
        verbose_name = "Documento de Cartera"
        verbose_name_plural = "Documentos de Cartera"
        # Asegúrate que esta combinación sea única para evitar duplicados.
        unique_together = ('cliente', 'tipo_documento', 'numero_documento') 
        ordering = ['cliente', 'fecha_vencimiento'] 

    def __str__(self):
        return f"{self.get_tipo_documento_display()} {self.numero_documento} - Cliente: {self.cliente.nombre_completo if self.cliente else 'N/A'} - Saldo: {self.saldo_actual}"

    @property
    def dias_mora(self):
        if self.fecha_vencimiento and self.saldo_actual > 0:
            hoy = timezone.now().date()
            if hoy > self.fecha_vencimiento:
                return (hoy - self.fecha_vencimiento).days
        return 0

    @property
    def esta_vencido(self):
        return self.dias_mora > 0

