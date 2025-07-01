# core/views.py
import os
import base64
import pandas as pd # DESCOMENTA ESTO si tus funciones convertir_... lo usan. Asegúrate que pandas esté instalado.
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.urls import reverse, reverse_lazy, NoReverseMatch # NoReverseMatch es importante
from django.conf import settings
from django.contrib.auth.views import LoginView
from django.shortcuts import render
from decimal import Decimal, InvalidOperation # Para convertir_saldo_excel
from datetime import datetime # Para convertir_fecha_excel
from core.mixins import TenantAwareMixin

# Importa tus funciones de rol desde auth_utils.py
from .auth_utils import (
    es_vendedor, es_bodega,
    es_admin_sistema_app, es_cartera,
    es_admin_sistema, es_factura,
    es_diseno, es_online, 
    # Asegúrate de tener todas las funciones que usarás en rol_checkers
)

# Importa tu configuración del panel
from .panel_config import PANEL_OPTIONS_CONFIG

# Mapeo de nombres de función de rol (string) a las funciones reales
# Se puede definir aquí a nivel de módulo para que vista_index lo use.
ROL_CHECKERS_MAP = {
    'es_vendedor': es_vendedor,
    'es_bodega': es_bodega,
    'es_admin_sistema_app': es_admin_sistema_app,
    'es_cartera': es_cartera,
    'es_admin_sistema': es_admin_sistema,
    'es_factura': es_factura,
    'es_diseno': es_diseno,
    'es_online': es_online,
    # Añade cualquier otra función 'es_...' que uses en PANEL_OPTIONS_CONFIG
}

# --- CustomLoginView (al principio después de imports) ---
class CustomLoginView(TenantAwareMixin, LoginView):
    template_name = 'registration/login.html'
    def get_success_url(self):
        user = self.request.user
        # ... (tu lógica completa de get_success_url)
        if user.is_staff or user.is_superuser: return reverse_lazy('core:index')
        if es_admin_sistema_app(user): return reverse_lazy('core:index')
        # ... y así para los otros roles ...
        return settings.LOGIN_REDIRECT_URL

# --- Tus funciones de utilidad ---
NO_COLOR_SLUG = '-'

def convertir_fecha_excel(valor_excel, num_fila=None, nombre_campo_para_error="Fecha"):
    if pd.isna(valor_excel) or valor_excel == '': # Si usas pd.isna, necesitas 'import pandas as pd'
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
    if pd.isna(valor_excel) or valor_excel == '': # Si usas pd.isna, necesitas 'import pandas as pd'
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
    opciones_visibles_dict = {}
    

    # Determinar el título de la página basado en el rol principal
    titulo_base = "Panel Principal"
    if user.is_superuser or es_admin_sistema_app(user):
        titulo_base = "Panel de Administración General"
    elif es_admin_sistema(user):
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
    else:
        titulo_base = "Panel Principal"

    print(f"DEBUG: Usuario: {user.username}, Superuser: {user.is_superuser}, Staff: {user.is_staff}")
    if not PANEL_OPTIONS_CONFIG:
        print("DEBUG: PANEL_OPTIONS_CONFIG está vacío o no se importó correctamente.")
        
    titulo_pagina = f"{titulo_base} ({empresa_actual.nombre})" if empresa_actual else titulo_base

    for opcion_config in PANEL_OPTIONS_CONFIG:
        perm_requerido_config = opcion_config.get('permiso_requerido')
        rol_requerido_config = opcion_config.get('rol_requerido') # Puede ser string o lista de strings
        url_nombre_opcion = opcion_config.get('url_nombre')
        titulo_opcion = opcion_config.get('titulo', 'Opción sin título')
        mostrar_opcion = False

        if not url_nombre_opcion:
            print(f"ADVERTENCIA: Opción '{titulo_opcion}' no tiene 'url_nombre' definido en PANEL_OPTIONS_CONFIG.")
            continue

        if url_nombre_opcion == 'admin:index':
            if user.is_staff:
                mostrar_opcion = True
        elif user.is_superuser:
            mostrar_opcion = True
        elif perm_requerido_config:
            if isinstance(perm_requerido_config, (list, tuple)):
                if user.has_perms(perm_requerido_config): # Requiere TODOS
                    mostrar_opcion = True
            elif isinstance(perm_requerido_config, str):
                if user.has_perm(perm_requerido_config): # Requiere el único
                    mostrar_opcion = True
        elif rol_requerido_config:
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
                        break 
                    elif not checker_func:
                        print(f"ADVERTENCIA: Función de rol '{rol_func_name}' en lista para opción '{titulo_opcion}' no encontrada en ROL_CHECKERS_MAP.")
        
        print(f"DEBUG: Opción '{titulo_opcion}': PermisoCfg='{perm_requerido_config}', RolCfg='{rol_requerido_config}', Mostrar={mostrar_opcion}")

        if mostrar_opcion:
            if url_nombre_opcion not in opciones_visibles_dict:
                try:
                    opcion_render = opcion_config.copy()
                    opcion_render['url'] = reverse(url_nombre_opcion)
                    opcion_render['url_target'] = opcion_render['url']
                    opcion_render['nueva_pestana'] = opcion_config.get('nueva_pestana', False)
                    orden_final_calculado = opcion_config.get('order', 999) # Toma el 'order' base o un default alto

                    order_especifico_por_rol = opcion_config.get('order_por_rol')
                    if isinstance(order_especifico_por_rol, dict):
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
                        elif es_admin_sistema_app(user) and 'es_admin_sistema_app' in order_especifico_por_rol:
                            orden_final_calculado = order_especifico_por_rol['es_admin_sistema_app']
                        # Puedes añadir más 'elif es_otro_rol(user)...' si esta tarjeta tiene más órdenes específicos

                    opcion_render['final_order_key'] = orden_final_calculado # Guardamos el orden calculado
                    
                    
                    opciones_visibles_dict[url_nombre_opcion] = opcion_render
                except NoReverseMatch:
                    print(f"ADVERTENCIA: No se pudo resolver URL '{url_nombre_opcion}' para opción '{titulo_opcion}'.")
                except Exception as e:
                    print(f"Error procesando opción '{titulo_opcion}': {e}")

    opciones_para_template = sorted(list(opciones_visibles_dict.values()), key=lambda op: op.get('titulo', ''))
    
    opciones_para_template.sort(key=lambda op: (op.get('order', 999), op.get('titulo', '')))
    
    print(f"DEBUG: Opciones finales para plantilla: {len(opciones_para_template)} items")

    context = {
        'titulo': titulo_pagina,
        'opciones': opciones_para_template,
    }
    return render(request, 'core/index.html', context)