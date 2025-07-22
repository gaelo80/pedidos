from collections import defaultdict
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView
from bodega.models import MovimientoInventario, CabeceraConteo, ConteoInventario
from django.shortcuts import render, get_object_or_404, redirect
from pedidos.models import Pedido
from django.http import JsonResponse
import openpyxl
import csv
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from .models import SalidaInternaCabecera
from .forms import SalidaInternaCabeceraForm, DetalleSalidaInternaFormSet
import json
import logging
from django.conf import settings
from django.db.models import Prefetch
from pedidos.models import DetallePedido
from django.http import HttpResponse
from django.utils import timezone
from core.utils import render_pdf_weasyprint, get_logo_base_64_despacho
from weasyprint import HTML
from bodega.forms import DetalleIngresoFormSet, InfoGeneralConteoForm, IngresoBodegaForm
from .forms import InfoGeneralConteoForm, ImportarConteoForm
from productos.models import Producto
from django.template.loader import render_to_string
from .models import IngresoBodega
from .models import ComprobanteDespacho, DetalleComprobanteDespacho
from django.db.models import Max, F
from core.mixins import TenantAwareMixin
from .resources import PlantillaConteoResource
from factura.models import EstadoFacturaDespacho


@login_required
@permission_required('pedidos.change_pedido', login_url='core:acceso_denegado')
def vista_despacho_pedido(request, pk):
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.") 
        return redirect('core:index')

    prefetch_queryset = Pedido.objects.prefetch_related('detalles__producto')
    pedido = get_object_or_404(prefetch_queryset, pk=pk, empresa=empresa_actual)

    ESTADOS_PERMITIDOS = ['APROBADO_ADMIN', 'PROCESANDO']

    if pedido.estado not in ESTADOS_PERMITIDOS and not request.user.is_superuser:
        messages.info(request, f"El pedido #{pedido.pk} ya fue enviado. Puedes revisar el comprobante generado.")
        return redirect('bodega:imprimir_comprobante_especifico', pk_comprobante=comprobante.pk)


    # --- Lógica POST (cuando se guarda o finaliza) ---
    if request.method == 'POST':
        action = request.POST.get('action', 'guardar_parcial')

        try:
            with transaction.atomic():
                hubo_cambios = False
                detalles_completos = True
                
                # Tu lógica para actualizar cantidades verificadas está bien.
                for detalle in pedido.detalles.all():
                    input_name = f'despachado_{detalle.pk}'
                    cantidad_despachada_str = request.POST.get(input_name, str(detalle.cantidad_verificada or 0))
                    cantidad_despachada_actual = int(cantidad_despachada_str)

                    if cantidad_despachada_actual > detalle.cantidad:
                         messages.error(request, f"Error en producto {detalle.producto}: Se intentó despachar {cantidad_despachada_actual} pero solo se pidieron {detalle.cantidad}.")
                         raise transaction.TransactionManagementError("Cantidad despachada excede la pedida.")

                    if detalle.cantidad_verificada != cantidad_despachada_actual:
                        detalle.cantidad_verificada = cantidad_despachada_actual
                        detalle.save(update_fields=['cantidad_verificada'])
                        hubo_cambios = True

                    if detalle.cantidad_verificada < detalle.cantidad:
                        detalles_completos = False

                # --- Lógica para Finalizar y Crear Comprobante ---
                if action == 'finalizar_despacho':
                    if not detalles_completos:
                        messages.warning(request, f"No se puede finalizar. Faltan ítems por despachar en el Pedido #{pedido.pk}.")
                    else:
                        # ✅ CORRECCIÓN 1: LÓGICA PARA CREAR COMPROBANTE AÑADIDA
                        comprobante, created = ComprobanteDespacho.objects.get_or_create(
                            pedido=pedido,
                            empresa=empresa_actual,
                            defaults={'usuario_responsable': request.user}
                        )
                        
                        if created:
                            detalles_a_crear = [
                                DetalleComprobanteDespacho(
                                    comprobante_despacho=comprobante,
                                    producto=d.producto,
                                    cantidad_despachada=d.cantidad_verificada,
                                    detalle_pedido_origen=d
                                )
                                for d in pedido.detalles.filter(cantidad_verificada__gt=0)
                            ]
                            DetalleComprobanteDespacho.objects.bulk_create(detalles_a_crear)
                            
                            pedido.estado = 'ENVIADO'
                            pedido.save(update_fields=['estado'])
                            messages.success(request, f"Comprobante #{comprobante.pk} creado. Pedido #{pedido.pk} marcado como 'Enviado'.")
                        else:
                            messages.info(request, f"El Pedido #{pedido.pk} ya tiene un comprobante (#{comprobante.pk}) asociado.")
                
                elif hubo_cambios: # Guardado parcial
                    if pedido.estado != 'PROCESANDO':
                       pedido.estado = 'PROCESANDO'
                       pedido.save(update_fields=['estado'])
                    messages.info(request, f"Despacho parcial del Pedido #{pedido.pk} guardado.")
                else:
                    messages.info(request, "No se detectaron cambios para guardar.")

        except Exception as e:
            messages.error(request, f"Ocurrió un error inesperado al guardar: {e}")
            
        return redirect('bodega:despacho_pedido', pk=pk)

    # --- Lógica GET (cuando se muestra la página) ---
    detalles_pedido = pedido.detalles.all().order_by('producto__referencia', 'producto__talla')

    # ✅ CORRECCIÓN 2: LÓGICA PARA HABILITAR EL BOTÓN 'FINALIZAR'
    # Calculamos si todas las cantidades ya fueron verificadas
    cantidades_completas = all(d.cantidad == d.cantidad_verificada for d in detalles_pedido)
    
    detalles_json = json.dumps([
        {'id': d.pk, 'codigo_barras': d.producto.codigo_barras or "", 'cantidad_pedida': d.cantidad, 'cantidad_verificada': d.cantidad_verificada or 0} for d in detalles_pedido
    ])

    context = {
        'pedido': pedido,
        'detalles_pedido': detalles_pedido,
        'detalles_json': detalles_json,
        'titulo': f"Despacho Pedido #{pedido.pk}",
        # La variable ahora depende de si las cantidades están completas Y del estado del pedido
        'puede_finalizar': cantidades_completas and pedido.estado in ESTADOS_PERMITIDOS
    }
    return render(request, 'bodega/despacho_pedido.html', context)


@login_required
@permission_required('bodega.view_lista_pedidos_bodega', login_url='core:acceso_denegado')
def vista_lista_pedidos_bodega(request):
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')

    # --- Obtener parámetros de búsqueda ---
    ref_query = request.GET.get('ref', '').strip()
    cliente_query = request.GET.get('cliente', '').strip()
    estado_query = request.GET.get('estado', '').strip()
    ref_producto_query = request.GET.get('ref_producto', '').strip()

    # --- Preparar Prefetch (sin cambios) ---
    prefetch_detalles = Prefetch(
        'detalles',
        queryset=DetallePedido.objects.select_related('producto'),
        to_attr='detalles_precargados'
    )

    # --- Query base SIN filtro de estado inicial ---
    pedidos_list = Pedido.objects.filter(
        empresa=empresa_actual
    ).select_related('cliente', 'vendedor__user').prefetch_related(prefetch_detalles)

    # --- Determinar qué estados mostrar ---
    # Asegúrate que estos estados coincidan con los definidos en tu modelo Pedido.ESTADO_PEDIDO_CHOICES
    estados_validos = [choice[0] for choice in Pedido.ESTADO_PEDIDO_CHOICES] # ['PENDIENTE', 'APROBADO_CARTERA', ..., 'CANCELADO']
    estados_por_defecto = ['APROBADO_ADMIN', 'PROCESANDO'] # Estados a mostrar si no se filtra

    titulo = f'Pedidos Bodega ({empresa_actual.nombre})'
    estado_display_filtro = "Todos (por defecto)"


    if estado_query:
        if estado_query in estados_validos:
            pedidos_list = pedidos_list.filter(estado=estado_query)
            # CORREGIDO: Forma correcta de obtener el "display name" de un choice.
            estado_display_filtro = dict(Pedido.ESTADO_PEDIDO_CHOICES).get(estado_query, estado_query)
            titulo = f'Pedidos: {estado_display_filtro} ({empresa_actual.nombre})'
        else:
            messages.warning(request, f"El estado '{estado_query}' no es válido.")
            pedidos_list = Pedido.objects.none()
            titulo = f'Pedidos Bodega (Estado Inválido) - {empresa_actual.nombre}'
    else:
        pedidos_list = pedidos_list.filter(estado__in=estados_por_defecto)
        titulo = f'Pedidos Pendientes Bodega ({empresa_actual.nombre})'
        
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


    context = {
        'pedidos_list': pedidos_list,
        'titulo': titulo,
        'ref_query': ref_query,
        'cliente_query': cliente_query,
        'estado_query': estado_query, 
        'ref_producto_query': ref_producto_query,
        'ESTADO_PEDIDO_CHOICES': Pedido.ESTADO_PEDIDO_CHOICES, # Pasar todos los choices para el select del filtro
    }
    return render(request, 'bodega/lista_pedidos_bodega.html', context) 



