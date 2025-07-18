from django.db import models
from django.contrib import admin
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import ROUND_HALF_UP
from django.core.exceptions import ValidationError
from clientes.models import Empresa

class IngresoBodega(models.Model):
        """Representa un ingreso de mercancía a la bodega."""
    
        empresa = models.ForeignKey(
            Empresa,
            on_delete=models.CASCADE,
            related_name='ingresos_bodega',
            verbose_name="Empresa",
            #null=True
        )
        
        fecha_hora = models.DateTimeField(default=timezone.now, verbose_name="Fecha y Hora Ingreso")
        proveedor_info = models.CharField(max_length=200, blank=True, null=True, verbose_name="Información Proveedor/Origen")
        documento_referencia = models.CharField(max_length=100, blank=True, null=True, verbose_name="Documento Referencia (Factura Compra, Remisión, etc.)")
        
        usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='ingresos_registrados', verbose_name="Usuario Registrador")
        
        
        notas = models.TextField(blank=True, null=True, verbose_name="Notas Adicionales")

        def __str__(self):
            ref = f" ({self.documento_referencia})" if self.documento_referencia else ""
            prov = f" - {self.proveedor_info}" if self.proveedor_info else ""
            return f"Ingreso Bodega #{self.pk}{prov}{ref} ({self.fecha_hora.strftime('%d-%b-%Y')})"

        class Meta:
            verbose_name = "Ingreso a Bodega"
            verbose_name_plural = "Ingresos a Bodega"
            ordering = ['-fecha_hora']


class DetalleIngresoBodega(models.Model):
    """Detalle de un producto en un IngresoBodega."""
    ingreso = models.ForeignKey(IngresoBodega, related_name='detalles', on_delete=models.CASCADE, verbose_name="Ingreso Asociado")
    producto = models.ForeignKey('productos.Producto', on_delete=models.PROTECT, related_name='detalles_ingreso', verbose_name="Producto Ingresado")
    cantidad = models.PositiveIntegerField(default=1, verbose_name="Cantidad Ingresada")
    costo_unitario = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Costo Unitario (Opcional)")

    def clean(self):
        super().clean()
        
        ingreso_empresa = getattr(self.ingreso, 'empresa', None) if self.ingreso_id else None
        producto_empresa = getattr(self.producto, 'empresa', None) if self.producto_id else None

        if ingreso_empresa and producto_empresa and ingreso_empresa != producto_empresa:
            raise ValidationError("El producto no pertenece a la misma empresa que el ingreso de bodega.")
               

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre}"

    class Meta:
        verbose_name = "Detalle de Ingreso a Bodega"
        verbose_name_plural = "Detalles de Ingreso a Bodega"
        unique_together = ('ingreso', 'producto')

