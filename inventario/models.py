# inventario/models.py
from django.db import models
from django.conf import settings
from django.db.models import Sum # Import Sum
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP

    # Create your models here.

class Ciudad(models.Model):
        """Representa una ciudad donde pueden estar los clientes."""
        nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre de Ciudad")

        def __str__(self):
            return self.nombre

        class Meta:
            verbose_name = "Ciudad"
            verbose_name_plural = "Ciudades"


class Cliente(models.Model):
        """Representa un cliente que puede realizar pedidos."""
        nombre_completo = models.CharField(max_length=200, verbose_name="Nombre Completo")
        identificacion = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="Identificación (NIT/Cédula)")
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


# inventario/models.py
# ... (importaciones existentes: Sum, models, User, timezone) ...

class Producto(models.Model):
    """
    Representa una VARIANTE específica de un artículo (identificada por Ref+Talla+Color).
    """
    # La referencia base del producto (ej: 0808) - Ya NO es única por sí sola.
    referencia = models.CharField(max_length=50, db_index=True, verbose_name="Referencia Base") # Quitamos unique=True, añadimos db_index para búsquedas

    nombre = models.CharField(max_length=200, verbose_name="Nombre del Producto") # Ej: Jean Caballero Skinny
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")

    # --- CAMPOS NUEVOS PARA VARIANTES ---
    # Los hacemos opcionales (blank=True, null=True) por si algunos productos no tienen talla o color.
    talla = models.CharField(max_length=20, blank=True, null=True, db_index=True, verbose_name="Talla")
    color = models.CharField(max_length=50, blank=True, null=True, db_index=True, verbose_name="Color")
    # ------------------------------------
    
    GENERO_DAMA = 'DAMA'
    GENERO_CABALLERO = 'CABALLERO'
    GENERO_UNISEX = 'UNISEX' # Opcional, si aplica
    GENERO_CHOICES = [
        (GENERO_DAMA, 'Dama'),
        (GENERO_CABALLERO, 'Caballero'),
        (GENERO_UNISEX, 'Unisex'),
        # Puedes añadir más si es necesario
    ]
    genero = models.CharField(
        max_length=10,
        choices=GENERO_CHOICES,
        db_index=True,
        blank=False,  # NO permitir vacío en formularios
        null=False,   # NO permitir nulo en la base de datos
        # --- AÑADIR UN DEFAULT es crucial para la migración ---
        default=GENERO_UNISEX, # Elige el default más apropiado (DAMA, CABALLERO, UNISEX)
        help_text="Género OBLIGATORIO al que pertenece la referencia"
)
    # --- Otros campos existentes ---
    costo = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Costo")
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Precio de Venta")
    unidad_medida = models.CharField(max_length=20, default='UND', verbose_name="Unidad de Medida")
    ubicacion = models.CharField(max_length=100, blank=True, null=True, verbose_name="Ubicación en Bodega")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    activo = models.BooleanField(default=True, db_index=True, verbose_name="¿Está Activo?") # db_index útil para filtrar por activos
    codigo_barras = models.CharField(
        max_length=100,
        unique=True,        # Asegura que cada código de barras sea único
        blank=True,         # Permite dejarlo vacío inicialmente (importante para productos existentes)
        null=True,          # Permite valor NULL en la BD (importante para productos existentes)
        db_index=True,      # Optimiza búsquedas por código de barras
        verbose_name="Código de Barras",
        help_text="Código de barras único para esta variante de producto (Ref+Talla+Color)."
    )

    # La propiedad stock_actual sigue funcionando igual, calcula para esta variante específica
    @property
    def stock_actual(self):
        """Calcula el stock actual sumando todos los movimientos."""
        # Asegúrate que MovimientoInventario esté importado o definido después
        # if 'MovimientoInventario' not in globals(): return 0 # Protección opcional
        suma_movimientos = MovimientoInventario.objects.filter(producto=self).aggregate(
            total_stock=Sum('cantidad')
        )['total_stock']
        return suma_movimientos or 0

    def __str__(self):
        # Representación que incluye talla y color si existen
        variante = []
        # Usamos getattr para evitar errores si los campos no existieran (aunque sí existen)
        talla_val = getattr(self, 'talla', None)
        color_val = getattr(self, 'color', None)
        if talla_val:
            variante.append(f"T:{talla_val}")
        if color_val:
            variante.append(f"C:{color_val}")
        variante_str = " ".join(variante)

        ref_str = self.referencia or ""
        nombre_str = self.nombre or ""

        if variante_str:
            return f"{ref_str} - {nombre_str} ({variante_str})"
        else:
            return f"{ref_str} - {nombre_str}"


    class Meta:
        verbose_name = "Producto (Variante)"
        verbose_name_plural = "Productos (Variantes)"
        # Orden por defecto más lógico con variantes
        ordering = ['referencia', 'nombre', 'color', 'talla']
        constraints = [ 
            models.UniqueConstraint(fields=['referencia', 'talla', 'color'], name='variante_unica'),
            models.UniqueConstraint(fields=['codigo_barras'], condition=models.Q(codigo_barras__isnull=False), name='codigo_barras_unico_no_nulo')
        ]
            

