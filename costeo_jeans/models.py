from django.db import models
from core.models import Empresa
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import F
from django.db import transaction

# --- NUEVO MODELO: COSTO FIJO ---
class CostoFijo(models.Model):
    class TipoCosto(models.TextChoices):
        PORCENTAJE_SUBTOTAL = 'PORCENTAJE', '% del Subtotal (Insumos + Procesos)'
        VALOR_FIJO_UNIDAD = 'FIJO_UNIDAD', '$ Valor Fijo por Unidad'

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100, help_text="Ej: Gastos Administrativos, Ganancia, Transporte")
    tipo = models.CharField(max_length=20, choices=TipoCosto.choices)
    valor = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="El valor numérico. Si es porcentaje, escribir 10 para 10%."
    )
    incluir_por_defecto = models.BooleanField(default=True, help_text="Marcar si este costo debe añadirse automáticamente a cada nuevo costeo.")

    def __str__(self):
        if self.tipo == self.TipoCosto.PORCENTAJE_SUBTOTAL:
            return f"{self.nombre} ({self.valor}%)"
        return f"{self.nombre} (${self.valor})"

class Confeccionista(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=150)
    documento_identidad = models.CharField(max_length=20, unique=True, blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    aplica_iva = models.BooleanField(default=False, help_text="Marcar si este confeccionista factura con IVA")
    def __str__(self):
        return self.nombre

class Insumo(models.Model):
    class CategoriaInsumo(models.TextChoices):
        TELA = 'TELA', 'Tela'
        AVIO = 'AVIO', 'Avío / Otros' # Avío es el término para botones, hilos, etc.
        
    categoria = models.CharField(
        max_length=20, 
        choices=CategoriaInsumo.choices, 
        default=CategoriaInsumo.AVIO
    )    

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100)
    unidad_medida = models.CharField(max_length=20, choices=[('m', 'Metros'), ('un', 'Unidades'), ('kg', 'Kilogramos')])
    costo_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    def __str__(self):
        return f"{self.nombre} (${self.costo_unitario})"
    
    
    
    

class Proceso(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100)
    TIPO_PROCESO = [('PROCESO', 'Proceso Industrial'), ('CONFECCION', 'Confección por Prenda')]
    tipo = models.CharField(max_length=20, choices=TIPO_PROCESO, default='PROCESO')
    
    def __str__(self):
        return self.nombre
    
    
    

class Costeo(models.Model):
    class EstadoCosteo(models.TextChoices):
        BORRADOR = 'BORRADOR', 'Borrador'
        FINALIZADO = 'FINALIZADO', 'Finalizado'
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_index=True)
    referencia = models.CharField(max_length=100)
    cantidad_producida = models.PositiveIntegerField()
    fecha = models.DateField(auto_now_add=True)
    costo_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    precio_venta_unitario = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0.00,
        help_text="Precio de venta final de cada unidad."
    )
    
    porcentaje_descuento_cliente = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Porcentaje de descuento para el cliente (ej: 10 para 10%)."
    )
    porcentaje_comision_vendedor = models.DecimalField(
        max_digits=5, decimal_places=2, default=6.00, # Default del 6%
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Porcentaje de comisión para el vendedor (ej: 6 para 6%)."
    )
    estado = models.CharField(max_length=20, choices=EstadoCosteo.choices, default=EstadoCosteo.BORRADOR) 
      
    @property
    def costo_unitario(self):
        if self.cantidad_producida and self.cantidad_producida > 0:
            return self.costo_total / self.cantidad_producida
        return 0
    def __str__(self):
        return f"Costeo {self.referencia} - {self.fecha}"

    # --- NUEVAS PROPIEDADES PARA UTILIDAD ---
    @property
    def utilidad_unitaria(self):
        if self.precio_venta_unitario and self.costo_unitario:
            return self.precio_venta_unitario - self.costo_unitario
        return 0

    @property
    def utilidad_total(self):
        return self.utilidad_unitaria * self.cantidad_producida

    @property
    def margen_utilidad(self):
        if self.precio_venta_unitario > 0:
            return (self.utilidad_unitaria / self.precio_venta_unitario) * 100
        return 0

    def __str__(self):
        return f"Costeo {self.referencia} - {self.fecha}"
    
    
    @property
    def valor_descuento_unitario(self):
        """Calcula el monto del descuento al cliente por unidad."""
        return self.precio_venta_unitario * (self.porcentaje_descuento_cliente / 100)

    @property
    def precio_final_unitario(self):
        """Calcula el precio de venta final después del descuento al cliente."""
        return self.precio_venta_unitario - self.valor_descuento_unitario

    @property
    def valor_comision_unitaria(self):
        """Calcula el monto de la comisión del vendedor por unidad (sobre el precio final)."""
        return self.precio_final_unitario * (self.porcentaje_comision_vendedor / 100)
    
    @property
    def utilidad_neta_unitaria(self):
        """Utilidad final por prenda después de TODOS los costos y deducciones."""
        deducciones_totales = self.costo_unitario + self.valor_comision_unitaria
        return self.precio_final_unitario - deducciones_totales

    @property
    def utilidad_neta_total(self):
        """Utilidad neta total de toda la producción."""
        return self.utilidad_neta_unitaria * self.cantidad_producida

    @property
    def margen_neto(self):
        """Margen de utilidad final sobre el precio de venta final."""
        if self.precio_final_unitario > 0:
            return (self.utilidad_neta_unitaria / self.precio_final_unitario) * 100
        return 0
    
       
    
