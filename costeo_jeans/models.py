from django.db import models
from core.models import Empresa
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.validators import MinValueValidator, MaxValueValidator

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
    @property
    def costo_unitario(self):
        if self.cantidad_producida and self.cantidad_producida > 0:
            return self.costo_total / self.cantidad_producida
        return 0
    def __str__(self):
        return f"Costeo {self.referencia} - {self.fecha}"
    
    estado = models.CharField(max_length=20, choices=EstadoCosteo.choices, default=EstadoCosteo.BORRADOR)
    
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
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    @property
    def costo_total(self):
        return self.cantidad * self.insumo.costo_unitario

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
    