class CabeceraConteo(models.Model):
    """Agrupa los registros de un evento de conteo específico."""
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
    cabecera_conteo = models.ForeignKey(
        CabeceraConteo, 
        on_delete=models.CASCADE, 
        related_name='detalles_conteo', 
        verbose_name="Cabecera del Conteo",
        null=True,  # <--- AÑADIDO
        blank=True

        )
    
    producto = models.ForeignKey(
        Producto, # Se enlaza directamente a tu modelo Producto (que funciona como variante)
        on_delete=models.PROTECT, # Evita borrar un producto si tiene conteos asociados
        related_name='conteos_inventario',
        verbose_name="Producto Contado"
    )
    fecha_conteo = models.DateTimeField(
                 #default=timezone.now, # Usar default=timezone.now para que se pueda editar si es necesario
        auto_now_add=True,
        verbose_name="Fecha y Hora del Conteo"
    )
    cantidad_sistema_antes = models.IntegerField(
        verbose_name="Cantidad en Sistema (Antes del Conteo)"
    )
    cantidad_fisica_contada = models.IntegerField(
        verbose_name="Cantidad Física Contada"
    )
    usuario_conteo = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True, # Permitir conteos no asignados o de sistema si es necesario
        verbose_name="Usuario que Contó"
    )
    fecha_actualizacion_stock = models.DateField(
        default=timezone.now, 
        verbose_name="Fecha Efectiva del Ajuste"
        )
    motivo_conteo = models.CharField(
        max_length=150, 
        blank=True, 
        null=True, 
        verbose_name="Motivo del Conteo/Ajuste"
        )
    revisado_con = models.CharField(
        max_length=150, 
        blank=True, 
        null=True, verbose_name="Revisado/Contado Con"
        )
    notas_generales = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Notas Generales del Conteo"
        ) # Cambiado de 'notas'
    notas = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Notas Adicionales"
        )

    @property
    def diferencia(self):
        return self.cantidad_fisica_contada - self.cantidad_sistema_antes

    def __str__(self):
        # Usamos el __str__ del modelo Producto que ya es descriptivo
        return f"Detalle Conteo {self.pk} para {self.producto} (Cabecera: {self.cabecera_conteo_id})"

    class Meta:
        verbose_name = "Detalle de Conteo de Inventario"
        verbose_name_plural = "Detalles de Conteos de Inventario"
        ordering = ['cabecera_conteo', 'producto'] # Ordenar por fecha más reciente, luego por producto



