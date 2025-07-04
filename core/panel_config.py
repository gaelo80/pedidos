PANEL_OPTIONS_CONFIG = [
    # --- Opciones relacionadas con Pedidos y Vendedores ---
    {
        'titulo': 'Crear Pedido',
        'descripcion': 'Registrar un nuevo pedido para un cliente.',
        'url_nombre': 'pedidos:crear_pedido_web',
        'icono': 'fas fa-plus-circle',
        'icono_color_class': 'icon-success',
        #'permiso_requerido': 'pedidos.add_pedido', # Opción 1: Usar permiso Django
        'rol_requerido': 'es_vendedor', # No se necesita si se usa permiso_requerido
        'order': 1,
        'roles_info': ['vendedor', 'admin'], # Mantener para info si se usa en plantilla
        #ok
    },
    
    
    {
        'titulo': 'Borradores Guardados',
        'descripcion': 'Aquí encontrarás tus Borradores.',
        'url_nombre': 'pedidos:lista_pedidos_borrador',
        'icono': 'fas fa-edit',
        'icono_color_class': 'icon-warning',
        #'permiso_requerido': 'pedidos.view_pedido', # O un permiso más específico si lo tienes
        'rol_requerido': 'es_vendedor',
        'order': 2,
        'roles_info': ['vendedor']
        #ok
    },
    {
        'titulo': 'Registrar Devolución', 
        'descripcion': 'Crear una devolución de cliente.',
        'url_nombre': 'devoluciones:crear_devolucion', 
        'icono': 'fas fa-undo',
        'icono_color_class': 'icon-danger',
        #'permiso_requerido': 'devoluciones.add_devolucioncliente',
        'rol_requerido': ['es_bodega', 'es_vendedor'],
        'order': 3,
        'order_por_rol': {
            'es_bodega': 3, 
            'es_vendedor': 3, 
        },
        'roles_info': ['vendedor', 'admin', 'bodega']
        #ok
    },
    {
        'titulo': 'Informe de Ventas por vendedor',
        'descripcion': 'Cantidad de unidades Vendidas por vendedor.',
        'url_nombre': 'informes:reporte_ventas_vendedor',
        'icono': 'fas fa-chart-line',
        'icono_color_class': 'icon-primary',
        #'permiso_requerido': 'informes.view_reporte_ventas_vendedor', 
        'rol_requerido': 'es_vendedor',
        'order': 4,
        'roles_info': ['Vendedor']
        #ok
    },
    {
        'titulo': 'Listado de clientes',
        'descripcion': 'Ver lista de clientes LOUIS FERRY.',
        'url_nombre': 'clientes:cliente_listado_v2',
        'icono': 'fa-solid fa-list',
        'icono_color_class': 'icon-success',
        #'permiso_requerido': 'clientes.view_cliente', 
        'rol_requerido': ['es_vendedor'],
        'roles_info': ['vendedor', 'admin', 'cartera', 'factura']
        #ok
    },
    {
        'titulo': 'Informe de Despachos',
        'descripcion': 'Informe de los despachos de pedidos.',
        'url_nombre': 'bodega:informe_despachos',
        'icono': 'fa-solid fa-info',
        'icono_color_class': 'icon-success',
        #'permiso_requerido': 'informes.view_comprobantes_despacho',
        'rol_requerido': ['es_vendedor', 'es_admin_sistema_app', 'es_cartera', 'es_factura', 'es_bodega'],
        'roles_info': ['vendedor', 'admin', 'factura', 'cartera']
        #ok
    },

    # --- Opciones relacionadas con Cartera ---
    {
        'titulo': 'Informe de Ventas General',
        'descripcion': 'Cantidad de unidades Vendidas en general.',
        'url_nombre': 'informes:reporte_ventas_general',
        'icono': 'fas fa-chart-pie', 
        'icono_color_class': 'icon-primary',
        #'permiso_requerido': 'informes.view_reporte_ventas_general',
        'rol_requerido': ['es_admin_sistema'],
        'roles_info': ['administracion']
        #ok
    },
    {
        'titulo': 'Cartera (Informe General)',
        'descripcion': 'Ver el estado de tu Cartera General.',
        'url_nombre': 'cartera:reporte_cartera_general',
        'icono': 'fas fa-wallet',
        'icono_color_class': 'icon-success',
        #'permiso_requerido': 'cartera.view_reporte_cartera',
        'rol_requerido': ['es_vendedor', 'es_cartera','es_admin_sistema'],
        'roles_info': ['admin', 'cartera']
        #ok
    },
    {
        'titulo': 'Cargar Cartera',
        'descripcion': 'Cargar la cartera actualizada.',
        'url_nombre': 'cartera:importar_cartera',
        'icono': 'fa-solid fa-paperclip',
        'icono_color_class': 'icon-info',
        #'permiso_requerido': 'cartera.import_cartera', 
        'rol_requerido': ['es_cartera'],
        'roles_info': ['cartera', 'admin', 'diseno'] 
        #ok
    },
    {
        'titulo': 'Clientes (Gestión)',
        'descripcion': 'Crear, editar o eliminar clientes.',
        'url_nombre': 'clientes:cliente_listado', # O la URL principal de gestión de clientes
        'icono': 'fas fa-users-cog', # Icono diferente
        'icono_color_class': 'icon-info',
        #'permiso_requerido': 'clientes.change_cliente',
        'rol_requerido': ['es_factura', 'es_cartera'],
        'roles_info': ['admin', 'cartera', 'factura']
        #ok
    },
    {
        'titulo': 'Informe de pedidos APROBADOS por admin',
        'descripcion': 'Ver los pedidos APROBADOS.',
        'url_nombre': 'informes:informe_pedidos_aprobados_bodega',
        'icono': 'fa-solid fa-check-double', # Icono diferente
        'icono_color_class': 'icon-info',
        #'permiso_requerido': 'informes.view_pedidos_aprobados', # Permiso custom
        'rol_requerido': ['es_cartera', 'es_admin_sistema'],
        'roles_info': ['admin', 'cartera', 'administracion']
    },
    {
        'titulo': 'Informes pedidos RECHAZADOS',
        'descripcion': 'Ver los pedidos que han sido RECHAZADOS.',
        'url_nombre': 'informes:informe_pedidos_rechazados',
        'icono': 'fa-solid fa-ban',
        'icono_color_class': 'icon-danger', # Color diferente
        #'permiso_requerido': 'informes.view_pedidos_rechazados', # Permiso custom
        'rol_requerido': ['es_cartera', 'es_admin_sistema'],
        'roles_info': ['admin', 'cartera', 'administracion']
        #ok
    },
    {
        'titulo': 'Pedidos Pendientes por Aprobar',
        'descripcion': 'Pedidos pendientes para aprobar por Cartera.',
        'url_nombre': 'pedidos:lista_aprobacion_cartera',
        'icono': 'fa-solid fa-file-circle-question',
        'icono_color_class': 'icon-warning',
        #'permiso_requerido': 'pedidos.can_approve_cartera',
        'rol_requerido': ['es_cartera',],
        'order': 1,
        'roles_info': ['cartera', 'admin']
        #ok
    },
    {
        'titulo': 'Informe Devoluciones Clientes',
        'descripcion': 'Devoluciones realizadas por los clientes.',
        'url_nombre': 'informes:informe_lista_devoluciones',
        'icono': 'fas fa-people-carry',
        'icono_color_class': 'icon-info',
        'permiso_requerido': 'informes.view_informe_devoluciones',
        'roles_info': ['cartera', 'administracion']
        #ok
    },

    # --- Opciones relacionadas con Bodega ---
    {
        'titulo': 'DESPACHAR MERCANCÍA',
        'descripcion': 'Ver y gestionar pedidos pendientes para despacho.',
        'url_nombre': 'bodega:lista_pedidos_bodega',
        'icono': 'fas fa-tasks',
        'icono_color_class': 'icon-info',
        #'permiso_requerido': 'bodega.view_pedidos_bodega', # Permiso custom
        'rol_requerido': ['es_bodega', 'es_admin_sistema_app'],
        'order': 1,
        'roles_info': ['bodega', 'admin', 'cartera']
        #OK
    },
    {
        'titulo': 'Informe de Ingresos a Bodega',
        'descripcion': 'Ingresos de mercancía a bodega.',
        'url_nombre': 'informes:informe_ingresos_bodega',
        'icono': 'fa-solid fa-dolly-flatbed', 
        'icono_color_class': 'icon-primary', 
        #'permiso_requerido': 'informes.view_informe_ingresos_bodega', 
        'rol_requerido': ['es_bodega', 'es_admin_sistema_app', 'es_diseno'],
        'roles_info': ['admin', 'administracion', 'diseno', 'bodega', 'factura']
        #ok
    },
    {
        'titulo': 'Registrar Salida Interna',
        'descripcion': 'Registrar las salidas internas de Bodega.',
        'url_nombre': 'bodega:lista_salidas_internas',
        'icono': 'fas fa-truck-loading',
        'icono_color_class': 'icon-info',
        'permiso_requerido': 'bodega.add_salidainternacabecera',
        'roles_info': ['admin', 'administracion', 'diseno', 'bodega', 'factura']
        #ok
    },
    {
        'titulo': 'Realizar Conteo de Inventario',
        'descripcion': 'Interfaz para el conteo físico de inventario.',
        'url_nombre': 'bodega:vista_conteo_inventario',
        'icono': 'fas fa-clipboard-check',
        'icono_color_class': 'icon-warning',
        'permiso_requerido': 'bodega.view_cabeceraconteo', # Permiso para ver/iniciar la interfaz
        'roles_info': ['bodega', 'admin']
        #ok
    },


    # --- Opciones relacionadas con Facturación ---
    {
        'titulo': 'Despachos listos para Facturar',
        'descripcion': 'Ver despachos listos para generar factura.',
        'url_nombre': 'factura:lista_despachos_a_facturar',
        'icono': 'fa-solid fa-file-invoice-dollar',
        'icono_color_class': 'icon-success',
        #'permiso_requerido': 'factura.view_despachos_a_facturar', # Permiso custom
        'rol_requerido': ['es_factura', 'es_admin_sistema'],
        'order': 1,
        'order_por_rol': {
            'es_factura': 1, 
            'es_admin_sistema': 5, 
        },      
        
        'roles_info': ['factura', 'admin']
        #ok
    },
    {
        'titulo': 'Consultar Despachos por Cliente',
        'descripcion': 'Buscar despachos facturados por cliente.',
        'url_nombre': 'factura:informe_despachos_cliente',
        'icono': 'fa-solid fa-user-tag',
        'icono_color_class': 'icon-info',
        #'permiso_requerido': 'factura.view_informe_despachos_cliente', # Permiso custom
        'rol_requerido': ['es_factura', 'es_admin_sistema'],
        'roles_info': ['factura', 'admin']
        #ok
    },
    {
        'titulo': 'Consultar Despachos por Estado',
        'descripcion': 'Ver despachos según su estado de facturación.',
        'url_nombre': 'factura:informe_despachos_estado',
        'icono': 'fa-solid fa-file-circle-check',
        'icono_color_class': 'icon-info',
        #'permiso_requerido': 'factura.view_informe_despachos_estado', # Permiso custom
        'rol_requerido': ['es_factura', 'es_admin_sistema'],
        'roles_info': ['factura', 'admin']
        #ok
    },
    {
        'titulo': 'Consultar Despacho por número de Pedido',
        'descripcion': 'Buscar un despacho por su número de pedido original.',
        'url_nombre': 'factura:informe_despachos_pedido',
        'icono': 'fa-solid fa-magnifying-glass-dollar',
        'icono_color_class': 'icon-info',
        #'permiso_requerido': 'factura.view_informe_despachos_pedido', # Permiso custom
        'rol_requerido': ['es_factura', 'es_admin_sistema'],
        'roles_info': ['factura', 'admin']
        #ok
    },
    {
        'titulo': 'Despachos Facturados por Fecha',
        'descripcion': 'Informe de despachos ya facturados en un rango de fechas.',
        'url_nombre': 'factura:informe_facturados_fecha',
        'icono': 'fa-solid fa-calendar-check',
        'icono_color_class': 'icon-info',
        #'permiso_requerido': 'factura.view_informe_facturados_fecha',
        'rol_requerido': ['es_factura', 'es_admin_sistema'],
        'roles_info': ['factura', 'admin']
        #ok
    },

    # --- Opciones relacionadas con Diseño y Productos ---
    {
        'titulo': 'Gestión de Productos',
        'descripcion': 'Crear, modificar, eliminar productos y variantes.',
        'url_nombre': 'productos:producto_listado',
        'icono': 'fa-solid fa-tags',
        'icono_color_class': 'icon-primary',
        #'permiso_requerido': 'productos.view_producto',
        'rol_requerido': 'es_diseno', 
        'roles_info': ['diseno', 'admin']
        #ok
    },
    {
        'titulo': 'Subir Fotos de Productos',
        'descripcion': 'Cargar fotos para el catálogo de productos.',
        'url_nombre': 'productos:producto_subir_fotos_agrupadas',
        'icono': 'fa-solid fa-images',
        'icono_color_class': 'icon-info',
        #'permiso_requerido': 'productos.upload_fotos_producto', # Permiso custom
        'rol_requerido': ['es_diseno', 'es_online'],
        'roles_info': ['diseno', 'admin']
        #ok
    },
    {
        'titulo': 'Registrar Ingreso', 
        'descripcion': 'Registrar ingresos de mercancía a bodega.',
        'url_nombre': 'bodega:vista_registrar_ingreso',
        'icono': 'fa-solid fa-truck-ramp-box',
        'icono_color_class': 'icon-info',
        #'permiso_requerido': 'bodega.add_ingresobodega',
        'rol_requerido': ['es_diseno', 'es_bodega'],
        'roles_info': ['diseno', 'admin', 'bodega']
        #ok
    },
    
     {
        'titulo': 'Compartir Catálogo',
        'descripcion': 'Generar un enlace temporal para compartir el catálogo con clientes.',
        'url_nombre': 'catalogo:catalogo_generar_enlace_usuario', # La URL que creamos para la vista de generación
        'icono': 'fas fa-share-alt', # Ejemplo de icono, puedes cambiarlo
        'icono_color_class': 'icon-primary', # O la clase de color que prefieras
        'rol_requerido': 'es_vendedor', # Define qué roles pueden ver esta tarjeta (ajusta según necesites)
        'order': 5, # Ajusta el orden en el que quieres que aparezca esta tarjeta para los vendedores
        'roles_info': ['vendedor'], # Roles que tendrían esta opción
    },

    # --- Opciones para Administración del Sistema ---
    {
        'titulo': 'Pedidos Pendientes Por Aprobar',
        'descripcion': 'Pedidos pendientes por Administración.',
        'url_nombre': 'pedidos:lista_aprobacion_admin',
        'icono': 'fa-solid fa-user-check',
        'icono_color_class': 'icon-dark',
        #'permiso_requerido': 'pedidos.can_approve_admin', # Permiso custom
        'rol_requerido': ['es_admin_sistema', 'es_factura'],
        'order': 1,
        
        
        
        'roles_info': ['administracion']
        #ok
    },
    {
        'titulo': 'COMPROBANTES DE DESPACHO',
        'descripcion': 'Consultar comprobantes de despacho generados.',
        'url_nombre': 'informes:informe_comprobantes_despacho',
        'icono': 'fa-solid fa-receipt',
        'icono_color_class': 'icon-dark',
        'permiso_requerido': 'informes.view_comprobantes_despacho',
        'roles_info': ['administracion', 'admin', 'bodega', 'cartera', 'factura']
        #ok
    },
    {
        'titulo': 'LISTA TOTAL PEDIDOS',
        'descripcion': 'Consultar todos los pedidos existentes en el sistema.',
        'url_nombre': 'informes:informe_total_pedidos',
        'icono': 'fa-solid fa-list-ol',
        'icono_color_class': 'icon-dark',
        'permiso_requerido': 'informes.view_total_pedidos', # Permiso custom (o 'pedidos.view_pedido' si es general)
        'roles_info': ['administracion', 'admin', 'cartera', 'factura']
        #ok
    },
    {
        'titulo': 'Admin Django',
        'descripcion': 'Acceder al panel de administración avanzado.',
        'url_nombre': 'admin:index',
        'icono': 'fas fa-cog',
        'icono_color_class': 'icon-dark',
        'permiso_requerido': None, # Se maneja con user.is_staff
        'roles_info': ['admin'] # Solo para staff/superusers
    },

    # --- Opciones de Catálogo ---
    {
        'titulo': 'VER CATÁLOGO',
        'descripcion': 'Visualizar el catálogo de productos LOUIS FERRY.',
        'url_nombre': 'catalogo:lista_referencias',
        'icono': 'fas fa-book-open', # Icono diferente
        'icono_color_class': 'icon-success',
        #'permiso_requerido': 'catalogo.view_catalogo',
        'rol_requerido': ['es_vendedor', 'es_diseno', 'es_online', 'es_cartera', 'es_factura', 'es_bodega'],
        'roles_info': ['catalogo', 'admin', 'vendedor'] # Vendedores también deberían ver el catálogo
    },
     {
        'titulo': 'Gestion Usuarios',
        'descripcion': 'Crear, modificar y asignar permisos a usuarios.',
        'url_nombre': 'user_management:user_list', # La app que estamos creando
        'icono': 'fas fa-users-cog',
        'icono_color_class': 'icon-primary',
        'permiso_requerido': 'auth.view_user', # O un permiso más general de "gestionar usuarios"
        'roles_info': ['admin_app', 'administracion']
    },
]