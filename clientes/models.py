#clientes/models.py

from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings


class Empresa(models.Model):
    nombre = models.CharField(max_length=255, unique=True, verbose_name="Nombre de la Empresa")
    responsable_de_iva = models.BooleanField('Responsable de IVA', default=True)
    direccion = models.CharField(max_length=255, blank=True, null=True)
    ciudad = models.ForeignKey('Ciudad', on_delete=models.SET_NULL, null=True, blank=True)
    telefono = models.CharField(max_length=100, blank=True, null=True)
    correo_electronico = models.EmailField('Correo Electrónico', blank=True)    
    nit = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="NIT")    
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
    
    talla_mapeo = models.JSONField(
        null=True, 
        blank=True, 
        verbose_name="Mapeo de Tallas (Traducción)",
        help_text="OPCIONAL. Traduce tallas internas a tallas de muestra. Ej: {\"6\": \"3\", \"8\": \"5\"}"
    )
    
    categorias_tallas = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Configuración de Categorías y Tallas",
        help_text="""Define las categorías de productos y sus tallas para los PDFs. 
                     Formato: {"NOMBRE_CATEGORIA": ["talla1", "talla2"], ...}. 
                     Ej: {"DAMA": ["3", "5", "7"], "NIÑO": ["2", "4", "6"]}"""
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
    activo = models.BooleanField(default=True, verbose_name="¿Está Activo?")
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
        
        
      