class PersonalBodega(models.Model):
    """
    Perfil para el Bodega, asociado a un usuario de Django.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE, # Si se borra el User, se borra el perfil Bodega
        related_name='perfil_bodega' # Nombre para acceder al perfil desde el usuario (ej: user.perfil_bodega)
    )
    # --- Campos Adicionales (Opcional) ---
    # Añade aquí campos específicos si los necesitas, por ejemplo:
    codigo_empleado = models.CharField(max_length=50, unique=True, blank=True, null=True, help_text="ID interno o código del empleado de bodega")
    area_asignada = models.CharField(max_length=100, blank=True, null=True, help_text="Área específica de la bodega asignada")
    activo = models.BooleanField(default=True, help_text="Indica si el perfil de bodega está activo")
    # Puedes añadir más campos como 'turno', 'fecha_contratacion', etc.
    
    
class Meta:
    verbose_name = "Bodega"
    verbose_name_plural = "Bodega"
    ordering = ['user__username'] # Ordenar por nombre de usuario

def __str__(self):
    # Representación legible, usa el nombre de usuario asociado
    return self.user.get_username()


class MovimientoInventario(models.Model):
        """Registra cada entrada o salida de stock para un producto."""
        empresa = models.ForeignKey(
            Empresa,
            on_delete=models.CASCADE,
            related_name='movimientos_inventario',
            verbose_name="Empresa",
            #null=True # Temporal para la migración
        )
        TIPO_MOVIMIENTO_CHOICES = [
        ('ENTRADA_COMPRA', 'Entrada por Compra'),
        ('ENTRADA_AJUSTE', 'Entrada por Ajuste'),
        ('ENTRADA_DEVOLUCION_CLIENTE', 'Entrada por Devolución de Cliente'), 
        ('SALIDA_VENTA_PENDIENTE', 'Salida por Venta (Pendiente Aprob)'), 
        ('SALIDA_VENTA_APROBADA', 'Salida por Venta (Aprobada)'), 
        ('SALIDA_AJUSTE', 'Salida por Ajuste'),
        ('SALIDA_OTRO', 'Salida por Otro Motivo'),
        ('ENTRADA_OTRO', 'Entrada por Otro Motivo'),
        ('ENTRADA_RECHAZO_CARTERA', 'Entrada por Rechazo Pedido Cartera'),
        ('ENTRADA_RECHAZO_ADMIN', 'Entrada por Rechazo Pedido Admin'),     
        ('SALIDA_MUESTRARIO', 'Salida para Muestrario'),
        ('SALIDA_EXHIBIDOR', 'Salida para Exhibidor'),
        ('SALIDA_TRASLADO', 'Salida por Traslado Interno'),
        ('SALIDA_PRESTAMO', 'Salida por Préstamo'),
        ('SALIDA_DONACION_BAJA', 'Salida por Donación/Baja'),
        ('SALIDA_INTERNA_OTRA', 'Salida Interna (Otra)'),        
        ('ENTRADA_DEV_MUESTRARIO', 'Devolución de Muestrario'),
        ('ENTRADA_DEV_EXHIBIDOR', 'Devolución de Exhibidor'),
        ('ENTRADA_DEV_TRASLADO', 'Devolución de Traslado Interno'), 
        ('ENTRADA_DEV_PRESTAMO', 'Devolución de Préstamo'),
        ('ENTRADA_DEV_INTERNA_OTRA', 'Devolución Interna (Otra)'),
        ]
        producto = models.ForeignKey('productos.Producto', on_delete=models.PROTECT, related_name='movimientos', verbose_name="Producto")
        cantidad = models.IntegerField(verbose_name="Cantidad Movida")
        tipo_movimiento = models.CharField(max_length=35, choices=TIPO_MOVIMIENTO_CHOICES, verbose_name="Tipo de Movimiento")
        fecha_hora = models.DateTimeField(default=timezone.now, verbose_name="Fecha y Hora")
        usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos_registrados', verbose_name="Usuario Registrador")
        documento_referencia = models.CharField(max_length=100, blank=True, null=True, verbose_name="Documento Referencia (ID Pedido, Factura, etc.)")
        notas = models.TextField(blank=True, null=True, verbose_name="Notas")

        def save(self, *args, **kwargs):
            if not self.empresa_id and self.producto_id:
                self.empresa = self.producto.empresa
            super().save(*args, **kwargs)

        def __str__(self):
            signo = '+' if self.cantidad > 0 else ''
            return f"{self.get_tipo_movimiento_display()} ({signo}{self.cantidad}) - {self.producto.referencia}"

        class Meta:
            verbose_name = "Movimiento de Inventario"
            verbose_name_plural = "Movimientos de Inventario"
            ordering = ['-fecha_hora', 'producto__nombre']
            
            
class CabeceraConteo(models.Model):
    """Agrupa los registros de un evento de conteo específico."""

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='conteos_inventario',
        verbose_name="Empresa",
        #null=True
        #default=1
    )
    

    fecha_conteo = models.DateField(default=timezone.now, verbose_name="Fecha Efectiva del Conteo")
    motivo = models.CharField(max_length=150, blank=True, null=True, verbose_name="Motivo del Conteo")
    revisado_con = models.CharField(max_length=150, blank=True, null=True, verbose_name="Revisado Con")
    notas_generales = models.TextField(blank=True, null=True, verbose_name="Notas Generales")
    usuario_registro = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Usuario que Registró")
    fecha_hora_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Conteo ID {self.pk} - {self.fecha_conteo.strftime('%Y-%m-%d')} - Motivo: {self.motivo or 'N/A'}"

    class Meta:
        verbose_name = "Cabecera de Conteo de Inventario"
        verbose_name_plural = "Cabeceras de Conteos de Inventario"
        ordering = ['-fecha_hora_registro']


class ConteoInventario(models.Model):
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='detalles_conteo_inventario', verbose_name="Empresa")
    cabecera_conteo = models.ForeignKey(CabeceraConteo, on_delete=models.CASCADE, related_name='detalles_conteo', verbose_name="Cabecera del Conteo")
    producto = models.ForeignKey('productos.Producto', on_delete=models.PROTECT, related_name='conteos_inventario', verbose_name="Producto Contado")
    
    # Dejamos solo los campos que pertenecen al detalle
    cantidad_sistema_antes = models.IntegerField(verbose_name="Cantidad en Sistema (Antes del Conteo)")
    cantidad_fisica_contada = models.IntegerField(verbose_name="Cantidad Física Contada")
    
    usuario_conteo = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Usuario que Contó")
    fecha_conteo = models.DateTimeField(auto_now_add=True, verbose_name="Fecha y Hora del Conteo")
    notas = models.TextField(blank=True, null=True, verbose_name="Notas del Ítem Específico") # Solo dejamos las notas del ítem

    @property
    def diferencia(self):
        return self.cantidad_fisica_contada - self.cantidad_sistema_antes
    
    def clean(self):
        super().clean()
        if self.cabecera_conteo_id and self.producto_id:
            if self.cabecera_conteo.empresa_id != self.producto.empresa_id:
                raise ValidationError("El producto y la cabecera del conteo deben pertenecer a la misma empresa.")
    
    def save(self, *args, **kwargs):
        if not self.empresa_id and self.cabecera_conteo_id:
            self.empresa = self.cabecera_conteo.empresa
        self.clean()
        super().save(*args, **kwargs)
    
    
    

    def __str__(self):
        # Usamos el __str__ del modelo Producto que ya es descriptivo
        return f"Detalle Conteo {self.pk} para {self.producto} (Cabecera: {self.cabecera_conteo_id})"

    class Meta:
        verbose_name = "Detalle de Conteo de Inventario"
        verbose_name_plural = "Detalles de Conteos de Inventario"
        ordering = ['cabecera_conteo', 'producto'] # Ordenar por fecha más reciente, luego por producto

admin.site.register(ConteoInventario)


class ComprobanteDespacho(models.Model):
    """
    Representa un comprobante de despacho individual, que puede ser parcial o total
    para un pedido. Cada vez que se confirma una salida de mercancía desde bodega
    para un cliente, se crea un registro aquí.
    """
    pedido = models.ForeignKey(
        'pedidos.Pedido',
        on_delete=models.PROTECT, # O SET_NULL si un despacho puede existir sin pedido (raro)
        related_name='comprobantes_despacho',
        verbose_name="Pedido Asociado",
        #null=True
        
    )
    
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='comprobantes_despacho',
        verbose_name="Empresa",
        #null=True # Temporal para la migración
    )
    
    fecha_hora_despacho = models.DateTimeField(
        default=timezone.now,
        verbose_name="Fecha y Hora del Despacho"
    )
    usuario_responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='comprobantes_despachados',
        verbose_name="Usuario Responsable (Bodega)"
    )

    notas = models.TextField(blank=True, null=True, verbose_name="Notas del Despacho")
    
    def save(self, *args, **kwargs):
        if not self.empresa_id and self.pedido_id:
            self.empresa = self.pedido.empresa
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Comprobante de Despacho #{self.pk} para Pedido #{self.pedido_id}"

    class Meta:
        verbose_name = "Comprobante de Despacho"
        verbose_name_plural = "Comprobantes de Despacho"
        ordering = ['-fecha_hora_despacho']

class DetalleComprobanteDespacho(models.Model):
    """
    Representa un producto específico y la cantidad despachada
    en un ComprobanteDespacho particular.
    """
    comprobante_despacho = models.ForeignKey(
        ComprobanteDespacho,
        related_name='detalles',
        on_delete=models.CASCADE, # Si se borra el comprobante, se borran sus detalles
        verbose_name="Comprobante de Despacho"
    )
    producto = models.ForeignKey(
        'productos.Producto',
        on_delete=models.PROTECT, # Proteger el producto si está en un despacho
        related_name='en_despachos',
        verbose_name="Producto Despachado"
    )
    cantidad_despachada = models.PositiveIntegerField(
        verbose_name="Cantidad Despachada en este Comprobante"
    )
    # Referencia al DetallePedido original para trazabilidad (opcional pero útil)
    detalle_pedido_origen = models.ForeignKey(
        'pedidos.DetallePedido',
        on_delete=models.SET_NULL, # Si se borra el detalle del pedido, no borrar este registro
        null=True,
        blank=True,
        related_name='items_despachados',
        verbose_name="Línea del Pedido Original"
    )

    def clean(self):
        super().clean()
        if self.comprobante_despacho_id and self.producto_id:
            if self.comprobante_despacho.empresa_id != self.producto.empresa_id:
                raise ValidationError("El producto y el comprobante de despacho deben pertenecer a la misma empresa.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.cantidad_despachada} x {self.producto.nombre} (Comprobante #{self.comprobante_despacho.pk})"

    class Meta:
        verbose_name = "Detalle de Comprobante de Despacho"
        verbose_name_plural = "Detalles de Comprobantes de Despacho"
        # Evitar duplicados del mismo producto en el mismo comprobante
        unique_together = ('comprobante_despacho', 'producto', 'detalle_pedido_origen')


class SalidaInternaCabecera(models.Model):
    
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='salidas_internas',
        verbose_name="Empresa",
        #null=True
    )
      
    
    TIPO_SALIDA_CHOICES = [
        ('MUESTRARIO', 'Muestrario para Vendedor'),
        ('EXHIBIDOR', 'Para Exhibidor/Punto de Venta'),
        ('TRASLADO_INTERNO', 'Traslado Interno entre Almacenes/Bodegas'),
        ('PRESTAMO', 'Préstamo Temporal'),
        ('DONACION_BAJA', 'Donación o Baja de Inventario'),
        ('OTRO', 'Otro Tipo de Salida Interna'),
    ]
    ESTADO_SALIDA_CHOICES = [
        ('DESPACHADA', 'Despachada (Pendiente Devolución)'),
        ('DEVUELTA_PARCIAL', 'Devuelta Parcialmente'),
        ('DEVUELTA_TOTAL', 'Devuelta Totalmente'),
        ('CERRADA', 'Cerrada (No requiere devolución, ej. baja)'),
    ]

    fecha_hora_salida = models.DateTimeField(default=timezone.now, verbose_name="Fecha y Hora de Salida")
    tipo_salida = models.CharField(max_length=20, choices=TIPO_SALIDA_CHOICES, verbose_name="Tipo de Salida")
    destino_descripcion = models.CharField(max_length=255, verbose_name="Destino / Entregado A", help_text="Ej: Vendedor Juan Pérez, Tienda Centro, Evento XYZ")
    responsable_entrega = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='salidas_internas_entregadas',
        verbose_name="Responsable de Entrega (Bodega)"
    )
    documento_referencia_externo = models.CharField(max_length=100, blank=True, null=True, verbose_name="Doc. Referencia Externo (Opcional)")
    estado = models.CharField(max_length=20, choices=ESTADO_SALIDA_CHOICES, default='DESPACHADA', verbose_name="Estado de la Salida")
    fecha_prevista_devolucion = models.DateField(null=True, blank=True, verbose_name="Fecha Prevista Devolución (si aplica)")
    observaciones_salida = models.TextField(blank=True, null=True, verbose_name="Observaciones Generales de la Salida")

    def __str__(self):
        return f"Salida Interna #{self.pk} - {self.get_tipo_salida_display()} a {self.destino_descripcion}"

    class Meta:
        verbose_name = "Salida Interna (Cabecera)"
        verbose_name_plural = "Salidas Internas (Cabeceras)"
        ordering = ['-fecha_hora_salida']

class SalidaInternaDetalle(models.Model):
    cabecera_salida = models.ForeignKey(SalidaInternaCabecera, related_name='detalles', on_delete=models.CASCADE, verbose_name="Cabecera de Salida Interna")
    producto = models.ForeignKey('productos.Producto', on_delete=models.PROTECT, verbose_name="Producto")
    cantidad_despachada = models.PositiveIntegerField(verbose_name="Cantidad Despachada")
    # Para la Fase 2 (Devoluciones)
    cantidad_devuelta = models.PositiveIntegerField(default=0, verbose_name="Cantidad Devuelta")
    observaciones_detalle = models.TextField(blank=True, null=True, verbose_name="Observaciones del Ítem")

    @property
    def cantidad_pendiente_devolucion(self):
        return self.cantidad_despachada - self.cantidad_devuelta
    
    
    def clean(self):
        super().clean()
        if self.cabecera_salida_id and self.producto_id:
            if self.cabecera_salida.empresa_id != self.producto.empresa_id:
                raise ValidationError("El producto y la cabecera de la salida deben pertenecer a la misma empresa.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)  
    

    def __str__(self):
        return f"{self.cantidad_despachada} x {self.producto.nombre} (Salida Interna #{self.cabecera_salida.pk})"

    class Meta:
        verbose_name = "Detalle de Salida Interna"
        verbose_name_plural = "Detalles de Salidas Internas"
        unique_together = ('cabecera_salida', 'producto') # Evitar duplicar producto en la misma salida
        permissions = [
            ("view_lista_pedidos_bodega", "Puede ver la lista de pedidos para bodega"),

        ]