class TarifaConfeccionista(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    confeccionista = models.ForeignKey(Confeccionista, on_delete=models.CASCADE, related_name='tarifas')
    proceso = models.ForeignKey(Proceso, on_delete=models.CASCADE, related_name='tarifas')
    costo = models.DecimalField(max_digits=10, decimal_places=2, help_text="Costo del servicio SIN IVA.")

    class Meta:
        # Asegura que no puedas asignar el mismo proceso al mismo confeccionista dos veces
        unique_together = ('confeccionista', 'proceso')

    def __str__(self):
        # Esto hará que el dropdown en el formulario sea muy claro
        return f"{self.proceso.nombre} - ({self.confeccionista.nombre}) - ${self.costo:,.2f}"
    
    
    

class DetalleInsumo(models.Model):
    costeo = models.ForeignKey(Costeo, on_delete=models.CASCADE, related_name='detalle_insumos')
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)
    
    # NUEVO CAMPO: Este es el que el usuario llenará.
    # Ej: 0.8 para 0.8 metros de tela por jean, o 6 para 6 botones por jean.
    consumo_unitario = models.DecimalField(
        max_digits=10, 
        decimal_places=4, 
        help_text="Cantidad o metros necesarios para UNA SOLA UNIDAD del producto.",
        default=0
    )
    
    # CAMPO EXISTENTE: Ahora será calculado automáticamente.
    cantidad = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        editable=False, 
        help_text="Cantidad total calculada para toda la producción."
    )

    @property
    def costo_total(self):
        # Esta propiedad ya es correcta, usa la cantidad total.
        return self.cantidad * self.insumo.costo_unitario

    def save(self, *args, **kwargs):
        # Lógica de cálculo automático antes de guardar
        if self.insumo.categoria == Insumo.CategoriaInsumo.TELA:
            # Para tela, es consumo * cantidad total de prendas
            self.cantidad = self.consumo_unitario * self.costeo.cantidad_producida
        else:
            # Para avíos (botones, hilos), asumimos que el consumo es por unidad también.
            self.cantidad = self.consumo_unitario * self.costeo.cantidad_producida

        super().save(*args, **kwargs)
    
    
    
    
    

class DetalleProceso(models.Model):
    costeo = models.ForeignKey(Costeo, on_delete=models.CASCADE, related_name='detalle_procesos')
    tarifa = models.ForeignKey(
        TarifaConfeccionista, 
        on_delete=models.PROTECT, 
        help_text="Selecciona el proceso y quién lo realiza",
        null=True, 
        blank=True
    )
    cantidad = models.PositiveIntegerField()
    
    # Campos para guardar el valor histórico con defaults permanentes
    costo_unitario_registrado = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False)
    aplica_iva_registrado = models.BooleanField(default=False, editable=False)

    @property
    def costo_subtotal(self):
        if self.costo_unitario_registrado is None:
            return 0
        return self.cantidad * self.costo_unitario_registrado
        
    @property
    def valor_iva(self):
        # Asumimos una tasa de IVA del 19%
        if self.aplica_iva_registrado:
            return self.costo_subtotal * 0.19
        return 0

    @property
    def costo_total(self):
        return self.costo_subtotal + self.valor_iva

    def save(self, *args, **kwargs):
        # Antes de guardar, capturamos los datos si se seleccionó una tarifa
        if self.tarifa and self.pk is None:
            self.costo_unitario_registrado = self.tarifa.costo
            self.aplica_iva_registrado = self.tarifa.confeccionista.aplica_iva
        super().save(*args, **kwargs)

