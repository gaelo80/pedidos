# inventario/views.py

# --- Django Imports ---
import json
import os
import base64
import pandas as pd
from django.http import HttpResponse
from django.db.models import F, ExpressionWrapper, DecimalField # Para cálculos
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from urllib.parse import quote # Necesario para codificar el mensaje de WhatsApp
from django.urls import reverse, reverse_lazy
from django.conf import settings
from django.contrib.auth.views import LoginView
import re # Para limpiar el número de teléfono
# from django.contrib.auth.models import User # Descomentar si se necesita User directamente
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import get_template
from django.utils import timezone # Usado potencialmente en PDF/Movimientos
from django.shortcuts import render, get_object_or_404, redirect
from .models import Pedido, Vendedor, Cliente # Asegúrate que Vendedor esté importado
from django.db.models import Q # Para búsquedas OR
from django.views.decorators.http import require_POST
from .models import MovimientoInventario, DevolucionCliente, DetalleDevolucion # <-- Modelos necesarios
from .forms import DevolucionClienteForm, DetalleDevolucionFormSet, InfoGeneralConteoForm # <-- Formularios que creamos
from .models import IngresoBodega, DetalleIngresoBodega, MovimientoInventario # <-- Modelos necesarios
from .forms import IngresoBodegaForm, DetalleIngresoFormSet # <-- Formularios que creamos
from .utils import image_to_base64
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch
from weasyprint import HTML, CSS
from django.db.models.functions import Coalesce
from django.db.models import Sum, F, Value, Q
from decimal import Decimal, InvalidOperation
from datetime import datetime
from inventario.models import Cliente
from django.template.loader import render_to_string
from .forms import UploadCarteraFileForm



# --- Third-Party Imports ---
from io import BytesIO
from rest_framework import viewsets, permissions # 'serializers' base no se usa directamente aquí
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly # Importar permisos específicos
from rest_framework.authentication import SessionAuthentication # O la que uses (TokenAuthentication, etc)
from rest_framework.response import Response
from xhtml2pdf import pisa


# --- Local Imports ---
from .forms import PedidoForm
from .models import (
    Ciudad, Producto, Cliente, Pedido, Vendedor, DetallePedido, Pedido, DetallePedido, MovimientoInventario, ConteoInventario, CabeceraConteo, DocumentoCartera
)
from .serializers import (
    CiudadSerializer, ProductoSerializer, ClienteSerializer, PedidoSerializer
    # Importa otros serializers si los necesitas
)

# --- Constantes ---
NO_COLOR_SLUG = '-' # Constante unificada para representar 'Sin Color' en slugs/URLs

def es_bodega(user):
    """Devuelve True si el usuario pertenece al grupo 'Personal de Bodega'."""
    if not user.is_authenticated:
        return False
    return user.groups.filter(name='Personal de Bodega').exists()

def es_vendedor(user):
    """Devuelve True si el usuario pertenece al grupo 'Vendedores'."""
    if not user.is_authenticated:
        return False
    return user.groups.filter(name='Vendedores').exists()

def es_admin_app(user):
    """Devuelve True si el usuario pertenece al grupo 'Administrador Aplicacion'."""
    if not user.is_authenticated:
        return False
    return user.groups.filter(name='Administrador Aplicacion').exists()

def get_logo_base64_despacho():
    ruta_relativa_logo = 'img/logo.jpg' # <--- ¡¡¡IMPORTANTE: CAMBIA ESTA LÍNEA!!!
                                        # Pon la ruta correcta a tu archivo de logo.
                                        # Esta ruta es relativa a uno de tus directorios STATICFILES_DIRS
                                        # o a la carpeta 'static' de tu aplicación 'inventario'.

    ruta_al_logo_completa = None
    # Intentar encontrar el logo en los directorios estáticos definidos en settings.py
    if settings.STATICFILES_DIRS:
        for static_dir in settings.STATICFILES_DIRS:
            test_path = os.path.join(static_dir, ruta_relativa_logo)
            if os.path.exists(test_path):
                ruta_al_logo_completa = test_path
                break
    
    # Si no se encontró, intentar en la carpeta static de la app 'inventario' (si existe)
    if not ruta_al_logo_completa:
        try:
            # Esto asume que tienes una app llamada 'inventario'
            app_static_dir = os.path.join(settings.BASE_DIR, 'inventario', 'static')
            test_path = os.path.join(app_static_dir, ruta_relativa_logo)
            if os.path.exists(test_path):
                ruta_al_logo_completa = test_path
        except Exception: # Si 'inventario' no es una app típica o BASE_DIR no está bien
            pass

    if ruta_al_logo_completa and os.path.exists(ruta_al_logo_completa):
        try:
            with open(ruta_al_logo_completa, "rb") as image_file:
                print(f"Logo cargado exitosamente desde: {ruta_al_logo_completa}")
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            print(f"Error abriendo o codificando el logo desde '{ruta_al_logo_completa}': {e}")
            return None
    else:
        print(f"ADVERTENCIA: Logo no encontrado. Ruta relativa intentada: '{ruta_relativa_logo}'. Ruta completa probada (si aplica): '{ruta_al_logo_completa}'.")
        return None


def render_pdf_weasyprint(request, template_src, context_dict={}, filename_prefix="documento"):
    """Renderiza una plantilla HTML a PDF usando WeasyPrint y devuelve HttpResponse."""
    template = get_template(template_src)
    html_string = template.render(context_dict)

    try:
        # Usar el request para construir la URL base ayuda a WeasyPrint a encontrar archivos estáticos (CSS, imágenes)
        base_url = request.build_absolute_uri('/') 
        html = HTML(string=html_string, base_url=base_url)

        # Renderizar PDF directamente a bytes
        pdf_bytes = html.write_pdf()

        # Crear respuesta HTTP
        response = HttpResponse(pdf_bytes, content_type='application/pdf')

        # Crear nombre de archivo sugerido (intenta obtener ID del objeto principal en el contexto)
        obj_pk_str = ""
        if 'pedido' in context_dict and hasattr(context_dict['pedido'], 'pk'):
             obj_pk_str = f"_{context_dict['pedido'].pk}"
        elif 'devolucion' in context_dict and hasattr(context_dict['devolucion'], 'pk'): # Ejemplo para otro contexto
             obj_pk_str = f"_{context_dict['devolucion'].pk}"
        # ... puedes añadir más elif para otros tipos de objetos ...

        # Formato de fecha y hora para el nombre del archivo
        timestamp = timezone.now().strftime("%Y%m%d_%H%M")
        filename = f"{filename_prefix}{obj_pk_str}_{timestamp}.pdf"

        # Añadir cabecera Content-Disposition para nombre de archivo y manejo
        # 'inline' intenta mostrarlo en navegador, 'attachment' fuerza descarga
        response['Content-Disposition'] = f'inline; filename="{filename}"' 

        print(f"PDF generado exitosamente con WeasyPrint: {filename}")
        return response

    except Exception as e:
        print(f"Error generando PDF con WeasyPrint ({template_src}): {type(e).__name__} - {e}")
        import traceback
        traceback.print_exc() 
        # Es útil devolver el HTML si falla para poder depurarlo
        # return HttpResponse(f"<h1>Error WeasyPrint</h1><pre>{e}</pre><hr><h2>HTML:</h2><pre>{html_string}</pre>", status=500)
        messages.error(request, f"Error interno al generar el PDF: {e}") # Añadir mensaje para el usuario
        # Devolver un error HTTP 500 claro
        return HttpResponse(f"Error interno del servidor al generar el PDF con WeasyPrint.", status=500)
    
def convertir_fecha_excel(valor_excel, num_fila=None, nombre_campo_para_error="Fecha"): # <--- PARÁMETRO AÑADIDO
    """Intenta convertir un valor de Excel (número o texto YYYYMMDD) a fecha."""
    if pd.isna(valor_excel) or valor_excel == '':
        return None
    try:
        valor_str = str(valor_excel).strip()
        if '.' in valor_str:
            valor_str = valor_str.split('.')[0]

        if len(valor_str) == 8 and valor_str.isdigit():
            return datetime.strptime(valor_str, '%Y%m%d').date()
        else:
            # Aquí podrías añadir más formatos si es necesario usando datetime.strptime
            # Por ejemplo, si también esperas 'DD/MM/YYYY' o 'YYYY-MM-DD'
            # for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            # try:
            # return datetime.strptime(valor_str, fmt).date()
            # except ValueError:
            # continue
            print(f"Advertencia Fila {num_fila or '?'}: {nombre_campo_para_error} '{valor_excel}' no tiene formato YYYYMMDD esperado u otro formato reconocido. Se omite.")
            return None
    except (ValueError, TypeError) as e:
        print(f"Advertencia Fila {num_fila or '?'}: Error convirtiendo {nombre_campo_para_error} '{valor_excel}'. Error: {e}. Se omite.")
        return None

def convertir_saldo_excel(valor_excel, num_fila=None, nombre_campo_para_error="Saldo"): # <--- PARÁMETRO AÑADIDO
    """Intenta convertir un valor de Excel a Decimal, manejando puntos y comas."""
    if pd.isna(valor_excel) or valor_excel == '':
       return Decimal('0.00') # O None, si tu modelo lo permite y es más apropiado
    try:
        valor_str = str(valor_excel).strip()
        # Si quieres permitir ambos formatos (ej. 1.234,56 y 1234.56)
        # Esta lógica asume que la coma es el separador decimal si está presente
        # y los puntos son separadores de miles.
        if ',' in valor_str and '.' in valor_str:
            # Asumir que el punto es de miles si la coma está después del último punto
            if valor_str.rfind(',') > valor_str.rfind('.'):
                valor_limpio = valor_str.replace('.', '').replace(',', '.') # 1.234,56 -> 1234.56
            else: # Asumir que la coma es de miles
                valor_limpio = valor_str.replace(',', '') # 1,234.56 -> 1234.56
        elif ',' in valor_str: # Solo comas, asumir que es decimal
            valor_limpio = valor_str.replace(',', '.')
        else: # Solo puntos (o ninguno), asumir que el punto es decimal
            valor_limpio = valor_str

        return Decimal(valor_limpio)
    except (ValueError, TypeError, InvalidOperation) as e:
        print(f"Advertencia Fila {num_fila or '?'}: Error convirtiendo {nombre_campo_para_error} '{valor_excel}'. Error: {e}. Se usará 0.00.")
        return Decimal('0.00')


# ----------------------------------------
# --- API ViewSets ---
# ----------------------------------------

class CiudadViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint que permite ver Ciudades (solo lectura)."""
    queryset = Ciudad.objects.all().order_by('nombre')
    serializer_class = CiudadSerializer
    # permission_classes = [permissions.AllowAny] # O define permisos específicos si es necesario

class ProductoViewSet(viewsets.ModelViewSet):
    """API endpoint que permite ver o editar Productos."""
    queryset = Producto.objects.filter(activo=True).order_by('referencia', 'color', 'talla')
    serializer_class = ProductoSerializer
    permission_classes = [IsAuthenticatedOrReadOnly] # Cualquiera puede ver, solo autenticados pueden editar

class ClienteViewSet(viewsets.ModelViewSet):
    """API endpoint que permite ver o editar Clientes."""
    queryset = Cliente.objects.all().order_by('nombre_completo')
    serializer_class = ClienteSerializer
    permission_classes = [IsAuthenticated] # Solo usuarios autenticados

class PedidoViewSet(viewsets.ModelViewSet):
    """API endpoint que permite ver y crear Pedidos."""
    serializer_class = PedidoSerializer
    permission_classes = [IsAuthenticatedOrReadOnly] # Cualquiera puede ver lista/detalle, solo auth crear/editar

    def get_queryset(self):
        """Filtra pedidos para vendedores o muestra todos para staff."""
        user = self.request.user
        if not user.is_authenticated:
            return Pedido.objects.none()
        if user.is_staff or user.is_superuser:
            return Pedido.objects.all().order_by('-fecha_hora')
        else:
            try:
                # Intenta obtener el vendedor asociado al usuario
                vendedor = Vendedor.objects.get(user=user)
                return Pedido.objects.filter(vendedor=vendedor).order_by('-fecha_hora')
            except Vendedor.DoesNotExist:
                # Si el usuario no es staff ni tiene perfil de vendedor, no ve ningún pedido
                return Pedido.objects.none()

    def perform_create(self, serializer):
        """Asigna automáticamente el vendedor y estado al crear un pedido vía API."""
        try:
            vendedor = Vendedor.objects.get(user=self.request.user)
            # Guarda el pedido asociando el vendedor y estado inicial
            serializer.save(vendedor=vendedor, estado='PENDIENTE')
        except Vendedor.DoesNotExist:
            # Si el usuario no tiene perfil de vendedor, no puede crear pedidos vía API
            # Usa serializers.ValidationError de DRF para devolver un error 400 claro
            from rest_framework import serializers # Importar aquí para evitar import circular o si solo se usa aquí
            raise serializers.ValidationError(
                "El usuario que realiza la solicitud no tiene un perfil de vendedor asociado."
            )

# ----------------------------------------
# --- VISTAS WEB (HTML) ---
# ----------------------------------------


# --- (Tus imports y otras vistas/código sin cambios) ---
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, get_object_or_404, redirect
from .forms import PedidoForm
# from .models import Producto, Cliente, Pedido, Vendedor, DetallePedido

# --- Función de Ayuda _prepare_crear_pedido_context (sin cambios necesarios aquí) ---
# ... (tu código existente) ...


def _prepare_crear_pedido_context(pedido_instance=None, detalles_existentes=None, pedido_form=None):
    print(f"\nDEBUG Helper - RECIBIDO pedido_instance: {repr(pedido_instance)}") # LOG HELPER 1
    """Prepara el contexto, incluyendo detalles agrupados como JSON si se edita."""
    if pedido_form is None:
        if pedido_instance:
            pedido_form = PedidoForm(instance=pedido_instance) # Usa la instancia si existe
        else:
            pedido_form = PedidoForm()

    referencias_qs = Producto.objects.filter(activo=True)\
                                     .values_list('referencia', flat=True)\
                                     .distinct().order_by('referencia')

    detalles_agrupados_json = None
    linea_counter_init = 0 # Para inicializar JS consistentemente

    if detalles_existentes:
        # --- LÓGICA PARA AGRUPAR DETALLES (la que tenías antes) ---
        grupos = {} 
        # (Esta es la lógica larga que procesa los detalles_existentes
        # para crear 'grupos' y luego 'lista_grupos_final')
        # ... (Asegúrate que toda esta lógica esté aquí)...
        for detalle in detalles_existentes:
             producto = detalle.producto
             ref = producto.referencia
             color_val = producto.color
             color_slug = '-' if color_val is None or color_val == '' else color_val
             color_display = 'Sin Color' if color_slug == '-' else color_val
             grupo_key = (ref, color_slug)

             if grupo_key not in grupos:
                 linea_counter_init += 1
                 grupos[grupo_key] = {
                     'lineaId': f'linea-{linea_counter_init}', 
                     'ref': ref, 'color_slug': color_slug, 'color_display': color_display,
                     'precio_unitario': float(detalle.precio_unitario), 
                     'total_qty': 0, 'total_value': 0.0,
                     'variants': [], 'quantities_obj': {} 
                 }
             
             variant_data = { 'id': producto.id, 'talla': producto.talla, 'cantidad': detalle.cantidad }
             grupos[grupo_key]['variants'].append(variant_data)
             grupos[grupo_key]['quantities_obj'][producto.id] = detalle.cantidad
             grupos[grupo_key]['total_qty'] += detalle.cantidad
             # Usa try-except o hasattr si subtotal podría no existir o fallar
             try:
                 grupos[grupo_key]['total_value'] += float(detalle.subtotal) 
             except: # Considera manejar excepciones específicas si es necesario
                 pass # O loggea un error

        lista_grupos_final = []
        for grupo_data in grupos.values():
            grupo_data['variants'].sort(key=lambda x: x['talla'] or '', reverse=False) 
            grupo_data['tallas_string'] = ", ".join([f"{v['talla']}: {v['cantidad']}" for v in grupo_data['variants']])
            grupo_data['quantities_json'] = json.dumps(grupo_data['quantities_obj'])
            lista_grupos_final.append(grupo_data)
        
        lista_grupos_final.sort(key=lambda g: (g['ref'], g['color_display']))
        detalles_agrupados_json = json.dumps(lista_grupos_final) 
        # --- FIN LÓGICA AGRUPAR ---



    context = {
        'pedido_form': pedido_form,
        'referencias': list(referencias_qs),
        'titulo': f'Editar Pedido Borrador #{pedido_instance.pk}' if pedido_instance else 'Crear Nuevo Pedido',
        'pedido_instance': pedido_instance,
        # ---> CORREGIDO: Usa el mismo nombre que la variable <---
        # O asegúrate que la plantilla usa 'detalles_agrupados_json_data' y cambia el nombre de la variable de arriba
        'detalles_agrupados_json_data': detalles_agrupados_json, # Asumiendo que tu plantilla usa {{ detalles_agrupados_json_data|safe }}
        'linea_counter_init': linea_counter_init if detalles_existentes else 0
    }
    print(f"DEBUG Helper - RETORNANDO context['pedido_instance']: {repr(context.get('pedido_instance'))}") # LOG HELPER 2
    return context

@login_required # O el permiso adecuado
def api_cartera_cliente(request, cliente_id):
    """Devuelve la información de cartera pendiente (Facturas y Remisiones) para un cliente."""
    print(f"API Cartera: Recibida petición para cliente ID: {cliente_id}") # Debug
    cliente = get_object_or_404(Cliente, pk=cliente_id) 
    
    documentos_pendientes = DocumentoCartera.objects.filter(
        cliente=cliente, 
        saldo_actual__gt=Decimal('0.00') # Filtrar saldos mayores a cero
    ).order_by('fecha_vencimiento') # Ordenar por vencimiento

    total_deuda = documentos_pendientes.aggregate(total=Sum('saldo_actual'))['total'] or Decimal('0.00')
    # Calcular saldo vencido (documentos con fecha vencimiento anterior a hoy)
    hoy = timezone.now().date()
    total_vencido = documentos_pendientes.filter(fecha_vencimiento__lt=hoy).aggregate(total=Sum('saldo_actual'))['total'] or Decimal('0.00')
    
    max_dias_mora = 0
    documentos_data = []

    for doc in documentos_pendientes:
        dias_mora_doc = doc.dias_mora
        if dias_mora_doc > max_dias_mora:
            max_dias_mora = dias_mora_doc
        
        documentos_data.append({
            'tipo': doc.get_tipo_documento_display(),
            'numero': doc.numero_documento,
            'fecha_doc': doc.fecha_documento.strftime('%Y-%m-%d') if doc.fecha_documento else '-',
            'fecha_ven': doc.fecha_vencimiento.strftime('%Y-%m-%d') if doc.fecha_vencimiento else '-',
            # Formatear saldo como string con separadores de miles y decimales
            'saldo': '{:,.2f}'.format(doc.saldo_actual).replace(',', 'TEMP').replace('.', ',').replace('TEMP', '.'), 
            'dias_mora': dias_mora_doc,
            'esta_vencido': doc.esta_vencido,
            'vendedor': doc.nombre_vendedor_cartera or '-', # Añadido vendedor
        })

    respuesta = {
        'cliente_id': cliente.pk,
        'cliente_nombre': cliente.nombre_completo,
        'documentos': documentos_data,
        'total_documentos': documentos_pendientes.count(),
        # Formatear totales también
        'saldo_total': '{:,.2f}'.format(total_deuda).replace(',', 'TEMP').replace('.', ',').replace('TEMP', '.'),
        'saldo_vencido': '{:,.2f}'.format(total_vencido).replace(',', 'TEMP').replace('.', ',').replace('TEMP', '.'),
        'max_dias_mora': max_dias_mora,
        'tiene_deuda_vencida': total_vencido > 0,
    }
    print(f"API Cartera: Enviando respuesta para cliente ID: {cliente_id}") # Debug
    return JsonResponse(respuesta)


@login_required
# @user_passes_test(lambda u: u.is_staff)
def vista_importar_cartera(request):
    if request.method == 'POST':
        form = UploadCarteraFileForm(request.POST, request.FILES)
        if form.is_valid():
            archivo_excel = request.FILES['archivo_excel']
            tipo_archivo_form = form.cleaned_data['tipo_archivo'] # 'LF' o 'FYN'

            # --- MAPEAMOS EL TIPO_ARCHIVO DEL FORM AL VALOR REAL EN EL MODELO ---
            # Debes tener estos valores definidos, ya sea como constantes en el modelo DocumentoCartera
            # o como los strings exactos que usas en el campo 'tipo_documento'
            # Ejemplo: DocumentoCartera.FACTURA_OFICIAL = 'Factura Oficial'
            #         DocumentoCartera.REMISION = 'Remisión'
            
            tipo_documento_bd = None
            if tipo_archivo_form == 'LF':
                # Reemplaza 'Factura Oficial' con el valor exacto que guardas en DocumentoCartera.tipo_documento
                tipo_documento_bd = "LF" # EJEMPLO, AJUSTA ESTO
            elif tipo_archivo_form == 'FYN':
                # Reemplaza 'Remisión' con el valor exacto que guardas en DocumentoCartera.tipo_documento
                tipo_documento_bd = "FYN" # EJEMPLO, AJUSTA ESTO
            else:
                messages.error(request, "Tipo de archivo seleccionado no es válido para procesamiento.")
                return redirect('inventario_api:importar_cartera') # Revisa el nombre de tu URL

            filas_leidas = 0
            filas_procesadas_ok = 0 # Solo las que se crean/actualizan sin error de fila
            # Ya no necesitamos filas_actualizadas y filas_creadas si borramos todo antes
            # pero si quieres mantener la lógica de update_or_create (más seguro) y solo borrar antes, las puedes mantener.
            # Por ahora, asumiremos que el objetivo es borrar y re-crear para el tipo específico.
            nuevos_registros_creados_en_esta_importacion = 0

            filas_saltadas_concepto = 0
            clientes_no_encontrados = set()
            errores_fila_detalle = [] # Para mensajes más detallados

            try:
                print(f"Iniciando lectura del archivo: {archivo_excel.name} (Tipo Form: {tipo_archivo_form}, Tipo BD: {tipo_documento_bd})")
                df = pd.read_excel(archivo_excel, header=2, dtype=str)
                filas_leidas = len(df)
                print(f"Se leyeron {filas_leidas} filas de datos (después de la cabecera).")

                with transaction.atomic():
                    # --- 1. BORRAR REGISTROS EXISTENTES DEL MISMO TIPO_DOCUMENTO ---
                    if tipo_documento_bd: # Solo si hemos determinado un tipo válido
                        registros_borrados, _ = DocumentoCartera.objects.filter(
                            tipo_documento=tipo_documento_bd
                        ).delete()
                        messages.info(request, f"Se eliminaron {registros_borrados} registros anteriores de tipo '{tipo_documento_bd}'.")
                        print(f"BORRADO: {registros_borrados} registros de tipo '{tipo_documento_bd}' eliminados.")
                    else:
                        # Esto no debería ocurrir si la validación anterior funcionó.
                        raise Exception("No se pudo determinar el tipo de documento de base de datos para el borrado.")

                    # --- 2. PROCESAR NUEVAS FILAS ---
                    for index, row in df.iterrows():
                        num_fila_excel = index + 3 + 1 # +1 porque iterrows es 0-indexed, +3 por el header en fila 3. Ajusta si header es 2.

                        try:
                            concepto = str(row.get('CONCEPTO', '')).strip()
                            if concepto not in ['52', '89']:
                                filas_saltadas_concepto += 1
                                #print(f"DEBUG Fila {num_fila_excel}: Saltada por CONCEPTO='{concepto}'")
                                continue

                            codigo_cliente = str(row.get('CODIGO', '')).strip()
                            numero_doc = str(row.get('DOCUMENTO', '')).strip()

                            if not codigo_cliente or not numero_doc:
                                msg_error = f"Fila {num_fila_excel}: Falta Código de Cliente o Número de Documento."
                                errores_fila_detalle.append(msg_error)
                                print(f"DEBUG Fila {num_fila_excel}: Saltada por falta de CODIGO o DOCUMENTO. Cliente='{codigo_cliente}', Doc='{numero_doc}'")
                                print(f"ERROR VALIDACION: {msg_error}")
                                continue
                            
                            print(f"\nProcesando Fila Excel {num_fila_excel}: Cliente '{codigo_cliente}', Doc '{numero_doc}'")

                            try:
                                cliente_obj = Cliente.objects.get(identificacion=codigo_cliente)
                                print(f"DEBUG Fila {num_fila_excel}: Cliente ENCONTRADO: {cliente_obj}")
                            except Cliente.DoesNotExist:
                                clientes_no_encontrados.add(codigo_cliente)
                                print(f"DEBUG Fila {num_fila_excel}: Cliente con CODIGO '{codigo_cliente}' NO encontrado. Saltando fila.")
                                print(f"ERROR CLIENTE: Fila {num_fila_excel}: Cliente con CODIGO '{codigo_cliente}' NO encontrado.")
                                continue

                            fecha_doc = convertir_fecha_excel(row.get('FECHADOC'), num_fila_excel, 'FECHADOC')
                            print(f"DEBUG Fila {num_fila_excel}: fecha_doc convertida: {fecha_doc} (Tipo: {type(fecha_doc)})")
                            fecha_ven = convertir_fecha_excel(row.get('FECHAVEN'), num_fila_excel, 'FECHAVEN')
                            print(f"DEBUG Fila {num_fila_excel}: fecha_ven convertida: {fecha_ven} (Tipo: {type(fecha_ven)})")
                            saldo = convertir_saldo_excel(row.get('SALDOACT'), num_fila_excel)
                            print(f"DEBUG Fila {num_fila_excel}: saldo convertido: {saldo} (Tipo: {type(saldo)})")
                            nombre_vend = str(row.get('NOMVENDEDOR', '')).strip() or None
                            
                            valor_columna_vendedor = row.get('VENDEDOR')
                            codigo_vend_excel = None
                            print(f"DEBUG Fila {num_fila_excel}: Datos para crear -> cliente:{cliente_obj.pk if cliente_obj else 'N/A'}, tipo_doc:{tipo_documento_bd}, num_doc:{numero_doc}, f_doc:{fecha_doc}, f_ven:{fecha_ven}, saldo:{saldo}, nom_vend:{nombre_vend}, cod_vend:{codigo_vend_excel}")
                            if not pd.isna(valor_columna_vendedor) and valor_columna_vendedor != '':
                                try:
                                    codigo_vend_excel = str(valor_columna_vendedor).strip()
                                except Exception: # Ser más específico si es posible
                                    codigo_vend_excel = None
                            
                            # --- CREAR el registro en DocumentoCartera ---
                            # Ya que borramos antes, cada registro procesado de esta importación será una nueva creación.
                            DocumentoCartera.objects.create(
                                cliente=cliente_obj,
                                tipo_documento=tipo_documento_bd, # Usar el tipo determinado para esta importación
                                numero_documento=numero_doc,
                                fecha_documento=fecha_doc,
                                fecha_vencimiento=fecha_ven,
                                saldo_actual=saldo,
                                nombre_vendedor_cartera=nombre_vend,
                                codigo_vendedor_cartera=codigo_vend_excel,
                                # Asegúrate de incluir todos los campos necesarios de tu modelo DocumentoCartera
                            )
                            nuevos_registros_creados_en_esta_importacion += 1
                            filas_procesadas_ok +=1 # Contar solo las que pasan todas las validaciones y se crean
                            print(f"CREADO: Fila Excel {num_fila_excel} para Cliente '{codigo_cliente}', Doc '{numero_doc}' de tipo '{tipo_documento_bd}'.")

                        except Exception as e_row:
                            msg_error_fila = f"Fila {num_fila_excel}: {e_row}"
                            errores_fila_detalle.append(msg_error_fila)
                            print(f"ERROR EN FILA (EXCEPCIÓN): {msg_error_fila}")
                            import traceback
                            traceback.print_exc(limit=1) # Imprime un traceback corto para el error de fila

                messages.success(request, f"Importación del archivo '{archivo_excel.name}' (Tipo: {tipo_documento_bd}) finalizada.")
                messages.info(request, f"Resumen: {filas_procesadas_ok} filas del Excel procesadas y creadas exitosamente.")
                if nuevos_registros_creados_en_esta_importacion != filas_procesadas_ok : # Chequeo de sanidad
                     messages.warning(request, f"Discrepancia: {filas_procesadas_ok} filas procesadas OK vs {nuevos_registros_creados_en_esta_importacion} registros creados.")

                if filas_saltadas_concepto > 0:
                    messages.info(request, f"{filas_saltadas_concepto} filas fueron ignoradas por concepto diferente a 52 u 89.")
                if clientes_no_encontrados:
                    messages.warning(request, f"{len(clientes_no_encontrados)} códigos de cliente del archivo no fueron encontrados: {', '.join(sorted(list(clientes_no_encontrados)))}")
                if errores_fila_detalle:
                    messages.error(request, f"Se encontraron errores en {len(errores_fila_detalle)} filas (ver consola del servidor para detalles). Primeros errores:")
                    for err_msg in errores_fila_detalle[:3]: # Muestra los primeros 3 errores
                        messages.error(request, err_msg)

            except Exception as e:
                print(f"Error general durante la importación: {e}")
                import traceback
                traceback.print_exc()
                messages.error(request, f"Error crítico al procesar el archivo Excel: {e}")

            return redirect('inventario_api:importar_cartera') # Revisa el nombre de tu URL

        else: # form not valid
            messages.error(request, "Error en el formulario. Por favor, selecciona tipo y archivo.")
    
    else: # request.method == 'GET'
        form = UploadCarteraFileForm()

    context = {
        'form': form,
        'titulo': 'Importar Cartera desde Excel (Reemplazar por Tipo)'
    }
    return render(request, 'inventario/importacion/upload_cartera.html', context)

@login_required
@user_passes_test(lambda u: es_bodega(u) or u.is_superuser or es_admin_app(u), login_url='inventario_api:acceso_denegado') # Ajusta permisos y URL
def vista_despacho_pedido(request, pk):
    """
    Vista para el proceso de despacho de pedidos usando lector de código de barras.
    """
    pedido = get_object_or_404(Pedido.objects.prefetch_related('detalles__producto'), pk=pk) # Precarga detalles y productos

    # Estados en los que se permite despachar
    ESTADOS_PERMITIDOS = ['PENDIENTE', 'PROCESANDO'] # Ajusta según tu flujo

    if pedido.estado not in ESTADOS_PERMITIDOS and not request.user.is_superuser: # Superusuario puede forzar
         messages.warning(request, f"El pedido #{pedido.pk} está en estado '{pedido.get_estado_display()}' y no se puede despachar.")
         # Redirige a donde tenga sentido, quizás la lista de pedidos de bodega
         return redirect('inventario_api:lista_pedidos_bodega') # Ajusta nombre URL

    if request.method == 'POST':
        print(f"--- VISTA_DESPACHO_PEDIDO (POST) --- Pedido #{pk}")
        # Indica qué acción se realizó (Guardar Parcial o Finalizar Despacho)
        action = request.POST.get('action', 'guardar_parcial')

        try:
            with transaction.atomic():
                hubo_cambios = False
                detalles_completos = True # Asumimos inicialmente que todo se despachará

                # Recorrer los detalles del pedido para actualizar cantidades verificadas
                for detalle in pedido.detalles.all():
                    input_name = f'despachado_{detalle.pk}' # Nombre del input hidden que actualizará el JS
                    cantidad_despachada_str = request.POST.get(input_name, '0') # Obtener valor del form

                    try:
                        cantidad_despachada_actual = int(cantidad_despachada_str)
                        if cantidad_despachada_actual < 0:
                            raise ValueError("Cantidad despachada no puede ser negativa.")

                        # Validar que no se despache más de lo pedido
                        if cantidad_despachada_actual > detalle.cantidad:
                             messages.error(request, f"Error en producto {detalle.producto}: Se intentó despachar {cantidad_despachada_actual} pero solo se pidieron {detalle.cantidad}.")
                             raise transaction.TransactionManagementError("Cantidad despachada excede la pedida.")

                        # Actualizar si el valor es diferente al guardado
                        if detalle.cantidad_verificada != cantidad_despachada_actual:
                            detalle.cantidad_verificada = cantidad_despachada_actual
                            detalle.verificado_bodega = True # Marcar como verificado
                            detalle.save(update_fields=['cantidad_verificada', 'verificado_bodega'])
                            hubo_cambios = True
                            print(f"  Detalle {detalle.pk} actualizado. Cantidad Verificada: {cantidad_despachada_actual}")

                        # Verificar si este detalle quedó completamente despachado
                        if detalle.cantidad_verificada < detalle.cantidad:
                             detalles_completos = False # Si alguno falta, el pedido no está completo

                    except (ValueError, TypeError) as e:
                        messages.error(request, f"Error procesando cantidad para {detalle.producto}: {e}. Se recibió '{cantidad_despachada_str}'.")
                        raise transaction.TransactionManagementError("Error en datos de cantidad.")

                # --- Actualizar Estado del Pedido ---
                if hubo_cambios:
                    estado_anterior = pedido.estado
                    if action == 'finalizar_despacho':
                        if detalles_completos:
                            # Cambia a ENVIADO (o el estado que sigue después del despacho completo)
                            pedido.estado = 'ENVIADO' # ¡Ajusta este estado!
                            messages.success(request, f"Pedido #{pedido.pk} marcado como Despachado/Enviado.")
                        else:
                            # No se puede finalizar si faltan items
                            messages.warning(request, f"No se puede finalizar el despacho del Pedido #{pedido.pk} porque faltan ítems por escanear/confirmar.")
                            # Mantenemos el estado PROCESANDO si ya estaba, o lo cambiamos a PROCESANDO
                            if pedido.estado == 'PENDIENTE':
                                pedido.estado = 'PROCESANDO'
                    else: # Guardar Parcial
                        # Si estaba PENDIENTE y hubo cambios, pasa a PROCESANDO
                        if pedido.estado == 'PENDIENTE':
                             pedido.estado = 'PROCESANDO'
                        messages.info(request, f"Despacho parcial guardado para Pedido #{pedido.pk}.")

                    # Guardar cambio de estado si ocurrió
                    if pedido.estado != estado_anterior:
                         pedido.save(update_fields=['estado'])
                         print(f"  Estado del Pedido {pedido.pk} cambiado de '{estado_anterior}' a '{pedido.estado}'")
                else:
                    messages.info(request, f"No se detectaron cambios en el despacho para guardar.")


            # Redirigir a la misma página después de guardar
            return redirect('inventario_api:despacho_pedido', pk=pk) # Ajusta nombre URL

        except transaction.TransactionManagementError as e:
            print(f"Error de transacción (rollback): {e}")
            # El mensaje de error ya se añadió antes
            # Vuelve a renderizar el GET con los datos actuales (no los del POST fallido)
            pass # Dejar que caiga al render GET de abajo
        except Exception as e:
            print(f"Error inesperado guardando despacho: {e}")
            import traceback
            traceback.print_exc()
            messages.error(request, f"Error inesperado al guardar el despacho: {e}")
            # Vuelve a renderizar el GET

    # --- Lógica GET (Mostrar el formulario/interfaz) ---
    detalles_pedido = pedido.detalles.all().order_by('producto__referencia', 'producto__nombre', 'producto__color', 'producto__talla')
    # Convertir detalles a un formato JSON para usar fácilmente en JavaScript
    detalles_json = json.dumps([
        {
            'id': d.pk,
            'producto_id': d.producto.pk,
            'codigo_barras': d.producto.codigo_barras or "", # Incluir código de barras
            'nombre': str(d.producto), # Usar el __str__ del producto para descripción
            'cantidad_pedida': d.cantidad,
            'cantidad_verificada': d.cantidad_verificada or 0
        }
        for d in detalles_pedido
    ])

    context = {
        'pedido': pedido,
        'detalles_pedido': detalles_pedido, # Para la tabla inicial
        'detalles_json': detalles_json,     # Para el JavaScript
        'titulo': f"Despacho Pedido #{pedido.pk}",
        'puede_finalizar': pedido.estado in ESTADOS_PERMITIDOS # Lógica simple, podría ser más compleja
    }
    return render(request, 'inventario/despacho_pedido.html', context) # Ajusta ruta plantilla



@login_required
def api_detalle_cliente(request, cliente_id):
    """
    Devuelve detalles de un cliente por su ID.
    """
    # Solo permite peticiones GET
    if request.method == 'GET':
        try:
            # Busca el cliente en la base de datos usando el ID de la URL
            # !!! USA 'Cliente' o el nombre de tu modelo de cliente !!!
            cliente = get_object_or_404(Cliente, pk=cliente_id)

            # Prepara los datos que quieres enviar al navegador
            # !!! IMPORTANTE: CAMBIA los nombres después de 'cliente.'
            #     para que coincidan con los nombres de los campos en TU MODELO Cliente !!!
            #     (Puedes ver los nombres correctos en tu archivo models.py)
            datos_cliente = {
                'id': cliente.pk, # El ID siempre es 'pk'
                'nombre': cliente.nombre_completo, # CAMBIA ESTO si tu campo de nombre se llama diferente
                'nit': cliente.identificacion, # CAMBIA ESTO si tu campo de NIT/ID se llama diferente
                'direccion': cliente.direccion, # CAMBIA ESTO por tu campo de dirección
                'telefono': cliente.telefono, # CAMBIA ESTO por tu campo de teléfono
                'email': cliente.email, # CAMBIA ESTO por tu campo de email
                'ciudad': cliente.ciudad.nombre,       # Ahora es una cadena de texto (o None)
                            # 'ciudad': cliente.ciudad.nombre if cliente.ciudad else None, # Ejemplo
            }
            # Envía los datos como respuesta JSON
            return JsonResponse(datos_cliente)

        except Exception as e:
            # Si ocurre un error inesperado
            print(f"Error en api_detalle_cliente: {e}") # Muestra el error en la consola del servidor
            # Envía un mensaje de error genérico al navegador
            return JsonResponse({'error': 'Error interno al obtener detalles'}, status=500)
    else:
        # Si intentan usar un método diferente a GET (como POST)
        return JsonResponse({'error': 'Método no permitido'}, status=405)

# --- Vista para Crear Pedido Web (MODIFICADA) ---
@login_required
@user_passes_test(lambda u: not es_bodega(u) or es_admin_app(u), login_url='acceso_denegado')
def vista_crear_pedido_web(request, pk=None):
    print(f"\n--- DEBUG Vista: INICIO Petición GET ---")
    print(f"DEBUG Vista: PK recibido = {pk}")
    """
    Maneja GET para mostrar formulario (nuevo o edición) y POST para guardar.
    """
    
    #if not hasattr(request.user, 'vendedor') and not request.user.is_staff:
        # Si no tiene perfil vendedor Y TAMPOCO es staff...
        #messages.warning(request, "Acceso denegado. Debes tener un perfil de vendedor asignado.")
        #return redirect('acceso_denegado') # Redirige a la página de acceso denegado

    # Si pasa el check inicial, intenta obtener el objeto vendedor
    try:
        # Asumimos que el staff también necesita un perfil vendedor para usar esta vista
        # Si no es así, necesitas ajustar esta lógica
         vendedor = request.user.vendedor # Acceso directo si la relación es OneToOne
    except Vendedor.DoesNotExist:
         # Si es staff pero NO tiene perfil vendedor asociado
        if request.user.is_staff:
             messages.warning(request, "Acceso staff detectado, pero no se encontró perfil Vendedor asociado.")
             # Decide qué hacer: ¿redirigir o asignar un vendedor 'None'?
             # Por seguridad, redirigimos a acceso denegado si 'vendedor' es obligatorio más adelante
             #return redirect('acceso_denegado')
             pass # Permitir continuar a staff
         
        elif es_admin_app(request.user): # ¡Comprobación añadida!
                # Es Admin App, también puede continuar
            print("DEBUG Vista: Es Admin App, permitiendo continuar.")
            pass # Permitir continuar
        else:
             # Otro caso inesperado (usuario normal sin perfil, aunque hasattr debería haberlo capturado)
              messages.error(request, "Error inesperado al buscar perfil de vendedor.")
              return redirect('acceso_denegado')
    # --- Fin Bloque de Verificación ---
    
    
    

    pedido_instance = None
    detalles_existentes = None
    print(f"DEBUG Vista: pedido_instance INICIAL = {repr(pedido_instance)}")

    # Inicializar context aquí, antes de los condicionales
    context = {}  # Inicializar con un diccionario vacío

    # --- Lógica GET: Diferenciar Crear vs Editar ---
    if pk is not None:
        print(f"DEBUG Vista: Entrando a lógica GET para EDITAR (pk={pk})")
        pedido_instance = get_object_or_404(Pedido, pk=pk, vendedor=vendedor, estado='BORRADOR')
        print(f"DEBUG Vista: Pedido encontrado para editar: {repr(pedido_instance)}")
        detalles_existentes = pedido_instance.detalles.select_related('producto').all()
        print(f"DEBUG Vista: Detalles existentes encontrados: {detalles_existentes}")

    # --- Lógica POST ---
    if request.method == 'POST':
        print("DEBUG: POST data recibido en la vista de Pedido:", request.POST)
        form_instance = pedido_instance
        pedido_form = PedidoForm(request.POST, instance=form_instance)
        
        accion = request.POST.get('accion')
        
        

        if pedido_form.is_valid():
            detalles_para_crear = []
            errores_stock = []
            errores_generales = []
            al_menos_un_detalle = False

            # Procesar inputs de cantidad
            for key, value in request.POST.items():
                if key.startswith('cantidad_') and value:
                    try:
                        producto_id_str = key.split('_')[1]
                        producto_id = int(producto_id_str)
                        cantidad_pedida = int(value)

                        if cantidad_pedida > 0:
                            al_menos_un_detalle = True
                            try:
                                producto_variante = Producto.objects.select_related().get(pk=producto_id, activo=True)
                                detalles_para_crear.append({
                                    'producto': producto_variante,
                                    'cantidad': cantidad_pedida,
                                    'precio_unitario': producto_variante.precio_venta,
                                    'stock_disponible': producto_variante.stock_actual
                                })
                            except Producto.DoesNotExist:
                                errores_generales.append(f"Producto ID {producto_id} no encontrado o inactivo.")
                            except Exception as e:
                                errores_generales.append(f"Error buscando producto ID {producto_id}: {e}")
                        elif cantidad_pedida < 0:
                            errores_generales.append(f"Cantidad negativa no permitida para producto ID {producto_id}.")

                    except (ValueError, TypeError, IndexError):
                        errores_generales.append(f"Dato inválido en campo '{key}' (valor: '{value}').")
            # --- Fin procesamiento detalles ---

            # --- Ejecutar acción ---
            if accion == 'guardar_borrador' or accion == 'crear_definitivo':
                if errores_generales:
                    for error in errores_generales: messages.error(request, error)
                else:
                    # Validaciones específicas de 'crear_definitivo'
                    stock_suficiente = True
                    
                    if accion == 'crear_definitivo':         
                                                                     
                                                
                        if not al_menos_un_detalle:
                            errores_generales.append("Debes agregar al menos un producto para crear el pedido definitivo.")
                            stock_suficiente = False
                        else:
                            # Validar stock
                            for detalle in detalles_para_crear:
                                if detalle['cantidad'] > detalle['stock_disponible']:
                                    stock_suficiente = False
                                    errores_stock.append(f"Stock insuficiente para '{detalle['producto']}'. Pedido: {detalle['cantidad']}, Disp: {detalle['stock_disponible']}")
                            if not stock_suficiente:
                                for error in errores_stock: messages.error(request, error)
                    
                    # Proceder a guardar si no hubo errores fatales y stock es suficiente (si aplica)
                    if not errores_generales and stock_suficiente:
                            try:
                                with transaction.atomic():
                                    pedido = pedido_form.save(commit=False)
                                    pedido.vendedor = vendedor
                                    pedido.estado = 'PENDIENTE' if accion == 'crear_definitivo' else 'BORRADOR'
                                    pedido.save() # Guardamos el pedido principal primero

                                    # --- Lógica de Actualización/Creación de Detalles ---
                                    productos_guardados_ids = set() # Para saber qué productos procesamos

                                    for detalle_data in detalles_para_crear:
                                        producto_obj = detalle_data['producto']
                                        cantidad_actual = detalle_data['cantidad']
                                        precio_actual = detalle_data['precio_unitario']

                                        # Intenta actualizar si ya existe, si no, crea uno nuevo
                                        detalle_obj, created = DetallePedido.objects.update_or_create(
                                            pedido=pedido,
                                            producto=producto_obj,
                                            defaults={
                                                'cantidad': cantidad_actual,
                                                'precio_unitario': precio_actual
                                            }
                                        )
                                        productos_guardados_ids.add(producto_obj.pk) # Agrega el ID del producto procesado

                                    # --- Eliminar detalles que ya no están (cantidad 0 o eliminados del form) ---
                                    # Solo aplica si estamos editando (pk existe)
                                    if pk is not None:
                                        DetallePedido.objects.filter(pedido=pedido).exclude(producto_id__in=productos_guardados_ids).delete()

                                    # --- Lógica de Movimiento de Inventario (SOLO para pedido definitivo) ---
                                    if accion == 'crear_definitivo':
                                        # La lógica de validación de stock ya se hizo antes
                                        # Ahora creamos los movimientos para los detalles guardados
                                        detalles_finales = DetallePedido.objects.filter(pedido=pedido) # Obtenemos los detalles finales guardados
                                        for detalle_final in detalles_finales:
                                            # --- >>> INICIO DESCUENTO STOCK <<< ---
                                            producto_a_mover = detalle_final.producto
                                            cantidad_a_mover = detalle_final.cantidad

                                            # Asegúrate de importar F al inicio del archivo si usas la línea comentada de abajo: from django.db.models import F
                                            MovimientoInventario.objects.create(
                                                producto=producto_a_mover,
                                                cantidad= -cantidad_a_mover, # Negativo para salida
                                                tipo_movimiento='SALIDA_VENTA',
                                                documento_referencia=f'Pedido #{pedido.pk}',
                                                usuario=request.user,
                                                notas=f'Salida automática por creación pedido {pedido.pk}'
                                            )
                                            print(f"Movimiento de inventario creado para {producto_a_mover}: {-cantidad_a_mover}")
                                            # Actualizar el stock en el modelo Producto (opcional pero recomendado si no usas señales o triggers)
                                            # Producto.objects.filter(pk=producto_a_mover.pk).update(stock_actual=F('stock_actual') - cantidad_a_mover)
                                            # --- >>> FIN DESCUENTO STOCK <<< ---

                                    # --- Lógica de éxito y redirección ---
                                    if accion == 'crear_definitivo':
                                        messages.success(request, f"Pedido #{pedido.pk} creado exitosamente.")
                                        return redirect('inventario_api:pedido_creado_exito', pk=pedido.pk) # Ajusta a tu URL de éxito
                                    else: # Guardar Borrador
                                        messages.success(request, f"Pedido Borrador #{pedido.pk} guardado exitosamente.")
                                        return redirect('editar_pedido_web', pk=pedido.pk) # Ajusta a tu URL de lista de borradores

                            except Exception as e:
                                messages.error(request, f"Error inesperado al guardar: {e}")
                                # Considera loggear el error completo aquí para debugging
                                print(f"Error guardando pedido {pk}: {e}")
                                import traceback
                                traceback.print_exc()
                                # Re-renderizar abajo con errores (fuera del 'try/except')
                            
            elif accion == 'eliminar_borrador':
                # Asegurarnos que estamos editando (pedido_instance debería existir)
                if pedido_instance:
                    try:
                        with transaction.atomic():
                            pedido_pk_eliminado = pedido_instance.pk
                            pedido_instance.delete()
                            messages.success(request, f"Pedido Borrador #{pedido_pk_eliminado} eliminado exitosamente.")
                            # Redirigir a la lista de borradores (o a donde quieras)
                            print("DEBUG Delete: Borrado exitoso, devolviendo HttpResponse de prueba.")
                            return render(request, 'inventario/lista_pedidos_borrador.html', context)
                    except Exception as e:
                        print(f"DEBUG Delete: !!! EXCEPCIÓN DENTRO DEL TRY: {type(e).__name__}: {e}")
                        print(f"DEBUG Delete: Traceback de excepción:\n{traceback.format_exc()}")
                        messages.error(request, f"Error inesperado al eliminar el borrador: {e}")
                        # Deja que caiga al render final con error
                else:
                    # Esto no debería pasar si el botón solo aparece al editar, pero por seguridad:
                    messages.error(request, "No se puede eliminar un pedido que no se está editando.")
                    # Deja que caiga al render final con error
            elif accion == 'cancelar':
                return render(request, 'inventario/crear_pedido_web_matriz.html', context)        
      
            #else: # Acción desconocida
            messages.error(request, "Acción de guardado no reconocida.")
            
            
            
            
            

        else: # pedido_form NO es válido
            print(f"DEBUG Vista: Entrando a lógica final GET (antes de llamar a helper)")
            print(f"DEBUG Vista: Valor de pedido_instance ANTES de llamar a helper: {repr(pedido_instance)}")
            messages.error(request, "Por favor corrige los errores en la sección del cliente/notas.")
            
            # --- Si POST falló (form inválido, error stock, error general, etc.) ---
            # Necesitamos reconstruir el contexto con los datos fallidos para mostrar errores
            # La función _prepare_crear_pedido_context necesita el pedido_form con errores
            # y potencialmente los detalles que SÍ se pudieron procesar antes del error
            # (Esto puede ser complejo de reconstruir perfectamente, una simplificación es
            # pasar el form con errores y los detalles originales si editábamos)
            context_form = pedido_form # El form ya tiene errores
            context = _prepare_crear_pedido_context(
                pedido_instance=pedido_instance,
                detalles_existentes=detalles_existentes,
                pedido_form=context_form
            )
    
        print(f"DEBUG Vista: Contexto FINAL ['pedido_instance'] antes de render: {repr(context.get('pedido_instance'))}")    
        return render(request, 'inventario/crear_pedido_web_matriz.html', context)

       # --- Lógica GET (o si POST no se procesó) ---
        # Si es GET, prepara el contexto para nuevo o para editar
        # pedido_instance y detalles_existentes ya se calcularon arriba si pk is not None
    else: # request.method == 'GET'
        print("DEBUG: Procesando GET...")
        # pedido_instance ya se obtuvo arriba si pk existe
        # detalles_existentes ya se obtuvo arriba si pk existe
        pedido_form_inicial = PedidoForm(instance=pedido_instance)
        context = _prepare_crear_pedido_context(
            pedido_instance=pedido_instance,
            detalles_existentes=detalles_existentes,
            pedido_form=pedido_form_inicial
    )
        return render(request, 'inventario/crear_pedido_web_matriz.html', context)
        

@login_required
def vista_conteo_inventario(request):
    print(f"****** VISTA CONTEO: Método Recibido = {request.method} ******")

    # --- Lógica POST: Procesar datos enviados ---
    if request.method == 'POST':
        print("****** VISTA CONTEO: PROCESANDO POST ******")

        # 1. Verificar Permisos
        if not request.user.has_perm('inventario.change_producto') and not request.user.is_superuser:
             messages.error(request, "Acción no permitida.")
             return render(request, 'inventario/acceso_denegado.html', status=403)

        # 2. Validar Formulario de Información General
        info_form = InfoGeneralConteoForm(request.POST) # Validar con datos POST
        if info_form.is_valid():
            print("  -> Formulario InfoGeneralConteoForm es VÁLIDO.")
            # Extraer datos del info_form
            fecha_ajuste = info_form.cleaned_data['fecha_actualizacion_stock']
            motivo = info_form.cleaned_data['motivo_conteo']
            revisado = info_form.cleaned_data['revisado_con']
            notas_gral = info_form.cleaned_data['notas_generales']

            items_procesados_correctamente = 0
            items_con_error_o_sin_cambio = 0
            inconsistencias = [] # Para el informe futuro
            cabecera_conteo_guardada = None # Para guardar el ID

            try:
                # 3. Procesar cada producto dentro de una transacción
                with transaction.atomic():
                    # --- Crear la Cabecera del Conteo ---
                    cabecera = CabeceraConteo.objects.create(
                        fecha_conteo=fecha_ajuste,
                        motivo=motivo,
                        revisado_con=revisado,
                        notas_generales=notas_gral,
                        usuario_registro=request.user
                    )
                    cabecera_conteo_guardada = cabecera.pk # Guardar el ID
                    print(f"  -> Cabecera de Conteo creada con ID: {cabecera.pk}")

                    items_a_procesar = list(Producto.objects.filter(activo=True))
                    print(f"  -> Encontrados {len(items_a_procesar)} productos activos para procesar en POST.")

                    for producto_item in items_a_procesar:
                        input_name = f'cantidad_fisica_{producto_item.pk}'
                        cantidad_fisica_str = request.POST.get(input_name)

                        if cantidad_fisica_str is not None and cantidad_fisica_str.strip() != '':
                            try:
                                cantidad_fisica = int(cantidad_fisica_str)
                                if cantidad_fisica < 0: continue

                                stock_sistema_actual = producto_item.stock_actual
                                diferencia_stock = cantidad_fisica - stock_sistema_actual

                                # --- Crear Detalle de Conteo asociado a la Cabecera ---
                                conteo_guardado_obj = ConteoInventario.objects.create( # Guardar el objeto para obtener su ID si es necesario
                                    cabecera_conteo=cabecera, # Enlazar a la cabecera
                                    producto=producto_item,
                                    cantidad_sistema_antes=stock_sistema_actual,
                                    cantidad_fisica_contada=cantidad_fisica,
                                    usuario_conteo=request.user, # Si aún necesitas el usuario por línea
                                    # Los campos generales ahora están en la cabecera
                                    # fecha_actualizacion_stock=fecha_ajuste, # Ya no va aquí
                                    # motivo_conteo=motivo,                   # Ya no va aquí
                                    # revisado_con=revisado,                 # Ya no va aquí
                                    # notas_generales=notas_gral              # Ya no va aquí
                                )
                                print(f"  -> Detalle Conteo registrado para {producto_item.pk}. Sistema: {stock_sistema_actual}, Físico: {cantidad_fisica}")


                                # --- Crear MovimientoInventario si hay diferencia ---
                                if diferencia_stock != 0:
                                    tipo_movimiento_ajuste = 'ENTRADA_AJUSTE' if diferencia_stock > 0 else 'SALIDA_AJUSTE'
                                    MovimientoInventario.objects.create(
                                        producto=producto_item,
                                        cantidad=diferencia_stock,
                                        tipo_movimiento=tipo_movimiento_ajuste,
                                        usuario=request.user,
                                        documento_referencia=f"Conteo ID {cabecera.pk}", # Referencia a la cabecera
                                        notas=f"Ajuste por conteo. Sistema: {stock_sistema_actual}, Físico: {cantidad_fisica}, Dif: {diferencia_stock}. Motivo: {motivo or 'N/A'}"
                                    )
                                    print(f"  -> Movimiento de ajuste creado para {producto_item.pk}. Diferencia: {diferencia_stock}")
                                    items_procesados_correctamente += 1

                                    # Guardar inconsistencia para el informe
                                    inconsistencias.append({
                                        'referencia': producto_item.referencia,
                                        'nombre': producto_item.nombre,
                                        'color': producto_item.color or '',
                                        'talla': producto_item.talla or '',
                                        'sistema': stock_sistema_actual,
                                        'fisico': cantidad_fisica,
                                        'diferencia': diferencia_stock,
                                        #'producto': producto_item # Pasar objeto para la plantilla PDF si es necesario
                                    })
                                else:
                                    items_con_error_o_sin_cambio += 1
                            except (ValueError, Exception) as e_item:
                                 messages.error(request, f"Error procesando {producto_item}: {e_item}")
                                 items_con_error_o_sin_cambio += 1

                # --- FIN DEL BUCLE Y DE LA TRANSACCIÓN ---

            except Exception as e_global:
                messages.error(request, f"Error general al guardar el conteo: {e_global}")
                print(f"****** VISTA CONTEO: ERROR FATAL EN POST: {e_global} ******")
                # Volver a mostrar el formulario con errores
                items_a_contar = Producto.objects.filter(activo=True).order_by('referencia', 'nombre', 'color', 'talla')
                puede_guardar = request.user.has_perm('inventario.change_producto') or request.user.is_superuser
                # Pasar el formulario con errores, no uno nuevo
                context = {'items_para_conteo': items_a_contar, 'titulo': "Error en Conteo", 'info_form': info_form, 'puede_guardar': puede_guardar}
                return render(request, 'inventario/conteo_inventario.html', context)

            # --- Procesamiento POST exitoso ---
            # Mensajes de éxito/info
            if items_procesados_correctamente > 0 or items_con_error_o_sin_cambio > 0: # Si se procesó algo
                 if items_procesados_correctamente > 0:
                      messages.success(request, f"Conteo ID {cabecera_conteo_guardada} guardado. Stock ajustado para {items_procesados_correctamente} ítem(s).")
                 if items_con_error_o_sin_cambio > 0 and items_procesados_correctamente == 0:
                      messages.info(request, "Se registraron conteos, pero no hubo diferencias para ajustar el stock o no se ingresaron cantidades.")
            else: # No se procesó nada (ej. todos los inputs vacíos)
                 messages.warning(request, "No se ingresaron cantidades para procesar en el conteo.")


            # Guardar datos en sesión para el informe (si hay cabecera)
            if cabecera_conteo_guardada:
                request.session['conteo_inconsistencias'] = inconsistencias
                request.session['conteo_info_general'] = {
                     'cabecera_id': cabecera_conteo_guardada,
                     'fecha_ajuste': fecha_ajuste.strftime('%Y-%m-%d'),
                     'motivo': motivo,
                     'revisado': revisado,
                     'notas': notas_gral,
                     'registrado_por': request.user.username
                }
                print(f"****** VISTA CONTEO POST: Guardando {len(inconsistencias)} inconsistencias en sesión ******")
                print(f"****** VISTA CONTEO POST: Redirigiendo a 'descargar_informe_conteo' con ID {cabecera_conteo_guardada} ******")
                # --- REDIRECCIÓN A LA VISTA DE DESCARGA PDF ---
                return redirect('inventario_api:descargar_informe_conteo', cabecera_id=cabecera_conteo_guardada)
            else:
                 # Si por alguna razón no se creó cabecera (ej. error antes), volver a la vista normal
                 return redirect('inventario_api:vista_conteo_inventario')


        else: # El formulario InfoGeneralConteoForm NO fue válido
            print("  -> Formulario InfoGeneralConteoForm NO es VÁLIDO.")
            print("  -> Errores:", info_form.errors.as_json())
            messages.error(request, "Por favor corrige los errores en la información general del conteo.")
            # Volver a renderizar la misma página mostrando los errores del info_form
            items_a_contar = Producto.objects.filter(activo=True).order_by('referencia', 'nombre', 'color', 'talla')
            puede_guardar = request.user.has_perm('inventario.change_producto') or request.user.is_superuser
            # Pasar el formulario con errores de vuelta a la plantilla
            context = {'items_para_conteo': items_a_contar, 'titulo': "Conteo de Inventario Físico", 'info_form': info_form, 'puede_guardar': puede_guardar}
            return render(request, 'inventario/conteo_inventario.html', context)


    # --- Lógica GET: Mostrar el formulario ---
    else: # request.method == 'GET'
        print("****** VISTA CONTEO: PROCESANDO GET ******")
        items_a_contar = Producto.objects.filter(activo=True).order_by('referencia', 'nombre', 'color', 'talla')
        puede_guardar = request.user.has_perm('inventario.change_producto') or request.user.is_superuser
        info_form = InfoGeneralConteoForm() # Formulario vacío para GET

        # Recuperar resultados de la sesión si venimos de un redirect
        inconsistencias = request.session.pop('conteo_inconsistencias', None)
        info_general_conteo = request.session.pop('conteo_info_general', None)
        print(f"  -> Datos recuperados de sesión -> inconsistencias: {'Sí' if inconsistencias is not None else 'No'}, info_general: {'Sí' if info_general_conteo is not None else 'No'}")

        print(f"  -> Obtenidos {items_a_contar.count()} productos activos para mostrar.")
        print(f"  -> Usuario '{request.user.username}' puede guardar? {puede_guardar}")

        context = {
            'items_para_conteo': items_a_contar,
            'titulo': "Conteo de Inventario Físico",
            'info_form': info_form,
            'puede_guardar': puede_guardar,
            'inconsistencias': inconsistencias, # Pasar inconsistencias (puede ser None)
            'info_general_conteo': info_general_conteo # Pasar info general (puede ser None)
        }
        return render(request, 'inventario/conteo_inventario.html', context)

# --- Vista para Listar Pedidos Pendientes (Ej: Para Bodega) ---
@login_required
@user_passes_test(lambda u: es_bodega(u) or u.is_superuser or es_admin_app(u), login_url='inventario:acceso_denegado') # Revisa URL
def vista_lista_pedidos_bodega(request):
    """Muestra una lista de pedidos para Bodega, permitiendo filtrar por estado (incluido COMPLETADO)."""

    # --- Obtener parámetros de búsqueda (sin cambios) ---
    ref_query = request.GET.get('ref', '').strip()
    cliente_query = request.GET.get('cliente', '').strip()
    estado_query = request.GET.get('estado', '').strip() # Valor seleccionado por el usuario
    ref_producto_query = request.GET.get('ref_producto', '').strip()

    # --- Preparar Prefetch (sin cambios) ---
    prefetch_detalles = Prefetch(
        'detalles',
        queryset=DetallePedido.objects.select_related('producto'),
        to_attr='detalles_precargados'
    )

    # --- Query base SIN filtro de estado inicial ---
    pedidos_list = Pedido.objects.select_related('cliente', 'vendedor__user').prefetch_related(prefetch_detalles)

    # --- Determinar qué estados mostrar ---
    estados_validos = ['PENDIENTE', 'PROCESANDO', 'COMPLETADO', 'ENVIADO', 'ENTREGADO', 'CANCELADO'] # Lista de todos los estados posibles en tu modelo
    estados_por_defecto = ['PENDIENTE', 'PROCESANDO'] # Estados a mostrar si no se filtra

    estados_a_mostrar = []
    if estado_query and estado_query in estados_validos:
        # Si el usuario seleccionó un estado válido, mostrar solo ese
        estados_a_mostrar = [estado_query]
        estado_display = estado_query # Valor por defecto si no se encuentra
        # Buscar en la lista de choices del modelo Pedido
        for valor_interno, nombre_legible in Pedido.ESTADO_PEDIDO_CHOICES:
            if valor_interno == estado_query:
                estado_display = nombre_legible # Encontramos el nombre legible (ej: "Completado")
                break # Salir del bucle una vez encontrado
        titulo = f'Pedidos Bodega ({estado_display})' # Usar el nombre legible encontrado

    elif not estado_query:
         # Si el usuario seleccionó "-- Cualquier Estado --" (valor vacío)
         # Podríamos mostrar todos los estados o los por defecto. Mostremos los por defecto.
         estados_a_mostrar = estados_por_defecto
         titulo = 'Pedidos Pendientes Bodega (Pendiente/Procesando)' # Título por defecto
    # else: Si estado_query tiene un valor inválido, estados_a_mostrar queda vacío y no se mostrará nada.

    # --- Aplicar filtro de ESTADO ---
    if estados_a_mostrar:
         pedidos_list = pedidos_list.filter(estado__in=estados_a_mostrar)
    elif estado_query: # Si se ingresó un estado pero no era válido
        messages.warning(request, f"El estado '{estado_query}' no es válido.")
        pedidos_list = Pedido.objects.none() # No mostrar nada
    # Si estado_query estaba vacío y no definimos estados por defecto (estados_a_mostrar vacío), se mostrarían todos.
    # Pero como definimos estados_por_defecto, siempre habrá filtro de estado.

    # --- Aplicar OTROS filtros (lógica existente) ---
    if ref_query:
        try:
            pedido_id = int(ref_query)
            pedidos_list = pedidos_list.filter(pk=pedido_id)
        except ValueError:
            messages.error(request, f"El ID del pedido '{ref_query}' debe ser un número.")
            pedidos_list = Pedido.objects.none()

    if cliente_query:
        pedidos_list = pedidos_list.filter(cliente__nombre_completo__icontains=cliente_query)

    if ref_producto_query:
        pedidos_list = pedidos_list.filter(
            detalles__producto__referencia__icontains=ref_producto_query
        ).distinct()

    # --- Orden final (sin cambios) ---
    pedidos_list = pedidos_list.order_by('-fecha_hora')

    # --- Contexto (sin cambios, pero asegúrate que el título refleje el filtro) ---
    # Si no se filtró por estado, el título será el por defecto.
    if not estado_query:
         titulo = 'Pedidos Pendientes Bodega (Pendiente/Procesando)'
    elif not estados_a_mostrar and estado_query: # Estado inválido
         titulo = 'Pedidos Bodega (Estado Inválido)'
    # El título ya se ajustó si se eligió un estado válido.

    context = {
        'pedidos_list': pedidos_list,
        'titulo': titulo,
        'ref_query': ref_query,
        'cliente_query': cliente_query,
        'estado_query': estado_query, # Pasar el estado seleccionado para mantenerlo en el <select>
        'ref_producto_query': ref_producto_query,
        # 'ESTADO_CHOICES_DICT': pedido.ESTADO_CHOICES_DICT # Pasar diccionario si lo usas en el título
    }
    return render(request, 'inventario/lista_pedidos_bodega.html', context) # Revisa nombre plantilla

@login_required # Mantener si es necesario
def imprimir_comprobante_devolucion(request, devolucion_id): # Mantenemos el nombre original o cámbialo a generar_devolucion_pdf
    """
    Genera un comprobante de devolución en formato PDF usando WeasyPrint.
    """
    try:
        # 1. Obtener Devolución y Detalles
        devolucion = get_object_or_404(DevolucionCliente, pk=devolucion_id)
        # ¡IMPORTANTE! Ajusta 'detalles_devolucion' al related_name correcto si es diferente
        # Usamos select_related para optimizar (si tienes ForeignKey a Producto, Color, Talla en Detalle)
        detalles = devolucion.detalles.select_related(
            'producto'

        ).all()

        # 2. Calcular Totales (simplificado para devolución)
        total_cantidad_devuelta = detalles.aggregate(total=Sum('cantidad'))['total'] or 0

        # 3. Cargar Logo (usando la misma lógica que en tu vista de pedido)
        logo_b64 = None
        try:
            # ¡AJUSTA RUTA A TU LOGO DENTRO DE LA CARPETA STATIC!
            logo_b64 = image_to_base64('img/logo.jpg')
        except Exception as e:
            print(f"Advertencia PDF Devolución: No se pudo cargar el logo: {e}")

        # 4. Preparar Contexto (¡SIMPLIFICADO!)
        context = {
            'devolucion': devolucion,
            'detalles': detalles, # Pasamos la lista directa de detalles
            'total_cantidad_devuelta': total_cantidad_devuelta,
            'logo_base64': logo_b64,
            'fecha_generacion': timezone.now(), # Opcional
            # Ya no necesitamos pasar 'grupos_*', 'tallas_cols_*', etc.
        }
        print(f"PDF Devolución {devolucion_id}: Contexto preparado.") # Debug

        # 5. Renderizar y generar PDF (¡USANDO LA MISMA LÓGICA WEASYPRINT!)
        #    Asegúrate que esta ruta sea correcta
        template_path = 'inventario/devolucion_comprobante.html'
        template = get_template(template_path)
        html_string = template.render(context)

        response = HttpResponse(content_type='application/pdf')
        # Cambiamos el nombre del archivo sugerido
        filename = f"devolucion_{devolucion_id}_{timezone.now():%Y%m%d}.pdf"
        disposition = 'inline' # O 'attachment' para forzar descarga
        response['Content-Disposition'] = f'{disposition}; filename="{filename}"'

        try:
            # Usamos la misma lógica WeasyPrint que en generar_pedido_pdf
            base_url = request.build_absolute_uri('/')
            pdf_file = HTML(string=html_string, base_url=base_url).write_pdf()
            response.write(pdf_file)
            print(f"PDF generado exitosamente para devolución {devolucion_id}.") # Debug
            return response
        except Exception as e:
            print(f"Error generando PDF con WeasyPrint para Devolución {devolucion_id}: {e}")
            import traceback
            traceback.print_exc()
            # messages.error(request, f"Error inesperado al generar el PDF de la devolución #{devolucion.pk}.") # Descomentar si usas messages
            return HttpResponse(f'Error interno del servidor al generar el PDF.', status=500)

    except Exception as e:
        print(f"Error general en vista PDF devolución {devolucion_id}: {e}")
        return HttpResponse(f"Error inesperado al generar el comprobante.", status=500)


# --- Vista para Verificar Pedido (Ej: Por Bodega) ---
@login_required
@user_passes_test(lambda u: es_bodega(u) or u.is_superuser or es_admin_app(u), login_url='acceso_denegado') # Revisa esta URL
def vista_verificar_pedido(request, pk):
    """Muestra detalles de pedido y procesa la verificación de artículos, generando PDF de despacho si aplica."""
    pedido = get_object_or_404(Pedido, pk=pk)

    # --- Lógica GET ---
    if request.method == 'GET':
        detalles_para_mostrar = pedido.detalles.select_related('producto').all().order_by('producto__referencia', 'producto__color', 'producto__talla')
        context = {
            'pedido': pedido,
            'detalles_pedido': detalles_para_mostrar,
            'titulo': f'Verificar Pedido #{pedido.pk}'
        }
        # Revisa el nombre de tu plantilla HTML del formulario
        return render(request, 'inventario/verificar_pedido.html', context) 

    # --- Lógica POST ---
    elif request.method == 'POST':
        print(f"--- VISTA_VERIFICAR_PEDIDO (POST - Solo Guarda): INICIO para Pedido #{pk} ---")
        print(f"Estado actual del pedido ANTES: '{pedido.estado}'")

        ESTADOS_PERMITIDOS_VERIFICACION = ['APROBADO', 'PENDIENTE', 'PENDIENTE_BODEGA', 'PROCESANDO']
        if pedido.estado not in ESTADOS_PERMITIDOS_VERIFICACION:
            messages.error(request, f"El pedido #{pedido.pk} no se puede modificar en su estado actual ({pedido.get_estado_display()}).")
            return redirect('inventario_api:verificar_pedido', pk=pedido.pk) # Revisa nombre URL

        items_efectivamente_despachados_en_esta_sesion = [] # Para guardar en sesión
        hubo_cambios_generales = False

        try:
            with transaction.atomic():
                print("Dentro de transaction.atomic(). Iniciando bucle for detalles...")
                detalles_a_procesar = pedido.detalles.select_related('producto').all().order_by('pk')

                for detalle in detalles_a_procesar:
                    input_name = f'cantidad_a_despachar_{detalle.id}'
                    cantidad_a_despachar_str = request.POST.get(input_name)
                    print(f"  - Detalle ID {detalle.id} ({detalle.producto}): Leyendo '{input_name}', Valor recibido='{cantidad_a_despachar_str}'")

                    cantidad_ya_despachada = detalle.cantidad_verificada or 0
                    cantidad_a_despachar_ahora_int = 0

                    try:
                        if cantidad_a_despachar_str is not None and cantidad_a_despachar_str.strip().isdigit():
                            cantidad_a_despachar_ahora_int = int(cantidad_a_despachar_str)
                        elif cantidad_a_despachar_str is not None and cantidad_a_despachar_str.strip() != '':
                            raise ValueError(f"Valor no numérico '{cantidad_a_despachar_str}' ingresado.")

                        if cantidad_a_despachar_ahora_int < 0:
                            raise ValueError("Cantidad a despachar no puede ser negativa.")

                        pendiente_total_item = detalle.cantidad - cantidad_ya_despachada
                        if cantidad_a_despachar_ahora_int > pendiente_total_item:
                            error_msg = f"Intenta despachar {cantidad_a_despachar_ahora_int} pero solo quedan {pendiente_total_item} pendientes para {detalle.producto.nombre_completo}"
                            messages.error(request, error_msg)
                            raise transaction.TransactionManagementError(error_msg)

                        # --- Poblar lista para sesión ---
                        if cantidad_a_despachar_ahora_int > 0:
                            items_efectivamente_despachados_en_esta_sesion.append({
                                'producto_referencia': detalle.producto.referencia,
                                'producto_nombre': detalle.producto.nombre,
                                'producto_talla': getattr(detalle.producto, 'talla', '-'),
                                'producto_color': getattr(detalle.producto, 'color', '-'),
                                'cantidad_despachada': cantidad_a_despachar_ahora_int,
                            })
                            print(f"      Guardando para sesión/PDF: {detalle.producto.nombre} - Cantidad: {cantidad_a_despachar_ahora_int}")

                        # --- Actualizar DetallePedido ---
                        nuevo_total_verificado = cantidad_ya_despachada + cantidad_a_despachar_ahora_int
                        if nuevo_total_verificado != cantidad_ya_despachada or \
                           (not detalle.verificado_bodega and cantidad_a_despachar_str is not None and cantidad_a_despachar_str.strip().isdigit()):
                            detalle.cantidad_verificada = nuevo_total_verificado
                            detalle.verificado_bodega = True
                            detalle.save(update_fields=['cantidad_verificada', 'verificado_bodega'])
                            hubo_cambios_generales = True
                            print(f"    Detalle ID {detalle.id} ACTUALIZADO. Nuevo Total Verificado: {detalle.cantidad_verificada}")
                        else:
                            print(f"    Detalle ID {detalle.id} sin cambios necesarios.")

                    except ValueError as e_val_item:
                        error_msg_item = f"Error en ítem {detalle.producto.nombre_completo} ({detalle.producto.referencia}): {e_val_item}"
                        messages.error(request, error_msg_item)
                        raise transaction.TransactionManagementError(error_msg_item)

                # --- FIN DEL BUCLE for detalle ---
                print("Fin del bucle for detalles.")

                # --- GUARDAR ITEMS DESPACHADOS EN SESIÓN ---
                session_key = f'last_despacho_items_{pk}' # Clave única para este pedido
                if items_efectivamente_despachados_en_esta_sesion:
                    request.session[session_key] = items_efectivamente_despachados_en_esta_sesion
                    print(f"Guardados {len(items_efectivamente_despachados_en_esta_sesion)} ítems despachados en sesión (key: {session_key}).")
                    # Opcional: Limpiar datos de sesión antiguos para este pedido si existieran
                elif session_key in request.session:
                     # Si no se despachó nada AHORA, pero había datos de un despacho anterior en sesión, limpiarlos.
                     del request.session[session_key]
                     print(f"Limpiados datos de despacho anteriores de la sesión (key: {session_key}).")
                # --- FIN GUARDAR EN SESIÓN ---


                # --- Lógica para actualizar estado general del Pedido (SOLO si hubo cambios generales) ---
                # (Mantenemos esta lógica aquí para verificar el estado COMPLETADO)
                print(f"DEBUG Estado Pedido: Verificando estado... hubo_cambios_generales = {hubo_cambios_generales}") # DEBUG
                if hubo_cambios_generales:
                    pedido.refresh_from_db()
                    detalles_refrescados = pedido.detalles.all()

                    print("  DEBUG Estado Check: Verificando detalles para 'todas_completas':") # DEBUG
                    for d_debug in detalles_refrescados: print(f"    - Detalle {d_debug.pk}: Pedido={d_debug.cantidad}, Verificado={d_debug.cantidad_verificada or 0}") # DEBUG

                    todas_completas = all((d.cantidad_verificada or 0) >= d.cantidad for d in detalles_refrescados)
                    print(f"DEBUG Estado Pedido: Calculado -> todas_completas = {todas_completas}") # DEBUG

                    nuevo_estado_pedido = pedido.estado

                    if todas_completas:
                        print(f"DEBUG Estado Pedido: 'todas_completas' es True. Estado actual ANTES: {pedido.estado}") # DEBUG
                        if pedido.estado not in ['COMPLETADO', 'ENVIADO', 'ENTREGADO', 'CANCELADO']:
                            nuevo_estado_pedido = 'COMPLETADO'
                            print(f"DEBUG Estado Pedido: Estado cambiará a COMPLETADO.") # DEBUG
                            messages.success(request, f'¡Pedido #{pedido.pk} marcado como COMPLETAMENTE VERIFICADO!') # Mensaje más enfático
                        else:
                            print(f"DEBUG Estado Pedido: No se cambia a COMPLETADO porque el estado actual ({pedido.estado}) ya es final.") # DEBUG
                    else:
                        print(f"DEBUG Estado Pedido: 'todas_completas' es False.") # DEBUG
                        if pedido.estado in ['PENDIENTE', 'APROBADO', 'PENDIENTE_BODEGA']:
                            nuevo_estado_pedido = 'PROCESANDO'
                            print(f"DEBUG Estado Pedido: Estado cambiará a PROCESANDO.") # DEBUG
                            messages.info(request, f'Pedido #{pedido.pk} ahora en estado PROCESANDO.')
                        elif pedido.estado == 'PROCESANDO':
                            print(f"DEBUG Estado Pedido: Estado se mantiene en PROCESANDO.") # DEBUG
                            messages.info(request, f'Verificación actualizada para pedido #{pedido.pk} (sigue en PROCESANDO).')

                    if nuevo_estado_pedido != pedido.estado:
                        print(f"DEBUG Estado Pedido: Guardando nuevo estado '{nuevo_estado_pedido}' en BD...") # DEBUG
                        pedido.estado = nuevo_estado_pedido
                        pedido.save(update_fields=['estado'])
                        print(f"DEBUG Estado Pedido: Estado guardado.") # DEBUG
                    elif hubo_cambios_generales: # Si no hubo cambio de estado pero sí cambios en detalles
                        messages.success(request, f"Verificación guardada para pedido #{pedido.pk}.")

                elif not hubo_cambios_generales: # Si no hubo ningún cambio en los detalles
                     messages.info(request, f'No se detectaron cambios en la verificación para Pedido #{pedido.pk}.')


                # --- SIEMPRE REDIRIGIR AL FINAL DE UN POST EXITOSO ---
                print("Fin bloque 'with transaction.atomic()'. Transacción exitosa. Redirigiendo...")
                return redirect('inventario_api:verificar_pedido', pk=pedido.pk) # Revisa nombre URL

        # --- Manejo de Errores (No cambia) ---
        except transaction.TransactionManagementError as e_trans:
            print(f"TransactionManagementError: {e_trans}. Rollback realizado.")
        except ValueError as e_val:
            print(f"ValueError: {e_val}")
            messages.error(request, str(e_val))
        except Exception as e_global:
            print(f"Error global inesperado (POST): {type(e_global).__name__} - {e_global}")
            import traceback
            traceback.print_exc()
            messages.error(request, f"Error inesperado al procesar la verificación: {e_global}")

        # Si hubo error, renderizar de nuevo el formulario GET (la redirección es más simple)
        print("POST procesado con errores o rollback. Redirigiendo a GET...")
        return redirect('inventario:verificar_pedido', pk=pedido.pk) # Revisa nombre URL

    else: # Método no es GET ni POST
        return HttpResponse("Método no permitido.", status=405)

@login_required
@user_passes_test(lambda u: es_bodega(u) or u.is_superuser or es_admin_app(u), login_url='inventario_api:acceso_denegado') # Revisa permisos y URL
def vista_generar_comprobante_despacho(request, pk):
    """Genera el PDF del último despacho registrado en sesión para un pedido."""
    print(f"--- VISTA_GENERAR_COMPROBANTE_DESPACHO: INICIO GET para Pedido #{pk} ---")
    pedido = get_object_or_404(Pedido, pk=pk)

    # Construir la clave de sesión específica para este pedido
    session_key = f'last_despacho_items_{pk}'
    print(f"Buscando datos en sesión con la clave: {session_key}")

    # Leer los ítems despachados de la sesión
    items_para_pdf = request.session.get(session_key, []) # Obtener la lista o [] si no existe

    # Opcional: Limpiar la sesión después de leerla, para que el enlace genere
    # solo el PDF de la última acción de guardado. Si quieres que el enlace
    # siempre muestre el último PDF generado aunque no se guarde de nuevo, comenta estas líneas.
    # if session_key in request.session:
    #     try:
    #         del request.session[session_key]
    #         request.session.modified = True # Asegurar que el cambio en sesión se guarde
    #         print(f"Datos de sesión limpiados para la clave: {session_key}")
    #     except KeyError:
    #         print(f"No se encontró la clave {session_key} para limpiar (puede que ya se haya limpiado).")


    if not items_para_pdf:
         # Si no hay datos en sesión (ej. se accedió a la URL directamente sin guardar antes)
         messages.warning(request, f"No hay datos del último despacho para generar el comprobante del pedido #{pk}. Guarde primero.")
         # Redirigir de vuelta a la página de verificación podría ser lo más útil
         return redirect('inventario_api:verificar_pedido', pk=pedido.pk) # Revisa nombre URL
         # O mostrar un mensaje de error simple:
         # return HttpResponse(f"No hay datos del último despacho para generar el comprobante del pedido #{pk}.", status=404)

    print(f"Encontrados {len(items_para_pdf)} ítems en sesión para generar el PDF.")
    # Preparar contexto para la plantilla PDF
    context_pdf = {
        'pedido': pedido,
        'items_despachados': items_para_pdf, # La lista guardada en sesión
        'fecha_despacho': timezone.now(), # Fecha/Hora de generación del PDF
        'logo_base64': get_logo_base64_despacho(), # Función del logo
    }

    # Llamar a la función de renderizado WeasyPrint (asegúrate que esté definida)
    return render_pdf_weasyprint(
        request,
        'inventario/comprobante_despacho_pdf.html', # Ruta a tu plantilla PDF
        context_pdf,
        filename_prefix=f"Comprobante_Despacho_Pedido" # Prefijo nombre archivo
    )


def preparar_datos_seccion(items_seccion, tallas_columnas_definidas):
    grupos = {} 
    tallas_presentes_en_seccion = set()
    print(f"Preparando sección con {len(items_seccion)} items y tallas definidas: {tallas_columnas_definidas}") # Debug

    for item in items_seccion:
        try:
            # !!! Sigue verificando que estos nombres de campo sean correctos !!!
            ref = item.producto.referencia
            color = item.producto.color 
            talla_actual = item.producto.talla
            cantidad_actual = item.cantidad

            # Asegurarnos que los valores monetarios sean Decimal
            # Si ya vienen como Decimal del modelo, está bien. 
            # Si pudieran ser None o float, los convertimos.
            precio_unitario_val = item.precio_unitario
            subtotal_linea_val = item.subtotal
            print(f"    ---> Procesando Detalle PK={item.pk}: Ref='{ref}', Color='{color}', Talla='{talla_actual}', Qty={cantidad_actual}")


            precio_unitario = Decimal(str(precio_unitario_val)) if precio_unitario_val is not None else Decimal('0.00')
            subtotal_linea = Decimal(str(subtotal_linea_val)) if subtotal_linea_val is not None else Decimal('0.00')

        except AttributeError as e:
             print(f"Error! Campo no encontrado en 'item.producto'. Verifica 'models.py'. Error: {e}")
             continue 
        except (TypeError, ValueError) as e_conv: # Captura error si no se puede convertir a Decimal
             print(f"Error convirtiendo a Decimal para item {item.pk}. Precio='{precio_unitario_val}', Subtotal='{subtotal_linea_val}'. Error: {e_conv}")
             continue # Saltar este item si hay problemas con los valores

        clave = (ref, color) 

        if clave not in grupos:
            grupos[clave] = {
                'ref': ref, 'color': color, 
                'tallas_cantidades': {}, 'cantidad_total': 0,
                # <<< CAMBIO: Inicializar como Decimal >>>
                'subtotal_total': Decimal('0.00'), 
                'precio_unitario': precio_unitario # Guardar como Decimal
            }

        grupos[clave]['tallas_cantidades'][talla_actual] = grupos[clave]['tallas_cantidades'].get(talla_actual, 0) + cantidad_actual
        grupos[clave]['cantidad_total'] += cantidad_actual

        # <<< CORRECCIÓN: Ahora la suma es Decimal += Decimal >>>
        grupos[clave]['subtotal_total'] += subtotal_linea

        if talla_actual in tallas_columnas_definidas:
             tallas_presentes_en_seccion.add(talla_actual)

    # --- Resto de la función (ordenar tallas y grupos) sin cambios ---
    def ordenar_tallas_llave(talla):
        try: return int(talla)
        except ValueError: return float('inf') 

    tallas_columnas_finales = sorted(list(tallas_presentes_en_seccion), key=ordenar_tallas_llave)
    lista_grupos_ordenada = sorted(grupos.values(), key=lambda g: (g['ref'], g['color']))
    print(f"Sección preparada: {len(lista_grupos_ordenada)} grupos. Columnas de talla a mostrar: {tallas_columnas_finales}") # Debug
    return lista_grupos_ordenada, tallas_columnas_finales

# --- Vista para Generar PDF de Pedido ---
@login_required
def generar_pedido_pdf(request, pk):
    # ... (inicio de la función igual que antes: obtener pedido, user, permisos) ...
    pedido = get_object_or_404(Pedido, pk=pk)
    user = request.user
    # (Tu código de permisos...)
    
    # Obtenemos los detalles originales (los necesitaremos para separar)
    detalles_originales = pedido.detalles.select_related('producto').all() # Usar select_related para eficiencia

    # --- Inicio Bloque 1 (modificado): Separar por Género ---
    items_dama = []
    items_caballero = []
    items_unisex = []
    print(f"PDF Pedido {pk}: Separando {len(detalles_originales)} detalles por género...") # Debug

    for detalle in detalles_originales:
        genero_producto = None 
        try:
            # --- !!! TU ACCIÓN AQUÍ: Elige y AJUSTA la opción correcta para obtener el GÉNERO !!! ---
            # genero_producto = detalle.producto.genero  # Opción 1: Campo directo?
            genero_producto = detalle.producto.get_genero_display() # Opción 2: Campo con choices? (Prueba esta primero si no estás seguro)
            # genero_producto = detalle.producto.categoria.genero # Opción 3: Modelo relacionado?
            # ... (Otras opciones si es necesario) ...

            if genero_producto not in ['Dama', 'Caballero', 'Unisex']:
                print(f"Advertencia PDF: Género '{genero_producto}' no reconocido para REF {detalle.producto.referencia}")
                genero_producto = None 
        except AttributeError as e:
            print(f"Error PDF! No se pudo acceder al género para REF {detalle.producto.referencia}. Verifica 'models.py'. Error: {e}")
            pass 

        if genero_producto == 'Dama': items_dama.append(detalle)
        elif genero_producto == 'Caballero': items_caballero.append(detalle)
        elif genero_producto == 'Unisex': items_unisex.append(detalle)
    
    print(f"PDF Separados: Dama={len(items_dama)}, Caballero={len(items_caballero)}, Unisex={len(items_unisex)}") # Debug
    # --- Fin Bloque 1 ---

    # --- Inicio Bloque 2 (modificado): Definir Tallas para Columnas ---
    tallas_col_dama = ['3', '5', '7', '9', '11', '16', '18', '20', '22'] # Confirma
    tallas_col_caballero = [str(t) for t in range(28, 45, 2)] # 28 a 44

    # !!! TU ACCIÓN AQUÍ: Define la lista para Unisex !!!
    tallas_col_unisex = ['0']  # <<<----- PON AQUÍ LAS TALLAS UNISEX (ej: ['XS', 'S', 'M'])
    print(f"PDF Tallas Definidas: Dama={tallas_col_dama}, Caballero={tallas_col_caballero}, Unisex={tallas_col_unisex}") # Debug
    # --- Fin Bloque 2 ---

    # --- Inicio Bloque 4 (modificado): Procesar Cada Sección usando la función ---
    print("PDF Procesando sección Dama...")
    grupos_dama, cols_dama = preparar_datos_seccion(items_dama, tallas_col_dama)

    print("PDF Procesando sección Caballero...")
    grupos_caballero, cols_caballero = preparar_datos_seccion(items_caballero, tallas_col_caballero)
    
    print(f"PDF Resultado Caballero: {len(grupos_caballero)} grupos encontrados. Columnas: {cols_caballero}")


    print("PDF Procesando sección Unisex...")
    grupos_unisex, cols_unisex = preparar_datos_seccion(items_unisex, tallas_col_unisex)
    # --- Fin Bloque 4 ---

    # --- Preparar el contexto para la plantilla (MODIFICADO) ---
    # ... (código para obtener logo_b64 y tasa_iva_para_mostrar - igual que antes) ...
    try:
        logo_b64 = image_to_base64('img/logo.jpg') # Asegúrate que la ruta 'img/logo.jpg' sea correcta relativa a tu proyecto
    except Exception as e:
        logo_b64 = None
        print(f"Advertencia PDF: No se pudo cargar el logo: {e}")
        
    tasa_iva_para_mostrar = int(pedido.IVA_RATE * 100) if hasattr(pedido, 'IVA_RATE') else 19 # O un valor por defecto

    # !!! TU ACCIÓN AQUÍ: Decide si incluir estas columnas !!!
    incluir_color = True  # ¿Sí o No?
    incluir_vr_unit = True # ¿Sí o No?

    # <<< ESTE es el NUEVO contexto que se envía al HTML >>>
    context = {
        'pedido': pedido,
        # 'detalles_pedido': detalles, # <<< YA NO PASAMOS LA LISTA ORIGINAL
        'logo_base64': logo_b64,
        'fecha_generacion': timezone.now(),
        'tasa_iva_pct': tasa_iva_para_mostrar,
        # --- Nuevos Datos Procesados ---
        'grupos_dama': grupos_dama,
        'tallas_cols_dama': cols_dama,
        'grupos_caballero': grupos_caballero,
        'tallas_cols_caballero': cols_caballero,
        'grupos_unisex': grupos_unisex,
        'tallas_cols_unisex': cols_unisex,
        'incluir_color': incluir_color, 
        'incluir_vr_unit': incluir_vr_unit,
    }
    print("PDF Contexto final preparado.") # Debug

    # --- Renderizar y generar PDF (igual que antes) ---
    template_path = 'inventario/pedido_pdf.html' # <<< Nombre de tu plantilla HTML
    template = get_template(template_path)
    html_string = template.render(context) # <<< Usa el NUEVO contexto

    response = HttpResponse(content_type='application/pdf')
    disposition = 'inline' 
    response['Content-Disposition'] = f'{disposition}; filename="pedido_{pedido.pk}_{timezone.now():%Y%m%d}.pdf"'

    try:
        base_url = request.build_absolute_uri('/')
        pdf_file = HTML(string=html_string, base_url=base_url).write_pdf()
        response.write(pdf_file)
        print(f"PDF generado exitosamente para pedido {pk}.") # Debug
        return response
    except Exception as e:
        print(f"Error generando PDF con WeasyPrint para Pedido {pk}: {e}") 
        import traceback
        traceback.print_exc() # Imprime el error completo en la consola de Django
        messages.error(request, f"Error inesperado al generar el PDF del pedido #{pedido.pk}.")
        # Podrías retornar un HttpResponse con el error HTML para depurar más fácil a veces:
        # return HttpResponse(f"<h1>Error generando PDF</h1><pre>{e}</pre><hr><pre>{html_string}</pre>") 
        return HttpResponse(f'Error interno del servidor al generar el PDF.', status=500)
    
    
@login_required
def descargar_informe_conteo(request, cabecera_id):
    cabecera = get_object_or_404(CabeceraConteo, pk=cabecera_id)

    # Obtener solo los detalles con diferencia para el informe
    detalles_conteo = ConteoInventario.objects.filter(cabecera_conteo=cabecera).select_related('producto')
    inconsistencias = [d for d in detalles_conteo if d.diferencia != 0]

    context = {
        'cabecera': cabecera,
        'inconsistencias': inconsistencias
    }

    # Renderizar la plantilla HTML del PDF
    html_string = render_to_string('inventario/conteo_informe_pdf.html', context)

    try:
        # Crear el PDF usando WeasyPrint
        html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))
        pdf_file = html.write_pdf()

        # Crear la respuesta HTTP con el PDF
        response = HttpResponse(pdf_file, content_type='application/pdf')
        # Indicar al navegador que lo descargue con un nombre de archivo
        response['Content-Disposition'] = f'attachment; filename="informe_conteo_{cabecera.pk}_{cabecera.fecha_conteo.strftime("%Y%m%d")}.pdf"'
        return response

    except Exception as e:
        print(f"Error generando PDF con WeasyPrint para conteo {cabecera.pk}: {e}")
        messages.error(request, f"Error al generar el informe PDF: {e}")
        # Redirigir a la página de conteo si falla la generación del PDF
        # Podrías también redirigir a una página de detalle del conteo si la tuvieras
        return redirect('inventario_api:vista_conteo_inventario')



# -------------------------------------------------------------
# --- ENDPOINTS API DE APOYO PARA FORMULARIO WEB DINÁMICO ---
# -------------------------------------------------------------

# --- API para obtener Colores por Referencia ---
@api_view(['GET'])
@authentication_classes([SessionAuthentication]) # O la que uses
@permission_classes([IsAuthenticated]) # Requiere autenticación para acceder
def get_colores_por_referencia(request, ref):
    """
    Devuelve una lista de colores únicos ({valor, display}) para una referencia dada,
    manejando el caso 'Sin Color' (None o vacío en BD) con el slug NO_COLOR_SLUG.
    """
    # Obtener colores distintos, incluyendo None o '' si existen
    colores_qs = Producto.objects.filter(
        referencia=ref,
        activo=True
    ).values_list('color', flat=True).distinct().order_by('color')

    colores_procesados = set() # Para evitar duplicados si hay '' y None tratados igual
    respuesta = []
    has_no_color = False

    for color in colores_qs:
        if color is None or color == '':
            if not has_no_color: # Añadir solo una vez la opción 'Sin Color'
                has_no_color = True
        elif color not in colores_procesados:
            respuesta.append({'valor': color, 'display': color})
            colores_procesados.add(color)

    # Si se encontró algún producto sin color (None o ''), añadir la opción especial
    if has_no_color:
        respuesta.append({'valor': NO_COLOR_SLUG, 'display': 'Sin Color'})

    # Ordenar alfabéticamente por el texto mostrado (display)
    respuesta.sort(key=lambda x: x['display'])

    return Response(respuesta)


# --- API para obtener Tallas y Precio por Referencia y Color ---
# (Versión conservada: Incluye precio y ordena tallas numéricamente)
@api_view(['GET'])
@authentication_classes([SessionAuthentication]) # O la que uses
@permission_classes([IsAuthenticated]) # Requiere autenticación
def get_tallas_por_ref_color(request, ref, color_slug):
    """
    Devuelve tallas y IDs de variante para ref y color, INCLUYENDO PRECIO y STOCK
    en la estructura correcta para el JS:
    {'precio_venta': P, 'variantes': [{'id': Y, 'talla': T, 'stock_actual': S}, ...]}.
    Ordena las tallas numéricamente.
    """
    # Determinar el valor para filtrar el color en la BD
    color_filtro = None if color_slug == NO_COLOR_SLUG else color_slug

    # Buscar variantes activas que coincidan y tengan talla
    variantes = Producto.objects.filter(
        referencia=ref,
        color=color_filtro,
        activo=True,
        talla__isnull=False
    ) # No ordenamos aún en DB si vamos a reordenar en Python

    # Convertir a lista para poder ordenar y acceder al precio
    variantes_lista = list(variantes)

    if not variantes_lista:
        # Si no hay variantes, devolver estructura vacía esperada por JS
        return Response({"precio_venta": 0, "variantes": []})

    # Función para ordenar tallas: numérico primero, luego texto/infinito
    def sort_key(producto):
        try: return float(producto.talla)
        except (ValueError, TypeError): return float('inf')

    # Ordenar la lista de variantes en Python
    variantes_ordenadas = sorted(variantes_lista, key=sort_key)

    # Tomar el precio de la primera variante encontrada (después de ordenar)
    # Asegúrate que esta lógica sea correcta
    precio_grupo = variantes_ordenadas[0].precio_venta

    # Construir la respuesta final, AÑADIENDO EL STOCK
    respuesta = {
        'precio_venta': precio_grupo,
        'variantes': [
            {
                'id': v.id,
                'talla': v.talla,
                # --- ¡¡CAMBIO PRINCIPAL AQUÍ!! ---
                'stock_actual': v.stock_actual # Asume que tu campo/propiedad se llama stock_actual
                # --- FIN DEL CAMBIO ---
            } for v in variantes_ordenadas
        ]
    }

    return Response(respuesta)

@login_required
# El decorador permite AdminApp y cualquiera que NO sea Bodega
@user_passes_test(lambda u: not es_bodega(u) or es_admin_app(u), login_url='acceso_denegado')
def vista_lista_pedidos_borrador(request):
    """
    Muestra una lista de pedidos en estado 'BORRADOR'.
    - Vendedores ven solo los suyos.
    - Staff/Superuser/AdminApp ven todos.
    Permite buscar por ID de pedido o nombre de cliente.
    """
    user = request.user
    search_query = request.GET.get('q', None)
    queryset = Pedido.objects.none() # Empezar con queryset vacío por seguridad
    titulo = 'Mis Pedidos Borrador' # Título por defecto

    # Determinar qué borradores mostrar según el rol
    # Usamos una variable para simplificar la condición de admin general
    es_admin_general = user.is_staff or user.is_superuser or es_admin_app(user)

    if es_admin_general:
        # Staff/Superuser/AdminApp ven TODOS los borradores
        queryset = Pedido.objects.filter(estado='BORRADOR')
        titulo = 'Todos los Pedidos Borrador'
    elif es_vendedor(user):
        # Es Vendedor (y sabemos que no es admin general), muestra solo los suyos
        try:
            # No necesitamos get() aquí si la relación es OneToOne y se llama 'vendedor'
            # vendedor = Vendedor.objects.get(user=user) # Podríamos usar user.vendedor directamente
            # Usamos filter para ser más seguros si la relación pudiera no existir
            queryset = Pedido.objects.filter(vendedor__user=user, estado='BORRADOR')
            titulo = 'Mis Pedidos Borrador'
        except AttributeError: # O Vendedor.DoesNotExist si user.vendedor falla
             messages.error(request, "Error: Perfil de vendedor no encontrado.")
             queryset = Pedido.objects.none()
    # else: # Otros tipos de usuario ya fueron bloqueados por el decorador @user_passes_test

    # Aplicar filtro de búsqueda si existe
    if search_query:
        queryset = queryset.filter(
            Q(pk__icontains=search_query) |
            Q(cliente__nombre_completo__icontains=search_query)
        ).distinct()

    # Preparar la lista final y el contexto
    # Optimización: Incluir cliente relacionado para evitar N+1 queries en la plantilla
    pedidos_list = queryset.select_related('cliente').order_by('-fecha_hora')

    context = {
        'pedidos_list': pedidos_list,
        'titulo': titulo,
        'search_query': search_query,
    }
    return render(request, 'inventario/lista_pedidos_borrador.html', context)


@login_required
@require_POST # Asegura que esta vista solo acepte solicitudes POST
@user_passes_test(lambda u: not es_bodega(u) or es_admin_app(u), login_url='acceso_denegado')
def vista_eliminar_pedido_borrador(request, pk):
    """
    Elimina un pedido en estado 'BORRADOR' si pertenece al vendedor logueado.
    """
    try:
        # Obtener el vendedor (o verificar si es staff si quieres permitirlo)
        vendedor = Vendedor.objects.get(user=request.user)
        # Buscar el pedido borrador específico de este vendedor
        pedido = get_object_or_404(Pedido, pk=pk, vendedor=vendedor, estado='BORRADOR')

        # Si se encuentra, proceder a eliminar
        pedido_id = pedido.pk # Guardar el ID para el mensaje
        pedido.delete() # Esto también eliminará los Detalles asociados (CASCADE)

        messages.success(request, f"El pedido borrador #{pedido_id} ha sido eliminado exitosamente.")

    except Vendedor.DoesNotExist:
        messages.error(request, "No tienes permiso de vendedor para eliminar borradores.")
    except Pedido.DoesNotExist:
        # Esto no debería pasar con get_object_or_404, pero por si acaso
        messages.error(request, "El pedido borrador que intentas eliminar no existe o no te pertenece.")
    except Exception as e:
        # Capturar otros posibles errores
        messages.error(request, f"Ocurrió un error inesperado al eliminar el borrador: {e}")

    # Siempre redirigir de vuelta a la lista de borradores
    return redirect('lista_pedidos_borrador')
    


@api_view(['GET'])
@permission_classes([IsAuthenticated]) # Asegura que solo usuarios logueados puedan buscar
def buscar_clientes_api(request):
    """
    Busca clientes por nombre o identificación para el widget Select2.
    Espera un parámetro 'term' en la query string.
    """
    term = request.GET.get('term', '').strip()
    results = []

    if len(term) >= 2: # Empezar a buscar después de 2 caracteres (opcional)
        clientes = Cliente.objects.filter(
            Q(nombre_completo__icontains=term) | Q(identificacion__icontains=term)
        ).order_by('nombre_completo')[:20] # Limita a 20 resultados por rendimiento

        results = [
            {
                "id": cliente.pk,
                # Texto que se mostrará en el desplegable de resultados
                "text": f"{cliente.nombre_completo} (NIT/ID: {cliente.identificacion or 'N/A'})"
            }
            for cliente in clientes
        ]
    # Select2 espera un formato específico: un objeto con una clave 'results'
    return Response({"results": results})

def buscar_productos_api(request):
    """
    Busca productos por término (referencia o descripción) y devuelve JSON para Select2.
    """
    term = request.GET.get('term', '').strip()
    resultados_json = {'results': []} # Formato esperado por Select2

    if len(term) >= 2: # Buscar solo si se escriben al menos 2 caracteres
        try:
            # --- AJUSTA ESTA BÚSQUEDA SEGÚN TUS CAMPOS ---
            # Busca por referencia O descripción (ignorando mayúsculas/minúsculas)
            # ¡Cambia 'referencia' y 'descripcion' si tus campos se llaman diferente!
            queryset = Producto.objects.filter(
            Q(referencia__icontains=term) | Q(descripcion__icontains=term)
            )
            # --- FIN AJUSTE BÚSQUEDA ---

            # Limita la cantidad de resultados
            productos_encontrados = queryset[:20] # Muestra máximo 20

            # Formatear para Select2: lista de diccionarios con 'id' y 'text'
            resultados = []
            for prod in productos_encontrados:
                # --- AJUSTA CÓMO SE MUESTRA EL TEXTO ---
                # Define cómo quieres que se vea cada opción en la lista desplegable
                texto_opcion = f"{prod.referencia} - {prod.nombre or ''}"
                if prod.color:
                     texto_opcion += f" / Color: {prod.color}"
                if prod.talla:
                     texto_opcion += f" / Talla: {prod.talla}"
                # --- FIN AJUSTE TEXTO ---

                resultados.append({'id': prod.pk, 'text': texto_opcion})

            resultados_json['results'] = resultados

        except Exception as e:
            print(f"Error en API buscar_productos_api: {e}")
            # Podrías devolver un error JSON si quieres, pero Select2 usualmente solo necesita 'results'

    # Devuelve siempre una respuesta JSON (aunque 'results' esté vacío)
    return JsonResponse(resultados_json)



def buscar_referencias_api(request):
    """
    Vista API para buscar referencias únicas para Select2.
    Espera un parámetro 'term' en la URL (ej: /api/buscar-referencias/?term=BUSQUEDA).
    """
    term = request.GET.get('term', '').strip()
    results = []

    if len(term) >= 1: # O 2, la longitud mínima que quieras para buscar
        # Busca productos cuya referencia contenga el término (ignorando mayúsculas/minúsculas)
        # distinct('referencia') obtiene solo una vez cada referencia encontrada
        # values('referencia') selecciona solo el campo referencia
        referencias_qs = Producto.objects.filter(
            referencia__icontains=term,
            activo=True # Opcional: solo buscar en productos activos
        ).values('referencia').distinct().order_by('referencia')[:20] # Limita a 20 resultados

        # Formatea para Select2: necesita 'id' y 'text'
        for item in referencias_qs:
            referencia_val = item['referencia']
            results.append({
                'id': referencia_val,   # El valor que se enviará (la propia referencia)
                'text': referencia_val # El texto que se mostrará
                # Podrías hacer el 'text' más descriptivo si quieres, ej:
                # 'text': f"{referencia_val} - Alguna descripción"
            })

    # Devuelve la respuesta en formato JSON que Select2 entiende
    return JsonResponse({'results': results})



@login_required
@user_passes_test(lambda u: es_bodega(u) or es_admin_app(u) or es_vendedor(u), login_url='acceso_denegado')
def vista_crear_devolucion(request):
    """
    Maneja la creación de una nueva Devolución de Cliente con sus detalles.
    """
    if request.method == 'POST':
        # Crear instancias del formulario principal y del formset con los datos POST
        form = DevolucionClienteForm(request.POST)
        formset = DetalleDevolucionFormSet(request.POST, prefix='detalles') # Usar prefijo

        # Validar ambos
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic(): # Asegura que todo se guarde o nada
                    # 1. Guardar la cabecera (DevolucionCliente)
                    devolucion_header = form.save(commit=False)
                    devolucion_header.usuario = request.user # Asignar usuario logueado
                    devolucion_header.fecha_hora = timezone.now() # Asignar fecha/hora actual
                    devolucion_header.save() # Guardar cabecera en BD

                    # 2. Guardar los detalles (DetalleDevolucion) asociados a la cabecera
                    # Necesitamos asignar la instancia padre al formset ANTES de guardarlo
                    formset.instance = devolucion_header
                    formset.save() # Guarda todas las líneas de detalle válidas

                    # 3. Actualizar Stock para productos en buen estado
                    print(f"Procesando stock para Devolución #{devolucion_header.pk}...")
                    detalles_guardados = devolucion_header.detalles.all() # Obtener detalles recién guardados
                    for detalle in detalles_guardados:
                        # Verificar si el estado es 'BUENO' (o como lo hayas llamado en el modelo)
                        if detalle.estado_producto == 'BUENO' and detalle.cantidad > 0:
                            MovimientoInventario.objects.create(
                                producto=detalle.producto,
                                cantidad=detalle.cantidad, # Positivo para ENTRADA por devolución
                                tipo_movimiento='ENTRADA_DEVOLUCION', # Asegúrate que este tipo exista en tus CHOICES
                                documento_referencia=f'Devolución #{devolucion_header.pk}',
                                usuario=request.user,
                                notas=f'Entrada por devolución cliente {devolucion_header.cliente} (Estado: Bueno)'
                            )
                            print(f" + Stock actualizado para {detalle.producto}: +{detalle.cantidad}")

                   # messages.success(request, f"Devolución #{devolucion_header.pk} registrada exitosamente.")
                    # Redirigir a una página de éxito, puede ser la misma vista (para nueva devolución)
                    # o una lista de devoluciones (que aún no hemos creado)
                    return redirect('detalle_devolucion', pk=devolucion_header.pk) # Redirige a la misma vista para limpiar

            except Exception as e:
                # Si algo falla dentro de la transacción, se revierte todo
                messages.error(request, f"Error al guardar la devolución: {e}")
                # Se re-renderizará el formulario con errores abajo

        else:
            # Si el form o el formset no son válidos, mostrar errores
            messages.error(request, "Por favor corrige los errores en el formulario.")
            # El form y formset con errores se pasarán al contexto abajo

    else: # Si es solicitud GET (cargar página por primera vez)
        # Crear instancias vacías del formulario y el formset
        form = DevolucionClienteForm()
        formset = DetalleDevolucionFormSet(prefix='detalles') # Usar prefijo también aquí

    # Preparar contexto para la plantilla
    context = {
        'form': form, # Formulario de cabecera
        'formset': formset, # Formulario para los detalles
        'titulo': 'Registrar Devolución de Cliente'
    }
    # Renderizar la plantilla (que crearemos en el siguiente paso)
    return render(request, 'inventario/crear_devolucion.html', context)


@login_required # O los permisos que necesites
def vista_detalle_devolucion(request, pk):
    devolucion = get_object_or_404(DevolucionCliente, pk=pk)
    # Podrías pasar también los detalles si quieres mostrarlos aquí
    # detalles = devolucion.detalles_devolucion.all()
    context = {
        'devolucion': devolucion,
        # 'detalles': detalles
    }
    # Renderizaremos una nueva plantilla para mostrar los detalles
    return render(request, 'inventario/devolucion_detalle.html', context)

@login_required
@user_passes_test(lambda u: es_bodega(u) or u.is_staff or es_admin_app(u), login_url='acceso_denegado')
def vista_registrar_ingreso(request):
    """
    Maneja el registro de un nuevo Ingreso a Bodega con sus detalles.
    """
    if request.method == 'POST':
        form = IngresoBodegaForm(request.POST)
        # Usar un prefijo para el formset es crucial si tienes más de uno en una página,
        # o si quieres evitar colisiones con nombres de campos del form principal.
        formset = DetalleIngresoFormSet(request.POST, prefix='detalles_ingreso')

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    # 1. Guardar cabecera (IngresoBodega)
                    ingreso_header = form.save(commit=False)
                    ingreso_header.usuario = request.user
                    ingreso_header.fecha_hora = timezone.now()
                    ingreso_header.save()

                    # 2. Guardar detalles (DetalleIngresoBodega)
                    formset.instance = ingreso_header
                    formset.save()

                    # 3. Actualizar Stock (AUMENTAR)
                    print(f"Registrando entrada de stock para Ingreso #{ingreso_header.pk}...")
                    detalles_guardados = ingreso_header.detalles.all()
                    for detalle in detalles_guardados:
                        if detalle.cantidad > 0:
                            MovimientoInventario.objects.create(
                                producto=detalle.producto,
                                cantidad=detalle.cantidad, # ¡¡Positivo para ENTRADA!!
                                # Elige el tipo correcto, ej: si es compra, devolución interna, etc.
                                tipo_movimiento='ENTRADA_COMPRA', # O 'ENTRADA_AJUSTE', etc.
                                documento_referencia=f"Ingreso #{ingreso_header.pk} ({ingreso_header.documento_referencia or ''})".strip(),
                                usuario=request.user,
                                notas=f'Entrada por Ingreso a Bodega #{ingreso_header.pk}'
                                # Podrías añadir el costo aquí si quieres registrarlo en el movimiento
                                # costo_unitario = detalle.costo_unitario
                            )
                            print(f" + Stock actualizado para {detalle.producto}: +{detalle.cantidad}")

                    messages.success(request, f"Ingreso a Bodega #{ingreso_header.pk} registrado exitosamente.")
                    # Redirigir a la misma página para un nuevo registro
                    return redirect('registrar_ingreso')

            except Exception as e:
                messages.error(request, f"Error al guardar el ingreso: {e}")
                # Se re-renderizará abajo con errores

        else:
            messages.error(request, "Por favor corrige los errores en el formulario.")

    else: # Solicitud GET
        form = IngresoBodegaForm()
        formset = DetalleIngresoFormSet(prefix='detalles_ingreso')

    context = {
        'form': form,
        'formset': formset,
        'titulo': 'Registrar Nuevo Ingreso a Bodega'
    }
    # Renderizar la plantilla (siguiente paso)
    return render(request, 'inventario/registrar_ingreso.html', context)

@login_required
def vista_pedido_exito(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk) # Obtener el pedido
    whatsapp_url = None
    telefono_cliente_limpio = None

    # Intentar obtener y limpiar el teléfono del cliente
    if pedido.cliente and pedido.cliente.telefono:
        # Eliminar caracteres no numéricos (espacios, +, -)
        telefono_crudo = pedido.cliente.telefono
        telefono_limpio = re.sub(r'\D', '', telefono_crudo)

        # Asumir código de país Colombia (57) si no está presente y el número tiene 10 dígitos
        # Ajusta esta lógica si manejas números internacionales de forma diferente
        if len(telefono_limpio) == 10:
             telefono_cliente_limpio = f"57{telefono_limpio}"
        elif len(telefono_limpio) > 10 and telefono_limpio.startswith('57'): # Ya tiene código de país
             telefono_cliente_limpio = telefono_limpio
        # else: Podrías añadir más lógica para otros formatos

    # Si tenemos un número limpio, crear URL de WhatsApp
    if telefono_cliente_limpio:
        # Crear el mensaje predeterminado (ajusta el texto como quieras)
        mensaje_texto = (
            f"Hola {pedido.cliente.nombre_completo if pedido.cliente else ''}, "
            f"te comparto el pedido #{pedido.pk}. "
            f"Por favor, adjunta el archivo PDF que descargaste para confirmar los detalles. Gracias."
        )
        # Codificar el mensaje para la URL
        mensaje_encoded = quote(mensaje_texto)
        # Crear la URL completa de WhatsApp Click to Chat
        whatsapp_url = f"https://wa.me/{telefono_cliente_limpio}?text={mensaje_encoded}"
        print(f"DEBUG: WhatsApp URL generada: {whatsapp_url}") # Para depuración

    context = {
        'pedido': pedido,
        'whatsapp_url': whatsapp_url, # Pasar la URL al template
        'titulo': f'Pedido #{pedido.pk} Creado'
    }
    return render(request, 'inventario/pedido_exito.html', context)


@login_required
@user_passes_test(lambda u: es_admin_app(u) or (not es_bodega(u) and (u.is_staff or u.is_superuser or es_vendedor(u))), login_url='inventario_api:acceso_denegado') # Revisa URL/permiso
def reporte_ventas_vendedor(request):
    """
    Muestra un informe de ventas (unidades) agrupado por vendedor,
    permitiendo filtrar por rango de fechas.
    """
    user = request.user
    print(f"DEBUG: Usuario actual: {user.username}")
    print(f"DEBUG: user.is_staff = {user.is_staff}")
    print(f"DEBUG: user.is_superuser = {user.is_superuser}")    
    try:
        resultado_es_admin_app = es_admin_app(user)
        print(f"DEBUG: es_admin_app(user) = {resultado_es_admin_app}")
    except NameError:
        resultado_es_admin_app = False # O maneja el error como prefieras
        print("DEBUG: La función es_admin_app no está definida o no es accesible.")

    es_admin_general = user.is_staff or user.is_superuser or resultado_es_admin_app
    print(f"DEBUG: Valor final de es_admin_general = {es_admin_general}")
    ESTADOS_INCLUIDOS = ['COMPLETADO', 'ENVIADO', 'ENTREGADO', 'PENDIENTE', 'PROCESANDO'] # Estados a incluir en el cálculo de unidades
    es_admin_general = user.is_staff or user.is_superuser or es_admin_app(user)

    # --- LEER FILTROS (INCLUYENDO FECHAS) ---
    fecha_desde_str = request.GET.get('fecha_desde', '') # Lee el valor del input 'fecha_desde'
    fecha_hasta_str = request.GET.get('fecha_hasta', '') # Lee el valor del input 'fecha_hasta'
    
    # --- Convertir strings de fecha a objetos date ---
    fecha_desde = None
    fecha_hasta = None
    error_fecha = False # Bandera para saber si hubo error en las fechas
    try:
        if fecha_desde_str:
            fecha_desde = datetime.datetime.strptime(fecha_desde_str, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, "Formato de 'Desde Fecha' inválido. Use AAAA-MM-DD.")
        error_fecha = True
    try:
        if fecha_hasta_str:
            fecha_hasta = datetime.datetime.strptime(fecha_hasta_str, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, "Formato de 'Hasta Fecha' inválido. Use AAAA-MM-DD.")
        error_fecha = True

    # Validar que la fecha desde no sea mayor que la fecha hasta
    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
         messages.error(request, "'Desde Fecha' no puede ser posterior a 'Hasta Fecha'.")
         error_fecha = True

    # --- Queryset base de Vendedores (como lo tenías) ---
    if es_admin_general:
        titulo_base = 'Informe de Unidades por Vendedor (Todos)'
        vendedores_qs = Vendedor.objects.filter(activo=True) 
    else:
        titulo_base = 'Mi Reporte de Unidades Vendidas'
        vendedores_qs = Vendedor.objects.filter(user=user, activo=True) 

    # --- Construir Filtro Q Combinado para los Pedidos ---
    # Empezamos con el filtro de estados
    
    filtro_q_anotacion = Q(pedidos__estado__in=ESTADOS_INCLUIDOS)
    filtro_pedidos_directo = Q() # Inicializar vacío para el total general
    if es_admin_general:
        # Aplicar filtro base de estado para el total general
        if ESTADOS_INCLUIDOS: 
            filtro_pedidos_directo = Q(estado__in=ESTADOS_INCLUIDOS) 
        else:
            # Si ESTADOS_INCLUIDOS pudiera estar vacío, manejarlo aquí
            print("ADVERTENCIA: ESTADOS_INCLUIDOS está vacío. No se aplica filtro de estado a total general.")

    titulo = titulo_base # Título por defecto

    # --- Añadir filtros de FECHA/HORA (usando GTE/LTE con timezone) ---
    if not error_fecha:
        # Convertir fechas a datetimes timezone-aware
        start_dt = None
        end_dt = None
        try:
            if fecha_desde: # fecha_desde es el objeto date del formulario
                # Combinar con la hora mínima y hacerlo timezone-aware
                start_dt = timezone.make_aware(datetime.datetime.combine(fecha_desde, datetime.time.min))
            if fecha_hasta: # fecha_hasta es el objeto date del formulario
                # Combinar con la hora máxima para incluir todo el día y hacerlo timezone-aware
                end_dt = timezone.make_aware(datetime.datetime.combine(fecha_hasta, datetime.time.max))
                
            print(f"DEBUG Fechas: start_dt={start_dt}, end_dt={end_dt}") # Para verificar las fechas/horas

            # Aplicar filtros usando >= (gte) y <= (lte)
            if start_dt and end_dt:
                # Filtros para ANOTACIÓN (con prefijo pedidos__)
                filtro_q_anotacion &= Q(pedidos__fecha_hora__gte=start_dt, pedidos__fecha_hora__lte=end_dt)
                # Filtros para TOTAL GENERAL (sin prefijo)
                if es_admin_general:
                    filtro_pedidos_directo &= Q(fecha_hora__gte=start_dt, fecha_hora__lte=end_dt)
                titulo = f'{titulo_base} ({fecha_desde_str} a {fecha_hasta_str})'
                
            elif start_dt: # Solo fecha desde
                filtro_q_anotacion &= Q(pedidos__fecha_hora__gte=start_dt)
                if es_admin_general:
                    filtro_pedidos_directo &= Q(fecha_hora__gte=start_dt)
                titulo = f'{titulo_base} (Desde: {fecha_desde_str})'
                
            elif end_dt: # Solo fecha hasta
                filtro_q_anotacion &= Q(pedidos__fecha_hora__lte=end_dt)
                if es_admin_general:
                    filtro_pedidos_directo &= Q(fecha_hora__lte=end_dt)
                titulo = f'{titulo_base} (Hasta: {fecha_hasta_str})'
                
        except Exception as e_tz:
            # Capturar error si falla la conversión de fecha/hora (poco probable si error_fecha es False)
            print(f"ERROR al crear datetimes timezone-aware: {e_tz}")
            messages.error(request, "Ocurrió un error procesando las fechas.")
            # Podrías querer redirigir o manejar el error de otra forma

    # Imprimir los filtros finales que se usarán
    print(f"DEBUG VISTA FINAL: filtro_q_anotacion = {filtro_q_anotacion}")

    # --- Calcular report_data (Datos de vendedores individuales) ---
    try:
        # Ejecutar la consulta para obtener los datos por vendedor
        report_data = vendedores_qs.annotate(
            total_unidades=Coalesce(
                Sum('pedidos__detalles__cantidad', filter=filtro_q_anotacion), 
                Value(0) # Usar Value(0) con Coalesce
            )
        ).values( # Seleccionar los campos necesarios
            'user__username', 
            'user__first_name',
            'user__last_name',
            'total_unidades'
        ).order_by('-total_unidades') # Ordenar
        
        print(f"DEBUG VISTA FINAL: report_data count = {report_data.count()}") # Ver cuántos vendedores tienen datos

    except Exception as e_annotate:
        print(f"ERROR al calcular report_data con annotate: {e_annotate}")
        # En caso de error, enviar un queryset vacío a la plantilla
        report_data = Vendedor.objects.none() # O el modelo base de vendedores_qs

    # --- Calcular Total General ---
    total_general_unidades = 0 # Inicializar
    if es_admin_general:
        try:
            print(f"DEBUG VISTA FINAL: filtro_pedidos_directo = {filtro_pedidos_directo}")
            
            # Filtrar todos los pedidos que cumplen las condiciones (estado y fecha/hora)
            pedidos_filtrados_generales = Pedido.objects.filter(filtro_pedidos_directo)
            num_pedidos_total = pedidos_filtrados_generales.count()
            print(f"DEBUG VISTA FINAL: Num pedidos para total general = {num_pedidos_total}")
            
            # Sumar las unidades solo si se encontraron pedidos
            if num_pedidos_total > 0:
                total_general_unidades_data = DetallePedido.objects.filter(pedido__in=pedidos_filtrados_generales).aggregate(
                    total=Coalesce(Sum('cantidad'), Value(0)) 
                )
                total_general_unidades = total_general_unidades_data['total']
                
            print(f"DEBUG VISTA FINAL: total_general_unidades calculado = {total_general_unidades}")
            
        except Exception as e_total:
            print(f"ERROR al calcular total_general_unidades: {e_total}")
            total_general_unidades = 0 # Mantener en 0 si hay error
    else:
        # total_general_unidades permanece en 0 si no es admin
        pass # No es necesario el print aquí a menos que depures el flujo

    # --- Preparar Contexto para la Plantilla ---
    context = {
        'report_data': report_data, # Ahora report_data debería estar definido
        'total_general_unidades': total_general_unidades,
        'titulo': titulo,
        'es_admin_general': es_admin_general,
        'fecha_desde_str': fecha_desde_str, 
        'fecha_hasta_str': fecha_hasta_str, 
    }
    return render(request, 'inventario/reporte_ventas_vendedor.html', context)



@login_required
def vista_index(request):
    """Página de inicio que muestra opciones según el rol del usuario."""
    user = request.user
    opciones_disponibles = []
    titulo_pagina = "Panel Principal" # Título por defecto

    # --- Opciones para Vendedores ---
    if es_vendedor(user) or es_admin_app(user) or user.is_superuser:
        opciones_disponibles.append({
            'titulo': 'Crear Pedido',
            'descripcion': 'Registrar un nuevo pedido para un cliente.',
            'url_nombre': 'inventario_api:crear_pedido', # Revisa namespace y nombre!
            'icono': 'fas fa-plus-circle text-success', # Icono de Font Awesome
            'roles': ['vendedor', 'admin'] # Roles que ven esto
        })
        opciones_disponibles.append({
            'titulo': 'Borradores Guardados',
            'descripcion': 'Aquí encontrarás tus Borradores.',
            'url_nombre': 'inventario_api:lista_pedidos_borrador', # Revisa namespace y nombre!
            'icono': 'fas fa-edit text-warning',
            'roles': ['vendedor', 'admin']
        })
        opciones_disponibles.append({
            'titulo': 'Registrar Devolución',
            'descripcion': 'Crear una devolución.',
            'url_nombre': 'crear_devolucion', # Revisa namespace y nombre!
            'icono': 'fas fa-edit text-warning',
            'roles': ['vendedor', 'admin']
        })
        opciones_disponibles.append({
            'titulo': 'Informe de Ventas',
            'descripcion': 'Aquí encontraras la cantidad de unidades Vendidas.',
            'url_nombre': 'reporte_ventas_vendedor', # Revisa namespace y nombre!
            'icono': 'fas fa-edit text-warning',
            'roles': ['vendedor', 'admin']
        })
        opciones_disponibles.append({
            'titulo': 'Cartera',
            'descripcion': 'En este espacio puedes ver el estado de tu Cartera.',
            'url_nombre': 'inventario_api:reporte_cartera_general', # Revisa namespace y nombre!
            'icono': 'fas fa-undo text-danger',
            'roles': ['vendedor', 'admin'] # ¿O también vendedores? Ajusta roles según necesidad
        })
       
       
    # --- Opciones para Personal de Bodega ---
    if es_bodega(user) or es_admin_app(user) or user.is_superuser:
        opciones_disponibles.append({
            'titulo': 'Pedidos Pendientes',
            'descripcion': 'Ver y gestionar pedidos pendientes para despacho.',
            'url_nombre': 'lista_pedidos_bodega', # Revisa namespace y nombre!
            'icono': 'fas fa-tasks text-info',
            'roles': ['bodega', 'admin']
        })
        opciones_disponibles.append({
            'titulo': 'Conteo Inventario',
            'descripcion': 'Realizar y registrar conteos físicos de inventario.',
            'url_nombre': 'inventario_api:vista_conteo_inventario', # Revisa namespace y nombre!
            'icono': 'fas fa-clipboard-check text-secondary',
            'roles': ['bodega', 'admin']
        })
        opciones_disponibles.append({
            'titulo': 'Registrar Ingreso',
            'descripcion': 'Registrar la entrada de mercancía a la bodega.',
            'url_nombre': 'registrar_ingreso', # Revisa namespace y nombre!
            'icono': 'fas fa-dolly-flatbed text-primary',
            'roles': ['bodega', 'admin']
        })
        

    # --- Opciones Solo para Administradores ---
    if es_admin_app(user) or user.is_superuser:
         opciones_disponibles.append({
            'titulo': 'Admin Django',
            'descripcion': 'Acceder al panel de administración avanzado.',
            'url_nombre': 'admin:index', # URL estándar del admin
            'icono': 'fas fa-cog text-dark',
            'roles': ['admin']
        })



    # --- Filtrar opciones basado en el rol REAL del usuario ---
    opciones_finales = []
    if user.is_superuser or es_admin_app(user):
        titulo_pagina = "Panel de Administración"
        opciones_finales = opciones_disponibles # Admin ve todo
    elif es_bodega(user):
        titulo_pagina = "Panel de Bodega"
        opciones_finales = [op for op in opciones_disponibles if 'bodega' in op['roles']]
    elif es_vendedor(user):
        titulo_pagina = "Panel de Vendedor"
        opciones_finales = [op for op in opciones_disponibles if 'vendedor' in op['roles']]
    # else: Un usuario sin rol específico no vería opciones (o define un caso base)

    # Crear las URLs finales para las opciones filtradas
    for opcion in opciones_finales:
        try:
            # Intentar generar la URL. No pasamos argumentos (pk) aquí.
            opcion['url'] = reverse(opcion['url_nombre']) 
        except Exception as e:
            print(f"Error generando URL para '{opcion['url_nombre']}': {e}")
            opcion['url'] = '#' # URL inválida si falla
            opcion['descripcion'] += " (Error en URL)"
            opcion['deshabilitado'] = True # Marcar para deshabilitar en plantilla

    context = {
        'titulo': titulo_pagina,
        'opciones': opciones_finales,
    }
    # Asegúrate que la ruta a la plantilla sea correcta
    return render(request, 'inventario/index.html', context)

@login_required
@user_passes_test(lambda u: es_vendedor(u) or es_admin_app(u) or u.is_superuser, login_url='inventario_api:acceso_denegado') # Revisa URL/permiso
def reporte_cartera_general(request):
    """Muestra el informe de cartera pendiente, filtrado por vendedor si aplica."""
    user = request.user
    titulo = "Informe General de Cartera"
    queryset_documentos = DocumentoCartera.objects.filter(saldo_actual__gt=Decimal('0.00')).select_related('cliente')

    # Filtrar por vendedor si el usuario NO es admin/staff
    # Asumimos que usamos el campo nombre_vendedor_cartera
    es_admin_general = user.is_staff or user.is_superuser or es_admin_app(user)
    vendedor_actual = None

    if not es_admin_general and es_vendedor(user):
        print("DEBUG Cartera: Usuario es Vendedor y no Admin. Intentando filtrar por CÓDIGO...")
        try:
            vendedor_actual = Vendedor.objects.get(user=user)
            # --- OBTENER CÓDIGO INTERNO DEL VENDEDOR ---
            # Asegúrate que tu modelo Vendedor tenga el campo 'codigo_interno'
            codigo_vendedor_filtro = vendedor_actual.codigo_interno 
            
            if codigo_vendedor_filtro is not None and codigo_vendedor_filtro != '':
                # Convertir a string por si acaso para comparar con CharField
                codigo_vendedor_filtro_str = str(codigo_vendedor_filtro) 
                print(f"DEBUG Cartera: Código interno del vendedor para filtrar = '{codigo_vendedor_filtro_str}'")
                
                # --- APLICAR FILTRO USANDO codigo_vendedor_cartera ---
                queryset_filtrado = queryset_documentos.filter(codigo_vendedor_cartera=codigo_vendedor_filtro_str)
                print(f"DEBUG Cartera: Queryset count DESPUÉS de filtrar por codigo_vendedor_cartera: {queryset_filtrado.count()}") 

                # Comprobación (opcional)
                if queryset_filtrado.count() == 0 and queryset_documentos.count() > 0:
                     print(f"¡ADVERTENCIA! El filtro por código de vendedor '{codigo_vendedor_filtro_str}' no encontró coincidencias.")
                     codigos_en_bd = list(queryset_documentos.values_list('codigo_vendedor_cartera', flat=True).distinct()[:10])
                     print(f"  -> Códigos encontrados en DocumentoCartera.codigo_vendedor_cartera (muestra): {codigos_en_bd}")
                     messages.warning(request, "No se encontraron documentos de cartera para tu código de vendedor.")

                queryset_documentos = queryset_filtrado 
                titulo = f"Mi Cartera Pendiente ({vendedor_actual.user.username})"
            else:
                print("DEBUG Cartera: Error - El perfil de Vendedor no tiene código interno asignado.")
                messages.error(request, "Tu perfil de vendedor no tiene un código interno asignado para filtrar la cartera.")
                queryset_documentos = DocumentoCartera.objects.none()
            
        except Vendedor.DoesNotExist:
            messages.error(request, "No se encontró tu perfil de vendedor.")
            queryset_documentos = DocumentoCartera.objects.none() # No mostrar nada si no hay perfil

    # --- Aplicar Filtros Adicionales (Ejemplo) ---
    # Puedes añadir filtros como en la lista de pedidos de bodega si lo deseas
    cliente_filtro = request.GET.get('cliente', '').strip()
    vencido_filtro = request.GET.get('vencido', '') # ej: ?vencido=1

    if cliente_filtro:
        queryset_documentos = queryset_documentos.filter(
            Q(cliente__nombre_completo__icontains=cliente_filtro) | 
            Q(cliente__identificacion__icontains=cliente_filtro)
        )

    hoy = timezone.now().date()
    if vencido_filtro == '1':
        queryset_documentos = queryset_documentos.filter(fecha_vencimiento__lt=hoy)
    elif vencido_filtro == '0':
         queryset_documentos = queryset_documentos.filter(Q(fecha_vencimiento__gte=hoy) | Q(fecha_vencimiento__isnull=True))


    # --- Calcular Totales ---
    total_general_saldo = queryset_documentos.aggregate(total=Sum('saldo_actual'))['total'] or Decimal('0.00')
    total_general_vencido = queryset_documentos.filter(fecha_vencimiento__lt=hoy).aggregate(total=Sum('saldo_actual'))['total'] or Decimal('0.00')
    
    # --- Agrupar por Cliente para la plantilla ---
    # Obtenemos todos los documentos filtrados y ordenados
    documentos_ordenados = list(queryset_documentos.order_by('cliente__nombre_completo', 'fecha_vencimiento'))
    
    # Puedes pasar esta lista directamente a la plantilla y agrupar allí con {% regroup %}
    # O pre-agrupar aquí en un diccionario si prefieres
    
    context = {
        'titulo': titulo,
        'documentos_list': documentos_ordenados, # Pasar la lista ordenada
        'total_general_saldo_fmt': '{:,.2f}'.format(total_general_saldo).replace(',', 'TEMP').replace('.', ',').replace('TEMP', '.'),
        'total_general_vencido_fmt': '{:,.2f}'.format(total_general_vencido).replace(',', 'TEMP').replace('.', ',').replace('TEMP', '.'),
        'total_documentos': len(documentos_ordenados),
        'es_admin_general': es_admin_general, # Para mostrar/ocultar cosas en plantilla
        # Pasar filtros actuales para mantenerlos en el formulario de búsqueda
        'cliente_filtro': cliente_filtro,
        'vencido_filtro': vencido_filtro,
    }
    
    return render(request, 'inventario/reporte_cartera.html', context) # Revisa nombre plantilla

@login_required # Asegura que solo usuarios logueados vean esta página
def acceso_denegado_view(request):
    """Muestra la página estándar de acceso denegado."""
    # El mensaje de error específico se añade en la vista que redirige aquí.
    # Esta vista solo muestra la plantilla.
    return render(request, 'inventario/acceso_denegado.html')


class CustomLoginView(LoginView):
    template_name = 'registration/login.html' # Asegúrate que esta ruta sea correcta!
    def get_success_url(self):
        """Redirige al usuario basado en su rol (grupo o staff status) después de un inicio de sesión exitoso."""
        user = self.request.user
        print(f"DEBUG get_success_url: Verificando usuario {user.username}") # Debug

        # 1. ¿Es Admin o Staff?
        if user.is_staff or user.is_superuser:
            print("DEBUG get_success_url: Es staff/superuser -> admin:index") # Debug
            return reverse_lazy('inventario_api:index')
        
        if es_admin_app(user):
            print("DEBUG get_success_url: Es Admin App -> ¿A dónde? Ej: crear_pedido_web")
             # Decide a dónde redirigirlo, ej: 'crear_pedido_web' o 'lista_pedidos_bodega' o un dashboard nuevo
            return reverse_lazy('inventario_api:index') # O la URL que prefieras para él

        # 2. ¿Pertenece al grupo 'Personal de Bodega'?
        if es_bodega(user): # Usa la función auxiliar
            print("DEBUG get_success_url: Es Bodega -> lista_pedidos_bodega") # Debug
            return reverse_lazy('inventario_api:index') # <-- ¡URL para Bodega!

        # 3. ¿Pertenece al grupo 'Vendedores'?
        if es_vendedor(user): # Usa la función auxiliar
            print("DEBUG get_success_url: Es Vendedor -> crear_pedido_web") # Debug
            return reverse_lazy('inventario_api:index') # <-- ¡URL para Vendedor!

        # 4. Fallback: Si no es ninguno de los anteriores
        print(f"DEBUG get_success_url: Fallback -> {settings.LOGIN_REDIRECT_URL}") # Debug
        # Usamos LOGIN_REDIRECT_URL de settings como fallback seguro
        return settings.LOGIN_REDIRECT_URL # Por defecto '/' si no está definido



# --- FIN ---