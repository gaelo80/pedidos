# cartera/admin.py
from django.contrib import admin
from .models import DocumentoCartera

@admin.register(DocumentoCartera)
class DocumentoCarteraAdmin(admin.ModelAdmin):
    # Campos a mostrar en la lista
    list_display = (
        'cliente', 
        'tipo_documento', 
        'numero_documento', 
        'fecha_documento', 
        'fecha_vencimiento', 
        'saldo_actual', 
        'esta_vencido', # Propiedad calculada
        'dias_mora',    # Propiedad calculada
        'nombre_vendedor_cartera', 
        'ultima_actualizacion_carga'
    )
    # Campos por los que se puede filtrar en la barra lateral
    list_filter = (
        'tipo_documento', 
        'cliente__nombre_completo', # Filtrar por nombre de cliente
        'nombre_vendedor_cartera', 
        'fecha_vencimiento', 
        'fecha_documento'
    )
    # Campos en los que se puede buscar
    search_fields = (
        'numero_documento', 
        'cliente__identificacion', # Buscar por identificación del cliente
        'cliente__nombre_completo',# Buscar por nombre del cliente
        'nombre_vendedor_cartera'
    )
    # Campos que no se pueden editar directamente en el admin (son calculados o automáticos)
    readonly_fields = ('dias_mora', 'esta_vencido', 'ultima_actualizacion_carga')
    # Número de ítems por página
    list_per_page = 30 
    
    # Para mejorar la visualización del filtro de cliente si tienes muchos
    autocomplete_fields = ['cliente'] # Asegúrate que ClienteAdmin tenga search_fields configurado