# --- Vista para Verificar Pedido (Ej: Por Bodega) ---
@login_required
@permission_required(['pedidos.change_pedido', 'bodega.add_comprobantedespacho'], login_url='core:acceso_denegado')
def vista_verificar_pedido(request, pk):
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')
    
    pedido = get_object_or_404(Pedido, pk=pk, empresa=empresa_actual)

    if request.method == 'GET':
        detalles_para_mostrar = pedido.detalles.select_related('producto').all().order_by('producto__referencia', 'producto__color', 'producto__talla')
        context = {
            'pedido': pedido,
            'detalles_pedido': detalles_para_mostrar,
            'titulo': f'Verificar Pedido #{pedido.pk}'
        }
        return render(request, 'bodega/verificar_pedido.html', context)

    elif request.method == 'POST':
        # --- INICIO DE LA VERIFICACIÓN DE CONTRASEÑA ---
        contraseña_ingresada = request.POST.get('contraseña_verificacion_pedido') # Nombre del input en tu plantilla
        contraseña_correcta = settings.CONTRASEÑA_PARA_VERIFICAR_PEDIDO

        if not contraseña_ingresada or contraseña_ingresada != contraseña_correcta:
            messages.error(request, "Contraseña de verificación incorrecta. No se procesaron los cambios.")
            # Redirigir a la misma página (GET) para mostrar el error y el formulario de nuevo
            return redirect('bodega:verificar_pedido', pk=pedido.pk)
        print(f"--- VISTA_VERIFICAR_PEDIDO (POST): INICIO para Pedido #{pk} ---")

        ESTADOS_PERMITIDOS_VERIFICACION = ['APROBADO_ADMIN', 'PENDIENTE', 'PENDIENTE_BODEGA', 'PROCESANDO']
        if pedido.estado not in ESTADOS_PERMITIDOS_VERIFICACION and not request.user.is_superuser : # Superusuario puede forzar
            messages.error(request, f"El pedido #{pedido.pk} no se puede modificar en su estado actual ({pedido.get_estado_display()}).")
            return redirect('bodega:verificar_pedido', pk=pedido.pk)

        items_efectivamente_despachados_para_comprobante = [] 
        hubo_cambios_generales_en_detalle_pedido = False 

        try:
            with transaction.atomic(): 
                print("Dentro de transaction.atomic(). Iniciando bucle for detalles...")
                detalles_a_procesar = pedido.detalles.select_related('producto').all().order_by('pk')

                for detalle_pedido_origen in detalles_a_procesar: 
                    input_name = f'cantidad_a_despachar_{detalle_pedido_origen.id}'
                    cantidad_a_despachar_str = request.POST.get(input_name)
                    print(f"  - DetallePedido ID {detalle_pedido_origen.id} ({detalle_pedido_origen.producto}): Leyendo '{input_name}', Valor recibido='{cantidad_a_despachar_str}'")

                    cantidad_ya_despachada_total_en_pedido = detalle_pedido_origen.cantidad_verificada or 0
                    cantidad_a_despachar_ahora_int = 0

                    try:
                        if cantidad_a_despachar_str is not None and cantidad_a_despachar_str.strip().isdigit():
                            cantidad_a_despachar_ahora_int = int(cantidad_a_despachar_str)
                        elif cantidad_a_despachar_str is not None and cantidad_a_despachar_str.strip() != '':
                            raise ValueError(f"Valor no numérico '{cantidad_a_despachar_str}' ingresado.")

                        if cantidad_a_despachar_ahora_int < 0:
                            raise ValueError("Cantidad a despachar no puede ser negativa.")

                        
                        pendiente_total_item_pedido = detalle_pedido_origen.cantidad - cantidad_ya_despachada_total_en_pedido
                        if cantidad_a_despachar_ahora_int > pendiente_total_item_pedido:
                            error_msg = (
                                f"Intenta despachar {cantidad_a_despachar_ahora_int} de {detalle_pedido_origen.producto.nombre} "
                                f"pero solo quedan {pendiente_total_item_pedido} pendientes en el pedido."
                            )
                            messages.error(request, error_msg)
                            raise transaction.TransactionManagementError(error_msg)

                        
                        if cantidad_a_despachar_ahora_int > 0:
                            items_efectivamente_despachados_para_comprobante.append({
                                'producto': detalle_pedido_origen.producto, 
                                'cantidad_despachada': cantidad_a_despachar_ahora_int,
                                'detalle_pedido_origen': detalle_pedido_origen 
                            })
                            print(f"      Agregado para Comprobante: {detalle_pedido_origen.producto.nombre} - Cantidad: {cantidad_a_despachar_ahora_int}")

                        
                        nuevo_total_verificado_pedido = cantidad_ya_despachada_total_en_pedido + cantidad_a_despachar_ahora_int
                        if nuevo_total_verificado_pedido != cantidad_ya_despachada_total_en_pedido or \
                           (not detalle_pedido_origen.verificado_bodega and cantidad_a_despachar_str is not None and cantidad_a_despachar_str.strip().isdigit()):
                            detalle_pedido_origen.cantidad_verificada = nuevo_total_verificado_pedido
                            detalle_pedido_origen.verificado_bodega = True 
                            detalle_pedido_origen.save(update_fields=['cantidad_verificada', 'verificado_bodega'])
                            hubo_cambios_generales_en_detalle_pedido = True
                            print(f"    DetallePedido ID {detalle_pedido_origen.id} ACTUALIZADO. Nuevo Total Verificado: {detalle_pedido_origen.cantidad_verificada}")

                    except ValueError as e_val_item:
                        error_msg_item = f"Error en ítem {detalle_pedido_origen.producto.nombre} ({detalle_pedido_origen.producto.referencia}): {e_val_item}"
                        messages.error(request, error_msg_item)
                        raise transaction.TransactionManagementError(error_msg_item)
                
                print("Fin del bucle for detalles.")

                
                comprobante_creado = None
                if items_efectivamente_despachados_para_comprobante:
                    
                    comprobante_creado = ComprobanteDespacho.objects.create(
                        empresa=empresa_actual,
                        pedido=pedido,
                        fecha_hora_despacho=timezone.now(),
                        usuario_responsable=request.user,
                    )
                    print(f"ComprobanteDespacho ID {comprobante_creado.pk} CREADO para empresa '{empresa_actual.nombre}'.")          
                    
                    
                    
                    
                    comprobante_creado = ComprobanteDespacho.objects.create(
                        pedido=pedido,
                        fecha_hora_despacho=timezone.now(),
                        usuario_responsable=request.user,
                        
                    )
                    print(f"ComprobanteDespacho ID {comprobante_creado.pk} CREADO.")
                    
                    
                    
                    
                    
                    
                    
                    if comprobante_creado:
                        from factura.models import EstadoFacturaDespacho # Importar el modelo
                        EstadoFacturaDespacho.objects.create(
                            empresa=empresa_actual,
                            despacho=comprobante_creado
                        )
                        print(f"EstadoFacturaDespacho CREADO para Comprobante ID {comprobante_creado.pk}")
                                   
                    for item_data in items_efectivamente_despachados_para_comprobante:
                        DetalleComprobanteDespacho.objects.create(
                            comprobante_despacho=comprobante_creado,
                            producto=item_data['producto'],
                            cantidad_despachada=item_data['cantidad_despachada'],
                            detalle_pedido_origen=item_data['detalle_pedido_origen']
                        )
                    print(f"  {len(items_efectivamente_despachados_para_comprobante)} Detalles de ComprobanteDespacho CREADOS.")
                    messages.success(request, f"Comprobante de Despacho #{comprobante_creado.pk} generado con {len(items_efectivamente_despachados_para_comprobante)} ítem(s).")


                elif hubo_cambios_generales_en_detalle_pedido: 
                    messages.info(request, "Se actualizaron las cantidades verificadas del pedido, pero no se generó un nuevo comprobante de despacho (0 ítems despachados esta vez).")
                else: 
                    messages.info(request, "No se despacharon ítems ni se realizaron cambios en la verificación del pedido.")

                
                if hubo_cambios_generales_en_detalle_pedido or comprobante_creado: 
                    pedido.refresh_from_db() 
                    detalles_refrescados = pedido.detalles.all()
                    todas_completas = all((d.cantidad_verificada or 0) >= d.cantidad for d in detalles_refrescados)
                    
                    nuevo_estado_pedido = pedido.estado
                    if todas_completas:
                        if pedido.estado not in ['COMPLETADO', 'ENVIADO', 'ENTREGADO', 'CANCELADO']:
                            nuevo_estado_pedido = 'COMPLETADO' 
                            messages.success(request, f'Pedido #{pedido.pk} marcado como COMPLETAMENTE DESPACHADO/VERIFICADO!')
                    else: 
                        if items_efectivamente_despachados_para_comprobante or hubo_cambios_generales_en_detalle_pedido : 
                            if pedido.estado in ['PENDIENTE', 'APROBADO_ADMIN', 'PENDIENTE_BODEGA']: # Ajustar estados según tu flujo
                                nuevo_estado_pedido = 'PROCESANDO'
                                messages.info(request, f'Pedido #{pedido.pk} ahora en estado PROCESANDO.')
                            elif pedido.estado == 'PROCESANDO':
                                messages.info(request, f'Verificación/Despacho actualizado para pedido #{pedido.pk} (sigue en PROCESANDO).')
                    
                    if nuevo_estado_pedido != pedido.estado:
                        pedido.estado = nuevo_estado_pedido
                        pedido.save(update_fields=['estado'])

                
                print("Fin bloque 'with transaction.atomic()'. Transacción exitosa. Redirigiendo...")
                
                return redirect('bodega:verificar_pedido', pk=pedido.pk)

        except transaction.TransactionManagementError as e_trans:
            print(f"TransactionManagementError: {e_trans}. Rollback realizado.")
            
        except ValueError as e_val: 
            print(f"ValueError: {e_val}")
            messages.error(request, str(e_val))
        except Exception as e_global:
            print(f"Error global inesperado (POST): {type(e_global).__name__} - {e_global}")
            import traceback
            traceback.print_exc()
            messages.error(request, f"Error inesperado al procesar la verificación/despacho: {e_global}")

        
        print("POST procesado con errores o rollback. Redirigiendo a GET para mostrar errores...")
        return redirect('bodega:verificar_pedido', pk=pedido.pk)

    else:
        return HttpResponse("Método no permitido.", status=405)
    
    #$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