# --- NUEVO MODELO: DETALLE COSTO FIJO ---
class DetalleCostoFijo(models.Model):
    costeo = models.ForeignKey(Costeo, on_delete=models.CASCADE, related_name='detalle_costos_fijos')
    costo_fijo = models.ForeignKey(CostoFijo, on_delete=models.CASCADE)
    valor_calculado = models.DecimalField(max_digits=12, decimal_places=2)
    @property
    def costo_total(self):
        return self.valor_calculado

# --- SEÑAL ACTUALIZADA ---
def update_costeo_total(instance):
    costeo = instance.costeo
    subtotal_insumos = sum(item.costo_total for item in costeo.detalle_insumos.all())
    subtotal_procesos = sum(item.costo_total for item in costeo.detalle_procesos.all())
    subtotal_costos_fijos = sum(item.costo_total for item in costeo.detalle_costos_fijos.all())
    costeo.costo_total = subtotal_insumos + subtotal_procesos + subtotal_costos_fijos
    costeo.save(update_fields=['costo_total'])

@receiver([post_save, post_delete], sender=DetalleInsumo)
def on_detalle_insumo_change(sender, instance, **kwargs):
    update_costeo_total(instance)

@receiver([post_save, post_delete], sender=DetalleProceso)
def on_detalle_proceso_change(sender, instance, **kwargs):
    update_costeo_total(instance)

@receiver([post_save, post_delete], sender=DetalleCostoFijo)
def on_detalle_costo_fijo_change(sender, instance, **kwargs):
    update_costeo_total(instance)
    
@receiver(post_save, sender=Costeo)
def on_costeo_finalize(sender, instance, created, **kwargs):
    """
    Cuando un Costeo se finaliza, crea movimientos de SALIDA para los insumos.
    El stock se actualizará automáticamente gracias a la señal de MovimientoInsumo.
    """
    if not created and instance.estado == Costeo.EstadoCosteo.FINALIZADO:
        with transaction.atomic():
            # Evita que se ejecute múltiples veces
            if not MovimientoInsumo.objects.filter(costeo_relacionado=instance).exists():
                for detalle in instance.detalle_insumos.all():
                    MovimientoInsumo.objects.create(
                        insumo=detalle.insumo,
                        tipo=MovimientoInsumo.Tipo.SALIDA,
                        cantidad=detalle.cantidad,
                        descripcion=f"Uso en producción para costeo: {instance.referencia}",
                        costeo_relacionado=instance
                    )
                
class MovimientoInsumo(models.Model):
    class Tipo(models.TextChoices):
        ENTRADA = 'ENTRADA', 'Entrada (Compra/Ingreso)'
        SALIDA = 'SALIDA', 'Salida (Uso en Producción)'
        AJUSTE = 'AJUSTE', 'Ajuste Manual'

    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE, related_name='movimientos')
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    fecha = models.DateTimeField(auto_now_add=True)
    descripcion = models.CharField(max_length=255, blank=True)
    costeo_relacionado = models.ForeignKey(Costeo, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.tipo} de {self.cantidad} para {self.insumo.nombre}"

    class Meta:
        ordering = ['-fecha']
        
@receiver(post_save, sender=MovimientoInsumo)
def actualizar_stock_insumo(sender, instance, created, **kwargs):
    """
    Actualiza el stock de un Insumo cada vez que se crea un Movimiento.
    """
    if created:
        if instance.tipo == MovimientoInsumo.Tipo.ENTRADA:
            instance.insumo.stock = F('stock') + instance.cantidad
        elif instance.tipo == MovimientoInsumo.Tipo.SALIDA:
            instance.insumo.stock = F('stock') - instance.cantidad
        # Para 'AJUSTE', podrías añadir una lógica más compleja si lo necesitas.

        instance.insumo.save()