class Vendedor(models.Model):
        """Representa a un vendedor o empleado que toma pedidos."""
        user = models.OneToOneField(
            User,
            on_delete=models.CASCADE,
            verbose_name="Usuario del Sistema"
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


class Pedido(models.Model):
    """Representa la cabecera de un pedido de cliente."""
    ESTADO_PEDIDO_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('PENDIENTE', 'Pendiente'),
        ('PROCESANDO', 'Procesando'),
        ('COMPLETADO', 'Completado'),
        ('ENVIADO', 'Enviado'),
        ('ENTREGADO', 'Entregado'),
        ('CANCELADO', 'Cancelado'),
    ]
    cliente = models.ForeignKey('Cliente', on_delete=models.PROTECT, related_name='pedidos', verbose_name="Cliente", null=True, blank=True) # Revisa si null=True es necesario
    vendedor = models.ForeignKey('Vendedor', on_delete=models.PROTECT, related_name='pedidos', verbose_name="Vendedor") # Revisa si null=True debería ir aquí
    fecha_hora = models.DateTimeField(default=timezone.now, verbose_name="Fecha y Hora del Pedido")
    estado = models.CharField(max_length=15, choices=ESTADO_PEDIDO_CHOICES, default='PENDIENTE', verbose_name="Estado del Pedido")
    notas = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    porcentaje_descuento = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Descuento Aplicado (%)"
    )

    # --- Constantes ---
    # Define tu tasa de IVA aquí. Ejemplo para 19% en Colombia
    # ¡¡¡IMPORTANTE: AJUSTA ESTA TASA A TU NECESIDAD!!!
    IVA_RATE = Decimal('0.19')
    IVA_FACTOR = Decimal('1.00') + IVA_RATE

    # --- Propiedades Calculadas (CORREGIDAS) ---

    @property
    def subtotal_base_bruto(self):
        """CORRECTO: Suma de precios SIN IVA y SIN Descuento."""
        total = Decimal('0.00')
        if self.IVA_FACTOR <= Decimal('1.00'):
             # Manejar caso sin IVA o con IVA inválido si es necesario
             # Podría devolver 0 o lanzar error. Aquí simplemente no dividirá.
             # Si los precios unitarios NO tuvieran IVA en este caso, el cálculo sería incorrecto.
             # Asumimos que IVA_FACTOR > 1 si los precios unitarios incluyen IVA.
            pass

        for detalle in self.detalles.select_related('producto').all():
            if detalle.precio_unitario and detalle.cantidad:
                # Calcula precio base unitario (sin IVA)
                # Solo dividir si hay IVA_FACTOR > 1, sino usar precio unitario tal cual
                base_unitaria = detalle.precio_unitario / self.IVA_FACTOR if self.IVA_FACTOR > Decimal('1.00') else detalle.precio_unitario
                total += (base_unitaria * detalle.cantidad)
        return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # Esta propiedad ahora es la base correcta para el descuento
    @property
    def subtotal_base_para_descuento(self):
        """CORREGIDO: Base sobre la cual se aplica el descuento (es la suma de precios SIN IVA)."""
        return self.subtotal_base_bruto

    @property
    def valor_total_descuento(self):
        """CORREGIDO: Calcula el valor monetario total del descuento aplicado."""
        if not self.porcentaje_descuento or self.porcentaje_descuento <= Decimal('0.00'):
            return Decimal('0.00')

        descuento_pct = self.porcentaje_descuento / Decimal('100.00')
        # Aplicar descuento sobre la base correcta (sin IVA)
        valor_dcto = self.subtotal_base_para_descuento * descuento_pct # Usa la propiedad corregida
        return valor_dcto.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @property
    def subtotal_final_neto(self):
        """CORREGIDO: Subtotal después de aplicar el descuento, pero ANTES de añadir el IVA final."""
        # Es la base (sin IVA) menos el valor del descuento.
        subtotal_neto = self.subtotal_base_para_descuento - self.valor_total_descuento
        # Asegurar que no sea negativo
        return max(Decimal('0.00'), subtotal_neto) # Redondeo implícito por las entradas

    @property
    def valor_iva_final(self):
        """NUEVO/CORREGIDO: Calcula el IVA sobre el subtotal ya descontado."""
        # El IVA se calcula sobre el precio después del descuento.
        iva_final = self.subtotal_final_neto * self.IVA_RATE # Usa la tasa de IVA definida
        return iva_final.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @property
    def total_a_pagar(self):
        """CORREGIDO: Total final que el cliente debe pagar (Subtotal descontado + IVA final)."""
        # Suma del subtotal neto (post-descuento) y el IVA calculado sobre ese neto.
        total = self.subtotal_final_neto + self.valor_iva_final
        return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    @property
    def total_cantidad_productos(self):
        """Calcula la suma total de las cantidades de todos los productos en el pedido."""
        # Usamos aggregate y Sum para sumar el campo 'cantidad' de todos los detalles relacionados
        resultado = self.detalles.aggregate(cantidad_total=Sum('cantidad'))
        # aggregate devuelve un diccionario como {'cantidad_total': 25}
        # Obtenemos el valor o 0 si no hay detalles (resultado sería {'cantidad_total': None})
        total = resultado.get('cantidad_total', 0) 
        return total if total is not None else 0 # Aseguramos devolver 0 si es None


    # --- Métodos Estándar y Meta ---
    def __str__(self):
        # ¡Recordar manejar cliente=None si es posible!
        cliente_str = self.cliente.nombre_completo if self.cliente else "Sin Cliente"
        return f"Pedido #{self.pk} - {cliente_str} ({self.get_estado_display()})"

    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        ordering = ['-fecha_hora']
        
        

