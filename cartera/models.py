# cartera/models.py

from django.db import models
from django.utils import timezone
from clientes.models import Cliente, Empresa # 1. IMPORTAMOS EL MODELO Empresa
from decimal import Decimal

class DocumentoCartera(models.Model):
    """Guarda la información de una Factura o Remisión pendiente de un cliente."""
    
    TIPO_DOCUMENTO_CHOICES = [
        ('LF', 'Factura Oficial'),
        ('FYN', 'Remisión'),
    ]

    empresa = models.ForeignKey(
        Empresa, 
        on_delete=models.CASCADE, 
        related_name='documentos_cartera',
        
    )

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='documentos_cartera_cliente') 
    tipo_documento = models.CharField(max_length=3, choices=TIPO_DOCUMENTO_CHOICES, db_index=True) 
    numero_documento = models.CharField(max_length=50, db_index=True) 
    fecha_documento = models.DateField(null=True, blank=True)
    fecha_vencimiento = models.DateField(null=True, blank=True, db_index=True)
    saldo_actual = models.DecimalField(max_digits=15, decimal_places=2, default=0.00) 
    nombre_vendedor_cartera = models.CharField(max_length=150, null=True, blank=True, help_text="Nombre del vendedor según el archivo de cartera (columna NOMVENDEDOR)")
    codigo_vendedor_cartera = models.CharField(max_length=20, null=True, blank=True, db_index=True, help_text="Código del vendedor según el archivo de cartera (VENDEDOR)")
    ultima_actualizacion_carga = models.DateTimeField(auto_now=True) 
    
    def save(self, *args, **kwargs):
        """
        Llama a clean() antes de guardar para asegurar que las validaciones se ejecuten siempre.
        """
        self.clean()
        super().save(*args, **kwargs)
    

    class Meta:
        verbose_name = "Documento de Cartera"
        verbose_name_plural = "Documentos de Cartera"
        #unique_together = ('empresa', 'tipo_documento', 'numero_documento') 
        ordering = ['empresa', 'cliente', 'fecha_vencimiento'] 
        constraints = [
            models.UniqueConstraint(
                fields=['empresa', 'cliente', 'numero_documento', 'tipo_documento'], 
                name='restriccion_factura_unica_por_cliente'
            )
        ]

    def __str__(self):
        return f"({self.empresa.nombre_corto if self.empresa else 'SIN EMPRESA'}) {self.get_tipo_documento_display()} {self.numero_documento} - Cliente: {self.cliente.nombre_completo if self.cliente else 'N/A'}"

    # Las properties no cambian, están perfectas.
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
    
class PerfilImportacionCartera(models.Model):
    """
    Define el mapeo de columnas y configuraciones para un formato de archivo Excel específico.
    """
    empresa = models.ForeignKey(
        Empresa, 
        on_delete=models.CASCADE,
        related_name='perfiles_importacion',
        help_text="Empresa a la que pertenece este formato de archivo."
    )
    nombre_perfil = models.CharField(
        max_length=100,
        unique=True,
        help_text="Nombre único para identificar este perfil (ej: 'Formato Contable S.A.S.')"
    )
    fila_inicio_header = models.PositiveIntegerField(
        default=3,
        help_text="Número de la fila en Excel donde comienzan los datos (ej: si los datos empiezan en la fila 4, poner 3)."
    )
    
    # --- Mapeo de Columnas ---
    # Guarda aquí el nombre EXACTO de la columna en el archivo Excel
    columna_id_cliente = models.CharField(max_length=50, default='CODIGO')
    columna_numero_documento = models.CharField(max_length=50, default='DOCUMENTO')
    columna_fecha_documento = models.CharField(max_length=50, default='FECHADOC')
    columna_fecha_vencimiento = models.CharField(max_length=50, default='FECHAVEN')
    columna_saldo = models.CharField(max_length=50, default='SALDOACT')
    columna_nombre_vendedor = models.CharField(max_length=50, default='NOMVENDEDOR')
    columna_codigo_vendedor = models.CharField(max_length=50, default='VENDEDOR')
    # Añade más campos si necesitas mapear más columnas (ej. concepto)

    def __str__(self):
        return f"{self.nombre_perfil} ({self.empresa.nombre})"

    class Meta:
        verbose_name = "Perfil de Importación de Cartera"
        verbose_name_plural = "Perfiles de Importación de Cartera"
        unique_together = ('empresa', 'nombre_perfil')