from django.db.models.signals import post_migrate
from django.contrib.auth.models import Group, Permission

# El decorador @receiver conecta esta función a la señal post_migrate
# Se ejecutará después de cada vez que corras 'python manage.py migrate'
def crear_grupos_y_permisos(sender, **kwargs):
    """
    Crea los grupos de usuarios con sus permisos específicos después de cada migración.
    Utiliza get_or_create para evitar duplicados si ya existen.
    """
    # --- Grupo Vendedor ---
    vendedor_group, created = Group.objects.get_or_create(name='Vendedores')
    if created:
        print("Grupo 'Vendedor' creado.")
        # Asignar permisos. Debes usar el 'codename' del permiso.
        # Por ejemplo, para el modelo Pedido de la app 'pedidos':
        # perm_crear_pedido = Permission.objects.get(codename='add_pedido')
        # perm_ver_pedido = Permission.objects.get(codename='view_pedido')
        
        # vendedor_group.permissions.add(perm_crear_pedido, perm_ver_pedido)
        # print("Permisos asignados a Vendedor.")

    # --- Grupo Cartera ---
    cartera_group, created = Group.objects.get_or_create(name='Cartera')
    if created:
        print("Grupo 'Cartera' creado.")
        # Asignar permisos para el grupo Cartera
        # perm_ver_cliente = Permission.objects.get(codename='view_cliente')
        # cartera_group.permissions.add(perm_ver_cliente)
        # print("Permisos asignados a Cartera.")

    # --- Puedes añadir más grupos aquí ---
    # ...
    
        # --- Grupo Cartera ---
    administracion_group, created = Group.objects.get_or_create(name='Administracion')
    if created:
        print("Grupo 'Administracion' creado.")
        # Asignar permisos para el grupo Cartera
        # perm_ver_cliente = Permission.objects.get(codename='view_cliente')
        # cartera_group.permissions.add(perm_ver_cliente)
        # print("Permisos asignados a Cartera.")

    # --- Puedes añadir más grupos aquí ---
    # ...
    
        # --- Grupo Cartera ---
    bodega_group, created = Group.objects.get_or_create(name='Bodega')
    if created:
        print("Grupo 'Bodega' creado.")
        # Asignar permisos para el grupo Cartera
        # perm_ver_cliente = Permission.objects.get(codename='view_cliente')
        # cartera_group.permissions.add(perm_ver_cliente)
        # print("Permisos asignados a Cartera.")

    # --- Puedes añadir más grupos aquí ---
    # ...
    
        # --- Grupo Cartera ---
    factura_group, created = Group.objects.get_or_create(name='Factura')
    if created:
        print("Grupo 'Factura' creado.")
        # Asignar permisos para el grupo Cartera
        # perm_ver_cliente = Permission.objects.get(codename='view_cliente')
        # cartera_group.permissions.add(perm_ver_cliente)
        # print("Permisos asignados a Cartera.")

    # --- Puedes añadir más grupos aquí ---
    # ...
    
        # --- Grupo Cartera ---
    diseno_group, created = Group.objects.get_or_create(name='Diseno')
    if created:
        print("Grupo 'Diseno' creado.")
        # Asignar permisos para el grupo Cartera
        # perm_ver_cliente = Permission.objects.get(codename='view_cliente')
        # cartera_group.permissions.add(perm_ver_cliente)
        # print("Permisos asignados a Cartera.")

    # --- Puedes añadir más grupos aquí ---
    # ...
    
        # --- Grupo Cartera ---
    online_group, created = Group.objects.get_or_create(name='Online')
    if created:
        print("Grupo 'Online' creado.")
        # Asignar permisos para el grupo Cartera
        # perm_ver_cliente = Permission.objects.get(codename='view_cliente')
        # cartera_group.permissions.add(perm_ver_cliente)
        # print("Permisos asignados a Cartera.")

    # --- Puedes añadir más grupos aquí ---
    # ...
   