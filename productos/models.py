# productos/models.py
from decimal import Decimal
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


def _digito_verificador_ean13(cuerpo_12_digitos):
    """Algoritmo estándar EAN13: posiciones impares x1, pares x3 (1-indexado)."""
    total = sum(
        int(digito) * (1 if (indice + 1) % 2 == 1 else 3)
        for indice, digito in enumerate(cuerpo_12_digitos)
    )
    return (10 - (total % 10)) % 10


def generar_codigo_ean13(empresa):
    """
    Genera un código EAN13 de uso interno, único incluso entre empresas
    distintas: prefijo '20' (GS1 reserva 20-29 para uso interno sin
    necesidad de registro) + 3 dígitos que identifican a la empresa
    (Empresa.codigo_ean13_empresa) + un consecutivo de 7 dígitos propio de
    esa empresa + dígito verificador estándar. Debe llamarse dentro de una
    transaction.atomic(): usa select_for_update() sobre la empresa para que
    dos productos creados al mismo tiempo nunca reciban el mismo código.
    """
    empresa_bloqueada = Empresa.objects.select_for_update().get(pk=empresa.pk)
    empresa_bloqueada.ultimo_consecutivo_ean13 += 1
    empresa_bloqueada.save(update_fields=['ultimo_consecutivo_ean13'])

    cuerpo = f"20{empresa_bloqueada.codigo_ean13_empresa:03d}{empresa_bloqueada.ultimo_consecutivo_ean13:07d}"
    return cuerpo + str(_digito_verificador_ean13(cuerpo))


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

def normalizar_nombre_color(nombre):
    """
    Recorta espacios, quita tildes/diacríticos y pasa a mayúsculas, para que
    "Café", "CAFÉ" y "cafe " terminen siendo el mismo registro. No intenta
    corregir errores de escritura reales (ej. "Beige" vs "Bage"), solo
    diferencias de formato/acentuación.
    """
    import unicodedata
    if not nombre:
        return nombre
    sin_tildes = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode('ascii')
    return sin_tildes.strip().upper()


