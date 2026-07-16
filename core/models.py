# core/models.py
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from clientes.models import Empresa

class User(AbstractUser):
    """
    Modelo de Usuario personalizado que hereda del de Django.
    AQUÍ SE CENTRALIZA LA RELACIÓN CON LA EMPRESA.
    """
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.SET_NULL,
        null=True,  # PERMITE QUE LOS SUPERUSUARIOS NO TENGAN EMPRESA
        blank=True,
        related_name='usuarios'
    )


class ModuloEmpresa(models.Model):
    """
    Controla si una empresa (tenant) tiene habilitada una categoría completa del
    panel (ej. 'Punto de Venta') o una opción individual específica dentro de
    una categoría (ej. solo 'Costeo de Productos' dentro de 'Productos y
    Catálogo'). Solo lo administra el superusuario.

    - Fila de CATEGORÍA COMPLETA: url_nombre='' -- apaga/prende TODA la
      categoría de un solo interruptor (ej. Punto de Venta como app completa).
    - Fila de OPCIÓN INDIVIDUAL: url_nombre='<namespace>:<vista>' -- apaga
      solo esa opción puntual, SIN afectar el resto de la categoría. Estas
      filas solo tienen efecto si la categoría, en general, sigue activa
      (si toda la categoría está apagada, ya no hay nada que mostrar y las
      filas individuales de esa categoría se vuelven irrelevantes).

    Si no existe fila, se considera HABILITADO por defecto -- así no afecta
    retroactivamente a las empresas que ya venían usando la función antes de
    crear este control.
    """
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='modulos')
    categoria = models.CharField(
        max_length=100, verbose_name="Módulo (categoría del panel)",
        help_text="Debe coincidir exactamente con el valor 'categoria' usado en core/panel_config.py"
    )
    url_nombre = models.CharField(
        max_length=150, blank=True, default='', verbose_name="Opción Específica (opcional)",
        help_text="Vacío = aplica a toda la categoría. Con valor (ej. 'bodega:lista_bodegas') = solo esa opción puntual."
    )
    activo = models.BooleanField(default=True, verbose_name="Habilitado")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )

    def __str__(self):
        estado = "Activo" if self.activo else "Inactivo"
        objetivo = self.url_nombre or f"(toda la categoría)"
        return f"{self.empresa.nombre} - {self.categoria} - {objetivo}: {estado}"

    @staticmethod
    def categorias_desactivadas(empresa):
        """Nombres de categoría COMPLETA explícitamente deshabilitados para esta empresa."""
        if not empresa:
            return set()
        return set(
            ModuloEmpresa.objects.filter(empresa=empresa, url_nombre='', activo=False).values_list('categoria', flat=True)
        )

    @staticmethod
    def items_desactivados(empresa):
        """url_nombre de opciones individuales desactivadas puntualmente (dentro de categorías que siguen activas)."""
        if not empresa:
            return set()
        return set(
            ModuloEmpresa.objects.filter(empresa=empresa, activo=False)
            .exclude(url_nombre='')
            .values_list('url_nombre', flat=True)
        )

    class Meta:
        verbose_name = "Módulo Contratado por Empresa"
        verbose_name_plural = "Módulos Contratados por Empresa"
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'categoria', 'url_nombre'], name='un_modulo_por_empresa_categoria_item')
        ]