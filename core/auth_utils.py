def es_admin_sistema(user):
    """Devuelve True si el usuario pertenece al grupo 'Administrador Aplicacion'."""
    if not user.is_authenticated:
        return False
    return user.groups.filter(name='Administrador_app').exists()

def es_admin_sistema(user):
    if not user.is_authenticated:
        return False
    return user.is_staff or user.groups.filter(name='Administracion').exists()

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

