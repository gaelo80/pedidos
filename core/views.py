# core/views.py
import os
import base64
import pandas as pd # DESCOMENTA ESTO si tus funciones convertir_... lo usan. Asegúrate que pandas esté instalado.
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.staticfiles import finders
from django.urls import reverse, reverse_lazy, NoReverseMatch
from django.conf import settings
from django.contrib.auth.views import LoginView
from django.shortcuts import render
from decimal import Decimal, InvalidOperation
from datetime import datetime
from core.mixins import TenantAwareMixin
from collections import defaultdict # Importación necesaria para el agrupamiento

# Importa tus funciones de rol desde auth_utils.py
from .auth_utils import (
    es_vendedor,
    es_bodega,
    es_cartera,
    es_factura,
    es_diseno,
    es_online,
    es_administracion, # Función para el grupo 'Administracion'
    es_administrador_app, # Función para el rol 'Administrador_app' (menú config)
    puede_ver_panel_django_admin, # Función para el enlace al admin de Django
)

# Importa tu configuración del panel
from .panel_config import PANEL_OPTIONS_CONFIG

# Mapeo de nombres de función de rol (string) a las funciones reales
# Se define a nivel de módulo para que vista_index lo use.
ROL_CHECKERS_MAP = {
    'es_vendedor': es_vendedor,
    'es_bodega': es_bodega,
    'es_cartera': es_cartera,
    'es_factura': es_factura,
    'es_diseno': es_diseno,
    'es_online': es_online,
    'es_administracion': es_administracion, # Deja una sola entrada para es_administracion
    'es_administrador_app': es_administrador_app,
    'puede_ver_panel_django_admin': puede_ver_panel_django_admin,
}

