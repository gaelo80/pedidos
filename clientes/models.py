#clientes/models.py

from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings


class Empresa(models.Model):
    nombre = models.CharField(max_length=255, unique=True, verbose_name="Nombre de la Empresa")
    nit = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="NIT")
    direccion = models.CharField(max_length=255, blank=True, null=True)
    telefono = models.CharField(max_length=100, blank=True, null=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    logo = models.ImageField(
        upload_to='logos/', # Directorio donde se guardarán los logos
        null=True,          # El logo es opcional
        blank=True,         # El logo es opcional en los formularios
        verbose_name="Logotipo"
    )

    titulo_web = models.CharField(
        max_length=100,
        blank=True, # Es opcional
        null=True,  # Es opcional
        verbose_name="Título para la Web",
        help_text="Ej: LOUIS FERRY Premiere, EXCLUSIVE. LA, etc."
    )

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Empresa Cliente"
        verbose_name_plural = "Empresas Clientes"

class Ciudad(models.Model):
    """Representa una ciudad donde pueden estar los clientes. Es un modelo global."""
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre de Ciudad")

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Ciudad"
        verbose_name_plural = "Ciudades"
        ordering = ['nombre']

class Cliente(models.Model):
    """Representa un cliente que puede realizar pedidos."""
    empresa = models.ForeignKey(
        Empresa, 
        on_delete=models.CASCADE, 
        related_name='clientes',
    )
    nombre_completo = models.CharField(max_length=200, verbose_name="Nombre Completo")
    
    # --- CORRECCIÓN CRÍTICA DE SEGURIDAD ---
    # Se elimina 'unique=True'. La unicidad a nivel de inquilino se maneja
    # con 'unique_together' en la clase Meta, que es la forma correcta.
    identificacion = models.CharField(max_length=20, blank=True, null=True, verbose_name="Identificación (NIT/Cédula)")
    
    direccion = models.CharField(max_length=255, blank=True, null=True, verbose_name="Dirección")
    ciudad = models.ForeignKey(
        Ciudad,
        on_delete=models.PROTECT,
        related_name='clientes',
        verbose_name="Ciudad"
    )
    telefono = models.CharField(max_length=30, blank=True, null=True, verbose_name="Teléfono")
    email = models.EmailField(max_length=100, blank=True, null=True, verbose_name="Correo Electrónico")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")

    def __str__(self):
        return f"{self.nombre_completo} ({self.identificacion or 'Sin ID'})"

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['nombre_completo']
        # Esta es la regla de unicidad CORRECTA para un sistema multi-inquilino.
        unique_together = [['empresa', 'identificacion']]

class Dominio(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='dominios')
    nombre_dominio = models.CharField(max_length=255, unique=True, db_index=True)
    es_principal = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.nombre_dominio} (para {self.empresa.nombre})"

    class Meta:
        verbose_name = "Dominio de Empresa"
        verbose_name_plural = "Dominios de Empresas"
        
        
      