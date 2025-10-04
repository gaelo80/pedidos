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
        
        elif '/' in valor_str and len(valor_str) == 10:
            return datetime.strptime(valor_str, '%d/%m/%Y').date()
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
            # --- CAMBIO CLAVE: OBTENEMOS EL TIPO DE DOCUMENTO DEL FORMULARIO ---
            tipo_documento_seleccionado = form.cleaned_data['tipo_documento']

            filas_leidas = 0
            filas_procesadas_ok = 0
            nuevos_registros_creados = 0
            filas_saltadas_concepto = 0
            clientes_no_encontrados = set()
            errores_fila_detalle = []

            try:
                df = pd.read_excel(archivo_excel, header=perfil_seleccionado.fila_inicio_header - 1, dtype=str)
                filas_leidas = len(df)
                
                with transaction.atomic():
                    # --- CAMBIO CRÍTICO: BORRAMOS SOLO LOS DOCUMENTOS DEL TIPO SELECCIONADO ---
                    DocumentoCartera.objects.filter(
                        empresa=empresa_actual,
                        tipo_documento=tipo_documento_seleccionado # <-- El filtro clave
                    ).delete()

                    for index, row in df.iterrows():
                        num_fila_excel = index + perfil_seleccionado.fila_inicio_header + 1 # Cálculo más robusto

                        try:
                            # (La lógica de extracción de datos de la fila no cambia...)
                            concepto = str(row.get('CONCEPTO', '')).strip()
                            if concepto not in ['52', '89']: 
                                filas_saltadas_concepto += 1
                                continue
                            
                            codigo_cliente_excel = str(row.get(perfil_seleccionado.columna_id_cliente, '')).strip()
                            numero_doc_excel = str(row.get(perfil_seleccionado.columna_numero_documento, '')).strip()

                            if not codigo_cliente_excel or not numero_doc_excel:
                                msg_error = f"Fila {num_fila_excel}: Falta Código de Cliente o Número de Documento."
                                errores_fila_detalle.append(msg_error)
                                continue
                            
                            # 1. Limpiamos el formato del número (elimina el ".0" si existe)
                            if codigo_cliente_excel.endswith('.0'):
                                codigo_cliente_excel = codigo_cliente_excel[:-2]
                            
                            # Validamos que el código no esté vacío después de limpiar
                            if not codigo_cliente_excel:
                                msg_error = f"Fila {num_fila_excel}: Falta Código de Cliente."
                                errores_fila_detalle.append(msg_error)
                                continue

                            # 2. Buscamos al cliente usando 'startswith' para ignorar el dígito de verificación
                            try:
                                cliente_obj = Cliente.objects.get(
                                    identificacion__startswith=codigo_cliente_excel,
                                    empresa=empresa_actual
                                )
                            except Cliente.DoesNotExist:
                                clientes_no_encontrados.add(codigo_cliente_excel)
                                continue
                            except Cliente.MultipleObjectsReturned:
                                # Esto previene un error si hay IDs duplicados (ej: 800123 y 800123-4)
                                print(f"ADVERTENCIA: Se encontraron múltiples clientes que comienzan con el ID '{codigo_cliente_excel}'. Se omite la fila {num_fila_excel}.")
                                clientes_no_encontrados.add(f"{codigo_cliente_excel} (Duplicado)")
                                continue

                            fecha_doc_excel = convertir_fecha_excel(row.get(perfil_seleccionado.columna_fecha_documento), num_fila_excel)
                            fecha_ven_excel = convertir_fecha_excel(row.get(perfil_seleccionado.columna_fecha_vencimiento), num_fila_excel)
                            saldo_excel = convertir_saldo_excel(row.get(perfil_seleccionado.columna_saldo), num_fila_excel)
                            nombre_vend_excel = str(row.get(perfil_seleccionado.columna_nombre_vendedor, '')).strip() or None
                            codigo_vend_excel = str(row.get(perfil_seleccionado.columna_codigo_vendedor, '')).strip() or None
                            if codigo_vend_excel and '.' in codigo_vend_excel:
                                codigo_vend_excel = codigo_vend_excel.split('.')[0]

                            # --- CAMBIO CLAVE: USAMOS EL TIPO DE DOCUMENTO SELECCIONADO AL CREAR ---
                            DocumentoCartera.objects.create(
                                empresa=empresa_actual,
                                cliente=cliente_obj,
                                tipo_documento=tipo_documento_seleccionado, # <-- Asignación clave
                                numero_documento=numero_doc_excel,
                                fecha_documento=fecha_doc_excel,
                                fecha_vencimiento=fecha_ven_excel,
                                saldo_actual=saldo_excel,
                                nombre_vendedor_cartera=nombre_vend_excel,
                                codigo_vendedor_cartera=codigo_vend_excel,
                            )
                            nuevos_registros_creados += 1
                            filas_procesadas_ok +=1

                        except Exception as e_row:
                            msg_error_fila = f"Fila Excel {num_fila_excel}: {e_row}"
                            errores_fila_detalle.append(msg_error_fila)
                            print(f"ERROR EN FILA (EXCEPCIÓN): {msg_error_fila}")
                            import traceback
                            traceback.print_exc(limit=1)

                # Obtenemos el nombre legible para el mensaje de éxito
                nombre_tipo_doc = dict(DocumentoCartera.TIPO_DOCUMENTO_CHOICES).get(tipo_documento_seleccionado)
                messages.success(request, f"Importación para '{nombre_tipo_doc}' finalizada desde el archivo '{archivo_excel.name}'.")
                messages.info(request, f"Resumen: {filas_procesadas_ok} de {filas_leidas} filas del Excel procesadas y creadas exitosamente.")
                
                if filas_saltadas_concepto > 0:
                    messages.info(request, f"{filas_saltadas_concepto} filas fueron ignoradas por concepto no válido.")
                if clientes_no_encontrados:
                    messages.warning(request, f"{len(clientes_no_encontrados)} códigos de cliente no encontrados: {', '.join(sorted(list(clientes_no_encontrados)))}")
                if errores_fila_detalle:
                    messages.error(request, f"Se encontraron errores en {len(errores_fila_detalle)} filas. Revise la consola del servidor para más detalles.")
                    for err_msg in errores_fila_detalle[:3]:
                        messages.error(request, err_msg)

            except pd.errors.EmptyDataError:
                 messages.error(request, f"El archivo Excel '{archivo_excel.name}' está vacío o no tiene datos en la hoja esperada después de la cabecera.")
            except KeyError as e:
                messages.error(request, f"Error al leer el archivo: Columna esperada '{e}' no encontrada. Verifica que el archivo Excel tenga las columnas correctas y que el perfil de importación seleccionado sea el correcto.")
            except Exception as e:
                print(f"Error general durante la importación: {e}")
                import traceback
                traceback.print_exc()
                messages.error(request, f"Error crítico al procesar el archivo Excel: {e}")

            return redirect('cartera:importar_cartera')

        else:
            messages.error(request, "Error en el formulario. Por favor, completa todos los campos requeridos.")
    
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



    if not puede_filtrar_por_vendedor_dropdown and es_vendedor(user):
        # Es un VENDEDOR viendo su propia cartera
        try:
            vendedor_actual = Vendedor.objects.get(user=user, user__empresa=empresa_actual)
            codigo_vendedor = str(vendedor_actual.codigo_interno) if vendedor_actual.codigo_interno else None
            
            titulo_dinamico = f"Cartera de: {vendedor_actual.user.get_full_name() or vendedor_actual.user.username}"

            if codigo_vendedor:
                # El vendedor tiene un código. Buscamos documentos que coincidan con su código
                # O que no tengan código y el cliente le pertenezca.
                queryset_documentos = queryset_documentos.filter(
                    Q(codigo_vendedor_cartera=codigo_vendedor) |
                    (Q(codigo_vendedor_cartera__isnull=True) | Q(codigo_vendedor_cartera='')) & Q(cliente__vendedor=vendedor_actual)
                )
            else:
                # El vendedor no tiene código, solo podemos filtrar por cliente asignado.
                messages.warning(request, "Tu perfil no tiene código interno. Se mostrará la cartera solo por clientes asignados.")
                queryset_documentos = queryset_documentos.filter(cliente__vendedor=vendedor_actual)

        except Vendedor.DoesNotExist:
            messages.error(request, "No se encontró tu perfil de vendedor asociado.")
            queryset_documentos = DocumentoCartera.objects.none()
            
    elif puede_filtrar_por_vendedor_dropdown:
        # Es un ADMIN/CARTERA que puede usar el dropdown para filtrar
        vendedor_seleccionado_id_get = request.GET.get('vendedor_filtro_id')
        if vendedor_seleccionado_id_get:
            try:
                vendedor_obj = Vendedor.objects.get(pk=int(vendedor_seleccionado_id_get), user__empresa=empresa_actual)
                codigo_vendedor = str(vendedor_obj.codigo_interno) if vendedor_obj.codigo_interno else None
                
                titulo_dinamico = f"Cartera de Vendedor: {vendedor_obj.user.get_full_name() or vendedor_obj.user.username}"

                if codigo_vendedor:
                     queryset_documentos = queryset_documentos.filter(
                        Q(codigo_vendedor_cartera=codigo_vendedor) |
                        (Q(codigo_vendedor_cartera__isnull=True) | Q(codigo_vendedor_cartera='')) & Q(cliente__vendedor=vendedor_obj)
                    )
                else:
                    messages.warning(request, f"El vendedor '{vendedor_obj.user.username}' no tiene código interno. Mostrando solo por clientes asignados a él.")
                    queryset_documentos = queryset_documentos.filter(cliente__vendedor=vendedor_obj)

            except (ValueError, Vendedor.DoesNotExist):
                messages.error(request, "El vendedor seleccionado no es válido.")
        else:
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