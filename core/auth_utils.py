# core/auth_utils.py

def es_administrador_app(user): # Controla la visibilidad del menú "Config."
    """Devuelve True si el usuario es superusuario o pertenece al grupo 'Administrador_app'."""
    if not user.is_authenticated:
        return False
    # Un superusuario siempre ve la configuración de la app
    if user.is_superuser:
        return True
    # Solo los del grupo 'Administrador_app' (que no son superuser/staff) ven el menú de la app.
    return user.groups.filter(name='Administrador_app').exists()

def puede_ver_panel_django_admin(user): # Controla la visibilidad del ENLACE al panel de Django
    """Devuelve True si el usuario es superusuario o staff."""
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.is_staff

# es_administracion queda igual si se usa para otros fines
def es_administracion(user):
    """Devuelve True si el usuario pertenece al grupo 'Administracion'."""
    if not user.is_authenticated:
        return False
    return user.groups.filter(name='Administracion').exists()

def es_bodega(user):
    """Devuelve True si el usuario pertenece al grupo 'Bodega'."""
    if not user.is_authenticated:
        return False
    return user.groups.filter(name='Bodega').exists()

def es_vendedor(user):
    """Devuelve True si el usuario pertenece al grupo 'Vendedores'."""
    if not user.is_authenticated:
        return False
    return user.groups.filter(name='Vendedores').exists()

def es_cartera(user):
    """Devuelve True si el usuario pertenece al grupo 'Cartera'."""
    if not user.is_authenticated:
        return False
    return user.groups.filter(name='Cartera').exists()

def es_factura(user):
    """Devuelve True si el usuario pertenece al grupo 'Factura'."""
    if not user.is_authenticated:
        return False
    return user.groups.filter(name='Factura').exists()

def es_diseno(user):
    """Devuelve True si el usuario pertenece al grupo 'Diseño'."""
    if not user.is_authenticated:
        return False
    return user.groups.filter(name='Diseno').exists()

def es_online(user):
    """Devuelve True si el usuario pertenece al grupo 'Online'."""
    if not user.is_authenticated:
        return False
    return user.groups.filter(name='Online').exists()