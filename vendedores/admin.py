# vendedores/admin.py
from django.contrib import admin
from .models import Vendedor

@admin.register(Vendedor)
class VendedorAdmin(admin.ModelAdmin):
    
    # 1. MOSTRAMOS LA EMPRESA A TRAVÉS DE UN MÉTODO
    list_display = ('user', 'get_empresa_del_usuario', 'telefono_contacto', 'codigo_interno', 'activo')
    
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'codigo_interno')
    list_filter = ('activo',)
    list_per_page = 25

    # 2. USAMOS 'fields' PARA DEFINIR UN FORMULARIO SIMPLE SIN EL CAMPO 'empresa'
    fields = ('user', 'telefono_contacto', 'codigo_interno', 'activo')

    # 3. CORREGIMOS EL FILTRADO DEL QUERYSET
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs

        empresa_actual = getattr(request, 'tenant', None)
        if empresa_actual:
            # Filtramos a través de la relación: Vendedor -> User -> Empresa
            return qs.filter(user__empresa=empresa_actual)
        
        return qs.none()

    # 4. AÑADIMOS EL MÉTODO PARA MOSTRAR LA EMPRESA EN LA LISTA
    def get_empresa_del_usuario(self, obj):
        # Accedemos a la empresa a través del usuario vinculado
        if obj.user and obj.user.empresa:
            return obj.user.empresa.nombre
        return "Sin Empresa Asignada"
    get_empresa_del_usuario.short_description = 'Empresa'
    get_empresa_del_usuario.admin_order_field = 'user__empresa'