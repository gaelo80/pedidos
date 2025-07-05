# prospectos/models.py
from django.db import models
from django.conf import settings
from clientes.models import Empresa, Ciudad # Reutilizamos modelos existentes de tu app clientes

class Prospecto(models.Model):
    """
    Representa a un cliente potencial que ha iniciado una solicitud de crédito
    pero que aún no es un cliente formal en el sistema.
    """
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente de Revisión'),
        ('EN_ESTUDIO', 'En Estudio de Crédito'),
        ('APROBADO', 'Aprobado'),
        ('RECHAZADO', 'Rechazado'),
    ]

    # --- Información básica del prospecto ---
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='prospectos', verbose_name="Empresa")
    nombre_completo = models.CharField(max_length=200, verbose_name="Nombre Completo")
    identificacion = models.CharField(max_length=20, verbose_name="Identificación (NIT/Cédula)")
    ciudad = models.ForeignKey(Ciudad, on_delete=models.PROTECT, verbose_name="Ciudad")
    direccion = models.CharField(max_length=255, verbose_name="Dirección")
    telefono = models.CharField(max_length=30, verbose_name="Teléfono")
    email = models.EmailField(max_length=100, verbose_name="Correo Electrónico")

    # --- Campos de control del flujo de aprobación ---
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE')
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    notas_evaluacion = models.TextField(blank=True, null=True, verbose_name="Notas de Evaluación de Cartera")
    
    # Enlace al usuario (vendedor) que registró el prospecto
    vendedor_asignado = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prospectos_asignados'
    )

    def __str__(self):
        return f"{self.nombre_completo} ({self.get_estado_display()})"

    class Meta:
        verbose_name = "Prospecto"
        verbose_name_plural = "Prospectos"
        # Asegura que no haya un prospecto duplicado (misma identificación) dentro de una misma empresa.
        unique_together = [['empresa', 'identificacion']]


class DocumentoAdjunto(models.Model):
    """
    Almacena un archivo (RUT, Cédula, etc.) asociado a un Prospecto.
    """
    TIPO_DOCUMENTO_CHOICES = [
        ('RUT', 'RUT'),
        ('CAMARA_COMERCIO', 'Cámara de Comercio'),
        ('REFERENCIAS', 'Referencias'),
        ('PAGARE', 'Pagaré Firmado'),
        ('TRATAMIENTO_DATOS', 'Autorización Tratamiento de Datos'),
        ('CEDULA', 'Cédula de Ciudadanía'),
        ('OTRO', 'Otro Documento'),
    ]

    prospecto = models.ForeignKey(Prospecto, on_delete=models.CASCADE, related_name='documentos', verbose_name="Prospecto Asociado")
    tipo_documento = models.CharField(max_length=30, choices=TIPO_DOCUMENTO_CHOICES, verbose_name="Tipo de Documento")
    archivo = models.FileField(upload_to='documentos_prospectos/%Y/%m/', verbose_name="Archivo Adjunto")
    fecha_carga = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Documento '{self.get_tipo_documento_display()}' para {self.prospecto.nombre_completo}"

    class Meta:
        verbose_name = "Documento Adjunto"
        verbose_name_plural = "Documentos Adjuntos"