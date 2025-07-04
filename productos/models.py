# productos/models.py
import os
import uuid
from django.db import models
from django.db.models import Sum, Q
from django.conf import settings
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from clientes.models import Empresa

# Se elimina la importación de 'bodega.models' de aquí para evitar errores de importación circular.
# Se importará directamente dentro de la función que la necesita.

def ruta_guardado_foto_producto_agrupada(instance, filename):
    """
    Construye la ruta de guardado para la imagen de un producto,
    organizada por la empresa a la que pertenece.
    """
    tenant_folder = "empresa_sin_asignar"
    if instance.referencia_color and instance.referencia_color.empresa:
        tenant_folder = f"empresa_{instance.referencia_color.empresa.id}"
    
    nombre_base, extension = os.path.splitext(filename)
    nombre_limpio = slugify(nombre_base)
    id_unico = uuid.uuid4().hex[:6]
    nuevo_filename = f"{nombre_limpio}-{id_unico}{extension.lower()}"
    
    return f'fotos_productos/{tenant_folder}/{nuevo_filename}'

class ReferenciaColor(models.Model):
    """
    Agrupa productos por referencia y color, y contiene las fotos.
    """
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='referencias_color',
        null=True
    )
    referencia_base = models.CharField(max_length=100, db_index=True)
    color = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    nombre_display = models.CharField(max_length=255, blank=True, null=True, help_text="Nombre para mostrar, ej: 'Camisa Polo Azul'")

    def __str__(self):
        empresa_str = self.empresa.nombre if self.empresa else "Sin Empresa"
        color_str = self.color if self.color else "Sin Color"
        return f"{self.referencia_base} - {color_str} ({empresa_str})"

    def save(self, *args, **kwargs):
        if not self.nombre_display:
            color_str = self.color if self.color else "General"
            self.nombre_display = f"Fotos para: {self.referencia_base} ({color_str})"
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Artículo por Color (para Fotos)"
        verbose_name_plural = "Artículos por Color (para Fotos)"
        ordering = ['empresa', 'referencia_base', 'color']
        constraints = [
            models.UniqueConstraint(
                fields=['empresa', 'referencia_base', 'color'], 
                name='agrupacion_unica_por_empresa'
            )
        ]

class FotoProducto(models.Model):
    """
    Almacena una imagen individual para una combinación de ReferenciaColor.
    """
    # --- CORRECCIÓN PARA LA MIGRACIÓN ---
    referencia_color = models.ForeignKey(
        ReferenciaColor,
        related_name='fotos_agrupadas',
        on_delete=models.CASCADE,
        verbose_name="Artículo por Color (Agrupador de Fotos)",
        #null=True # Se añade para permitir la migración en bases de datos existentes.
    )
    imagen = models.ImageField(
        upload_to=ruta_guardado_foto_producto_agrupada,
        verbose_name="Archivo de Imagen"
    )
    descripcion_foto = models.CharField(max_length=255, blank=True, null=True, verbose_name="Descripción de la Foto (Opcional)")
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden de Visualización")
    
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='fotos_productos',
        editable=False,
        null=True
    )

    def __str__(self):
        agrupador_str = str(self.referencia_color) if self.referencia_color else "Sin Agrupador"
        imagen_nombre = self.imagen.name.split('/')[-1] if self.imagen and self.imagen.name else "Sin Imagen"
        return f"Foto de {agrupador_str} - Archivo: {imagen_nombre}"
    
    def clean(self):
        super().clean()
        if not self.referencia_color:
            raise ValidationError("Una foto debe estar siempre asociada a un 'Artículo por Color'.")
        if self.referencia_color.empresa is None:
             raise ValidationError("El agrupador 'Artículo por Color' asociado no tiene una empresa definida.")

    def save(self, *args, **kwargs):
        if self.referencia_color:
            self.empresa = self.referencia_color.empresa
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Foto de Artículo (por Ref+Color)"
        verbose_name_plural = "Fotos de Artículos (por Ref+Color)"
        ordering = ['referencia_color', 'orden']

class Producto(models.Model):
    """
    Representa una VARIANTE específica (SKU) y pertenece a una Empresa.
    """
    empresa = models.ForeignKey(
        'clientes.Empresa',
        on_delete=models.CASCADE,
        related_name='productos',
        verbose_name="Empresa Propietaria",
        null=True
    )
    
    articulo_color_fotos = models.ForeignKey(
        ReferenciaColor,
        on_delete=models.PROTECT,
        related_name='variantes',
        verbose_name="Agrupación de Fotos (Ref+Color)",
        help_text="Se asigna automáticamente al guardar.",
        null=True, blank=True
    )
    
    referencia = models.CharField(max_length=50, db_index=True, verbose_name="Referencia")
    nombre = models.CharField(max_length=200, verbose_name="Nombre del Producto")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    talla = models.CharField(max_length=20, blank=True, null=True, db_index=True)
    color = models.CharField(max_length=50, blank=True, null=True, db_index=True)

    GENERO_CHOICES = [
        ('DAMA', 'Dama'), ('CABALLERO', 'Caballero'), ('UNISEX', 'Unisex'),
    ]
    genero = models.CharField(max_length=10, choices=GENERO_CHOICES, db_index=True, default='UNISEX')
    costo = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    unidad_medida = models.CharField(max_length=20, default='UND')
    ubicacion = models.CharField(max_length=100, blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True, db_index=True)
    codigo_barras = models.CharField(max_length=100, blank=True, null=True, db_index=True)

    @property
    def stock_actual(self):
        from bodega.models import MovimientoInventario
        if not self.empresa_id:
            return 0
        suma = MovimientoInventario.objects.filter(
            producto=self,
            empresa=self.empresa
        ).aggregate(total=Sum('cantidad'))['total']
        return suma or 0
    
    def save(self, *args, **kwargs):
        if self.empresa:
            color_para_agrupacion = self.color if self.color and self.color.strip() else None
            
            ref_color_obj, created = ReferenciaColor.objects.get_or_create(
                empresa=self.empresa,
                referencia_base=self.referencia,
                color=color_para_agrupacion
            )
            self.articulo_color_fotos = ref_color_obj
        
        super().save(*args, **kwargs)

    def __str__(self):
        variante_parts = []
        if self.talla: variante_parts.append(f"T:{self.talla}")
        if self.color: variante_parts.append(f"C:{self.color}")
        variante_str = f" ({' '.join(variante_parts)})" if variante_parts else ""
        return f"{self.referencia} - {self.nombre}{variante_str}"

    class Meta:
        verbose_name = "Producto (Variante Específica)"
        verbose_name_plural = "Productos (Variantes Específicas)"
        ordering = ['referencia', 'nombre', 'color', 'talla']
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'referencia', 'talla', 'color'], name='variante_unica_por_empresa'),
            models.UniqueConstraint(fields=['empresa', 'codigo_barras'], condition=models.Q(codigo_barras__isnull=False), name='codigo_barras_unico_por_empresa')
        ]
        permissions = [("upload_fotos_producto", "Puede subir fotos para productos"),]