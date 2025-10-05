# cartera/views.py
import pandas as pd
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum, Q
from decimal import Decimal, InvalidOperation
from datetime import datetime

from clientes.models import Cliente # De la app clientes
from core.auth_utils import es_administracion, es_vendedor, es_cartera, es_administracion
from vendedores.models import Vendedor # De la app vendedores
from .models import DocumentoCartera
from .forms import UploadCarteraFileForm
from core.mixins import TenantAwareMixin

def convertir_fecha_excel(valor_excel, num_fila=None, nombre_campo_para_error="Fecha"):
    if pd.isna(valor_excel) or valor_excel == '':
        return None
    try:
        valor_str = str(valor_excel).strip()
        if '.' in valor_str: # Manejar números flotantes de Excel para fechas
            valor_str = valor_str.split('.')[0]

        if len(valor_str) == 8 and valor_str.isdigit(): # Formato YYYYMMDD
            return datetime.strptime(valor_str, '%Y%m%d').date()
        # Podrías añadir más formatos aquí si es necesario
        # Ejemplo: elif '-' in valor_str: return datetime.strptime(valor_str, '%Y-%m-%d').date()
        else:
            # Intentar convertir desde número de serie de Excel si es un número
            if valor_str.isdigit():
                try:
                    # El origen de fecha de Excel es 30/12/1899 para compatibilidad con Lotus
                    # Python datetime usa 01/01/1900. Hay que ajustar por 2 días si el número es > 59
                    # (Excel tiene un bug donde considera 1900 como bisiesto)
                    fecha_dt = pd.to_datetime('1899-12-30') + pd.to_timedelta(int(valor_str), unit='D')
                    return fecha_dt.date()
                except ValueError:
                    pass # Continuar con el manejo de error si no es un número de serie válido
            print(f"Advertencia Fila {num_fila or '?'}: {nombre_campo_para_error} '{valor_excel}' no tiene formato YYYYMMDD esperado u otro formato reconocido. Se omite.")
            return None
    except (ValueError, TypeError) as e:
        print(f"Advertencia Fila {num_fila or '?'}: Error convirtiendo {nombre_campo_para_error} '{valor_excel}'. Error: {e}. Se omite.")
        return None

def convertir_saldo_excel(valor_excel, num_fila=None, nombre_campo_para_error="Saldo"):
    if pd.isna(valor_excel) or valor_excel == '':
       return Decimal('0.00')
    try:
        valor_str = str(valor_excel).strip()
        # Lógica para manejar comas como separadores decimales y puntos como miles o viceversa
        # Esta es una implementación simple, podrías necesitar algo más robusto
        # dependiendo de la consistencia de tus archivos Excel.
        valor_limpio = valor_str.replace('.', '').replace(',', '.') # Asume , como decimal si hay . de miles
        if valor_str.count(',') == 1 and valor_str.count('.') == 0: # Solo coma, es decimal
             valor_limpio = valor_str.replace(',', '.')
        
        return Decimal(valor_limpio)
    except (ValueError, TypeError, InvalidOperation) as e:
        print(f"Advertencia Fila {num_fila or '?'}: Error convirtiendo {nombre_campo_para_error} '{valor_excel}'. Error: {e}. Se usará 0.00.")
        return Decimal('0.00')

# --- Vistas de Cartera ---

@login_required
def api_cartera_cliente(request, cliente_id):
    """Devuelve la información de cartera pendiente para un cliente."""
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        # Si no hay un inquilino, devolvemos un error. Es crucial para una API.
        return JsonResponse({'error': 'Empresa no identificada. Acceso denegado.'}, status=403)
    
    cliente = get_object_or_404(Cliente, pk=cliente_id, empresa=empresa_actual) 
    
    documentos_pendientes = DocumentoCartera.objects.filter(
        cliente=cliente, 
        saldo_actual__gt=Decimal('0.00')
    ).order_by('fecha_vencimiento')

    total_deuda = documentos_pendientes.aggregate(total=Sum('saldo_actual'))['total'] or Decimal('0.00')
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
            'saldo': '{:,.2f}'.format(doc.saldo_actual).replace(',', 'TEMP').replace('.', ',').replace('TEMP', '.'), 
            'dias_mora': dias_mora_doc,
            'esta_vencido': doc.esta_vencido,
            'vendedor': doc.nombre_vendedor_cartera or '-',
        })

    respuesta = {
        'cliente_id': cliente.pk,
        'cliente_nombre': cliente.nombre_completo,
        'documentos': documentos_data,
        'total_documentos': documentos_pendientes.count(),
        'saldo_total': '{:,.2f}'.format(total_deuda).replace(',', 'TEMP').replace('.', ',').replace('TEMP', '.'),
        'saldo_vencido': '{:,.2f}'.format(total_vencido).replace(',', 'TEMP').replace('.', ',').replace('TEMP', '.'),
        'max_dias_mora': max_dias_mora,
        'tiene_deuda_vencida': total_vencido > 0,
    }
    return JsonResponse(respuesta)


