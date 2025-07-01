# vendedores/models.py
from django.db import models
from django.conf import settings
from clientes.models import Empresa

class Vendedor(models.Model):
    """
    Representa a un vendedor o empleado.
    Este modelo está ligado a una Empresa específica (inquilino).
    """

    # --- CORRECCIÓN PARA LA MIGRACIÓN ---
    # Se añade null=True para permitir que las filas existentes en la base de datos
    # tengan este campo vacío temporalmente.
    empresa = models.ForeignKey(
        'clientes.Empresa', 
        on_delete=models.CASCADE, 
        verbose_name="Empresa",
        related_name='vendedores',
        null=True
    )
    
    # El OneToOneField ya asegura que un usuario solo puede tener un perfil de vendedor
    # en todo el sistema. La restricción en Meta asegura que también sea único por empresa.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="Usuario del Sistema",
        related_name='perfil_vendedor'
    )
    telefono_contacto = models.CharField(max_length=30, blank=True, null=True, verbose_name="Teléfono de Contacto (Opcional)")
    codigo_interno = models.CharField(max_length=20, blank=True, null=True, verbose_name="Código Interno (Opcional)")
    activo = models.BooleanField(default=True, verbose_name="¿Está Activo?")

    def __str__(self):
        nombre_completo = self.user.get_full_name()
        nombre_display = nombre_completo if nombre_completo else self.user.username
        empresa_str = self.empresa.nombre if self.empresa else "Sin Empresa"
        return f"{nombre_display} ({empresa_str})"

    class Meta:
        verbose_name = "Vendedor"
        verbose_name_plural = "Vendedores"
        ordering = ['empresa', 'user__first_name', 'user__last_name']

        constraints = [
            # Un código de vendedor interno debe ser único dentro de una misma empresa.
            models.UniqueConstraint(
                fields=['empresa', 'codigo_interno'], 
                name='unique_codigo_vendedor_por_empresa',
                condition=models.Q(codigo_interno__isnull=False)
            ),
            # Un usuario solo puede ser vendedor para una empresa.
            # Esta restricción es una capa extra de seguridad sobre el OneToOneField.
            models.UniqueConstraint(
                fields=['empresa', 'user'],
                name='unique_usuario_vendedor_por_empresa'
            )
        ]