@login_required
@permission_required('bodega.view_comprobantedespacho', login_url='core:acceso_denegado')
def vista_imprimir_comprobante_especifico(request, pk_comprobante): 
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')
   
    try:
        
        queryset = ComprobanteDespacho.objects.select_related(
            'pedido', 
            'pedido__cliente',
            'pedido__vendedor__user', 
            'usuario_responsable' 
        ).prefetch_related(
            'detalles__producto' 
        )
        comprobante = get_object_or_404(
            queryset, 
            pk=pk_comprobante, 
            pedido__empresa=empresa_actual # ¡Este filtro es la clave de la seguridad aquí!
        )
        pedido_asociado = comprobante.pedido
        
    except ComprobanteDespacho.DoesNotExist:
        messages.error(request, f"El comprobante de despacho con ID #{pk_comprobante} no existe.")
        return redirect('factura:lista_despachos_a_facturar') 

    detalles_del_comprobante = comprobante.detalles.all()

    if not detalles_del_comprobante:
        messages.warning(request, f"El Comprobante de Despacho #{comprobante.pk} no tiene ítems detallados.")
        return redirect('factura:detalle_despacho_factura', pk_despacho=comprobante.pk)


    items_agrupados_dict = defaultdict(lambda: {
        'nombre_producto': '', 
        'color': '',
        'tallas_cantidades': [], 
        'total_cantidad_referencia_color': 0 
    })

    for detalle_item in detalles_del_comprobante:
        producto_obj = detalle_item.producto
        clave_agrupacion = (producto_obj.referencia, producto_obj.color)

        if not items_agrupados_dict[clave_agrupacion]['nombre_producto']:
            items_agrupados_dict[clave_agrupacion]['nombre_producto'] = producto_obj.nombre 
            items_agrupados_dict[clave_agrupacion]['color'] = producto_obj.color if producto_obj.color else "-"

        items_agrupados_dict[clave_agrupacion]['tallas_cantidades'].append({
            'talla': producto_obj.talla if producto_obj.talla else "-",
            'cantidad': detalle_item.cantidad_despachada
        })
        items_agrupados_dict[clave_agrupacion]['total_cantidad_referencia_color'] += detalle_item.cantidad_despachada

    items_agrupados_para_pdf = []
    for (referencia, color_agrupado), data in items_agrupados_dict.items():
        data['tallas_cantidades'].sort(key=lambda x: x.get('talla', ''))
        items_agrupados_para_pdf.append({
            'referencia': referencia,
            'nombre_producto': data['nombre_producto'],
            'color': color_agrupado if color_agrupado else "-",
            'tallas_cantidades': data['tallas_cantidades'],
            'total_cantidad_referencia_color': data['total_cantidad_referencia_color']
        })

    items_agrupados_para_pdf.sort(key=lambda x: x['referencia'])
    
    print(f"Procesados {len(items_agrupados_para_pdf)} grupos de ítems para el PDF del Comprobante #{comprobante.pk}.")

    context_pdf = {
        'comprobante_despacho': comprobante, 
        'pedido': pedido_asociado,           
        'items_despachados_agrupados': items_agrupados_para_pdf,
        'fecha_despacho': comprobante.fecha_hora_despacho, 
        'logo_base64': get_logo_base_64_despacho(empresa=empresa_actual),
    }
    
    filename = f"Comprobante_Despacho_Empresa{empresa_actual.pk}_{comprobante.pk}"
    
    return render_pdf_weasyprint(
        request,
        'bodega/comprobante_despacho_pdf.html', 
        context_pdf,
        filename_prefix=filename 
    )

