# core/mixins.py
from django.core.exceptions import FieldError

class TenantAwareMixin:
    """
    Mixin para vistas que son conscientes del inquilino (empresa).
    Filtra los querysets y asigna la empresa al crear nuevos objetos.
    """
    
    def get_queryset(self):
        # Esta parte probablemente ya la tienes y está bien.
        # Filtra la lista de objetos para mostrar solo los de la empresa actual.
        qs = super().get_queryset()
        if self.request.user.is_superuser:
            return qs
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            return qs.filter(empresa=tenant)
        return qs.none()

    # --- MÉTODO CORREGIDO ---
    def form_valid(self, form):
        """
        Sobrescribe form_valid para asignar la empresa y manejar diferentes tipos de formularios.
        """
        # Se comprueba si el formulario tiene un atributo '.instance'.
        # Los ModelForm (para crear Pedidos, Productos, etc.) lo tienen.
        # El AuthenticationForm (del login) NO lo tiene.
        if hasattr(form, 'instance'):
            tenant = getattr(self.request, 'tenant', None)
            
            # Se comprueba si la instancia tiene un campo 'empresa' antes de asignarlo.
            if hasattr(form.instance, 'empresa') and tenant:
                # Se asigna la empresa solo al crear un objeto nuevo (cuando no tiene pk).
                if not form.instance.pk:
                    form.instance.empresa = tenant

        # Llama al método form_valid original para que el formulario siga su curso normal.
        # Para el login, esto significa que autenticará y logueará al usuario.
        # Para otros formularios, guardará el objeto.
        return super().form_valid(form)