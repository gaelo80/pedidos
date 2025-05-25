# productos/models.py
from django.db import models
from django.conf import settings # Para MEDIA_ROOT/URL si es necesario aquí
from django.db.models import Sum
# Asumo que MovimientoInventario sigue siendo relevante para el stock de la variante Producto
from bodega.models import MovimientoInventario
import uuid # Para valores por defecto si los necesitas para algún ID nuevo

# --- NUEVO MODELO: ReferenciaColor ---
class ReferenciaColor(models.Model):
    referencia_base = models.CharField(
        max_length=50,
        db_index=True,
        verbose_name="Referencia Base del Artículo"
    )
    color = models.CharField(
        max_length=50,
        blank=True, # Permitir "Sin Color" si el color es opcional a este nivel
        null=True,
        db_index=True,
        verbose_name="Color del Artículo"
    )
    # Opcional: un nombre display generado automáticamente o manual
    nombre_display = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Nombre para Agrupación (Ref+Color)"
    )

    def __str__(self):
        color_str = self.color if self.color else "Sin Color"
        return f"{self.referencia_base} - {color_str}"

    def save(self, *args, **kwargs):
        # Generar nombre_display automáticamente si está vacío
        if not self.nombre_display:
            color_str = self.color if self.color else "Sin Color Específico"
            self.nombre_display = f"Artículo: {self.referencia_base} ({color_str})"
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Artículo por Color (para Fotos)"
        verbose_name_plural = "Artículos por Color (para Fotos)"
        unique_together = ('referencia_base', 'color') # Cada combinación Ref+Color es única
        ordering = ['referencia_base', 'color']


# --- MODELO Producto (Variante) MODIFICADO ---
class Producto(models.Model):
    """
    Representa una VARIANTE específica de un artículo (identificada por Ref+Talla+Color).
    Las fotos ahora se gestionarán a través del modelo ReferenciaColor.
    """
    # Campos existentes (referencia, nombre, descripcion, talla, color actual de la variante)
    referencia = models.CharField(max_length=50, db_index=True, verbose_name="Referencia Base (Variante)")
    nombre = models.CharField(max_length=200, verbose_name="Nombre del Producto (Variante)")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción (Variante)")
    talla = models.CharField(max_length=20, blank=True, null=True, db_index=True, verbose_name="Talla (Variante)")
    color = models.CharField(max_length=50, blank=True, null=True, db_index=True, verbose_name="Color (Variante)")

    # --- NUEVA ForeignKey a ReferenciaColor ---
    # Esta es la clave para agrupar las fotos.
    articulo_color_fotos = models.ForeignKey(
        ReferenciaColor,
        on_delete=models.PROTECT, # Decide la política: ¿Qué pasa si se borra una ReferenciaColor?
                                  # PROTECT previene el borrado si hay Productos (variantes) asociados.
                                  # SET_NULL podría ser una opción si 'null=True'.
        related_name='variantes', # Desde una ReferenciaColor, puedes hacer ref_color.variantes.all()
        verbose_name="Agrupación Ref+Color (para Fotos)",
        null=True, # Permitir null temporalmente durante la migración. Luego puedes decidir si hacerlo False.
        blank=True # Permitir blank temporalmente.
    )

    # Campos de Género y otros existentes...
    GENERO_DAMA = 'DAMA'
    GENERO_CABALLERO = 'CABALLERO'
    GENERO_UNISEX = 'UNISEX'
    GENERO_CHOICES = [
        (GENERO_DAMA, 'Dama'),
        (GENERO_CABALLERO, 'Caballero'),
        (GENERO_UNISEX, 'Unisex'),
    ]
    genero = models.CharField(
        max_length=10,
        choices=GENERO_CHOICES,
        db_index=True,
        default=GENERO_UNISEX,
        help_text="Género OBLIGATORIO al que pertenece la referencia"
    )
    costo = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Costo")
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Precio de Venta")
    unidad_medida = models.CharField(max_length=20, default='UND', verbose_name="Unidad de Medida")
    ubicacion = models.CharField(max_length=100, blank=True, null=True, verbose_name="Ubicación en Bodega")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    activo = models.BooleanField(default=True, db_index=True, verbose_name="¿Está Activo?")
    codigo_barras = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="Código de Barras",
        help_text="Código de barras único para esta variante de producto (Ref+Talla+Color)."
    )

    @property
    def stock_actual(self):
        suma_movimientos = MovimientoInventario.objects.filter(producto=self).aggregate(
            total_stock=Sum('cantidad')
        )['total_stock']
        return suma_movimientos or 0
    
    def save(self, *args, **kwargs):
        print(f"DEBUG Producto.save(): Iniciando para Producto REF='{self.referencia}', Color='{self.color}'")
        if self.referencia:
            color_para_agrupacion = self.color if self.color and self.color.strip() != "" else None
            print(f"DEBUG Producto.save(): Intentando get_or_create ReferenciaColor con ref_base='{self.referencia}', color='{color_para_agrupacion}'")
            try:
                # Asegúrate que ReferenciaColor esté accesible aquí
                ref_color_obj, created = ReferenciaColor.objects.get_or_create(
                    referencia_base=self.referencia,
                    color=color_para_agrupacion
                )
                if created:
                    print(f"DEBUG Producto.save(): CREADA NUEVA ReferenciaColor: {ref_color_obj}")
                else:
                    print(f"DEBUG Producto.save(): OBTENIDA ReferenciaColor existente: {ref_color_obj}")
                self.articulo_color_fotos = ref_color_obj
                print(f"DEBUG Producto.save(): 'articulo_color_fotos' asignado a {ref_color_obj}")
            except Exception as e:
                print(f"DEBUG Producto.save(): ERROR durante get_or_create ReferenciaColor: {e}")
        else:
            print("DEBUG Producto.save(): Condición para crear/obtener ReferenciaColor no cumplida (falta self.referencia).")
        super().save(*args, **kwargs)
        print(f"DEBUG Producto.save(): Objeto Producto (ID: {self.pk}) guardado.")

    def __str__(self):
        variante = []
        talla_val = getattr(self, 'talla', None)
        color_val_variante = getattr(self, 'color', None) # Color específico de la variante
        if talla_val:
            variante.append(f"T:{talla_val}")
        if color_val_variante: # Usar el color de la variante para el __str__ de la variante
            variante.append(f"C:{color_val_variante}")
        variante_str = " ".join(variante)

        ref_str = self.referencia or ""
        nombre_str = self.nombre or ""

        if variante_str:
            return f"{ref_str} - {nombre_str} ({variante_str})"
        else:
            return f"{ref_str} - {nombre_str}"

    class Meta:
        verbose_name = "Producto (Variante Específica)"
        verbose_name_plural = "Productos (Variantes Específicas)"
        ordering = ['referencia', 'nombre', 'color', 'talla'] # O basado en articulo_color_fotos
        constraints = [
            models.UniqueConstraint(fields=['referencia', 'talla', 'color'], name='variante_unica_productos_v2'),
            models.UniqueConstraint(fields=['codigo_barras'], condition=models.Q(codigo_barras__isnull=False), name='codigo_barras_unico_no_nulo_productos_v2')
        ]
        permissions = [
            ("upload_fotos_producto", "Puede subir fotos para productos"),
            # ... otros permisos personalizados si los tienes ...
        ]