@login_required
@permission_required('bodega.view_comprobantedespacho', login_url='core:acceso_denegado')
def vista_generar_ultimo_comprobante_pedido(request, pk): # pk_pedido es el ID del Pedido
    """
    Genera el PDF para el ÚLTIMO ComprobanteDespacho asociado a un Pedido específico.
    PK es el ID del Pedido.
    """
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')
    
    print(f"--- VISTA_GENERAR_ULTIMO_COMPROBANTE_PEDIDO: INICIO GET para Pedido ID #{pk} ---")
    
    pedido_obj = get_object_or_404(Pedido, pk=pk, empresa=empresa_actual)

    try:
        comprobante = ComprobanteDespacho.objects.select_related(
            'pedido', 
            'pedido__cliente',
            'pedido__vendedor__user', 
            'usuario_responsable' 
        ).prefetch_related(
            'detalles__producto' 
        ).filter(pedido=pedido_obj).latest('fecha_hora_despacho')
        
        pedido_asociado = comprobante.pedido 

    except ComprobanteDespacho.DoesNotExist:
        messages.error(request, f"No se encontró ningún comprobante de despacho para el Pedido #{pedido_obj.pk}.")
        return redirect('bodega:despacho_pedido', pk=pedido_obj.pk)
    except Exception as e:
        messages.error(request, f"Ocurrió un error inesperado buscando el comprobante: {e}")
        return redirect('bodega:despacho_pedido', pk=pedido_obj.pk)

    detalles_del_comprobante = comprobante.detalles.all()

    if not detalles_del_comprobante:
        messages.warning(request, f"El Comprobante de Despacho #{comprobante.pk} (último para el Pedido #{pedido_obj.pk}) no tiene ítems detallados.")
        return redirect('bodega:despacho_pedido', pk=pedido_obj.pk)

    items_agrupados_dict = defaultdict(lambda: {
        'nombre_producto': '', 
        'color': '',
        'tallas_cantidades': [], 
        'total_cantidad_referencia_color': 0 
    })

    for detalle_item in detalles_del_comprobante:
        producto_obj = detalle_item.producto
        clave_agrupacion = (producto_obj.referencia, producto_obj.color)

        if not items_agrupados_dict[clave_agrupacion]['nombre_producto']:
            items_agrupados_dict[clave_agrupacion]['nombre_producto'] = producto_obj.nombre 
            items_agrupados_dict[clave_agrupacion]['color'] = producto_obj.color if producto_obj.color else "-"

        items_agrupados_dict[clave_agrupacion]['tallas_cantidades'].append({
            'talla': producto_obj.talla if producto_obj.talla else "-",
            'cantidad': detalle_item.cantidad_despachada
        })
        items_agrupados_dict[clave_agrupacion]['total_cantidad_referencia_color'] += detalle_item.cantidad_despachada

    items_agrupados_para_pdf = []
    for (referencia, color_agrupado), data in items_agrupados_dict.items():
        data['tallas_cantidades'].sort(key=lambda x: str(x.get('talla', '')))
        items_agrupados_para_pdf.append({
            'referencia': referencia,
            'nombre_producto': data['nombre_producto'],
            'color': color_agrupado if color_agrupado else "-",
            'tallas_cantidades': data['tallas_cantidades'],
            'total_cantidad_referencia_color': data['total_cantidad_referencia_color']
        })

    items_agrupados_para_pdf.sort(key=lambda x: x['referencia'])
    
    print(f"Procesados {len(items_agrupados_para_pdf)} grupos de ítems para el PDF del Comprobante #{comprobante.pk} (Pedido #{pedido_obj.pk}).")

    context_pdf = {
        'comprobante_despacho': comprobante, 
        'pedido': pedido_asociado,          
        'items_despachados_agrupados': items_agrupados_para_pdf,
        'fecha_despacho': comprobante.fecha_hora_despacho, 
        'logo_base64': get_logo_base_64_despacho(empresa=empresa_actual),
    }
    
    filename = f"Comprobante_Despacho_Empresa{empresa_actual.pk}_P{pedido_obj.pk}_C{comprobante.pk}"
    
    return render_pdf_weasyprint(
        request,
        'bodega/comprobante_despacho_pdf.html', 
        context_pdf,
        filename_prefix=filename
    )


@login_required
@permission_required(['bodega.add_ingresobodega', 'bodega.add_movimientoinventario'], login_url='core:acceso_denegado')
def vista_registrar_ingreso(request):
    """
    Maneja el registro de un nuevo Ingreso a Bodega con sus detalles.
    """
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')
    
    if request.method == 'POST':
        form = IngresoBodegaForm(request.POST, empresa=empresa_actual)
        formset = DetalleIngresoFormSet(request.POST, prefix='detalles_ingreso', form_kwargs={'empresa': empresa_actual})


        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    ingreso_header = form.save(commit=False)
                    ingreso_header.usuario = request.user
                    ingreso_header.fecha_hora = timezone.now()
                    ingreso_header.empresa = empresa_actual
                    ingreso_header.save()

                    formset.instance = ingreso_header
                    formset.save()

                    print(f"Registrando entrada de stock para Ingreso #{ingreso_header.pk}...")
                    detalles_guardados = ingreso_header.detalles.all()
                    for detalle in detalles_guardados:
                        if detalle.cantidad > 0:
                            MovimientoInventario.objects.create(
                                empresa=empresa_actual,
                                producto=detalle.producto,
                                cantidad=detalle.cantidad, 
                                tipo_movimiento='ENTRADA_COMPRA', 
                                documento_referencia=f"Ingreso #{ingreso_header.pk} ({ingreso_header.documento_referencia or ''})".strip(),
                                usuario=request.user,
                                notas=f'Entrada por Ingreso a Bodega #{ingreso_header.pk}'
                            )
                            print(f" + Stock actualizado para {detalle.producto}: +{detalle.cantidad}")

                    messages.success(request, f"Ingreso a Bodega #{ingreso_header.pk} registrado exitosamente.")
                    return redirect('bodega:vista_registrar_ingreso') # Nombre corregido

            except Exception as e:
                messages.error(request, f"Error al guardar el ingreso: {e}")
        else:
            messages.error(request, "Por favor corrige los errores en el formulario.")
    else: 
        form = IngresoBodegaForm(empresa=empresa_actual)
        formset = DetalleIngresoFormSet(prefix='detalles_ingreso', form_kwargs={'empresa': empresa_actual})

    context = {
        'form': form,
        'formset': formset,
        'titulo': f'Registrar Ingreso a Bodega ({empresa_actual.nombre})'
    }
    return render(request, 'bodega/registrar_ingreso.html', context)


#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