class DocumentoCartera(models.Model):
    """Guarda la información de una Factura o Remisión pendiente de un cliente."""
    
    # Ajustamos los choices y etiquetas según tu descripción
    TIPO_DOCUMENTO_CHOICES = [
        ('LF', 'Factura Oficial'),  # Viene de LF.xlsx
        ('FYN', 'Remisión'),       # Viene de FYN.xlsx
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='documentos_cartera') 
    tipo_documento = models.CharField(max_length=3, choices=TIPO_DOCUMENTO_CHOICES, db_index=True) 
    numero_documento = models.CharField(max_length=50, db_index=True) 
    fecha_documento = models.DateField(null=True, blank=True)
    fecha_vencimiento = models.DateField(null=True, blank=True, db_index=True)
    saldo_actual = models.DecimalField(max_digits=15, decimal_places=2, default=0.00) 
    nombre_vendedor_cartera = models.CharField(max_length=150, null=True, blank=True, help_text="Nombre del vendedor según el archivo de cartera (columna NOMVENDEDOR)")
    codigo_vendedor_cartera = models.CharField(max_length=20, null=True, blank=True, db_index=True, help_text="Código del vendedor según el archivo de cartera (VENDEDOR)")
    ultima_actualizacion_carga = models.DateTimeField(auto_now=True) 

    class Meta:
        verbose_name = "Documento de Cartera"
        verbose_name_plural = "Documentos de Cartera"
        unique_together = ('cliente', 'tipo_documento', 'numero_documento') 
        ordering = ['cliente', 'fecha_vencimiento'] 

    def __str__(self):
        return f"{self.get_tipo_documento_display()} {self.numero_documento} - Cliente: {self.cliente_id} - Saldo: {self.saldo_actual}"

    @property
    def dias_mora(self):
        if self.fecha_vencimiento and self.saldo_actual > 0:
            hoy = timezone.now().date()
            if hoy > self.fecha_vencimiento:
                return (hoy - self.fecha_vencimiento).days
        return 0

    @property
    def esta_vencido(self):
        return self.dias_mora > 0

        




# --- Modelo DetallePedido (sin cambios necesarios basados en esta lógica) ---
class DetallePedido(models.Model):
    """Representa una línea (un producto específico) dentro de un pedido."""
    pedido = models.ForeignKey(Pedido, related_name='detalles', on_delete=models.CASCADE, verbose_name="Pedido Asociado")
    producto = models.ForeignKey('Producto', on_delete=models.PROTECT, related_name='detalles_pedido', verbose_name="Producto")
    cantidad = models.PositiveIntegerField(default=1, verbose_name="Cantidad")
    # Este precio incluye IVA
    precio_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Precio Unitario (IVA Incl.)" # Hacer explícito
    )
    verificado_bodega = models.BooleanField(default=False, verbose_name="Verificado Bodega")
    cantidad_verificada = models.IntegerField(null=True, blank=True, verbose_name="Cantidad Verificada") # Considera PositiveIntegerField

    @property
    def subtotal(self):
        """Subtotal de la línea (Cantidad * Precio Unitario CON IVA)."""
        if self.precio_unitario is not None and self.cantidad is not None:
            # Usa Decimal para el cálculo por si acaso
            return (Decimal(self.cantidad) * self.precio_unitario).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return Decimal('0.00')

    @property
    def cantidad_pendiente(self):
        if self.cantidad_verificada is None:
            return self.cantidad
        else:
            pendiente = self.cantidad - self.cantidad_verificada
            return max(0, pendiente)

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre} (Pedido #{self.pedido.pk})"

    class Meta:
        verbose_name = "Detalle de Pedido"
        verbose_name_plural = "Detalles de Pedido"
        unique_together = ('pedido', 'producto')


class MovimientoInventario(models.Model):
        """Registra cada entrada o salida de stock para un producto específico."""
        TIPO_MOVIMIENTO_CHOICES = [
            ('ENTRADA_COMPRA', 'Entrada por Compra'),
            ('ENTRADA_AJUSTE', 'Entrada por Ajuste'),
            ('ENTRADA_DEVOLUCION', 'Entrada por Devolución'),
            ('SALIDA_VENTA', 'Salida por Venta'),
            ('SALIDA_AJUSTE', 'Salida por Ajuste'),
            ('SALIDA_DEVOLUCION', 'Salida por Devolución'),
            ('SALIDA_OTRO', 'Salida por Otro Motivo'),
            ('ENTRADA_OTRO', 'Entrada por Otro Motivo'),
        ]
        producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='movimientos', verbose_name="Producto")
        cantidad = models.IntegerField(verbose_name="Cantidad Movida")
        tipo_movimiento = models.CharField(max_length=25, choices=TIPO_MOVIMIENTO_CHOICES, verbose_name="Tipo de Movimiento")
        fecha_hora = models.DateTimeField(default=timezone.now, verbose_name="Fecha y Hora")
        usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos_registrados', verbose_name="Usuario Registrador")
        documento_referencia = models.CharField(max_length=100, blank=True, null=True, verbose_name="Documento Referencia (ID Pedido, Factura, etc.)")
        notas = models.TextField(blank=True, null=True, verbose_name="Notas")

        def __str__(self):
            signo = '+' if self.cantidad > 0 else ''
            return f"{self.get_tipo_movimiento_display()} ({signo}{self.cantidad}) - {self.producto.referencia} | {self.fecha_hora.strftime('%d-%b-%Y %H:%M')}"

        class Meta:
            verbose_name = "Movimiento de Inventario"
            verbose_name_plural = "Movimientos de Inventario"
            ordering = ['-fecha_hora', 'producto__nombre']


