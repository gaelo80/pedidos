# pedidos_online/models.py

from django.db import models
from django.conf import settings
from clientes.models import Empresa # Reutilizamos el modelo Empresa existente
from productos.models import Producto # Reutilizamos el modelo Producto existente

class ClienteOnline(models.Model):
    """
    Nueva tabla para los clientes del canal Online.
    Contiene campos adicionales y específicos para este grupo.
    """
    # --- Choices para los nuevos campos ---
    TIPO_CLIENTE_CHOICES = [
        ('DETAL', 'Al Detal'),
        ('MAYOR', 'Al por Mayor'),
    ]
    FORMA_PAGO_CHOICES = [
        ('CONTADO', 'Contado'),
        ('CREDITO', 'Crédito'),
        ('ONLINE', 'Pago Online'),
    ]

    # --- Campos del modelo ---
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='clientes_online', verbose_name="Empresa")
    nombre_completo = models.CharField(max_length=255, verbose_name="Nombre Completo")
    identificacion = models.CharField(max_length=20, unique=True, verbose_name="Identificación")
    telefono = models.CharField(max_length=20, blank=True, verbose_name="Teléfono")
    email = models.EmailField(blank=True, verbose_name="Correo Electrónico")
    direccion = models.CharField(max_length=255, blank=True, verbose_name="Dirección")
    
    # --- Campos personalizados para el canal Online ---
    tipo_cliente = models.CharField(
        max_length=10, 
        choices=TIPO_CLIENTE_CHOICES, 
        default='DETAL', 
        verbose_name="Tipo de Cliente"
    )
    forma_pago_preferida = models.CharField(
        max_length=10, 
        choices=FORMA_PAGO_CHOICES, 
        default='CONTADO', 
        verbose_name="Forma de Pago Preferida"
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")

    def __str__(self):
        return f"{self.nombre_completo} (Online - {self.tipo_cliente})"

    class Meta:
        verbose_name = "Cliente Online"
        verbose_name_plural = "Clientes Online"
        ordering = ['nombre_completo']

class PrecioEspecial(models.Model):
    """
    Modelo para gestionar precios y promociones para el canal Online.
    Permite asignar un precio diferente a un producto para un tipo de cliente específico.
    """
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='precios_especiales', verbose_name="Producto")
    tipo_cliente = models.CharField(
        max_length=10, 
        choices=ClienteOnline.TIPO_CLIENTE_CHOICES, 
        verbose_name="Tipo de Cliente"
    )
    precio_especial = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio Especial")
    fecha_inicio = models.DateField(null=True, blank=True, verbose_name="Fecha de Inicio de Promoción")
    fecha_fin = models.DateField(null=True, blank=True, verbose_name="Fecha de Fin de Promoción")

    def __str__(self):
        return f"Precio para {self.producto.referencia} ({self.tipo_cliente}): ${self.precio_especial:,.0f}"

    class Meta:
        verbose_name = "Precio Especial"
        verbose_name_plural = "Precios Especiales"
        # Evita que se creen múltiples precios para la misma combinación de producto y tipo de cliente
        unique_together = ('producto', 'tipo_cliente')