@login_required
@permission_required('bodega.view_cabeceraconteo', login_url='core:acceso_denegado')
def exportar_plantilla_conteo(request, file_format='xlsx'): # Añadimos file_format
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido.")
        return redirect('core:index')

    # Obtenemos solo los productos de la empresa actual
    queryset = Producto.objects.filter(empresa=empresa_actual, activo=True)
    
    # Usamos el Resource, tal como lo haces en la app de clientes
    plantilla_resource = PlantillaConteoResource()
    dataset = plantilla_resource.export(queryset)
    
    # Lógica de respuesta idéntica a la tuya
    if file_format == 'csv':
        response_content = dataset.csv
        content_type = 'text/csv'
        filename = f'plantilla_conteo_{timezone.now().strftime("%Y%m%d")}.csv'
    elif file_format == 'xls':
        response_content = dataset.xls
        content_type = 'application/vnd.ms-excel'
        filename = f'plantilla_conteo_{timezone.now().strftime("%Y%m%d")}.xls'
    else: # xlsx por defecto
        response_content = dataset.xlsx
        content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        filename = f'plantilla_conteo_{timezone.now().strftime("%Y%m%d")}.xlsx'

    response = HttpResponse(response_content, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


logger = logging.getLogger(__name__)

# La función auxiliar _procesar_y_guardar_conteo está bien, no necesita cambios.
@transaction.atomic
def _procesar_y_guardar_conteo(request, empresa, datos_generales, datos_conteo):
    cabecera = CabeceraConteo.objects.create(
        empresa=empresa,
        fecha_conteo=datos_generales['fecha_actualizacion_stock'],
        motivo=datos_generales['motivo_conteo'],
        revisado_con=datos_generales['revisado_con'],
        notas_generales=datos_generales['notas_generales'],
        usuario_registro=request.user
    )
    stats = {'ajustados': 0, 'sin_cambio': 0}
    for producto in Producto.objects.filter(empresa=empresa, activo=True):
        cantidad_fisica = datos_conteo.get(producto.pk)
        if cantidad_fisica is not None and cantidad_fisica >= 0:
            stock_sistema = producto.stock_actual
            diferencia = cantidad_fisica - stock_sistema
            ConteoInventario.objects.create(
                empresa=empresa, cabecera_conteo=cabecera, producto=producto,
                cantidad_sistema_antes=stock_sistema, cantidad_fisica_contada=cantidad_fisica,
                usuario_conteo=request.user
            )
            if diferencia != 0:
                tipo_movimiento = 'ENTRADA_AJUSTE' if diferencia > 0 else 'SALIDA_AJUSTE'
                MovimientoInventario.objects.create(
                    empresa=empresa, producto=producto, cantidad=diferencia,
                    tipo_movimiento=tipo_movimiento, usuario=request.user,
                    documento_referencia=f"Conteo ID {cabecera.pk}",
                    notas=f"Ajuste por conteo. Sistema: {stock_sistema}, Físico: {cantidad_fisica}"
                )
                stats['ajustados'] += 1
            else:
                stats['sin_cambio'] += 1
    return cabecera, stats


@login_required
@permission_required('bodega.view_cabeceraconteo', login_url='core:acceso_denegado')
def vista_conteo_inventario(request):
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')

    user = request.user
    puede_guardar = user.has_perm('bodega.add_cabeceraconteo')

    if request.method == 'POST':
        if not puede_guardar:
            messages.error(request, "No tienes permiso para guardar conteos y ajustar el stock.")
            return redirect('bodega:vista_conteo_inventario')

        info_form = InfoGeneralConteoForm(request.POST)
        import_form = ImportarConteoForm(request.POST, request.FILES)

        if info_form.is_valid():
            action = request.POST.get('action')
            datos_conteo = {}

            if action == 'guardar_manual':
                logger.info(f"Intento de guardado manual por '{user.username}'.")
                for key, value in request.POST.items():
                    if key.startswith('cantidad_fisica_') and value.strip().isdigit():
                        producto_id = int(key.split('_')[-1])
                        datos_conteo[producto_id] = int(value)
            
            elif action == 'importar_excel':
                logger.info(f"Intento de importación por archivo por '{user.username}'.")
                
                # --- LÓGICA DE VALIDACIÓN SIMPLIFICADA Y CORREGIDA ---
                if not import_form.is_valid():
                    messages.error(request, "El formulario de importación tiene errores.")
                    return redirect('bodega:vista_conteo_inventario')
                
                if 'archivo_conteo' not in request.FILES:
                    messages.error(request, "Para importar, primero debes seleccionar un archivo.")
                    return redirect('bodega:vista_conteo_inventario')
                
                # Si pasamos las validaciones, ahora sí definimos las variables
                archivo_importado = request.FILES['archivo_conteo']
                nombre_archivo = archivo_importado.name.lower()

                try:
                    if nombre_archivo.endswith('.csv'):
                        contenido_str = archivo_importado.read().decode('utf-8')
                        dialect = csv.Sniffer().sniff(contenido_str.splitlines()[0], delimiters=',;')
                        reader = csv.reader(contenido_str.splitlines(), dialect)
                        next(reader)
                        for row in reader:
                            if len(row) < 7: continue
                            try:
                                p_id, c_fisica = int(row[0]), int(row[6])
                                if p_id > 0 and c_fisica >= 0: datos_conteo[p_id] = c_fisica
                            except (ValueError, TypeError, IndexError): continue

                    elif nombre_archivo.endswith(('.xlsx', '.xls')):
                        workbook = openpyxl.load_workbook(archivo_importado, data_only=True)
                        sheet = workbook[workbook.sheetnames[0]]
                        for row in sheet.iter_rows(min_row=2, values_only=True):
                            if len(row) < 7: continue
                            try:
                                p_id, c_fisica = int(row[0]), int(row[6])
                                if p_id > 0 and c_fisica >= 0: datos_conteo[p_id] = c_fisica
                            except (ValueError, TypeError, IndexError): continue
                    else:
                        messages.error(request, "Formato de archivo no soportado. Sube un .csv o .xlsx.")
                        return redirect('bodega:vista_conteo_inventario')

                except Exception as e:
                    messages.error(request, f"Error crítico durante la lectura del archivo: {e}")
                    logger.error(f"Error de parsing para conteo: {e}", exc_info=True)
                    return redirect('bodega:vista_conteo_inventario')
            
            # --- El resto del código se mantiene igual ---
            if not datos_conteo:
                messages.warning(request, "No se encontraron datos de cantidades para procesar, ni en la tabla ni en el archivo.")
                return redirect('bodega:vista_conteo_inventario')
            
            try:
                cabecera, stats = _procesar_y_guardar_conteo(request, empresa_actual, info_form.cleaned_data, datos_conteo)
                if stats['ajustados'] > 0:
                    messages.success(request, f"Conteo #{cabecera.pk} guardado. Se ajustó el stock de {stats['ajustados']} producto(s).")
                if stats['sin_cambio'] > 0 and stats['ajustados'] == 0:
                    messages.info(request, f"Conteo #{cabecera.pk} guardado. {stats['sin_cambio']} producto(s) no tuvieron cambios de stock.")
                return redirect('bodega:descargar_informe_conteo', cabecera_id=cabecera.pk)
            except Exception as e:
                messages.error(request, f"Ocurrió un error inesperado al guardar el conteo: {e}")
                logger.critical(f"Error fatal al llamar a _procesar_y_guardar_conteo: {e}", exc_info=True)
                return redirect('bodega:vista_conteo_inventario')
        else:
            messages.error(request, "Por favor corrige los errores en la información general del conteo.")

    # --- LÓGICA GET ---
    items_a_contar = Producto.objects.filter(empresa=empresa_actual, activo=True).order_by('referencia', 'nombre', 'color', 'talla')
    info_form = InfoGeneralConteoForm()
    import_form = ImportarConteoForm()

    context = {
        'items_para_conteo': items_a_contar,
        'titulo': f"Conteo de Inventario Físico ({empresa_actual.nombre})",
        'info_form': info_form,
        'import_form': import_form,
        'puede_guardar': puede_guardar,
    }
    return render(request, 'bodega/conteo_inventario.html', context)
    
    
@login_required
@permission_required('bodega.view_cabeceraconteo', login_url='core:acceso_denegado')
def descargar_informe_conteo(request, cabecera_id):
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')
    
    cabecera = get_object_or_404(CabeceraConteo, pk=cabecera_id, empresa=empresa_actual)
    detalles_conteo = ConteoInventario.objects.filter(cabecera_conteo=cabecera).select_related('producto')
    inconsistencias = [d for d in detalles_conteo if d.diferencia != 0]

    context = {
        'cabecera': cabecera,
        'inconsistencias': inconsistencias, # Solo los que tuvieron diferencia
        'detalles_completos': detalles_conteo, # Todos los detalles para un informe completo si se desea
        'logo_base64': get_logo_base_64_despacho(empresa=empresa_actual),
        'fecha_generacion': timezone.now(),
    }

    html_string = render_to_string('bodega/conteo_informe_pdf.html', context)
    try:
        html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))
        pdf_file = html.write_pdf()
        response = HttpResponse(pdf_file, content_type='application/pdf')
        filename = f'Informe_conteo_Empresa{empresa_actual.pk}_{cabecera.pk}_{cabecera.fecha_conteo.strftime("%Y%m%d")}.pdf'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        print(f"Error generando PDF con WeasyPrint para conteo {cabecera.pk}: {e}")
        messages.error(request, f"Error al generar el informe PDF: {e}")
        return redirect('bodega:vista_conteo_inventario')


