# notificaciones/models.py

from django.db import models
from django.conf import settings
from clientes.models import Empresa

class Notificacion(models.Model):
    """
    Representa una notificación para un usuario específico.
    """
        
    empresa = models.ForeignKey(
        Empresa, 
        on_delete=models.CASCADE,
        related_name='notificaciones_empresa', # 'notificaciones' ya está usado por 'destinatario'

    )
    # El usuario que recibirá la notificación.
    destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='notificaciones'
    )
  
    mensaje = models.CharField(max_length=255)   
    url = models.URLField(max_length=200, blank=True, null=True)    
    leido = models.BooleanField(default=False, db_index=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"Notificación para {self.destinatario.username}: {self.mensaje[:30]}..."
    