@login_required
@user_passes_test(lambda u: u.is_staff or es_administracion(u) or es_cartera(u) or u.is_staff, login_url='core:acceso_denegado')
def vista_importar_cartera(request):
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')

    if request.method == 'POST':
        form = UploadCarteraFileForm(request.POST, request.FILES, empresa=empresa_actual)
        if form.is_valid():
            archivo_excel = request.FILES['archivo_excel']
            perfil_seleccionado = form.cleaned_data['perfil_importacion']
            tipo_documento_seleccionado = form.cleaned_data['tipo_documento']

            try:
                df = pd.read_excel(archivo_excel, header=perfil_seleccionado.fila_inicio_header - 1, dtype=str)
                df.dropna(subset=[perfil_seleccionado.columna_id_cliente, perfil_seleccionado.columna_numero_documento], inplace=True)

                documentos_para_crear = []
                clientes_no_encontrados = set()
                condiciones_para_borrar = []

                # --- LÓGICA DE REEMPLAZO INTELIGENTE ---
                # 1. Preparamos los datos y las condiciones para el borrado
                for index, row in df.iterrows():
                    num_fila_excel = index + perfil_seleccionado.fila_inicio_header + 1
                    
                    codigo_cliente_excel = str(row.get(perfil_seleccionado.columna_id_cliente, '')).strip()
                    if codigo_cliente_excel.endswith('.0'):
                        codigo_cliente_excel = codigo_cliente_excel[:-2]

                    if not codigo_cliente_excel:
                        continue

                    cliente_obj = Cliente.objects.filter(identificacion__startswith=codigo_cliente_excel, empresa=empresa_actual).first()

                    if not cliente_obj:
                        clientes_no_encontrados.add(codigo_cliente_excel)
                        continue

                    numero_doc_excel = str(row.get(perfil_seleccionado.columna_numero_documento, '')).strip()
                    
                    # Agregamos la condición para el borrado masivo
                    condiciones_para_borrar.append(
                        Q(cliente=cliente_obj, numero_documento=numero_doc_excel)
                    )

                    # Preparamos el objeto para la creación masiva
                    fecha_doc_excel = convertir_fecha_excel(row.get(perfil_seleccionado.columna_fecha_documento), num_fila_excel)
                    fecha_ven_excel = convertir_fecha_excel(row.get(perfil_seleccionado.columna_fecha_vencimiento), num_fila_excel)
                    saldo_excel = convertir_saldo_excel(row.get(perfil_seleccionado.columna_saldo), num_fila_excel)
                    nombre_vend_excel = str(row.get(perfil_seleccionado.columna_nombre_vendedor, '')).strip() or None
                    codigo_vend_excel = str(row.get(perfil_seleccionado.columna_codigo_vendedor, '')).strip() or None
                    if codigo_vend_excel and '.' in codigo_vend_excel:
                        codigo_vend_excel = codigo_vend_excel.split('.')[0]

                    documentos_para_crear.append(DocumentoCartera(
                        empresa=empresa_actual,
                        cliente=cliente_obj,
                        tipo_documento=tipo_documento_seleccionado,
                        numero_documento=numero_doc_excel,
                        fecha_documento=fecha_doc_excel,
                        fecha_vencimiento=fecha_ven_excel,
                        saldo_actual=saldo_excel,
                        nombre_vendedor_cartera=nombre_vend_excel,
                        codigo_vendedor_cartera=codigo_vend_excel,
                    ))

                with transaction.atomic():
                    # 2. Borramos de forma masiva todos los documentos que vamos a reemplazar
                    if condiciones_para_borrar:
                        from functools import reduce
                        import operator
                        query_final_borrado = reduce(operator.or_, condiciones_para_borrar)
                        
                        documentos_a_borrar = DocumentoCartera.objects.filter(
                            empresa=empresa_actual,
                            tipo_documento=tipo_documento_seleccionado
                        ).filter(query_final_borrado)
                        
                        count_borrados = documentos_a_borrar.count()
                        documentos_a_borrar.delete()
                    
                    # 3. Creamos de forma masiva todos los nuevos documentos
                    DocumentoCartera.objects.bulk_create(documentos_para_crear)

                messages.success(request, f"Importación finalizada. Se procesaron {len(documentos_para_crear)} documentos.")
                if 'count_borrados' in locals() and count_borrados > 0:
                    messages.info(request, f"Se actualizaron {count_borrados} documentos existentes con la nueva información del archivo.")
                if clientes_no_encontrados:
                    messages.warning(request, f"No se encontraron clientes para {len(clientes_no_encontrados)} IDs: {', '.join(sorted(list(clientes_no_encontrados)))}")

            except Exception as e:
                messages.error(request, f"Error crítico al procesar el archivo: {e}")

            return redirect('cartera:importar_cartera')
        else:
            messages.error(request, "Error en el formulario. Por favor, completa los campos requeridos.")
    
    else:
        form = UploadCarteraFileForm(empresa=empresa_actual)

    context = {
        'form': form,
        'titulo': f'Importar Cartera ({empresa_actual.nombre})',
        'app_name': 'Cartera'
    }
    return render(request, 'cartera/importacion/upload_cartera.html', context)

