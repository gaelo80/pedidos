from collections import defaultdict
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse
from django.views.generic import ListView
from bodega.models import MovimientoInventario, CabeceraConteo, ConteoInventario
from django.shortcuts import render, get_object_or_404, redirect
from pedidos.models import Pedido
from django.http import Http404, JsonResponse
import openpyxl
import csv
from django.views.generic import DetailView
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from .models import BorradorDespacho, DetalleBorradorDespacho, SalidaInternaCabecera
from .forms import SalidaInternaCabeceraForm, DetalleSalidaInternaFormSet
import json
from django.utils.decorators import method_decorator
import logging
from django.conf import settings
from django.db.models import Prefetch
from pedidos.models import DetallePedido
from django.db.models import Sum
from django.core.paginator import Paginator
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

    # Prefetch para optimización de consultas
    pedido = get_object_or_404(
        Pedido.objects.prefetch_related('detalles__producto'), 
        pk=pk, 
        empresa=empresa_actual
    )
    
    # Definir los estados en los que el pedido puede ser despachado/procesado
    ESTADOS_PERMITIDOS_PARA_DESPACHO = ['APROBADO_ADMIN', 'PROCESANDO', 'PENDIENTE_BODEGA', 'LISTO_BODEGA_DIRECTO']

    # --- Lógica POST (para manejar botones de formulario tradicionales) ---
    if request.method == 'POST':
        action = request.POST.get('action') # Obtiene el valor del atributo 'name="action"' del botón submit

        try:
            with transaction.atomic():
                # Nota: La lógica de 'guardar_parcial' (cuando el botón era submit tradicional) ya no se maneja aquí.
                # Ahora es una llamada AJAX a 'guardar_parcialmente_detalle_ajax'.
                # Este bloque POST solo manejará otros submits de formulario tradicionales.

                if action == 'finalizar_pedido_incompleto': 
                    # Redirige a la vista específica que maneja esta acción
                    return redirect('bodega:finalizar_pedido_incompleto', pk=pk)

                elif action == 'cancelar_pedido_bodega': 
                    # Redirige a la vista específica que maneja esta acción
                    return redirect('bodega:cancelar_pedido_bodega', pk=pk)
                
                # Si llega aquí, significa que se envió un POST con una acción no reconocida o no esperada.
                messages.error(request, f"Acción '{action}' no válida o no implementada para este pedido.")
                # Redirige de vuelta a la misma página del despacho
                return redirect('bodega:despacho_pedido', pk=pk)

        except Exception as e:
            messages.error(request, f"Ocurrió un error inesperado al procesar la acción: {e}")
            # Si hay un error en la acción POST, redirige de nuevo a la página de despacho
            return redirect('bodega:despacho_pedido', pk=pk)

    # --- Lógica GET (cuando se muestra la página de despacho) ---
    # PRIMERO: Verificar el estado del pedido al cargar la página GET
    if pedido.estado not in ESTADOS_PERMITIDOS_PARA_DESPACHO and not request.user.is_superuser:
        messages.info(request, f"El pedido #{pedido.pk} ya está en estado '{pedido.get_estado_display()}' y no puede ser modificado aquí. Puedes revisar los comprobantes generados si aplica.")
        # Si el pedido no es modificable, redirigimos a la lista de pedidos de bodega.
        return redirect('bodega:lista_pedidos_bodega')
    
    # Si el estado es válido, procedemos a cargar los detalles
    
    # Cargar el borrador de despacho existente para este pedido
    # Se usa .first() porque unique_together = ('pedido', 'empresa') asegura que solo hay uno.
    borrador_existente = BorradorDespacho.objects.filter(
        pedido=pedido,
        empresa=empresa_actual
    ).first()
    
    # Mapear las cantidades escaneadas del borrador para inicializar el frontend
    cantidades_en_borrador_map = {}
    if borrador_existente:
        cantidades_en_borrador_map = {
            db.detalle_pedido_origen_id: db.cantidad_escaneada_en_borrador 
            for db in borrador_existente.detalles_borrador.all()
        }

    detalles_pedido = pedido.detalles.all().order_by('producto__referencia', 'producto__talla')

    items_agrupados_dict = defaultdict(lambda: {
        'referencia': '', 'nombre': '', 'color': '', 'tallas': [],
        'total_pedida': 0, 'total_verificada': 0 # total_verificada aquí es la suma de lo que está en el borrador
    })

    for detalle in detalles_pedido:
        producto_obj = detalle.producto
        clave_agrupacion = (producto_obj.referencia, producto_obj.color or '')
        
        # Cantidad acumulada en el borrador para este detalle
        # Esta es la cantidad que el frontend debe mostrar como "Despachado" en la UI de escaneo
        cantidad_a_mostrar_en_frontend = cantidades_en_borrador_map.get(detalle.pk, 0) 

        if not items_agrupados_dict[clave_agrupacion]['referencia']:
            items_agrupados_dict[clave_agrupacion]['referencia'] = producto_obj.referencia
            items_agrupados_dict[clave_agrupacion]['nombre'] = producto_obj.nombre
            items_agrupados_dict[clave_agrupacion]['color'] = producto_obj.color or ''

        items_agrupados_dict[clave_agrupacion]['tallas'].append({
            'nombre': producto_obj.talla or '',
            'detalle': { 
                'id': detalle.pk,
                'codigo_barras': producto_obj.codigo_barras or '', 
                'cantidad_pedida': detalle.cantidad,
                'cantidad_verificada': cantidad_a_mostrar_en_frontend, # Cantidad del borrador para el frontend
            }
        })
        items_agrupados_dict[clave_agrupacion]['total_pedida'] += detalle.cantidad
        items_agrupados_dict[clave_agrupacion]['total_verificada'] += cantidad_a_mostrar_en_frontend # Suma de lo que está en el borrador

    detalles_json_data = list(items_agrupados_dict.values())
    detalles_json_data.sort(key=lambda x: (x['referencia'], x['color']))
    detalles_json = json.dumps(detalles_json_data) 
    
    context = {
        'pedido': pedido,
        'detalles_pedido': detalles_pedido, # Aún útil para los enlaces y otros datos, pero NO para cantidad_verificada
        'detalles_json': detalles_json, # JSON que ahora incluye cantidades del borrador
        'titulo': f"Despacho Pedido #{pedido.pk}",
    }
    return render(request, 'bodega/despacho_pedido.html', context)

