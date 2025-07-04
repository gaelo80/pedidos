# vendedores/models.py
from django.db import models
from django.conf import settings
from clientes.models import Empresa

class Vendedor(models.Model):
    """
    Representa a un vendedor o empleado.
    Este modelo está ligado a una Empresa específica (inquilino).
    """
    
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
        empresa_str = self.user.empresa.nombre if self.user.empresa else "Global"        
        return f"{nombre_display} ({empresa_str})"

    class Meta:
        verbose_name = "Vendedor"
        verbose_name_plural = "Vendedores"
        ordering = ['user__first_name', 'user__last_name']
        
    @property
    def empresa(self):
        return self.user.empresa


