from django.db import models
from django.contrib.auth.models import User 
from django.conf import settings 


# Create your models here.
class Vendedor(models.Model):
        """Representa a un vendedor o empleado que toma pedidos."""
        user = models.OneToOneField(
            User,
            on_delete=models.CASCADE,
            verbose_name="Usuario del Sistema",
            related_name='perfil_vendedor'
        )
        telefono_contacto = models.CharField(max_length=30, blank=True, null=True, verbose_name="Teléfono de Contacto (Opcional)")
        codigo_interno = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="Código Interno (Opcional)")
        activo = models.BooleanField(default=True, verbose_name="¿Está Activo?")

        def __str__(self):
            nombre = self.user.get_full_name()
            if nombre:
                return nombre
            return self.user.username

        class Meta:
            verbose_name = "Vendedor"
            verbose_name_plural = "Vendedores"
            ordering = ['user__username']