@login_required
@user_passes_test(lambda u: es_vendedor(u) or es_administracion(u) or es_cartera(u) or u.is_superuser, login_url='core:acceso_denegado')
def reporte_cartera_general(request):
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')
    
    user = request.user
    titulo_original = f"Informe General de Cartera ({empresa_actual.nombre})"
    titulo_dinamico = titulo_original # Título que puede cambiar
    
    queryset_documentos = DocumentoCartera.objects.filter(
        empresa=empresa_actual, 
        saldo_actual__gt=Decimal('0.00')
    ).select_related('cliente')

    # Determinar si el usuario es un tipo de administrador general o de cartera que puede filtrar
    # es_administracion = user.is_staff or user.is_superuser or es_administracion(user)
    # O usa la condición del decorador (excluyendo es_vendedor para el dropdown)
    puede_filtrar_por_vendedor_dropdown = es_administracion(user) or es_cartera(user) or user.is_superuser

    codigo_vendedor_para_filtrar = None
    vendedor_seleccionado_id_get = request.GET.get('vendedor_filtro_id') # Nuevo parámetro GET

    if not puede_filtrar_por_vendedor_dropdown and es_vendedor(user):
        # Si es un vendedor (y no admin/cartera con capacidad de elegir), filtra por su propio código
        try:
            vendedor_actual = Vendedor.objects.get(user=user, user__empresa=empresa_actual)
            if vendedor_actual.codigo_interno:
                codigo_vendedor_para_filtrar = str(vendedor_actual.codigo_interno)
                titulo_dinamico = f"Cartera de: {vendedor_actual.user.get_full_name() or vendedor_actual.user.username}"
            else:
                messages.error(request, "Tu perfil de vendedor no tiene un código interno asignado.")
                queryset_documentos = DocumentoCartera.objects.none()
        except Vendedor.DoesNotExist:
            messages.error(request, "No se encontró tu perfil de vendedor asociado.")
            queryset_documentos = DocumentoCartera.objects.none()
            
    elif puede_filtrar_por_vendedor_dropdown and vendedor_seleccionado_id_get:
        # Si es admin/cartera Y ha seleccionado un vendedor del dropdown
        try:
            vendedor_obj_seleccionado = Vendedor.objects.get(
                pk=int(vendedor_seleccionado_id_get),
                user__empresa=empresa_actual
            ) 
            if vendedor_obj_seleccionado.codigo_interno:
                codigo_vendedor_para_filtrar = str(vendedor_obj_seleccionado.codigo_interno)
                titulo_dinamico = f"Cartera de Vendedor: {vendedor_obj_seleccionado.user.get_full_name() or vendedor_obj_seleccionado.user.username}"
            else:
                messages.warning(request, f"El vendedor '{vendedor_obj_seleccionado.user.username}' no tiene código interno para filtrar.")
                # Decide si mostrar todo o nada. Por ahora, no se aplica filtro de vendedor.
        except (ValueError, Vendedor.DoesNotExist):
            messages.error(request, "El vendedor seleccionado en el filtro no es válido.")
            # Podrías no aplicar filtro o mostrar queryset vacío
            # queryset_documentos = DocumentoCartera.objects.none() 
    
    # Aplicar el filtro de vendedor si se determinó un código
    if codigo_vendedor_para_filtrar:
        queryset_documentos = queryset_documentos.filter(codigo_vendedor_cartera=codigo_vendedor_para_filtrar)
    elif puede_filtrar_por_vendedor_dropdown and not vendedor_seleccionado_id_get:
        titulo_dinamico = f"Informe General de Cartera ({empresa_actual.nombre}) - Todos los Vendedores"


    # --- Tus filtros existentes por cliente y estado de vencimiento ---
    cliente_filtro = request.GET.get('cliente', '').strip()
    vencido_filtro = request.GET.get('vencido', '') # '1' para vencido, '0' para no vencido, '' para todos

    if cliente_filtro:
        queryset_documentos = queryset_documentos.filter(
            Q(cliente__nombre_completo__icontains=cliente_filtro) | 
            Q(cliente__identificacion__icontains=cliente_filtro)
        )

    hoy = timezone.now().date()
    if vencido_filtro == '1': # Vencido
        queryset_documentos = queryset_documentos.filter(fecha_vencimiento__lt=hoy, fecha_vencimiento__isnull=False)
    elif vencido_filtro == '0': # No vencido (o con fecha futura o sin fecha)
        queryset_documentos = queryset_documentos.filter(Q(fecha_vencimiento__gte=hoy) | Q(fecha_vencimiento__isnull=True))
    # Si vencido_filtro está vacío, no se aplica filtro por vencimiento.

    # --- Cálculos de totales (sin cambios) ---
    total_general_saldo = queryset_documentos.aggregate(total=Sum('saldo_actual'))['total'] or Decimal('0.00')
    # Para total_general_vencido, filtramos de nuevo sobre el queryset ya filtrado por vendedor/cliente si aplica
    total_general_vencido = queryset_documentos.filter(fecha_vencimiento__lt=hoy, fecha_vencimiento__isnull=False).aggregate(total=Sum('saldo_actual'))['total'] or Decimal('0.00')
    
    documentos_ordenados = list(queryset_documentos.order_by('cliente__nombre_completo', 'fecha_vencimiento'))
    
    # --- Lista de vendedores para el dropdown (solo para admin/cartera) ---
    vendedores_para_dropdown = None
    if puede_filtrar_por_vendedor_dropdown:
        vendedores_para_dropdown = Vendedor.objects.filter(            
            user__empresa=empresa_actual,
            activo=True
            ).select_related('user').order_by('user__first_name', 'user__last_name')

    context = {
        'titulo': titulo_dinamico,
        'documentos_list': documentos_ordenados,
        'total_general_saldo_fmt': '{:0,.2f}'.format(total_general_saldo).replace(',', 'TEMP').replace('.', ',').replace('TEMP', '.'),
        'total_general_vencido_fmt': '{:0,.2f}'.format(total_general_vencido).replace(',', 'TEMP').replace('.', ',').replace('TEMP', '.'),
        'total_documentos': len(documentos_ordenados),
        'puede_filtrar_por_vendedor_dropdown': puede_filtrar_por_vendedor_dropdown, # Para la plantilla
        'vendedores_list_filtro': vendedores_para_dropdown, # Lista para el dropdown
        'vendedor_id_seleccionado_filtro': vendedor_seleccionado_id_get, # Para mantener el valor en el dropdown
        'cliente_filtro': cliente_filtro,
        'vencido_filtro': vencido_filtro,
        'app_name': 'Cartera' # Asumo que esta vista está en la app 'cartera'
    }
    return render(request, 'cartera/reporte_cartera.html', context)