# --- MODELO FotoProducto MODIFICADO ---
def ruta_guardado_foto_producto_agrupada(instance, filename):
    # Guardar fotos bajo el ID de la ReferenciaColor
    # Esto asegura que todas las fotos para "Ref X, Color Y" estén en la misma carpeta.
    identificador_agrupacion = instance.articulo_agrupador.id if instance.articulo_agrupador else 'sin_agrupacion'
    return f'fotos_producto_agrupadas/{identificador_agrupacion}/{filename}'

class FotoProducto(models.Model):
    articulo_agrupador = models.ForeignKey(
        ReferenciaColor,
        related_name='fotos_agrupadas',
        on_delete=models.CASCADE,
        verbose_name="Artículo por Color (Agrupador de Fotos)",
        null=True,  # <--- ¡IMPORTANTE TEMPORALMENTE!
        blank=True  # <--- OPCIONAL, PERO BUENO PARA FORMS SI FUERA EDITABLE
    )
    imagen = models.ImageField(
        upload_to=ruta_guardado_foto_producto_agrupada, # Asegúrate que esta función exista
        verbose_name="Archivo de Imagen"
    )
    descripcion_foto = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Descripción de la Foto (Opcional)"
    )
    orden = models.PositiveIntegerField(
        default=0,
        verbose_name="Orden de Visualización"
    )

    def __str__(self):
        # Asegurarse que articulo_agrupador no sea None antes de intentar acceder a sus atributos
        agrupador_str = str(self.articulo_agrupador) if self.articulo_agrupador else "Sin Agrupador"
        imagen_nombre = self.imagen.name.split('/')[-1] if self.imagen and self.imagen.name else "Sin Imagen"
        return f"Foto de {agrupador_str} - Archivo: {imagen_nombre}"

    class Meta:
        verbose_name = "Foto de Artículo (por Ref+Color)"
        verbose_name_plural = "Fotos de Artículos (por Ref+Color)"
        ordering = ['articulo_agrupador', 'orden']