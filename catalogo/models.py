# catalogo/models.py
import uuid
from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.urls import reverse
from django.conf import settings

class EnlaceCatalogoTemporal(models.Model):
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    descripcion = models.CharField(max_length=255, blank=True, help_text="Descripción opcional para identificar el enlace.")
    creado_el = models.DateTimeField(auto_now_add=True)
    expira_el = models.DateTimeField()
    activo = models.BooleanField(default=True, help_text="Permite desactivar el enlace manualmente antes de que expire.")
    veces_usado = models.PositiveIntegerField(default=0, help_text="Contador de cuántas veces se ha accedido al enlace (opcional).")
    generado_por = models.ForeignKey( # <--- NUEVO CAMPO
        settings.AUTH_USER_MODEL,    # Enlaza al modelo User de tu proyecto
        on_delete=models.SET_NULL,   # Qué hacer si el usuario se elimina (SET_NULL, CASCADE, PROTECT, etc.)
        null=True,                   # Permite valores nulos (ej. si el sistema lo genera)
        blank=True,                  # Permite que el campo esté vacío en formularios (si aplica)
        related_name='enlaces_catalogo_generados',
        verbose_name="Generado por"
    )


    def save(self, *args, **kwargs):
        if not self.expira_el: # Si no se especifica la fecha de expiración al crear
            self.expira_el = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    def esta_expirado(self):
        return timezone.now() >= self.expira_el

    def esta_disponible(self):
        return self.activo and not self.esta_expirado()

    def obtener_url_absoluta(self):
        # Asegúrate que el nombre de la URL 'catalogo_publico_temporal' coincida con el que definirás en urls.py
        return reverse('catalogo:catalogo_publico_temporal', kwargs={'token': str(self.token)})

    def __str__(self):
        estado = "Expirado" if self.esta_expirado() else "Activo"
        estado = "Inactivo" if not self.activo else estado
        return f"Enlace {self.token} ({estado}) - Expira: {self.expira_el.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        verbose_name = "Enlace Temporal de Catálogo"
        verbose_name_plural = "Enlaces Temporales de Catálogo"
        ordering = ['-creado_el']