class InformeDespachosView(TenantAwareMixin, LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Pedido
    template_name = 'bodega/informe_despachos.html' 
    context_object_name = 'lista_pedidos'
    paginate_by = 25
    
    permission_required = 'informes.view_comprobantes_despacho'
    login_url = 'core:acceso_denegado'

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para acceder a este informe.")
        return redirect('core:index')

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        empresa_actual = self.request.tenant

        # CORRECCIÓN: Las importaciones se mueven aquí, fuera del bloque try/except,
        # para que Pylance y otros analizadores las reconozcan siempre.
        from core.auth_utils import es_vendedor, es_admin_sistema, es_factura, es_cartera
        from vendedores.models import Vendedor

        if es_vendedor(user) and not (user.is_superuser or es_admin_sistema(user) or es_factura(user) or es_cartera(user)):
            try:
                vendedor_actual = Vendedor.objects.get(user=user, user__empresa=empresa_actual)
                queryset = queryset.filter(vendedor=vendedor_actual)
            except Vendedor.DoesNotExist:
                messages.warning(self.request, "Tu usuario no está asociado a un perfil de vendedor.")
                return Pedido.objects.none()
        
        # --- SECCIÓN DE FILTRADO POR PARÁMETROS GET (INTACTA) ---
        nit_cliente_query = self.request.GET.get('nit_cliente', '').strip()
        nombre_cliente_query = self.request.GET.get('nombre_cliente', '').strip()
        numero_pedido_query = self.request.GET.get('numero_pedido', '').strip()
        fecha_pedido_inicio_query = self.request.GET.get('fecha_pedido_inicio', '').strip()
        fecha_pedido_fin_query = self.request.GET.get('fecha_pedido_fin', '').strip()
        estado_pedido_query = self.request.GET.get('estado_pedido', '').strip()

        if nit_cliente_query:
            queryset = queryset.filter(cliente__identificacion__icontains=nit_cliente_query)
        if nombre_cliente_query:
            queryset = queryset.filter(cliente__nombre_completo__icontains=nombre_cliente_query)
        if numero_pedido_query:
            try:
                pedido_pk = int(numero_pedido_query)
                queryset = queryset.filter(pk=pedido_pk)
            except (ValueError, TypeError):
                pass 
        if fecha_pedido_inicio_query and fecha_pedido_fin_query:
            queryset = queryset.filter(fecha_hora__date__range=[fecha_pedido_inicio_query, fecha_pedido_fin_query])
        elif fecha_pedido_inicio_query:
            queryset = queryset.filter(fecha_hora__date__gte=fecha_pedido_inicio_query)
        elif fecha_pedido_fin_query:
            queryset = queryset.filter(fecha_hora__date__lte=fecha_pedido_fin_query)
        
        if estado_pedido_query:
            queryset = queryset.filter(estado=estado_pedido_query)
            
        # --- OPTIMIZACIÓN Y RETORNO FINAL (INTACTO) ---
        return queryset.select_related('cliente', 'vendedor__user').annotate(
            ultima_fecha_despacho=Max('comprobantes_despacho__fecha_hora_despacho')
        ).order_by('-fecha_hora').distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        empresa_actual = self.request.tenant
        
        from core.auth_utils import es_vendedor, es_admin_sistema, es_factura, es_cartera
        
        if es_vendedor(user) and not (user.is_superuser or es_admin_sistema(user) or es_factura(user) or es_cartera(user)):
            context['titulo_pagina'] = f"Mis Pedidos y Despachos ({empresa_actual.nombre})"
        else:
            context['titulo_pagina'] = f"Informe General de Despachos ({empresa_actual.nombre})"

        context['nit_cliente_query'] = self.request.GET.get('nit_cliente', '')
        context['nombre_cliente_query'] = self.request.GET.get('nombre_cliente', '')
        context['numero_pedido_query'] = self.request.GET.get('numero_pedido', '')
        context['fecha_pedido_inicio_query'] = self.request.GET.get('fecha_pedido_inicio', '')
        context['fecha_pedido_fin_query'] = self.request.GET.get('fecha_pedido_fin', '')
        context['estado_pedido_query'] = self.request.GET.get('estado_pedido', '')
        context['ESTADO_PEDIDO_CHOICES'] = Pedido.ESTADO_PEDIDO_CHOICES
        
        return context

@login_required
@permission_required('factura.view_ingresobodega', login_url='core:acceso_denegado')
def vista_detalle_ingreso_bodega(request, pk):
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')
    
    ingreso = get_object_or_404(
        IngresoBodega.objects.select_related('usuario'), 
        pk=pk, 
        empresa=empresa_actual
    )
    detalles_del_ingreso = ingreso.detalles.select_related('producto').all()

    context = {
        'ingreso': ingreso,
        'detalles_del_ingreso': detalles_del_ingreso,
        'titulo': f'Detalle del Ingreso #{ingreso.pk} ({empresa_actual.nombre})',
        'app_name': 'bodega' 
    }
    return render(request, 'bodega/detalle_ingreso_bodega.html', context)


@login_required
@permission_required(['bodega.add_salidainternacabecera', 'bodega.add_movimientoinventario'], login_url='core:acceso_denegado')
def registrar_salida_interna(request):
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')
    
    if request.method == 'POST':
        form_cabecera = SalidaInternaCabeceraForm(request.POST) # Este form no tiene campos que dependan de la empresa
        formset_detalles = DetalleSalidaInternaFormSet(request.POST, prefix='detalles_salida', form_kwargs={'empresa': empresa_actual})

        if form_cabecera.is_valid() and formset_detalles.is_valid():
            try:
                with transaction.atomic():
                    cabecera = form_cabecera.save(commit=False)
                    cabecera.responsable_entrega = request.user
                    cabecera.empresa = empresa_actual
                    
                    if cabecera.tipo_salida == 'DONACION_BAJA':
                        cabecera.estado = 'CERRADA'
                    else:
                        # Para otros tipos, el estado por defecto 'DESPACHADA' ya está en el modelo.
                        # Si no hay fecha_prevista_devolucion y no es DONACION_BAJA, podría ser 'CERRADA' también?
                        # Esto depende de tu lógica de negocio. Por ahora, se mantiene simple.
                        pass
                    cabecera.save()

                    formset_detalles.instance = cabecera
                    detalles_guardados = formset_detalles.save() 

                    for detalle in detalles_guardados:
                        # Asegurarse que el detalle no fue marcado para borrarse y tiene cantidad
                        if detalle and detalle.cantidad_despachada > 0: 
                            tipo_mov_str = f"SALIDA_{cabecera.tipo_salida.upper()}"
                            
                            # Mapeo explícito para asegurar consistencia con MovimientoInventario.TIPO_MOVIMIENTO_CHOICES
                            tipo_mov_map = {
                                'MUESTRARIO': 'SALIDA_MUESTRARIO',
                                'EXHIBIDOR': 'SALIDA_EXHIBIDOR',
                                'TRASLADO_INTERNO': 'SALIDA_TRASLADO',
                                'PRESTAMO': 'SALIDA_PRESTAMO',
                                'DONACION_BAJA': 'SALIDA_DONACION_BAJA',
                                'OTRO': 'SALIDA_INTERNA_OTRA', # Asegúrate que 'SALIDA_INTERNA_OTRA' exista en choices
                            }
                            tipo_mov_str = tipo_mov_map.get(cabecera.tipo_salida, 'SALIDA_INTERNA_OTRA')


                            MovimientoInventario.objects.create(
                                empresa=empresa_actual,
                                producto=detalle.producto,
                                cantidad=-detalle.cantidad_despachada, 
                                tipo_movimiento=tipo_mov_str,
                                documento_referencia=f"SalidaInt #{cabecera.pk}",
                                usuario=request.user,
                                notas=f"Salida por {cabecera.get_tipo_salida_display()} a {cabecera.destino_descripcion}"
                            )
                    
                    messages.success(request, f"Salida Interna #{cabecera.pk} registrada exitosamente. Stock actualizado.")
                    return redirect('bodega:detalle_salida_interna', pk=cabecera.pk) 

            except Exception as e:
                messages.error(request, f"Error al guardar la salida interna: {e}")
        else:
            # Errores en form_cabecera o formset_detalles
            if not form_cabecera.is_valid():
                 messages.error(request, "Por favor corrige los errores en los datos generales de la salida.")
            if not formset_detalles.is_valid():
                 messages.error(request, "Por favor corrige los errores en los productos a despachar.")
                 # Podrías iterar sobre formset_detalles.errors para dar mensajes más específicos
                 for form_error in formset_detalles.errors:
                     print(f"Error en formset: {form_error}") # Para depuración
                 for i, form_detalle in enumerate(formset_detalles):
                    if form_detalle.errors:
                        for field, error_list in form_detalle.errors.items():
                            for error in error_list:
                                messages.warning(request, f"Error en Producto #{i+1} ({field}): {error}")


    else: # GET
        form_cabecera = SalidaInternaCabeceraForm()
        formset_detalles = DetalleSalidaInternaFormSet(prefix='detalles_salida', form_kwargs={'empresa': empresa_actual})

    context = {
        'form_cabecera': form_cabecera,
        'formset_detalles': formset_detalles,
        'titulo': f'Registrar Nueva Salida Interna ({empresa_actual.nombre})'
    }
    return render(request, 'bodega/registrar_salida_interna.html', context)

@login_required
@permission_required('bodega.view_salidainternacabecera', login_url='core:acceso_denegado')
def detalle_salida_interna(request, pk): 
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')
    
    salida_interna = get_object_or_404(
        SalidaInternaCabecera.objects.select_related('responsable_entrega'), 
        pk=pk, 
        empresa=empresa_actual
    )
    detalles_items = salida_interna.detalles.select_related('producto').all()

    context = {
        'salida_interna': salida_interna,
        'detalles_items': detalles_items,
        'titulo': f"Detalle Salida Interna #{salida_interna.pk} ({empresa_actual.nombre})"
    }
    return render(request, 'bodega/detalle_salida_interna.html', context)

@login_required
@permission_required('bodega.view_salidainternacabecera', login_url='core:acceso_denegado')
def generar_pdf_salida_interna(request, pk):
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')
    
    salida_interna = get_object_or_404(
        SalidaInternaCabecera.objects.select_related('responsable_entrega'), 
        pk=pk, 
        empresa=empresa_actual
    )
    detalles_items = salida_interna.detalles.select_related('producto').all()
    
    logo_para_pdf = get_logo_base_64_despacho(empresa=empresa_actual)

    context_pdf = {
        'salida_interna': salida_interna,
        'detalles_items': detalles_items,
        'logo_base64': logo_para_pdf,
        'fecha_generacion': timezone.now(),
    }
    
    filename = f"Comprobante_Despacho_Empresa{empresa_actual.pk}_{salida_interna.pk}"
    
    return render_pdf_weasyprint(
        request,
        'bodega/salida_interna_pdf.html',
        context_pdf,
        filename_prefix=filename
    )

@login_required
@permission_required('bodega.view_salidainternacabecera', login_url='core:acceso_denegado')
def lista_salidas_internas(request):
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')
    
    salidas_query = SalidaInternaCabecera.objects.filter(
        empresa=empresa_actual
    ).select_related('responsable_entrega')

    # Filtros
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    tipo_salida_filtro = request.GET.get('tipo_salida_filtro')
    estado_filtro = request.GET.get('estado_filtro') # Nuevo filtro por estado

    if fecha_inicio:
        salidas_query = salidas_query.filter(fecha_hora_salida__date__gte=fecha_inicio)
    if fecha_fin:
        salidas_query = salidas_query.filter(fecha_hora_salida__date__lte=fecha_fin)
    if tipo_salida_filtro:
        salidas_query = salidas_query.filter(tipo_salida=tipo_salida_filtro)
    if estado_filtro:
        salidas_query = salidas_query.filter(estado=estado_filtro)


    salidas = salidas_query.order_by('-fecha_hora_salida')
    
    context = {
        'salidas_list': salidas,
        'titulo': f"Salidas Internas de Bodega ({empresa_actual.nombre})",
        'TIPO_SALIDA_CHOICES': SalidaInternaCabecera.TIPO_SALIDA_CHOICES, # Para el dropdown de filtro
        'ESTADO_SALIDA_CHOICES': SalidaInternaCabecera.ESTADO_SALIDA_CHOICES, # Para el dropdown de filtro de estado
        'request_get': request.GET # Para mantener los valores de los filtros en la plantilla
    }
    return render(request, 'bodega/lista_salidas_internas.html', context)

@login_required
@permission_required(['bodega.change_salidainternacabecera', 'bodega.add_movimientoinventario'], login_url='core:acceso_denegado')
def registrar_devolucion_salida_interna(request, pk_cabecera):     
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')
    
    salida_interna = get_object_or_404(
        SalidaInternaCabecera.objects.prefetch_related('detalles__producto'), 
        pk=pk_cabecera,
        empresa=empresa_actual
    )

    if salida_interna.estado in ['CERRADA', 'DEVUELTA_TOTALMENTE']:
        messages.warning(request, f"La Salida Interna #{salida_interna.pk} ya está {salida_interna.get_estado_display()} y no admite más devoluciones.")
        return redirect('bodega:detalle_salida_interna', pk=salida_interna.pk)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                algo_devuelto_en_esta_transaccion = False
                total_items_con_devolucion_valida_esta_vez = 0

                for detalle_salida in salida_interna.detalles.all():
                    input_name = f'cantidad_devuelta_{detalle_salida.pk}'
                    cantidad_a_devolver_str = request.POST.get(input_name, '0')
                    
                    try:
                        cantidad_a_devolver_ahora = int(cantidad_a_devolver_str)
                    except ValueError:
                        messages.error(request, f"Valor inválido para cantidad a devolver del producto '{detalle_salida.producto}'. Use números enteros.")
                        raise transaction.TransactionManagementError("Valor de cantidad inválido.")

                    if cantidad_a_devolver_ahora < 0:
                        messages.error(request, f"La cantidad a devolver para '{detalle_salida.producto}' no puede ser negativa.")
                        raise transaction.TransactionManagementError("Cantidad negativa.")
                    
                    pendiente_devolucion_item = detalle_salida.cantidad_pendiente_devolucion
                    if cantidad_a_devolver_ahora > pendiente_devolucion_item:
                        messages.error(request, f"Para '{detalle_salida.producto}', intenta devolver {cantidad_a_devolver_ahora} pero solo hay {pendiente_devolucion_item} pendiente(s).")
                        raise transaction.TransactionManagementError("Devolución excede cantidad pendiente.")

                    if cantidad_a_devolver_ahora > 0:
                        detalle_salida.cantidad_devuelta = F('cantidad_devuelta') + cantidad_a_devolver_ahora
                        detalle_salida.save()
                        # No es necesario refresh_from_db aquí si solo usamos F() y no leemos el valor inmediatamente en la misma transacción.
                        
                        # Mapeo para tipo de movimiento de devolución
                        tipo_mov_devolucion_map = {
                            'MUESTRARIO': 'ENTRADA_DEV_MUESTRARIO',
                            'EXHIBIDOR': 'ENTRADA_DEV_EXHIBIDOR',
                            'TRASLADO_INTERNO': 'ENTRADA_DEV_TRASLADO',
                            'PRESTAMO': 'ENTRADA_DEV_PRESTAMO',
                            'OTRO': 'ENTRADA_DEV_INTERNA_OTRA',
                        }
                        # Usar el tipo de salida original para determinar el tipo de movimiento de devolución
                        tipo_mov_str = tipo_mov_devolucion_map.get(salida_interna.tipo_salida, 'ENTRADA_DEV_INTERNA_OTRA')


                        MovimientoInventario.objects.create(
                            empresa=empresa_actual,
                            producto=detalle_salida.producto,
                            cantidad=cantidad_a_devolver_ahora, 
                            tipo_movimiento=tipo_mov_str,
                            documento_referencia=f"Dev SalidaInt #{salida_interna.pk}", # Abreviado para claridad
                            usuario=request.user,
                            notas=f"Devolución de {detalle_salida.producto} de Salida Interna #{salida_interna.pk}"
                        )
                        algo_devuelto_en_esta_transaccion = True
                        total_items_con_devolucion_valida_esta_vez +=1
                
                if algo_devuelto_en_esta_transaccion:
                    salida_interna.refresh_from_db() 
                    todos_los_items_devueltos_completamente = all(
                        d.cantidad_pendiente_devolucion == 0 for d in salida_interna.detalles.all()
                    )
                    
                    if todos_los_items_devueltos_completamente:
                        salida_interna.estado = 'DEVUELTA_TOTALMENTE'
                    else:
                        salida_interna.estado = 'DEVUELTA_PARCIAL' # Se mantiene o cambia a parcial
                    salida_interna.save(update_fields=['estado'])
                    messages.success(request, f"Devolución de {total_items_con_devolucion_valida_esta_vez} ítem(s) para Salida Interna #{salida_interna.pk} registrada. Stock actualizado.")
                else:
                    messages.info(request, "No se ingresaron cantidades para devolver en ningún ítem.")

                return redirect('bodega:detalle_salida_interna', pk=salida_interna.pk)

        except transaction.TransactionManagementError:
            pass 
        except Exception as e:
            messages.error(request, f"Error inesperado al procesar la devolución: {e}")
            
    detalles_con_pendientes = []
    hay_algo_pendiente_general = False
    for d in salida_interna.detalles.all(): # Iterar sobre los detalles ya cargados
        pendiente = d.cantidad_pendiente_devolucion
        if pendiente > 0:
            hay_algo_pendiente_general = True
        detalles_con_pendientes.append({
            'detalle_id': d.pk,
            'producto_nombre': str(d.producto), # Usar el __str__ del producto
            'producto_referencia': d.producto.referencia,
            'cantidad_despachada': d.cantidad_despachada,
            'cantidad_ya_devuelta': d.cantidad_devuelta,
            'cantidad_pendiente': pendiente
        })

    context = {
        'salida_interna': salida_interna,
        'detalles_items': detalles_con_pendientes,
        'hay_algo_pendiente_general': hay_algo_pendiente_general,
        'titulo': f'Devolución de Salida Interna #{salida_interna.pk} ({empresa_actual.nombre})'
    }
    return render(request, 'bodega/registrar_devolucion_salida_interna.html', context)


@login_required
@permission_required('bodega.view_salidainternacabecera', login_url='core:acceso_denegado')
def generar_pdf_devolucion_salida_interna(request, pk_cabecera):
    """
    Genera un PDF para el comprobante de devolución de una Salida Interna.
    Muestra los ítems que han sido devueltos.
    """
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')
    
    salida_interna = get_object_or_404(
        SalidaInternaCabecera.objects.select_related('responsable_entrega').prefetch_related('detalles__producto'),
        pk=pk_cabecera,
        empresa=empresa_actual
    )

    detalles_para_pdf = []
    for detalle in salida_interna.detalles.all():
        detalles_para_pdf.append({
            'producto_referencia': detalle.producto.referencia,
            'producto_nombre': str(detalle.producto),
            'producto_color': detalle.producto.color or "N/A",
            'producto_talla': detalle.producto.talla or "N/A",
            'cantidad_despachada': detalle.cantidad_despachada,
            'cantidad_devuelta': detalle.cantidad_devuelta,
            'cantidad_pendiente': detalle.cantidad_pendiente_devolucion,
            'observaciones_detalle': detalle.observaciones_detalle
        })
    
    
    logo_para_pdf = get_logo_base_64_despacho(empresa=empresa_actual)

    context_pdf = {
        'salida_interna': salida_interna,
        'detalles_items_devolucion': detalles_para_pdf,
        'logo_base64': logo_para_pdf,
        'fecha_generacion': timezone.now(),
        'titulo_comprobante': f"Comprobante de Devolución - Salida Interna N° {salida_interna.pk}"
    }
    
    filename = f"Comprobante_Despacho_Empresa{empresa_actual.pk}_{salida_interna.pk}"
    
    return render_pdf_weasyprint(
        request,
        'bodega/devolucion_salida_interna_pdf.html',
        context_pdf,
        filename_prefix=filename
    )


@csrf_exempt
@require_POST
def validar_item_despacho_ajax(request):
    """
    Valida un producto escaneado contra un pedido, actualizando la cantidad despachada.
    Devuelve una respuesta JSON para ser manejada por el frontend.
    """
    try:
        data = json.loads(request.body)
        pedido_id = data.get('pedido_id')
        codigo_barras = data.get('codigo_barras')

        if not pedido_id or not codigo_barras:
            return JsonResponse({'status': 'error', 'message': 'Faltan datos (pedido o código de barras).'}, status=400)

        # 1. Buscar el producto por su código de barras
        try:
            # Asegúrate que el campo en tu modelo Producto se llame 'codigo_barras'
            producto = Producto.objects.get(codigo_barras=codigo_barras, empresa=request.tenant)
        except Producto.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': f'Código de barras "{codigo_barras}" no encontrado.'}, status=404)

        # 2. Validar si el producto pertenece al pedido
        detalle = DetallePedido.objects.filter(pedido_id=pedido_id, producto=producto).first()

        if not detalle:
            return JsonResponse({'status': 'error', 'message': f'El producto "{producto}" no pertenece a este pedido.'}, status=400)

        # 3. Verificar si aún se pueden despachar unidades de este ítem
        # Usamos el campo 'cantidad_verificada' que tienes en tu input
        if detalle.cantidad_verificada >= detalle.cantidad:
            return JsonResponse({
                'status': 'warning', # Usamos 'warning' para un estado diferente
                'message': f'Todas las unidades de "{producto}" ya fueron despachadas.',
                'detalle_id': detalle.pk
            }, status=200) # Devolvemos 200 para que el success de AJAX lo maneje

        # ¡Éxito! La validación es correcta.
        # Opcional: Aquí podrías incrementar 'cantidad_verificada' en la BD si quieres persistencia en cada escaneo.
        # detalle.cantidad_verificada += 1
        # detalle.save()

        return JsonResponse({
            'status': 'success',
            'message': f'Correcto: {producto}',
            'detalle_id': detalle.pk,
            'producto_nombre': str(producto)
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Error interno del servidor: {str(e)}'}, status=500)
    
@login_required
@permission_required('bodega.view_cabeceraconteo', login_url='core:acceso_denegado')
def lista_informes_conteo(request):
    """
    Muestra una lista paginada de todos los conteos de inventario realizados.
    """
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')

    conteos_list = CabeceraConteo.objects.filter(
        empresa=empresa_actual
    ).order_by('-fecha_hora_registro')

    context = {
        'conteos_list': conteos_list,
        'titulo': f'Historial de Conteos de Inventario ({empresa_actual.nombre})',
    }
    return render(request, 'bodega/lista_informes_conteo.html', context)    
    