# --- CustomLoginView (al principio después de imports) ---
class CustomLoginView(TenantAwareMixin, LoginView):
    template_name = 'registration/login.html'
    
    def form_valid(self, form):
        user = form.get_user()
        empresa_actual = self.request.tenant

        if user.is_superuser:
            return super().form_valid(form)

        if user.empresa and user.empresa == empresa_actual:
            return super().form_valid(form)
        else:
            messages.error(self.request, "No tienes permiso para acceder a este sitio.")
            return self.form_invalid(form)

    def get_success_url(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return reverse_lazy('core:index')
        if es_administracion(user):
            return reverse_lazy('core:index')
        
        return settings.LOGIN_REDIRECT_URL

# --- Tus funciones de utilidad (asegúrate de que estén aquí o importadas) ---
NO_COLOR_SLUG = '-'

def convertir_fecha_excel(valor_excel, num_fila=None, nombre_campo_para_error="Fecha"):
    if pd.isna(valor_excel) or valor_excel == '':
        return None
    try:
        valor_str = str(valor_excel).strip()
        if '.' in valor_str:
            valor_str = valor_str.split('.')[0]
        if len(valor_str) == 8 and valor_str.isdigit():
            return datetime.strptime(valor_str, '%Y%m%d').date()
        else:
            print(f"Advertencia Fila {num_fila or '?'}: {nombre_campo_para_error} '{valor_excel}' no tiene formato YYYYMMDD esperado. Se omite.")
            return None
    except (ValueError, TypeError) as e:
        print(f"Advertencia Fila {num_fila or '?'}: Error convirtiendo {nombre_campo_para_error} '{valor_excel}'. Error: {e}. Se omite.")
        return None

def convertir_saldo_excel(valor_excel, num_fila=None, nombre_campo_para_error="Saldo"):
    if pd.isna(valor_excel) or valor_excel == '':
       return Decimal('0.00')
    try:
        valor_str = str(valor_excel).strip()
        if ',' in valor_str and '.' in valor_str:
            if valor_str.rfind(',') > valor_str.rfind('.'):
                valor_limpio = valor_str.replace('.', '').replace(',', '.')
            else:
                valor_limpio = valor_str.replace(',', '')
        elif ',' in valor_str:
            valor_limpio = valor_str.replace(',', '.')
        else:
            valor_limpio = valor_str
        return Decimal(valor_limpio)
    except (ValueError, TypeError, InvalidOperation) as e:
        print(f"Advertencia Fila {num_fila or '?'}: Error convirtiendo {nombre_campo_para_error} '{valor_excel}'. Error: {e}. Se usará 0.00.")
        return Decimal('0.00')

@login_required
def acceso_denegado_view(request):
    return render(request, 'core/acceso_denegado.html')

# --- VISTA INDEX REFACTORIZADA COMPLETA ---
@login_required
def vista_index(request):
    
    empresa_actual = getattr(request, 'tenant', None)
    user = request.user
    
    print(f"DEBUG: Total de opciones cargadas desde panel_config.py: {len(PANEL_OPTIONS_CONFIG)}")
    
    # Determinar el título de la página basado en el rol principal
    titulo_base = "Panel Principal" # Valor por defecto inicializado
    # Prioriza los roles más "generales" o de "mayor autoridad" para asignar el título
    if user.is_superuser: # El más alto privilegio
        titulo_base = "Panel de Administración General"
    elif es_administrador_app(user): # Si es Administrador_app (nuestro rol para gestión de la app)
        titulo_base = "Panel de Administración de la Aplicación"
    # Los siguientes 'elif' son para roles más específicos si no fue cubierto por los anteriores
    elif es_administracion(user):
        titulo_base = "Panel Área Administrativa"
    elif es_bodega(user):
        titulo_base = "Panel de Bodega"
    elif es_vendedor(user):
        titulo_base = "Panel de Vendedor"
    elif es_cartera(user):
        titulo_base = "Panel de Cartera"
    elif es_factura(user):
        titulo_base = "Panel de Facturación"
    elif es_diseno(user):
        titulo_base = "Panel de Diseño"
    elif es_online(user):
        titulo_base = "Panel de Ventas Online"
    # No se necesita un 'else' final porque ya se inicializó titulo_base al principio

    titulo_pagina = f"{titulo_base} ({empresa_actual.nombre})" if empresa_actual else titulo_base

    print(f"DEBUG: Usuario: {user.username}, Superuser: {user.is_superuser}, Staff: {user.is_staff}")
    if not PANEL_OPTIONS_CONFIG:
        print("DEBUG: PANEL_OPTIONS_CONFIG está vacío o no se importó correctamente.")
        
    # Diccionario para agrupar las opciones por categoría
    opciones_por_categoria = defaultdict(list)

    # Orden predefinido para las categorías (las que no estén aquí se añadirán al final)
    ORDERED_CATEGORIES = [
        'Pedidos y Ventas',
        'Clientes y Prospectos',
        'Finanzas y Recaudos',
        'Bodega e Inventario',
        'Facturación',
        'Productos y Catálogo',
        'Informes Generales',
        'Administración del Sistema',
    ]

    for opcion_config in PANEL_OPTIONS_CONFIG:
        perm_requerido_config = opcion_config.get('permiso_requerido')
        rol_requerido_config = opcion_config.get('rol_requerido') # Puede ser string o lista de strings
        url_nombre_opcion = opcion_config.get('url_nombre')
        titulo_opcion = opcion_config.get('titulo', 'Opción sin título')
        categoria_opcion = opcion_config.get('categoria', 'Otras Opciones') # Categoría por defecto si no se especifica
        mostrar_opcion = False # Inicializa a False para cada opción

        if not url_nombre_opcion:
            print(f"ADVERTENCIA: Opción '{titulo_opcion}' no tiene 'url_nombre' definido en PANEL_OPTIONS_CONFIG.")
            continue

        # --- LÓGICA UNIFICADA PARA DETERMINAR SI LA OPCIÓN ES VISIBLE ---
        if user.is_superuser: # Un superusuario siempre ve todas las opciones
            mostrar_opcion = True
        elif perm_requerido_config: # Si hay un permiso de Django configurado
            if isinstance(perm_requerido_config, (list, tuple)):
                if user.has_perms(perm_requerido_config): # Requiere TODOS los permisos de la lista
                    mostrar_opcion = True
            elif isinstance(perm_requerido_config, str):
                if user.has_perm(perm_requerido_config): # Requiere el único permiso
                    mostrar_opcion = True
        elif rol_requerido_config: # Si hay un rol personalizado configurado
            if isinstance(rol_requerido_config, str): # Un solo nombre de función de rol
                checker_func = ROL_CHECKERS_MAP.get(rol_requerido_config)
                if checker_func and checker_func(user):
                    mostrar_opcion = True
                elif not checker_func:
                     print(f"ADVERTENCIA: Función de rol '{rol_requerido_config}' para opción '{titulo_opcion}' no encontrada en ROL_CHECKERS_MAP.")
            elif isinstance(rol_requerido_config, (list, tuple)): # Lista de nombres de función de rol (lógica OR)
                for rol_func_name in rol_requerido_config:
                    checker_func = ROL_CHECKERS_MAP.get(rol_func_name)
                    if checker_func and checker_func(user):
                        mostrar_opcion = True
                        break # Si encuentra un rol que coincide, ya puede mostrarse la opción
                    elif not checker_func:
                        print(f"ADVERTENCIA: Función de rol '{rol_func_name}' en lista para opción '{titulo_opcion}' no encontrada en ROL_CHECKERS_MAP.")
        # --- FIN DE LA LÓGICA DE VISIBILIDAD ---
        
        print(f"DEBUG: Opción '{titulo_opcion}': PermisoCfg='{perm_requerido_config}', RolCfg='{rol_requerido_config}', Mostrar={mostrar_opcion}, Categoría='{categoria_opcion}'")

        if mostrar_opcion:
            # Crea una copia para evitar modificar el PANEL_OPTIONS_CONFIG original
            opcion_render = opcion_config.copy()
            
            # Intenta resolver la URL, pasando url_kwargs si existen
            url_kwargs = opcion_config.get('url_kwargs', {}) # Obtiene los kwargs si están definidos
            try:
                opcion_render['url'] = reverse(url_nombre_opcion, kwargs=url_kwargs) # Pasa los kwargs a reverse
            except NoReverseMatch:
                print(f"ADVERTENCIA: No se pudo resolver URL '{url_nombre_opcion}' con kwargs {url_kwargs} para opción '{titulo_opcion}'. Esta opción no se mostrará.")
                continue # No añade la opción si la URL no se puede resolver

            opcion_render['url_target'] = opcion_render['url'] # Por defecto, la misma URL

            # Lógica para manejar si la opción debe abrir en nueva pestaña
            if url_nombre_opcion == 'admin:index' or opcion_config.get('nueva_pestana', False):
                opcion_render['nueva_pestana'] = True
            else:
                 opcion_render['nueva_pestana'] = False


            orden_final_calculado = opcion_config.get('order', 999) # Toma el 'order' base o un default alto

            # Lógica para orden específico por rol (si la tarjeta tiene 'order_por_rol')
            order_especifico_por_rol = opcion_config.get('order_por_rol')
            if isinstance(order_especifico_por_rol, dict):
                # Verifica si el usuario actual coincide con algún rol que tenga un orden específico
                if es_bodega(user) and 'es_bodega' in order_especifico_por_rol:
                    orden_final_calculado = order_especifico_por_rol['es_bodega']
                elif es_vendedor(user) and 'es_vendedor' in order_especifico_por_rol:
                    orden_final_calculado = order_especifico_por_rol['es_vendedor']
                elif es_cartera(user) and 'es_cartera' in order_especifico_por_rol:
                    orden_final_calculado = order_especifico_por_rol['es_cartera']
                elif es_factura(user) and 'es_factura' in order_especifico_por_rol:
                    orden_final_calculado = order_especifico_por_rol['es_factura']
                elif es_diseno(user) and 'es_diseno' in order_especifico_por_rol:
                    orden_final_calculado = order_especifico_por_rol['es_diseno']
                elif es_online(user) and 'es_online' in order_especifico_por_rol:
                    orden_final_calculado = order_especifico_por_rol['es_online']  
                elif es_administracion(user) and 'es_administracion' in order_especifico_por_rol:
                    orden_final_calculado = order_especifico_por_rol['es_administracion']
                elif es_administrador_app(user) and 'es_administrador_app' in order_especifico_por_rol:
                    orden_final_calculado = order_especifico_por_rol['es_administrador_app']
                # Puedes añadir más 'elif es_otro_rol(user)...' si esta tarjeta tiene más órdenes específicos

            opcion_render['final_order_key'] = orden_final_calculado # Guardamos el orden calculado
            opciones_por_categoria[categoria_opcion].append(opcion_render) # <-- ¡Añade a la categoría!

    # Convertir el defaultdict a una lista ordenada de categorías y sus opciones
    opciones_agrupadas_para_template = []
    for cat_name in ORDERED_CATEGORIES:
        if cat_name in opciones_por_categoria:
            # Ordenar las opciones dentro de cada categoría por su 'final_order_key'
            sorted_options = sorted(opciones_por_categoria[cat_name], 
                                    key=lambda op: (op.get('final_order_key', 999), op.get('titulo', '')))
            opciones_agrupadas_para_template.append({
                'nombre_categoria': cat_name,
                'opciones': sorted_options
            })
    
    # Añadir cualquier categoría que no estuviera en ORDERED_CATEGORIES (al final)
    for cat_name, ops in opciones_por_categoria.items():
        if cat_name not in ORDERED_CATEGORIES:
            sorted_options = sorted(ops, key=lambda op: (op.get('final_order_key', 999), op.get('titulo', '')))
            opciones_agrupadas_para_template.append({
                'nombre_categoria': cat_name,
                'opciones': sorted_options
            })

    print(f"DEBUG: Opciones finales agrupadas para plantilla: {len(opciones_agrupadas_para_template)} categorías")

    context = {
        'titulo': titulo_pagina,
        'opciones_agrupadas': opciones_agrupadas_para_template, # <--- ¡NUEVA VARIABLE PARA LA PLANTILLA!
    }
    return render(request, 'core/index.html', context)