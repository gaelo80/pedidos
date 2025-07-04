# core/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from clientes.models import Empresa

class User(AbstractUser):
    """
    Modelo de Usuario personalizado que hereda del de Django.
    AQUÍ SE CENTRALIZA LA RELACIÓN CON LA EMPRESA.
    """
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.SET_NULL,
        null=True,  # PERMITE QUE LOS SUPERUSUARIOS NO TENGAN EMPRESA
        blank=True,
        related_name='usuarios'
    )