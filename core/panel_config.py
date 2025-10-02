# panel_config.py

PANEL_OPTIONS_CONFIG = [
    # --- Pedidos y Ventas ---
    {
        'titulo': 'Crear Pedido',
        'descripcion': 'Registrar un nuevo pedido para un cliente.',
        'url_nombre': 'pedidos:crear_pedido_web',
        'icono': 'fas fa-plus-circle',
        'icono_color_class': 'icon-success',
        'rol_requerido': 'es_vendedor',
        'order': 1,
        'categoria': 'Pedidos y Ventas', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Crear Pedido Online',
        'descripcion': 'Registrar un nuevo pedido para un cliente.',
        'url_nombre': 'pedidos_online:crear_pedido_online',
        'icono': 'fas fa-plus-circle',
        'icono_color_class': 'icon-success',
        'rol_requerido': ['es_online', 'es_administracion'],
        'order': 1,
        'categoria': 'Pedidos y Ventas', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Borradores Guardados',
        'descripcion': 'Aquí encontrarás tus Borradores.',
        'url_nombre': 'pedidos:lista_pedidos_borrador',
        'icono': 'fas fa-file-alt',
        'icono_color_class': 'icon-warning',
        'rol_requerido': ['es_vendedor', 'es_administracion'],
        'order': 2,
        'categoria': 'Pedidos y Ventas', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Borradores Guardados (Online)',
        'descripcion': 'Aquí encontrarás tus Borradores.',
        'url_nombre': 'pedidos_online:lista_pedidos_borrador_online',
        'icono': 'fas fa-file-alt',
        'icono_color_class': 'icon-warning',
        'rol_requerido': ['es_online', 'es_administracion'],
        'order': 2,
        'categoria': 'Pedidos y Ventas', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Cambios de producto',
        'descripcion': 'Registrar cambios de producto.',
        'url_nombre': 'pedidos_online:registrar_cambio_online',
        'icono': 'fa-solid fa-undo-alt',
        'icono_color_class': 'icon-info',
        'rol_requerido': ['es_online', 'es_administracion'],
        'categoria': 'Pedidos y Ventas', # <-- NUEVA CATEGORÍA
    },

    # --- Clientes y Prospectos ---
    {
        'titulo': 'Formulario de Solicitud de Cliente Nuevo',
        'descripcion': 'Ingresa requisitos de estudio para nuevo cliente',
        'url_nombre': 'prospectos:crear_solicitud',
        'icono': 'fas fa-plus-circle',
        'icono_color_class': 'icon-success',
        'rol_requerido': ['es_vendedor', 'es_administracion'],
        'order': 5,
        'categoria': 'Clientes y Prospectos', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Lista de clientes Prospectos pendientes por aprobar',
        'descripcion': 'Estudiar solicitudes de clientes nuevos.',
        'url_nombre': 'prospectos:lista_solicitudes',
        'icono': 'fas fa-list',
        'icono_color_class': 'icon-success',
        'rol_requerido': ['es_cartera', 'es_vendedor', 'es_administracion'],
        'order': 4,
        'categoria': 'Clientes y Prospectos', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Listado de clientes',
        'descripcion': 'Ver lista de clientes registrados.',
        'url_nombre': 'clientes:cliente_listado_v2',
        'icono': 'fas fa-users',
        'icono_color_class': 'icon-success',
        'rol_requerido': ['es_vendedor', 'es_administracion', 'es_cartera', 'es_factura'],
        'categoria': 'Clientes y Prospectos', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Clientes (Gestión)',
        'descripcion': 'Crear, editar o eliminar clientes.',
        'url_nombre': 'clientes:cliente_listado',
        'icono': ' fas fa-users-cog',
        'icono_color_class': 'icon-info',
        'rol_requerido': ['es_factura', 'es_cartera'],
        'categoria': 'Clientes y Prospectos', # <-- NUEVA CATEGORÍA
    },

    # --- Finanzas y Recaudos ---
    {
        'titulo': 'Recaudos de Dinero',
        'descripcion': 'Registrar un recaudo de dinero recibido de un cliente.',
        'url_nombre': 'recaudos:crear_recaudo',
        'icono': 'fas fa-money-bill-wave',
        'icono_color_class': 'icon-warning',
        'rol_requerido': ['es_vendedor'],
        'order': 2,
        'categoria': 'Finanzas y Recaudos', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Gestionar Recaudos',
        'descripcion': 'Aquí puedes gestionar los recaudos de dinero.',
        'url_nombre': 'recaudos:panel_administracion',
        'icono': 'fas fa-money-bill-wave',
        'icono_color_class': 'icon-warning',
        'rol_requerido': ['es_administracion','es_cartera'],
        'order': 2,
        'categoria': 'Finanzas y Recaudos', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Informe de Recaudos',
        'descripcion': 'Ver el informe general de recaudos.',
        'url_nombre': 'recaudos:reporte_general_recaudos',
        'icono': 'fas fa-money-bill-wave',
        'icono_color_class': 'icon-warning',
        'rol_requerido': ['es_administracion','es_cartera'],
        'order': 2,
        'categoria': 'Finanzas y Recaudos', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Cartera (Informe General)',
        'descripcion': 'Ver el estado de tu Cartera General.',
        'url_nombre': 'cartera:reporte_cartera_general',
        'icono': 'fas fa-wallet',
        'icono_color_class': 'icon-success',
        'rol_requerido': ['es_vendedor', 'es_cartera','es_administracion'],
        'categoria': 'Finanzas y Recaudos', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Cargar Cartera',
        'descripcion': 'Cargar la cartera actualizada.',
        'url_nombre': 'cartera:importar_cartera',
        'icono': 'fa-solid fa-paperclip',
        'icono_color_class': 'icon-info',
        'rol_requerido': ['es_cartera', 'es_administracion'],
        'categoria': 'Finanzas y Recaudos', # <-- NUEVA CATEGORÍA
    },

    # --- Bodega e Inventario ---
    
    {
        'titulo': 'Consultar Kardex de Producto',
        'descripcion': 'Ver el historial de movimientos (entradas/salidas) de un producto específico.',
        'url_nombre': 'bodega:buscar_informe_movimiento',
        'icono': 'fas fa-search-plus',
        'icono_color_class': 'icon-primary',
        #'rol_requerido': ['es_bodega', 'es_administracion', 'es_diseno'],
        'order': 6, # Ajusta el orden como prefieras
        'categoria': 'Bodega e Inventario',
    },
    {
        'titulo': 'Registrar Devolución',
        'descripcion': 'Crear una devolución de cliente.',
        'url_nombre': 'devoluciones:crear_devolucion',
        'icono': 'fa-solid fa-undo',
        'icono_color_class': 'icon-danger',
        'rol_requerido': ['es_bodega', 'es_vendedor', 'es_administracion', 'es_cartera'],
        'order': 3,
        'categoria': 'Bodega e Inventario',
    },
    
    {
        'titulo': 'Cambio de Productos',
        'descripcion': 'Registrar un cambio de un producto por otro.',
        'url_nombre': 'bodega:realizar_cambio_producto',
        'icono': 'fas fa-exchange-alt',
        'icono_color_class': 'icon-info',
        'rol_requerido': ['es_administracion', 'es_cartera', 'es_factura', 'es_bodega', 'es_online', 'es_diseno'],
        'order': 4, 
        'categoria': 'Bodega e Inventario',
    },
    
    {
        'titulo': 'Historial de Cambios',
        'descripcion': 'Consultar todos los cambios de producto registrados.',
        'url_nombre': 'bodega:historial_cambios_producto',
        'icono': 'fas fa-history',
        'icono_color_class': 'icon-dark',
        'rol_requerido': ['es_administracion', 'es_cartera', 'es_factura', 'es_bodega', 'es_online', 'es_diseno'],
        'order': 5, # Justo después del formulario de cambio
        'categoria': 'Bodega e Inventario',
    },
    
    {
        'titulo': 'Pedidos Pendientes para Despacho',
        'descripcion': 'Ver y gestionar pedidos pendientes para despacho.',
        'url_nombre': 'bodega:lista_pedidos_bodega',
        'icono': 'fa-solid fa-boxes-stacked',
        'icono_color_class': 'icon-info',
        'rol_requerido': ['es_bodega', 'es_administracion'],
        'order': 1,
        'categoria': 'Bodega e Inventario', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Informe de Ingresos a Bodega',
        'descripcion': 'Ingresos de mercancía a bodega.',
        'url_nombre': 'informes:informe_ingresos_bodega',
        'icono': 'fa-solid fa-warehouse',
        'icono_color_class': 'icon-primary',
        'rol_requerido': ['es_bodega', 'es_administracion', 'es_diseno'],
        'categoria': 'Bodega e Inventario', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Inventario Físico',
        'descripcion': 'Vista de inventario físico de productos en bodega.',
        'url_nombre': 'bodega:informe_inventario',
        'icono': 'fa-solid fa-clipboard-list',
        'icono_color_class': 'icon-warning',
        'rol_requerido': ['es_bodega','es_administracion'],
        'categoria': 'Bodega e Inventario', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Registrar Salida Interna',
        'descripcion': 'Registrar las salidas internas de Bodega.',
        'url_nombre': 'bodega:lista_salidas_internas',
        'icono': 'fa-solid fa-box-open',
        'icono_color_class': 'icon-info',
        'rol_requerido': ['bodega.add_salidainternacabecera','es_bodega', 'es_administracion'], # Asumo que 'bodega.add_salidainternacabecera' es un permiso de Django
        'categoria': 'Bodega e Inventario', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Realizar Conteo de Inventario',
        'descripcion': 'Interfaz para el conteo físico de inventario.',
        'url_nombre': 'bodega:vista_conteo_inventario',
        'icono': 'fa-solid fa-clipboard-list',
        'icono_color_class': 'icon-warning',
        'rol_requerido': ['bodega.view_cabeceraconteo','es_administracion'], # Asumo que 'bodega.view_cabeceraconteo' es un permiso de Django
        'categoria': 'Bodega e Inventario', # <-- NUEVA CATEGORÍA
    },

    # --- Facturación ---
    {
        'titulo': 'Despachos listos para Facturar',
        'descripcion': 'Ver despachos listos para generar factura.',
        'url_nombre': 'factura:lista_despachos_a_facturar',
        'icono': 'fa-solid fa-file-invoice',
        'icono_color_class': 'icon-success',
        'rol_requerido': ['es_factura', 'es_administracion'],
        'order': 1,
        'categoria': 'Facturación', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Consultar Despachos por Cliente',
        'descripcion': 'Buscar despachos facturados por cliente.',
        'url_nombre': 'factura:informe_despachos_cliente',
        'icono': 'fa-solid fa-users',
        'icono_color_class': 'icon-info',
        'rol_requerido': ['es_factura', 'es_administracion'],
        'categoria': 'Facturación', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Consultar Despachos por Estado',
        'descripcion': 'Ver despachos según su estado de facturación.',
        'url_nombre': 'factura:informe_despachos_estado',
        'icono': 'fa-solid fa-info-circle',
        'icono_color_class': 'icon-info',
        'rol_requerido': ['es_factura', 'es_administracion'],
        'categoria': 'Facturación', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Consultar Despacho por número de Pedido',
        'descripcion': 'Buscar un despacho por su número de pedido original.',
        'url_nombre': 'factura:informe_despachos_pedido',
        'icono': 'fa-solid fa-search',
        'icono_color_class': 'icon-info',
        'rol_requerido': ['es_factura', 'es_administracion'],
        'categoria': 'Facturación', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Despachos Facturados por Fecha',
        'descripcion': 'Informe de despachos ya facturados en un rango de fechas.',
        'url_nombre': 'factura:informe_facturados_fecha',
        'icono': 'fa-solid fa-calendar-check',
        'icono_color_class': 'icon-info',
        'rol_requerido': ['es_factura', 'es_administracion'],
        'categoria': 'Facturación', # <-- NUEVA CATEGORÍA
    },

    # --- Productos y Catálogo ---
    {
        'titulo': 'Gestión de Productos',
        'descripcion': 'Crear, modificar, eliminar productos y variantes.',
        'url_nombre': 'productos:producto_listado',
        'icono': 'fa-solid fa-box',
        'icono_color_class': 'icon-primary',
        'rol_requerido': ['es_diseno', 'es_administracion'],
        'categoria': 'Productos y Catálogo', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Subir Fotos de Productos',
        'descripcion': 'Cargar fotos para el catálogo de productos.',
        'url_nombre': 'productos:producto_subir_fotos_agrupadas',
        'icono': 'fa-solid fa-images',
        'icono_color_class': 'icon-info',
        'rol_requerido': ['es_diseno', 'es_administracion'],
        'categoria': 'Productos y Catálogo', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Registrar Ingreso',
        'descripcion': 'Registrar ingresos de mercancía a bodega.',
        'url_nombre': 'bodega:vista_registrar_ingreso',
        'icono': 'fa-solid fa-warehouse',
        'icono_color_class': 'icon-info',
        'rol_requerido': ['es_diseno', 'es_bodega', 'es_administracion'],
        'categoria': 'Productos y Catálogo', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Compartir Catálogo',
        'descripcion': 'Generar un enlace temporal para compartir el catálogo con clientes.',
        'url_nombre': 'catalogo:catalogo_generar_enlace_usuario',
        'icono': 'fas fa-share-alt',
        'icono_color_class': 'icon-primary',
        'rol_requerido': ['es_vendedor', 'es_administracion', 'es_cartera', 'es_online'],
        'order': 5,
        'categoria': 'Productos y Catálogo', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'VER CATÁLOGO',
        'descripcion': 'Visualizar el catálogo de productos.',
        'url_nombre': 'catalogo:lista_referencias',
        'icono': 'fas fa-book-open',
        'icono_color_class': 'icon-success',
        'rol_requerido': ['es_vendedor', 'es_diseno', 'es_online', 'es_cartera', 'es_factura', 'es_bodega', 'es_administracion'],
        'categoria': 'Productos y Catálogo', # <-- NUEVA CATEGORÍA
    },

    # --- Informes Generales ---
    {
        'titulo': 'Informe de Ventas General',
        'descripcion': 'Cantidad de unidades Vendidas en general.',
        'url_nombre': 'informes:reporte_ventas_general',
        'icono': 'fas fa-chart-line',
        'icono_color_class': 'icon-primary',
        'rol_requerido': ['es_administracion', 'es_cartera'],
        'order': 2,
        'categoria': 'Informes Generales', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Informe de Ventas por vendedor',
        'descripcion': 'Cantidad de unidades Vendidas por vendedor.',
        'url_nombre': 'informes:reporte_ventas_vendedor',
        'icono': 'fas fa-chart-bar',
        'icono_color_class': 'icon-primary',
        'rol_requerido': ['es_vendedor'],
        'order': 4,
        'categoria': 'Informes Generales', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Informe de Ventas por vendedor online',
        'descripcion': 'Cantidad de unidades Vendidas por vendedor online.',
        'url_nombre': 'pedidos_online:reporte_ventas_vendedor_online',
        'icono': 'fas fa-chart-bar',
        'icono_color_class': 'icon-primary',
        'rol_requerido': ['es_online', 'es_administracion'],
        'order': 3,
        'categoria': 'Informes Generales', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Informe de Ventas General online',
        'descripcion': 'Cantidad de unidades Vendidas por vendedor online.',
        'url_nombre': 'pedidos_online:reporte_ventas_general_online',
        'icono': 'fas fa-chart-bar',
        'icono_color_class': 'icon-primary',
        'rol_requerido': ['es_administracion'],
        'order': 5,
        'categoria': 'Informes Generales', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Informe de pedidos APROBADOS por admin',
        'descripcion': 'Ver los pedidos APROBADOS.',
        'url_nombre': 'informes:informe_pedidos_aprobados_bodega',
        'icono': ' fa-solid fa-check',
        'icono_color_class': 'icon-info',
        'rol_requerido': ['es_cartera', 'es_administracion'],
        'categoria': 'Informes Generales', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Informes pedidos RECHAZADOS',
        'descripcion': 'Ver los pedidos que han sido RECHAZADOS.',
        'url_nombre': 'informes:informe_pedidos_rechazados',
        'icono': 'fa-solid fa-ban',
        'icono_color_class': 'icon-danger',
        'rol_requerido': ['es_cartera', 'es_administracion'],
        'categoria': 'Informes Generales', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Informe Devoluciones Clientes',
        'descripcion': 'Devoluciones realizadas por los clientes.',
        'url_nombre': 'informes:informe_lista_devoluciones',
        'icono': 'fa-solid fa-undo-alt',
        'icono_color_class': 'icon-info',
        'rol_requerido': ['es_bodega', 'es_administracion', 'es_vendedor', 'es_cartera', 'es_factura'], # Corregido error de sintaxis 'es_administracion' 'es_vendedor'
        'order': 6,
        'categoria': 'Informes Generales', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'COMPROBANTES DE DESPACHO',
        'descripcion': 'Consultar comprobantes de despacho generados.',
        'url_nombre': 'informes:informe_comprobantes_despacho',
        'icono': 'fa-solid fa-file-alt',
        'icono_color_class': 'icon-dark',
        'rol_requerido': ['informes.view_comprobantes_despacho', 'es_administracion', 'es_cartera', 'es_factura', 'es_bodega'], # Asumo que 'informes.view_comprobantes_despacho' es un permiso de Django
        'categoria': 'Informes Generales', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'LISTA TOTAL PEDIDOS',
        'descripcion': 'Consultar todos los pedidos existentes en el sistema.',
        'url_nombre': 'informes:informe_total_pedidos',
        'icono': 'fa-solid fa-list-ol',
        'icono_color_class': 'icon-dark',
        'rol_requerido': ['es_administracion', 'es_cartera', 'es_factura'],
        'order': 1,
        'categoria': 'Informes Generales',
    },
    {
        'titulo': 'Informe de Movimiento de Inventario',
        'descripcion': 'Ver el historial de movimientos de inventario de productos.',
        'url_nombre': 'bodega:informe_movimiento_inventario',
        'icono': 'fa-solid fa-dolly', # Icono de un carro para movimientos
        'icono_color_class': 'icon-info',
        'rol_requerido': ['es_bodega', 'es_administracion', 'es_diseno'],
        'categoria': 'Informes Generales', # <-- NUEVA CATEGORÍA
        #'url_kwargs': {'pk': 1}, # Ejemplo: Si la URL requiere un PK por defecto para el informe
    },

    # --- Administración del Sistema ---
    {
        'titulo': 'Pedidos Pendientes Por Aprobar Admin',
        'descripcion': 'Pedidos pendientes por Administración.',
        'url_nombre': 'pedidos:lista_aprobacion_admin',
        'icono': 'fa-solid fa-user-check',
        'icono_color_class': 'icon-warning',
        'rol_requerido': ['es_administracion'],
        'order': 1,
        'categoria': 'Administración del Sistema', # <-- NUEVA CATEGORÍA
    },
    
    {
        'titulo': 'Pedidos Pendientes Por Aprobar Cartera',
        'descripcion': 'Pedidos pendientes por Cartera.',
        'url_nombre': 'pedidos:lista_aprobacion_cartera',
        'icono': 'fa-solid fa-user-check',
        'icono_color_class': 'icon-warning',
        'rol_requerido': ['es_administracion', 'es_cartera'],
        'order': 1,
        'categoria': 'Administración del Sistema', # <-- NUEVA CATEGORÍA
    },
    
    {
        'titulo': 'Gestion Usuarios',
        'descripcion': 'Crear, modificar y asignar permisos a usuarios.',
        'url_nombre': 'user_management:user_list',
        'icono': 'fas fa-users-cog',
        'icono_color_class': 'icon-primary',
        'rol_requerido': 'es_administrador_app', # <--- Usa la función de rol
        'categoria': 'Administración del Sistema', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Gestion Grupos de Usuarios',
        'descripcion': 'Crea, modifica y asigna permisos a grupos de usuarios.',
        'url_nombre': 'user_management:group_list',
        'icono': 'fas fa-users-cog',
        'icono_color_class': 'icon-primary',
        'rol_requerido': 'es_administrador_app', # <--- Usa la función de rol
        'categoria': 'Administración del Sistema', # <-- NUEVA CATEGORÍA
    },
    {
        'titulo': 'Admin Django',
        'descripcion': 'Acceder al panel de administración avanzado.',
        'url_nombre': 'admin:index',
        'icono': 'fas fa-cog',
        'icono_color_class': 'icon-dark',
        'rol_requerido': 'puede_ver_panel_django_admin', # <--- Usa la función de rol
        'categoria': 'Administración del Sistema', # <-- NUEVA CATEGORÍA
    },
]