class DevolucionCliente(models.Model):
        """Representa una devolución de productos realizada por un cliente."""
        cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='devoluciones', verbose_name="Cliente que Devuelve")
        pedido_original = models.ForeignKey(Pedido, on_delete=models.SET_NULL, null=True, blank=True, related_name='devoluciones_asociadas', verbose_name="Pedido Original (Opcional)")
        fecha_hora = models.DateTimeField(default=timezone.now, verbose_name="Fecha y Hora de Devolución")
        motivo = models.TextField(blank=True, null=True, verbose_name="Motivo General")
        usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='devoluciones_procesadas', verbose_name="Usuario que Procesa")

        def __str__(self):
            return f"Devolución #{self.pk} - {self.cliente.nombre_completo}"

        class Meta:
            verbose_name = "Devolución de Cliente"
            verbose_name_plural = "Devoluciones de Clientes"
            ordering = ['-fecha_hora']


class DetalleDevolucion(models.Model):
        """Representa un producto específico dentro de una devolución."""
        ESTADO_PRODUCTO_DEVOLUCION_CHOICES = [
            ('BUENO', 'Buen estado (Reingresa a stock)'),
            ('DEFECTUOSO', 'Defectuoso (Revisión/Reparación)'),
            ('DESECHAR', 'Para Desechar'),
        ]
        devolucion = models.ForeignKey(DevolucionCliente, related_name='detalles', on_delete=models.CASCADE, verbose_name="Devolución Asociada")
        producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='productos_devueltos', verbose_name="Producto Devuelto")
        cantidad = models.PositiveIntegerField(default=1, verbose_name="Cantidad Devuelta")
        estado_producto = models.CharField(max_length=15, choices=ESTADO_PRODUCTO_DEVOLUCION_CHOICES, default='BUENO', verbose_name="Estado del Producto Devuelto")

        def __str__(self):
            return f"{self.cantidad} x {self.producto.nombre} [{self.get_estado_producto_display()}]"

        class Meta:
            verbose_name = "Detalle de Devolución"
            verbose_name_plural = "Detalles de Devolución"
            unique_together = ('devolucion', 'producto')


class IngresoBodega(models.Model):
        """Representa un ingreso de mercancía a la bodega (ej: compra a proveedor)."""
        fecha_hora = models.DateTimeField(default=timezone.now, verbose_name="Fecha y Hora Ingreso")
        proveedor_info = models.CharField(max_length=200, blank=True, null=True, verbose_name="Información Proveedor/Origen")
        documento_referencia = models.CharField(max_length=100, blank=True, null=True, verbose_name="Documento Referencia (Factura Compra, Remisión, etc.)")
        usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ingresos_registrados', verbose_name="Usuario Registrador")
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
        """Representa un producto específico y cantidad ingresado en un IngresoBodega."""
        ingreso = models.ForeignKey(IngresoBodega, related_name='detalles', on_delete=models.CASCADE, verbose_name="Ingreso Asociado")
        producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='detalles_ingreso', verbose_name="Producto Ingresado")
        cantidad = models.PositiveIntegerField(default=1, verbose_name="Cantidad Ingresada")
        costo_unitario = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Costo Unitario Ingreso (Opcional)")

        def __str__(self):
            costo_str = f" @ ${self.costo_unitario:,.2f}" if self.costo_unitario is not None else ""
            return f"{self.cantidad} x {self.producto.nombre}{costo_str}"

        class Meta:
            verbose_name = "Detalle de Ingreso a Bodega"
            verbose_name_plural = "Detalles de Ingreso a Bodega"
            unique_together = ('ingreso', 'producto')
            
            
class PersonalBodega(models.Model):
    """
    Perfil para el personal de bodega, asociado a un usuario de Django.
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
    verbose_name = "Personal de Bodega"
    verbose_name_plural = "Personal de Bodega"
    ordering = ['user__username'] # Ordenar por nombre de usuario

def __str__(self):
    # Representación legible, usa el nombre de usuario asociado
    return self.user.get_username()
    