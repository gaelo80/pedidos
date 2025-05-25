from django.db import models


class PermisosInformes(models.Model):

    nombre_placeholder = models.CharField(max_length=1, unique=True, default='P')


    class Meta:
        verbose_name = "Permiso de Informe"
        verbose_name_plural = "Permisos de Informes"
        permissions = [
            ("view_reporte_ventas_general", "Puede ver el informe de ventas general"),
            ("view_reporte_ventas_vendedor", "Puede ver el informe de ventas por vendedor"),
            ("view_informe_ingresos_bodega", "Puede ver el informe de ingresos a bodega"),
            ("view_pedidos_aprobados", "Puede ver el informe de pedidos aprobados"),
            ("view_pedidos_rechazados", "Puede ver el informe de pedidos rechazados"),
            ("view_informe_devoluciones", "Puede ver el informe de devoluciones de clientes"),
            ("view_comprobantes_despacho", "Puede ver el informe de comprobantes de despacho"),
            ("view_total_pedidos", "Puede ver el informe total de pedidos"),
          
        ]