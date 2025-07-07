# recaudos/admin.py
from django.contrib import admin
from .models import Recaudo, Consignacion

@admin.register(Recaudo)
class RecaudoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'vendedor', 'monto_recibido', 'fecha_recaudo', 'estado', 'consignacion', 'empresa')
    list_filter = ('estado', 'empresa', 'vendedor', 'fecha_recaudo')
    search_fields = ('id', 'cliente__nombre_completo', 'cliente__identificacion', 'vendedor__user__username', 'concepto')
    list_per_page = 25
    readonly_fields = ('fecha_recaudo',)
    autocomplete_fields = ['cliente', 'vendedor', 'consignacion']

    def get_queryset(self, request):
        """Filtra para que los usuarios no-superuser solo vean datos de su empresa."""
        qs = super().get_queryset(request).select_related('empresa', 'cliente', 'vendedor', 'consignacion')
        if request.user.is_superuser:
            return qs
        tenant = getattr(request, 'tenant', None)
        return qs.filter(empresa=tenant) if tenant else qs.none()

@admin.register(Consignacion)
class ConsignacionAdmin(admin.ModelAdmin):
    list_display = ('id', 'vendedor', 'fecha_consignacion', 'monto_total', 'numero_referencia', 'estado', 'empresa')
    list_filter = ('estado', 'empresa', 'vendedor', 'fecha_consignacion')
    search_fields = ('id', 'numero_referencia', 'vendedor__user__username')
    list_per_page = 25
    readonly_fields = ('fecha_creacion', 'fecha_verificacion')
    autocomplete_fields = ['vendedor']

    def get_queryset(self, request):
        """Filtra para que los usuarios no-superuser solo vean datos de su empresa."""
        qs = super().get_queryset(request).select_related('empresa', 'vendedor')
        if request.user.is_superuser:
            return qs
        tenant = getattr(request, 'tenant', None)
        return qs.filter(empresa=tenant) if tenant else qs.none()