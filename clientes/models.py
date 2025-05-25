from django.db import models
#from clientes.models import Cliente, Ciudad


# Create your models here.
class Cliente(models.Model):
        """Representa un cliente que puede realizar pedidos."""
        nombre_completo = models.CharField(max_length=200, verbose_name="Nombre Completo")
        identificacion = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="Identificación (NIT/Cédula)")
        direccion = models.CharField(max_length=255, blank=True, null=True, verbose_name="Dirección")
        ciudad = models.ForeignKey(
            'Ciudad',
            on_delete=models.PROTECT,
            related_name='clientes',
            verbose_name="Ciudad"
            #null=True,  # <--- AÑADIR TEMPORALMENTE
            #blank=True  # <--- AÑADIR TEMPORALMENTE (si quieres que también sea opcional en formularios/admin)

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
            
            
class Ciudad(models.Model):
        """Representa una ciudad donde pueden estar los clientes."""
        nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre de Ciudad")

        def __str__(self):
            return self.nombre

        class Meta:
            verbose_name = "Ciudad"
            verbose_name_plural = "Ciudades"