class Color(models.Model):
    """
    Catálogo de colores por empresa. Reemplaza el campo de texto libre que
    tenía Producto, para evitar duplicados por escritura inconsistente
    ("Azul", "AZUL", "azul rey"...).
    """
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='colores')
    nombre = models.CharField(max_length=50, verbose_name="Color")
    activo = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        self.nombre = normalizar_nombre_color(self.nombre)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Color"
        verbose_name_plural = "Colores"
        ordering = ['nombre']
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'nombre'], name='color_unico_por_empresa')
        ]


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

    # --- Campos para la integración con Shopify ---
    # Un ReferenciaColor (referencia+color) equivale a UN producto de Shopify;
    # cada Producto (variante/talla) es una variante de ese producto en Shopify.
    shopify_product_id = models.CharField(
        max_length=100, blank=True, null=True, unique=True,
        verbose_name="ID de Producto en Shopify"
    )
    shopify_titulo = models.CharField(
        max_length=255, blank=True, null=True,
        verbose_name="Título para Shopify",
        help_text="Si se deja vacío, se usa el nombre interno del producto."
    )
    shopify_descripcion = models.TextField(
        blank=True, null=True,
        verbose_name="Descripción para Shopify",
        help_text="Si se deja vacío, se usa la descripción interna del producto."
    )
    shopify_precio = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True,
        verbose_name="Precio para Shopify",
        help_text="Si se deja vacío, se usa el precio de venta interno."
    )
    shopify_tipo = models.CharField(
        max_length=255, blank=True, null=True,
        verbose_name="Tipo (Shopify)",
        help_text="Campo de texto libre de Shopify ('product_type'), ej. 'Skinny jean'."
    )
    shopify_categoria_id = models.CharField(
        max_length=100, blank=True, null=True,
        verbose_name="ID de Categoría (Shopify)",
        help_text="GID de la categoría oficial de la taxonomía de Shopify (ej. 'gid://shopify/TaxonomyCategory/aa-1-12-4')."
    )
    shopify_categoria_nombre = models.CharField(
        max_length=255, blank=True, null=True,
        verbose_name="Nombre de Categoría (Shopify)",
        help_text="Solo para mostrar en pantalla (ej. 'Apparel & Accessories > Clothing > Pants > Jeans')."
    )
    shopify_etiquetas = models.CharField(
        max_length=500, blank=True, null=True,
        verbose_name="Etiquetas adicionales (Shopify)",
        help_text="Etiquetas separadas por coma. El color se agrega siempre como etiqueta automática, además de estas."
    )
    shopify_colecciones_ids = models.CharField(
        max_length=1000, blank=True, null=True,
        verbose_name="IDs de Colecciones (Shopify)",
        help_text="GIDs de colección separados por coma. Uso interno, se sincroniza junto con shopify_colecciones_nombres."
    )
    shopify_colecciones_nombres = models.CharField(
        max_length=1000, blank=True, null=True,
        verbose_name="Nombres de Colecciones (Shopify)",
        help_text="Solo para mostrar en pantalla, en el mismo orden que shopify_colecciones_ids."
    )
    shopify_ultima_sincronizacion = models.DateTimeField(
        blank=True, null=True,
        verbose_name="Última sincronización con Shopify"
    )
    shopify_borrador_por_agotado = models.BooleanField(
        default=False,
        verbose_name="En borrador por falta de stock",
        help_text="Marca si el sistema pasó este producto a borrador automáticamente "
                   "por quedarse sin stock disponible para Web. Permite reactivarlo "
                   "solo (sin tocar productos que la administradora archivó por otro motivo)."
    )

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

    class GeneroOpciones(models.TextChoices):
        DAMA = 'DAMA', 'Dama'
        CABALLERO = 'CABALLERO', 'Caballero'
        NINO = 'NIÑO', 'Niño'
        NINA = 'NIÑA', 'Niña'
        PLUS = 'PLUS', 'Plus'
        UNISEX = 'UNISEX', 'Unisex'


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
    
    stock = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal(0),
        verbose_name="Stock"
    )
    
    permitir_preventa = models.BooleanField(
        default=False,
        verbose_name="Permitir Venta Sin Stock (Preventa)",
        help_text="Marcar esta opción si el producto está en producción y se puede vender sin tener stock físico."
    
    )
    
    referencia = models.CharField(max_length=50, db_index=True, verbose_name="Referencia")
    nombre = models.CharField(max_length=200, verbose_name="Nombre del Producto")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    talla = models.IntegerField(blank=True, null=True, verbose_name="Talla")
    color = models.ForeignKey(
        'Color', on_delete=models.PROTECT, null=True, blank=True,
        related_name='productos', verbose_name="Color"
    )

    genero = models.CharField(
        max_length=20,
        choices=GeneroOpciones.choices,
        default=GeneroOpciones.CABALLERO,
        verbose_name="Categoría/Género",
        help_text="Seleccione el género o categoría del producto."
    )
    #genero = models.CharField(max_length=10, choices=GENERO_CHOICES, db_index=True, default='UNISEX')
    costo = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    unidad_medida = models.CharField(max_length=20, default='UND')
    ubicacion = models.ForeignKey(
        'bodega.Bodega',
        on_delete=models.PROTECT,
        related_name='productos',
        verbose_name="Bodega",
        null=True,
        blank=True,
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True, db_index=True)
    codigo_barras = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    oculto_para_standar = models.BooleanField(default=False)

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

    CANAL_CAMPO_BODEGA = {
        'ESTANDAR': 'disponible_venta_estandar',
        'ONLINE': 'disponible_venta_online',
        'WEB': 'disponible_venta_web',
        'PUNTOVENTA': 'disponible_venta_puntoventa',
    }

    def stock_disponible_para_canal(self, canal, usuario=None):
        """
        Stock vendible/reservable para un canal de venta (ESTANDAR/ONLINE/WEB):
        solo suma las bodegas cuyo flag de canal correspondiente esté activo.
        Si 'usuario' tiene una excepción individual (AccesoBodega) para alguna
        bodega, esa excepción prevalece sobre el flag del canal (puede abrir
        una bodega cerrada para su canal, o cerrarle una que sí está abierta).
        A diferencia de 'stock_actual', esto NO cuenta lo que haya en bodegas
        no habilitadas para ese canal (ej. una bodega de 'Saldos y Colas'
        oculta a vendedores estándar).
        """
        from bodega.models import MovimientoInventario, Bodega, AccesoBodega

        if not self.empresa_id:
            return 0

        campo_canal = self.CANAL_CAMPO_BODEGA.get(canal)
        if not campo_canal:
            raise ValueError(f"Canal de venta desconocido: {canal!r}")

        bodegas_ids = set(
            Bodega.objects.filter(empresa=self.empresa, **{campo_canal: True}).values_list('pk', flat=True)
        )

        if usuario is not None and getattr(usuario, 'pk', None):
            accesos = AccesoBodega.objects.filter(
                usuario=usuario, bodega__empresa=self.empresa
            ).values_list('bodega_id', 'nivel')
            for bodega_id, nivel in accesos:
                if nivel == AccesoBodega.NivelAcceso.NINGUNO:
                    bodegas_ids.discard(bodega_id)
                else:
                    bodegas_ids.add(bodega_id)

        if not bodegas_ids:
            return 0

        suma = MovimientoInventario.objects.filter(
            producto=self, empresa=self.empresa, bodega_id__in=bodegas_ids
        ).aggregate(total=Sum('cantidad'))['total']
        return suma or 0

    def save(self, *args, **kwargs):
        if self.empresa:
            color_para_agrupacion = self.color.nombre if self.color_id else None

            ref_color_obj, created = ReferenciaColor.objects.get_or_create(
                empresa=self.empresa,
                referencia_base=self.referencia,
                color=color_para_agrupacion
            )
            self.articulo_color_fotos = ref_color_obj
        
        super().save(*args, **kwargs)

    # Campos de conexión exclusiva con Shopify
    shopify_variant_id = models.CharField(max_length=100, blank=True, null=True, unique=True, verbose_name="ID Variante Shopify")
    shopify_inventory_item_id = models.CharField(max_length=100, blank=True, null=True, unique=True, verbose_name="ID Inventario Shopify")

    def __str__(self):
        variante_parts = []
        if self.talla: variante_parts.append(f"T:{self.talla}")
        if self.color: variante_parts.append(f"C:{self.color}")
        variante_str = f" ({' '.join(variante_parts)})" if variante_parts else ""
        return f"{self.referencia} - {self.nombre}{variante_str}"

    class Meta:
        verbose_name = "Producto (Variante Específica)"
        verbose_name_plural = "Productos (Variantes Específicas)"
        ordering = ['referencia', 'nombre', 'color__nombre', 'talla']
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'referencia', 'talla', 'color'], name='variante_unica_por_empresa'),
            models.UniqueConstraint(fields=['empresa', 'codigo_barras'], condition=models.Q(codigo_barras__isnull=False), name='codigo_barras_unico_por_empresa')
        ]
        permissions = [
            ("upload_fotos_producto", "Puede subir fotos para productos"),
            ("view_inventory_report", "Puede ver el informe de inventario físico"),
            ]