@csrf_exempt
@require_POST
@login_required
@permission_required('pedidos.change_pedido', login_url='core:acceso_denegado')
def guardar_parcialmente_detalle_ajax(request, pk): # 'pk' es el pedido_id
    """
    Guarda el progreso de la verificación (cantidades escaneadas en borrador) de uno o más DetallePedido
    en el modelo BorradorDespacho. No afecta DetallePedido.cantidad_verificada ni genera comprobantes.
    """
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        logger.error("Error: Empresa no identificada en guardar_parcialmente_detalle_ajax.")
        return JsonResponse({'status': 'error', 'message': 'Empresa no identificada.'}, status=400)

    try:
        data = json.loads(request.body)
        detalles_a_guardar_frontend = data.get('detalles_a_guardar', [])

        if not detalles_a_guardar_frontend:
            return JsonResponse({'status': 'info', 'message': 'No se enviaron detalles para guardar.'}, status=200)

        with transaction.atomic():
            pedido = get_object_or_404(Pedido, pk=pk, empresa=empresa_actual)

            # Obtener o crear el borrador para este pedido y usuario
            borrador, _ = BorradorDespacho.objects.get_or_create(
                pedido=pedido,
                empresa=empresa_actual,
                defaults={'usuario': request.user}
            )

            # Mapear los detalles del pedido original y los del borrador existente
            detalles_pedido_map = {d.pk: d for d in pedido.detalles.select_for_update()} # Bloquear los DetallePedido
            detalles_borrador_map = {
                db.detalle_pedido_origen_id: db 
                for db in borrador.detalles_borrador.select_for_update() # Bloquear los DetalleBorradorDespacho
            }

            cambios_realizados = 0
            for item_data in detalles_a_guardar_frontend:
                detalle_id = item_data.get('id')
                cantidad_escaneada_borrador = item_data.get('cantidad_verificada_nueva') # Es la cantidad de escaneos para el borrador

                if detalle_id is None or cantidad_escaneada_borrador is None:
                    logger.warning(f"DEBUG: Detalle con datos incompletos en el payload: {item_data}")
                    continue

                try:
                    cantidad_escaneada_borrador = int(cantidad_escaneada_borrador)
                    if cantidad_escaneada_borrador < 0:
                        logger.warning(f"DEBUG: Cantidad negativa para detalle {detalle_id}: {cantidad_escaneada_borrador}")
                        continue
                except ValueError:
                    logger.warning(f"DEBUG: Cantidad no válida para detalle {detalle_id}: {cantidad_escaneada_borrador}")
                    continue

                detalle_original = detalles_pedido_map.get(detalle_id)
                if not detalle_original:
                    logger.warning(f"DEBUG: Detalle {detalle_id} no encontrado o no pertenece a este pedido/empresa.")
                    continue

                # Validar que la cantidad escaneada en borrador no exceda la pedida original
                if cantidad_escaneada_borrador > detalle_original.cantidad:
                    logger.warning(f"DEBUG: Exceso de cantidad para {detalle_original.producto.referencia}: {cantidad_escaneada_borrador} > {detalle_original.cantidad}.")
                    # Aquí puedes decidir si lanzar un error fatal o simplemente ignorar el exceso
                    cantidad_escaneada_borrador = detalle_original.cantidad # Limitar al máximo pedido

                detalle_borrador_obj = detalles_borrador_map.get(detalle_id)

                if detalle_borrador_obj: # Si ya existe un detalle de borrador para este DetallePedido
                    if detalle_borrador_obj.cantidad_escaneada_en_borrador != cantidad_escaneada_borrador:
                        detalle_borrador_obj.cantidad_escaneada_en_borrador = cantidad_escaneada_borrador
                        detalle_borrador_obj.save(update_fields=['cantidad_escaneada_en_borrador'])
                        cambios_realizados += 1
                        logger.info(f"DetalleBorradorDespacho {detalle_borrador_obj.pk} actualizado. Cant. Borrador: {cantidad_escaneada_borrador}.")
                else: # Si no existe, crear uno nuevo
                    DetalleBorradorDespacho.objects.create(
                        borrador_despacho=borrador,
                        detalle_pedido_origen=detalle_original,
                        producto=detalle_original.producto, # El producto del detalle original
                        cantidad_escaneada_en_borrador=cantidad_escaneada_borrador
                    )
                    cambios_realizados += 1
                    logger.info(f"Nuevo DetalleBorradorDespacho creado para {detalle_original.pk}. Cant. Borrador: {cantidad_escaneada_borrador}.")

            # Actualizar el estado del pedido a 'PROCESANDO' si se guarda progreso
            if cambios_realizados > 0 and pedido.estado in ['APROBADO_ADMIN', 'PROCESANDO', 'PENDIENTE_BODEGA', 'LISTO_BODEGA_DIRECTO']:
                pedido.estado = 'PROCESANDO'
                pedido.save(update_fields=['estado'])
                logger.info(f"Pedido {pedido.pk} estado cambiado a PROCESANDO.")

            if cambios_realizados > 0:
                return JsonResponse({'status': 'success', 'message': f'Progreso de {cambios_realizados} ítems guardado exitosamente.'})
            else:
                return JsonResponse({'status': 'info', 'message': 'No se detectaron cambios significativos para guardar.'})

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Formato JSON inválido.'}, status=400)
    except Exception as e:
        logger.error(f"Error inesperado en guardar_parcialmente_detalle_ajax para pedido {pk}: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': f'Error interno del servidor: {str(e)}'}, status=500)
    
    
@csrf_exempt
@require_POST
@login_required
@permission_required('pedidos.change_pedido', login_url='core:acceso_denegado')
def enviar_despacho_parcial_ajax(request, pk):
    """
    Procesa un envío parcial del despacho, tomando las cantidades del BorradorDespacho,
    generando un ComprobanteDespacho por esas cantidades, actualizando DetallePedido.cantidad_verificada
    y eliminando el borrador. NO AFECTA INVENTARIO DIRECTAMENTE.
    """
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        logger.error("Error: Empresa no identificada en enviar_despacho_parcial_ajax.")
        return JsonResponse({'status': 'error', 'message': 'Empresa no identificada.'}, status=400)

    try:
        with transaction.atomic():
            pedido = get_object_or_404(
                Pedido.objects.select_for_update().prefetch_related('detalles'), 
                pk=pk, 
                empresa=empresa_actual
            )

            ESTADOS_PERMITIDOS_ENVIO = ['APROBADO_ADMIN', 'PROCESANDO', 'PENDIENTE_BODEGA']
            if pedido.estado not in ESTADOS_PERMITIDOS_ENVIO and not request.user.is_superuser:
                logger.warning(f"DEBUG: Pedido {pk} en estado no permitido ({pedido.get_estado_display()}) para envío.")
                raise ValueError(f"El pedido #{pedido.pk} no puede ser enviado en su estado actual ({pedido.get_estado_display()}).")

            # Obtener el borrador de despacho para este pedido
            borrador = BorradorDespacho.objects.filter(pedido=pedido, empresa=empresa_actual).first()

            if not borrador or not borrador.detalles_borrador.exists():
                logger.warning("DEBUG: No hay borrador de despacho o no tiene ítems para este pedido. No se puede enviar.")
                return JsonResponse({'status': 'warning', 'message': 'No hay unidades escaneadas en borrador para enviar.'}, status=200)

            items_para_este_comprobante = []
            detalles_pedido_actualizados = [] # Para actualizar DetallePedido.cantidad_verificada

            # Iterar sobre los detalles del borrador para construir el comprobante
            for detalle_borrador in borrador.detalles_borrador.select_for_update():
                detalle_original = detalle_borrador.detalle_pedido_origen # El DetallePedido original

                cantidad_a_comprobar_en_esta_op = detalle_borrador.cantidad_escaneada_en_borrador

                if cantidad_a_comprobar_en_esta_op > 0:
                    items_para_este_comprobante.append({
                        'producto': detalle_original.producto, # Producto del detalle original
                        'cantidad_despachada': cantidad_a_comprobar_en_esta_op, # Cantidad del borrador
                        'detalle_pedido_origen': detalle_original
                    })

                    # Preparar la actualización de DetallePedido.cantidad_verificada (acumulada total)
                    # Sumar lo que ya estaba en DetallePedido.cantidad_verificada + lo que viene del borrador
                    detalle_original.cantidad_verificada = (detalle_original.cantidad_verificada or 0) + cantidad_a_comprobar_en_esta_op
                    detalle_original.verificado_bodega = True
                    detalles_pedido_actualizados.append(detalle_original)

                # Eliminar el detalle del borrador después de procesarlo para el comprobante
                detalle_borrador.delete() # Esto eliminará el detalle de borrador

            # Después de procesar todos los detalles, si el borrador está vacío, eliminarlo
            if not borrador.detalles_borrador.exists():
                borrador.delete()
                logger.info(f"DEBUG: Borrador de despacho {borrador.pk} eliminado al estar vacío.")

            if not items_para_este_comprobante:
                logger.warning("DEBUG: Aunque había borrador, ninguna unidad con cantidad > 0 fue encontrada para el comprobante.")
                return JsonResponse({'status': 'warning', 'message': 'No se detectaron unidades para despachar en el borrador.'}, status=200)

            # Crear el ComprobanteDespacho
            comprobante = ComprobanteDespacho.objects.create(
                pedido=pedido,
                empresa=empresa_actual,
                fecha_hora_despacho=timezone.now(),
                usuario_responsable=request.user,
                # es_parcial se determinará después de actualizar los DetallePedido
            )
            logger.info(f"DEBUG: Comprobante {comprobante.pk} creado.")

            # Bulk create los DetalleComprobanteDespacho
            detalles_comprobante_bulk_create = []
            for item_data in items_para_este_comprobante:
                detalles_comprobante_bulk_create.append(
                    DetalleComprobanteDespacho(
                        comprobante_despacho=comprobante,
                        producto=item_data['producto'],
                        cantidad_despachada=item_data['cantidad_despachada'],
                        detalle_pedido_origen=item_data['detalle_pedido_origen']
                    )
                )
            DetalleComprobanteDespacho.objects.bulk_create(detalles_comprobante_bulk_create)
            logger.info(f"DEBUG: {len(detalles_comprobante_bulk_create)} detalles creados para comprobante.")

            # Actualizar DetallePedido.cantidad_verificada para reflejar el acumulado real
            DetallePedido.objects.bulk_update(detalles_pedido_actualizados, ['cantidad_verificada', 'verificado_bodega'])
            logger.info(f"DEBUG: {len(detalles_pedido_actualizados)} DetallePedido actualizados con nuevas cantidades verificadas.")

            # *** ELIMINAR CREACIÓN DE MovimientoInventario AQUÍ ***
            # Esto es crucial porque el inventario se descuenta al tomar el pedido.
            # for item_data in items_para_este_comprobante:
            #     MovimientoInventario.objects.create(...) 
            # ******************************************************

            # Actualizar el estado del pedido y el comprobante es_parcial
            pedido.refresh_from_db() # Refrescar para que tenga los nuevos valores de cantidad_verificada
            todos_los_items_despachados_completamente = all(
                (d.cantidad_verificada or 0) >= d.cantidad for d in pedido.detalles.all()
            )

            comprobante.es_parcial = not todos_los_items_despachados_completamente
            comprobante.save(update_fields=['es_parcial']) # Guardar el campo es_parcial del comprobante

            if todos_los_items_despachados_completamente:
                pedido.estado = 'ENVIADO' # O 'COMPLETADO'
                messages.success(request, f"Pedido #{pedido.pk} completamente despachado y enviado.")
                logger.info(f"DEBUG: Pedido {pk} marcado como ENVIADO.")
            elif pedido.estado in ['APROBADO_ADMIN', 'PENDIENTE_BODEGA']:
                pedido.estado = 'PROCESANDO'
                messages.info(request, f"Despacho parcial del Pedido #{pedido.pk} enviado.")
                logger.info(f"DEBUG: Pedido {pk} marcado como PROCESANDO.")

            pedido.save(update_fields=['estado'])

            from factura.models import EstadoFacturaDespacho # Asegúrate de importar
            EstadoFacturaDespacho.objects.create(empresa=empresa_actual, despacho=comprobante)
            logger.info("DEBUG: EstadoFacturaDespacho creado para el nuevo comprobante.")

            comprobante_url = reverse('bodega:imprimir_comprobante_especifico', kwargs={'pk_comprobante': comprobante.pk})

            return JsonResponse({'status': 'success', 'message': 'Despacho enviado con éxito.', 'comprobante_url': comprobante_url})

    except ValueError as e:
        logger.error(f"Error de validación en enviar_despacho_parcial_ajax para pedido {pk}: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': f'Error de datos: {str(e)}'}, status=400)
    except DetallePedido.DoesNotExist as e:
        logger.error(f"Detalle de pedido no encontrado en enviar_despacho_parcial_ajax para pedido {pk}: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Uno o más detalles de pedido no encontrados o no pertenecen a este pedido.'}, status=404)
    except Exception as e:
        logger.critical(f"Error inesperado y crítico en enviar_despacho_parcial_ajax para pedido {pk}: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': f'Error interno del servidor al enviar despacho: {str(e)}'}, status=500)

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
    estados_por_defecto = ['APROBADO_ADMIN', 'PROCESANDO', 'LISTO_BODEGA_DIRECTO'] # Estados a mostrar si no se filtra

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

@require_POST
@login_required
@permission_required('pedidos.change_pedido', login_url='core:acceso_denegado')
def finalizar_pedido_incompleto(request, pk):
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')

    try:
        with transaction.atomic():
            pedido = get_object_or_404(Pedido.objects.select_for_update().prefetch_related('detalles__producto'), pk=pk, empresa=empresa_actual)

            if pedido.estado == 'ENVIADO' or pedido.estado == 'ENTREGADO' or pedido.estado == 'CANCELADO':
                messages.warning(request, f"El pedido #{pedido.pk} ya está en un estado final y no puede ser marcado como incompleto.")
                return redirect('bodega:lista_pedidos_bodega')
            
            # Eliminar cualquier borrador de despacho pendiente para este pedido
            BorradorDespacho.objects.filter(pedido=pedido, empresa=empresa_actual).delete()
            logger.info(f"DEBUG: Borrador de despacho para Pedido {pedido.pk} eliminado al finalizar incompleto.")

            # Actualizar el estado de los detalles del pedido y REINTRODUCIR MovimientoInventario para pendientes
            for detalle in pedido.detalles.all():
                cantidad_pendiente = detalle.cantidad - (detalle.cantidad_verificada or 0)
                if cantidad_pendiente > 0:
                    # REINTRODUCIR: Crear MovimientoInventario para las cantidades que VUELVEN
                    MovimientoInventario.objects.create(
                        empresa=empresa_actual,
                        producto=detalle.producto,
                        cantidad=cantidad_pendiente, # Cantidad positiva para entrada
                        tipo_movimiento='ENTRADA_CANCELACION', # Tipo que indica que regresa por cancelación
                        documento_referencia=f"Devolución por Pedido Incompleto {pedido.pk}",
                        usuario=request.user,
                        notas=f"Devolución de {cantidad_pendiente} unidades no despachadas del pedido {pedido.pk}"
                    )
                    logger.info(f"DEBUG: MovimientoInventario de ENTRADA para {cantidad_pendiente} de {detalle.producto.referencia} (Pedido {pedido.pk}) al finalizar incompleto.")
                
                # Opcional: Podrías querer setear cantidad_verificada a su cantidad total para asegurar la "finalización" lógica
                # pero para el borrador y la lógica actual, ya estará en el valor despachado.
                # Si el objetivo es que la cantidad verificada refleje solo lo *despachado*, no la toques aquí.

            pedido.estado = 'ENVIADO_INCOMPLETO' # O un estado similar que indique el cierre
            pedido.save(update_fields=['estado'])
            messages.success(request, f"Pedido #{pedido.pk} marcado como INCOMPLETO. Las unidades pendientes han regresado al inventario.")

    except Exception as e:
        messages.error(request, f"Error al finalizar pedido incompleto: {e}")
        logger.error(f"Error en finalizar_pedido_incompleto: {e}", exc_info=True)
    
    return redirect('bodega:lista_pedidos_bodega')

@require_POST
@login_required
@permission_required('pedidos.change_pedido', login_url='core:acceso_denegado')
def cancelar_pedido_bodega(request, pk):
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')

    try:
        with transaction.atomic():
            pedido = get_object_or_404(Pedido.objects.select_for_update().prefetch_related('detalles__producto'), pk=pk, empresa=empresa_actual)

            if pedido.estado == 'ENVIADO' or pedido.estado == 'ENTREGADO' or pedido.estado == 'CANCELADO':
                messages.warning(request, f"El pedido #{pedido.pk} ya está en un estado final y no puede ser cancelado.")
                return redirect('bodega:lista_pedidos_bodega')

            # Eliminar cualquier borrador de despacho pendiente para este pedido
            BorradorDespacho.objects.filter(pedido=pedido, empresa=empresa_actual).delete()
            logger.info(f"DEBUG: Borrador de despacho para Pedido {pedido.pk} eliminado al cancelar.")

            # Reintroducir MovimientoInventario para TODAS las unidades pedidas
            for detalle in pedido.detalles.all():
                cantidad_a_devolver = detalle.cantidad # Se devuelve toda la cantidad pedida
                if cantidad_a_devolver > 0:
                    # REINTRODUCIR: Crear MovimientoInventario para todas las cantidades que VUELVEN
                    MovimientoInventario.objects.create(
                        empresa=empresa_actual,
                        producto=detalle.producto,
                        cantidad=cantidad_a_devolver, # Cantidad positiva para entrada
                        tipo_movimiento='ENTRADA_CANCELACION', # Tipo que indica que regresa por cancelación
                        documento_referencia=f"Devolución por Cancelación Pedido {pedido.pk}",
                        usuario=request.user,
                        notas=f"Devolución de {cantidad_a_devolver} unidades del pedido cancelado {pedido.pk}"
                    )
                    logger.info(f"DEBUG: MovimientoInventario de ENTRADA para {cantidad_a_devolver} de {detalle.producto.referencia} (Pedido {pedido.pk}) al cancelar.")
                
                # Opcional: Resetear cantidad_verificada a 0 al cancelar el pedido completamente
                detalle.cantidad_verificada = 0
                detalle.save(update_fields=['cantidad_verificada'])


            pedido.estado = 'CANCELADO'
            pedido.save(update_fields=['estado'])
            messages.success(request, f"Pedido #{pedido.pk} CANCELADO exitosamente. Todas las unidades han regresado al inventario.")

    except Exception as e:
        messages.error(request, f"Error al cancelar el pedido: {e}")
        logger.error(f"Error en cancelar_pedido_bodega: {e}", exc_info=True)
    
    return redirect('bodega:lista_pedidos_bodega')

@login_required
# Asegúrate que el permiso sea el adecuado para tu app, ej: 'productos.view_producto'
@permission_required('productos.view_inventory_report', login_url='core:acceso_denegado')
def vista_informe_inventario(request):
    """
    Muestra un informe completo y paginado del inventario físico en bodega,
    con opciones de filtrado.
    """
    empresa_actual = getattr(request, 'tenant', None)
    
    # Query base: solo productos activos de la empresa actual
    productos_queryset = Producto.objects.filter(
        empresa=empresa_actual, 
        activo=True
    ).order_by('referencia', 'color', 'talla')

    # Lógica de filtrado
    referencia_q = request.GET.get('referencia', '').strip()
    nombre_q = request.GET.get('nombre', '').strip()
    ubicacion_q = request.GET.get('ubicacion', '').strip()

    if referencia_q:
        productos_queryset = productos_queryset.filter(referencia__icontains=referencia_q)
    if nombre_q:
        productos_queryset = productos_queryset.filter(nombre__icontains=nombre_q)
    if ubicacion_q:
        productos_queryset = productos_queryset.filter(ubicacion__icontains=ubicacion_q)

    # Calcular totales (después de filtrar)
    total_productos = productos_queryset.count()
    total_unidades = sum(p.stock_actual for p in productos_queryset)
    
    # Paginación
    paginator = Paginator(productos_queryset, 25) # Muestra 25 productos por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'productos': page_obj, # El objeto de página, no el queryset completo
        'titulo': f'Informe de Inventario Físico ({empresa_actual.nombre})',
        'total_productos': total_productos,
        'total_unidades': total_unidades,
        'filtros_activos': request.GET # Para mantener los filtros en la paginación y exportación
    }
    return render(request, 'bodega/informe_inventario.html', context)


@login_required
@permission_required('productos.view_producto', login_url='core:acceso_denegado')
def exportar_inventario_excel(request):
    """
    Genera y descarga un archivo Excel con el inventario actual,
    aplicando los mismos filtros que la vista del informe.
    """
    empresa_actual = getattr(request, 'tenant', None)
    productos_queryset = Producto.objects.filter(
        empresa=empresa_actual, 
        activo=True
    ).order_by('referencia', 'color', 'talla')

    # Re-aplicar los mismos filtros que en la vista principal
    referencia_q = request.GET.get('referencia', '').strip()
    nombre_q = request.GET.get('nombre', '').strip()
    ubicacion_q = request.GET.get('ubicacion', '').strip()

    if referencia_q:
        productos_queryset = productos_queryset.filter(referencia__icontains=referencia_q)
    if nombre_q:
        productos_queryset = productos_queryset.filter(nombre__icontains=nombre_q)
    if ubicacion_q:
        productos_queryset = productos_queryset.filter(ubicacion__icontains=ubicacion_q)
    
    # Crear el archivo Excel en memoria
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = 'Inventario'

    # Escribir la cabecera
    headers = ['Referencia', 'Descripción', 'Detalle', 'Color', 'Talla', 'Ubicación', 'Cantidad en Stock']
    sheet.append(headers)

    # Escribir los datos de los productos
    for producto in productos_queryset:
        sheet.append([
            producto.referencia,
            producto.nombre,
            producto.descripcion or '',
            producto.color or '',
            producto.talla or '',
            producto.ubicacion or '',
            producto.stock_actual
        ])

    # Preparar la respuesta HTTP
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="informe_inventario.xlsx"'
    workbook.save(response)

    return response

class InformeMovimientoInventarioView(TenantAwareMixin, LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = MovimientoInventario
    template_name = 'bodega/informe_movimiento_inventario.html'
    context_object_name = 'movimiento'
    
    permission_required = 'bodega.view_movimientoinventario' 
    login_url = 'core:acceso_denegado'

    def dispatch(self, request, *args, **kwargs):
        logger.debug(f"--- Iniciando dispatch para InformeMovimientoInventarioView ---")
        logger.debug(f"Usuario autenticado: {request.user.is_authenticated}")
        logger.debug(f"Usuario: {request.user.username}")
        logger.debug(f"Inquilino (request.tenant): {getattr(request, 'tenant', 'NO DISPONIBLE')}")
        
        # Verificar el permiso antes de llamar a super().dispatch()
        # PermissionRequiredMixin hace su chequeo aquí.
        # Puedes añadir un try-except para capturar PermissionDenied si quieres un manejo más específico.
        
        # Verifica si el usuario tiene el permiso requerido
        if not request.user.has_perm(self.permission_required):
            logger.warning(f"Permiso '{self.permission_required}' denegado para el usuario {request.user.username}")
            # Aquí se ejecutará handle_no_permission
            return self.handle_no_permission()

        logger.debug(f"Permiso '{self.permission_required}' CONCEDIDO para el usuario {request.user.username}")
        return super().dispatch(request, *args, **kwargs)

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para acceder a este informe de movimiento de inventario.")
        logger.warning(f"Redirigiendo a 'core:index' por falta de permisos para {self.request.user.username}")
        return redirect('core:index')

    def get_queryset(self):
        queryset = super().get_queryset()
        current_tenant = getattr(self.request, 'tenant', None)
        logger.debug(f"get_queryset: Inquilino actual: {current_tenant}")
        if current_tenant:
            queryset = queryset.filter(empresa=current_tenant)
            logger.debug(f"get_queryset: Filtrando por empresa: {current_tenant.nombre}")
        else:
            logger.error("get_queryset: request.tenant no está disponible. Esto podría ser un problema de middleware.")
        return queryset.select_related('producto', 'usuario')

    def get_object(self, queryset=None):
        logger.debug(f"--- Iniciando get_object ---")
        if queryset is None:
            queryset = self.get_queryset()
        
        pk = self.kwargs.get(self.pk_url_kwarg)
        logger.debug(f"get_object: PK de la URL: {pk}")
        
        obj = get_object_or_404(queryset, pk=pk)
        logger.debug(f"get_object: Objeto encontrado: {obj}")
        
        # Una verificación adicional a nivel de objeto (si tu sistema de inquilinos lo requiere)
        current_tenant = getattr(self.request, 'tenant', None)
        if current_tenant and obj.empresa != current_tenant:
            logger.error(f"get_object: Acceso denegado a objeto de otro inquilino. Objeto ID: {obj.pk}, Inquilino del objeto: {obj.empresa.nombre}, Inquilino actual: {current_tenant.nombre}")
            raise Http404("No se encontró el objeto o no tienes permiso para acceder a él.") # O PermissionDenied
        
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        movimiento = context.get('movimiento')
        if movimiento:
            context['producto'] = movimiento.producto 
            context['titulo'] = f'Detalles del Movimiento #{movimiento.pk} ({self.request.tenant.nombre})'
            logger.debug(f"get_context_data: Contexto preparado para movimiento {movimiento.pk}")
        else:
            logger.error("get_context_data: No se encontró el objeto 'movimiento' en el contexto.")
        return context