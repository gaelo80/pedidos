# pedidos/views.py
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction
from django.template.loader import get_template
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Q, Sum
from django.views.decorators.http import require_POST
from django.views import View
from urllib.parse import quote
from django.contrib.auth.models import User
import json
import re
from django.contrib.auth.decorators import login_required, permission_required
from .serializers import PedidoSerializer
from weasyprint import HTML
from rest_framework import viewsets, serializers
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from .models import Pedido, DetallePedido
from .forms import PedidoForm
from productos.models import Producto
from vendedores.models import Vendedor
from bodega.models import MovimientoInventario
from core.auth_utils import es_admin_sistema_app, es_bodega, es_vendedor, es_cartera
from core.utils import get_logo_base_64_despacho
from .utils import preparar_datos_seccion


def es_admin_sistema(user):
    """Verifica si el usuario tiene rol para la lista de aprobación de Administración."""
    if not user.is_authenticated:
        return False
    return user.is_staff or user.groups.filter(name='Administracion').exists()

def es_factura(user):
    """Verifica si el usuario tiene rol para la lista de aprobación de Administración."""
    if not user.is_authenticated:
        return False
    return user.is_staff or user.groups.filter(name='Factura').exists()


class PedidoViewSet(viewsets.ModelViewSet):
    serializer_class = PedidoSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Pedido.objects.none()
        if user.is_staff or user.is_superuser:
            return Pedido.objects.all().order_by('-fecha_hora')
        else:
            try:
                vendedor = Vendedor.objects.get(user=user)
                return Pedido.objects.filter(vendedor=vendedor).order_by('-fecha_hora')
            except Vendedor.DoesNotExist:
                return Pedido.objects.none()

    def perform_create(self, serializer):
        try:
            vendedor = Vendedor.objects.get(user=self.request.user)
            # El estado inicial para la API debería ser 'PENDIENTE_APROBACION_CARTERA'
            # si sigue el mismo flujo que la creación web.
            serializer.save(vendedor=vendedor, estado='PENDIENTE_APROBACION_CARTERA')
        except Vendedor.DoesNotExist:
            raise serializers.ValidationError(
                "El usuario que realiza la solicitud no tiene un perfil de vendedor asociado."
            )

@login_required
@permission_required('pedidos.add_pedido', login_url='core:acceso_denegado')
def vista_crear_pedido_web(request, pk=None):
    vendedor = None
    try:
        if hasattr(request.user, 'perfil_vendedor'):
             vendedor = request.user.perfil_vendedor
        elif request.user.is_staff or es_admin_sistema_app(request.user):
            pass
        else:
            messages.error(request, "Perfil de vendedor no encontrado y no es usuario administrador.")
            return redirect('core:acceso_denegado')
    except Vendedor.DoesNotExist:
        if not (request.user.is_staff or es_admin_sistema_app(request.user)):
            messages.error(request, "Perfil de vendedor no encontrado.")
            return redirect('core:acceso_denegado')
    except AttributeError:
        if not (request.user.is_staff or es_admin_sistema_app(request.user)):
            messages.error(request, "Atributo de perfil de vendedor no encontrado.")
            return redirect('core:acceso_denegado')

    pedido_instance = None
    detalles_existentes = None
    if pk is not None:
        query_params = {'pk': pk, 'estado': 'BORRADOR'}
        if vendedor and not (request.user.is_staff or es_admin_sistema_app(request.user)):
            query_params['vendedor'] = vendedor
        pedido_instance = get_object_or_404(Pedido, **query_params)
        detalles_existentes = pedido_instance.detalles.select_related('producto').all()

    if request.method == 'POST':
        form_instance = pedido_instance
        pedido_form = PedidoForm(request.POST, instance=form_instance)
        accion = request.POST.get('accion')
     
        detalles_para_crear = []
        errores_stock = []
        errores_generales = []
        al_menos_un_detalle = False

        for key, value in request.POST.items():
            if key.startswith('cantidad_') and value:
                try:
                    producto_id_str = key.split('_')[1]
                    producto_id = int(producto_id_str)
                    cantidad_pedida = int(value)
                    if cantidad_pedida > 0:
                        al_menos_un_detalle = True
                        try:
                            producto_variante = Producto.objects.get(pk=producto_id, activo=True)
                            detalles_para_crear.append({
                                'producto': producto_variante,
                                'cantidad': cantidad_pedida,
                                'precio_unitario': producto_variante.precio_venta,
                                'stock_disponible': producto_variante.stock_actual
                            })
                        except Producto.DoesNotExist:
                            errores_generales.append(f"Producto ID {producto_id} no encontrado o inactivo.")
                    elif cantidad_pedida < 0:
                        errores_generales.append(f"Cantidad negativa no permitida para producto ID {producto_id}.")
                except (ValueError, TypeError, IndexError):
                    errores_generales.append(f"Dato inválido en campo '{key}' (valor: '{value}').")
        
        if errores_generales:
            for error in errores_generales: messages.error(request, error)

        if pedido_form.is_valid() and not errores_generales:
            if accion == 'crear_definitivo':
                print("DEBUG PEDIDO-STOCK: Entrando a lógica de 'crear_definitivo'") # <<<< PRINT 2
                stock_suficiente_para_crear = True
                if not al_menos_un_detalle:
                    messages.error(request, "Debes agregar al menos un producto para crear el pedido.")
                    stock_suficiente_para_crear = False
                    print("DEBUG PEDIDO-STOCK: 'al_menos_un_detalle' es False") # <<<< PRINT 3
                else:
                    for detalle_data_check in detalles_para_crear:
                        if detalle_data_check['cantidad'] > detalle_data_check['producto'].stock_actual:
                            stock_suficiente_para_crear = False
                            errores_stock.append(f"Stock insuficiente para '{detalle_data_check['producto']}'. Pedido: {detalle_data_check['cantidad']}, Disp: {detalle_data_check['producto'].stock_actual}")
                
                if not stock_suficiente_para_crear:
                    for error in errores_stock: messages.error(request, error)
                    print(f"DEBUG PEDIDO-STOCK: 'stock_suficiente_para_crear' es False. Errores: {errores_stock}") # <<<< PRINT 4
                
                if not errores_generales and stock_suficiente_para_crear: # Condición combinada
                    print("DEBUG PEDIDO-STOCK: Condiciones previas a transacción CUMPLIDAS.") # <<<< PRINT 5
                    try:
                        with transaction.atomic():
                            pedido = pedido_form.save(commit=False)
                            
                            if vendedor:
                                pedido.vendedor = vendedor
                            elif request.user.is_staff or es_admin_sistema_app(request.user):
                                # Aquí debes definir cómo se asigna un vendedor si un admin crea el pedido
                                # Por ejemplo, si el PedidoForm tuviera un campo 'vendedor' para admins:
                                # if 'vendedor' in pedido_form.cleaned_data and pedido_form.cleaned_data['vendedor']:
                                #     pedido.vendedor = pedido_form.cleaned_data['vendedor']
                                # else:
                                #     Si es obligatorio y no se puede determinar, lanzar error
                                pass # Temporalmente

                            if not pedido.vendedor:
                                print("DEBUG PEDIDO-STOCK: ERROR VENDEDOR - Vendedor no asignado!") # <<<< PRINT 6
                                messages.error(request, "El vendedor es obligatorio para crear el pedido.")
                                raise Exception("Vendedor no asignado y es obligatorio.")

                            pedido.estado = 'PENDIENTE_APROBACION_CARTERA'
                            pedido.save()
                            print(f"DEBUG PEDIDO-STOCK: Pedido #{pedido.pk} guardado con estado {pedido.estado}.") # <<<< PRINT 7

                            productos_guardados_ids = set()
                            detalles_guardados_para_movimiento = []
                            for detalle_data in detalles_para_crear:
                                producto_obj = detalle_data['producto']
                                detalle_obj, created = DetallePedido.objects.update_or_create(
                                    pedido=pedido, producto=producto_obj,
                                    defaults={'cantidad': detalle_data['cantidad'], 'precio_unitario': detalle_data['precio_unitario']}
                                )
                                productos_guardados_ids.add(producto_obj.pk)
                                detalles_guardados_para_movimiento.append(detalle_obj)

                            if form_instance:
                                DetallePedido.objects.filter(pedido=pedido).exclude(producto_id__in=productos_guardados_ids).delete()
                            
                            print(f"DEBUG PEDIDO-STOCK: No. Detalles para movimiento = {len(detalles_guardados_para_movimiento)}") # <<<< PRINT 8
                            if not detalles_guardados_para_movimiento:
                                print("DEBUG PEDIDO-STOCK: ADVERTENCIA - No hay detalles para crear movimientos de inventario.") # <<<< PRINT 9

                            for detalle_final_mov in detalles_guardados_para_movimiento:
                                print(f"DEBUG PEDIDO-STOCK: Creando MovInv para Prod ID {detalle_final_mov.producto.id}, Cant: {-detalle_final_mov.cantidad}") # <<<< PRINT 10
                                MovimientoInventario.objects.create(
                                    producto=detalle_final_mov.producto,
                                    cantidad= -detalle_final_mov.cantidad,
                                    tipo_movimiento='SALIDA_VENTA_PENDIENTE',
                                    documento_referencia=f'Pedido #{pedido.pk} (Creado)',
                                    usuario=request.user,
                                    notas=f'Salida por creación de pedido #{pedido.pk} (pendiente aprobación)'
                                )
                            print("DEBUG PEDIDO-STOCK: Bucle de MovInv terminado.") # <<<< PRINT 11
                            
                            messages.success(request, f"Pedido #{pedido.pk} creado y enviado a aprobación. Stock descontado.")
                            return redirect('pedidos:pedido_creado_exito', pk=pedido.pk)
                    except Exception as e:
                        print(f"DEBUG PEDIDO-STOCK: EXCEPCIÓN en transacción: {e}") # <<<< PRINT 12
                        import traceback
                        traceback.print_exc() # Imprime el traceback completo en la consola
                        messages.error(request, f"Error inesperado al guardar el pedido definitivo: {e}")
                else:
                     print("DEBUG PEDIDO-STOCK: NO SE CUMPLIÓ 'stock_suficiente_para_crear' o había 'errores_generales'.") # <<<< PRINT 13

            elif accion == 'guardar_borrador':
                try:
                    with transaction.atomic():
                        pedido = pedido_form.save(commit=False)
                        if vendedor:
                            pedido.vendedor = vendedor
                        elif not pedido.vendedor and (request.user.is_staff or es_admin_sistema_app(request.user)):
                             pass # Lógica de asignación de vendedor para admin en borradores
                        
                        if not pedido.vendedor:
                            messages.error(request, "El vendedor es obligatorio para guardar el borrador.")
                            raise Exception("Vendedor no asignado y es obligatorio para borrador.")
                            
                        pedido.estado = 'BORRADOR'
                        pedido.save()
                        productos_guardados_ids = set()
                        for detalle_data in detalles_para_crear:
                            producto_obj = detalle_data['producto']
                            DetallePedido.objects.update_or_create(
                                pedido=pedido, producto=producto_obj,
                                defaults={'cantidad': detalle_data['cantidad'], 'precio_unitario': detalle_data['precio_unitario']}
                            )
                            productos_guardados_ids.add(producto_obj.pk)
                        if form_instance:
                            DetallePedido.objects.filter(pedido=pedido).exclude(producto_id__in=productos_guardados_ids).delete()
                        messages.success(request, f"Pedido Borrador #{pedido.pk} guardado exitosamente.")
                        return redirect('pedidos:editar_pedido_web', pk=pedido.pk)
                except Exception as e:
                    messages.error(request, f"Error al guardar el borrador: {e}")

            elif accion == 'eliminar_borrador' and form_instance:
                try:
                    with transaction.atomic():
                        pedido_pk_eliminado = form_instance.pk
                        form_instance.delete()
                        messages.success(request, f"Pedido Borrador #{pedido_pk_eliminado} eliminado exitosamente.")
                        return redirect('pedidos:lista_pedidos_borrador')
                except Exception as e:
                    messages.error(request, f"Error inesperado al eliminar el borrador: {e}")
            
            elif accion == 'cancelar':
                return redirect('pedidos:lista_pedidos_borrador')
        
        # Si el form no es válido o una acción falló y no redirigió (ej. error de stock)
        if not pedido_form.is_valid():
             messages.error(request, "Por favor corrige los errores en la sección del cliente/notas.")
        
        context = _prepare_crear_pedido_context(
            pedido_instance=pedido_instance,
            detalles_existentes=detalles_existentes,
            pedido_form=pedido_form
        )
        return render(request, 'pedidos/crear_pedido_web_matriz.html', context)

    else: # request.method == 'GET'
        pedido_form_inicial = PedidoForm(instance=pedido_instance)
        context = _prepare_crear_pedido_context(
            pedido_instance=pedido_instance,
            detalles_existentes=detalles_existentes,
            pedido_form=pedido_form_inicial
        )
        return render(request, 'pedidos/crear_pedido_web_matriz.html', context)


@login_required
@user_passes_test(lambda u: es_cartera(u) or u.is_superuser or es_admin_sistema_app(u), login_url='core:acceso_denegado')
def lista_pedidos_para_aprobacion_cartera(request):
    pedidos_pendientes = Pedido.objects.filter(estado='PENDIENTE_APROBACION_CARTERA').order_by('fecha_hora')
    context = {
        'pedidos_list': pedidos_pendientes,
        'titulo': 'Pedidos Pendientes de Aprobación por Cartera',
        'etapa_actual': 'cartera',
    }
    return render(request, 'pedidos/lista_aprobacion_etapa.html', context)

@login_required
@user_passes_test(lambda u: es_cartera(u) or u.is_superuser or es_admin_sistema_app(u), login_url='core:acceso_denegado')
@require_POST
def aprobar_pedido_cartera(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk, estado='PENDIENTE_APROBACION_CARTERA')
    motivo = request.POST.get('motivo', '')
    try:
        with transaction.atomic(): # Añadido por si acaso, aunque aquí es simple
            pedido.estado = 'PENDIENTE_APROBACION_ADMIN'
            pedido.usuario_decision_cartera = request.user
            pedido.fecha_decision_cartera = timezone.now()
            if motivo:
                pedido.motivo_cartera = motivo
            pedido.save()
            print(f"DEBUG APROB-CARTERA: Pedido #{pedido.pk} guardado con estado {pedido.estado}") # <<<< PRINT
            messages.success(request, f"Pedido #{pedido.pk} aprobado por Cartera y enviado a Administración.")
    except Exception as e:
        print(f"DEBUG APROB-CARTERA: Excepción al aprobar: {e}") # <<<< PRINT
        messages.error(request, f"Error al aprobar el pedido #{pedido.pk} por Cartera: {e}")
        # Considera redirigir a la misma lista o a una página de error si la transacción falla gravemente
        # return redirect('pedidos:lista_aprobacion_cartera') 
        
    return redirect('pedidos:lista_aprobacion_cartera')

@login_required
@user_passes_test(lambda u: es_cartera(u) or u.is_superuser or es_admin_sistema_app(u), login_url='core:acceso_denegado')
@require_POST
def rechazar_pedido_cartera(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk, estado='PENDIENTE_APROBACION_CARTERA')
    motivo = request.POST.get('motivo', '') # Ya no 'Rechazado por Cartera sin motivo específico.'

    if not motivo or not motivo.strip():
        messages.error(request, "Se requiere un motivo para rechazar el pedido por Cartera.")
        # Podrías querer redirigir al detalle del pedido para que el usuario añada el motivo,
        # o recargar la lista actual. La redirección a la lista es más simple.
        return redirect('pedidos:lista_aprobacion_cartera')
    
    try:
        with transaction.atomic():
            pedido.estado = 'RECHAZADO_CARTERA'
            pedido.motivo_cartera = motivo
            pedido.usuario_decision_cartera = request.user
            pedido.fecha_decision_cartera = timezone.now()
            pedido.save()

            # Reintegro de Stock
            for detalle_rechazado in pedido.detalles.all():
                MovimientoInventario.objects.create(
                    producto=detalle_rechazado.producto,
                    cantidad=detalle_rechazado.cantidad, # Positivo
                    tipo_movimiento='ENTRADA_RECHAZO_CARTERA',
                    documento_referencia=f'Pedido #{pedido.pk} (Rechazo Cartera)',
                    usuario=request.user,
                    notas=f'Reintegro por rechazo Cartera. Pedido #{pedido.pk}. Motivo: {motivo}'
                )
            messages.warning(request, f"Pedido #{pedido.pk} rechazado por Cartera. Stock reintegrado.")
    except Exception as e:
        messages.error(request, f"Error al rechazar el pedido #{pedido.pk} por Cartera: {e}")

    return redirect('pedidos:lista_aprobacion_cartera')

@login_required
@user_passes_test(es_admin_sistema, login_url='core:acceso_denegado')
def lista_pedidos_para_aprobacion_admin(request):
    usuario_actual = request.user
    print(f"\n--- DEBUG ADMIN LIST: Accediendo lista_pedidos_para_aprobacion_admin ---") # <<<< PRINT
    print(f"DEBUG ADMIN LIST: Usuario actual = {usuario_actual.username}") # <<<< PRINT
    print(f"DEBUG ADMIN LIST: Es staff? {usuario_actual.is_staff}") # <<<< PRINT
    print(f"DEBUG ADMIN LIST: Pertenece al grupo 'Administracion'? {usuario_actual.groups.filter(name='Administracion').exists()}") # <<<< PRINT
    print(f"DEBUG ADMIN LIST: Resultado de es_admin_sistema = {es_admin_sistema(usuario_actual)}") # <<<< PRINT

    pedidos_pendientes = Pedido.objects.filter(estado='PENDIENTE_APROBACION_ADMIN').order_by('fecha_hora')
    print(f"DEBUG ADMIN LIST: Pedidos encontrados en estado PENDIENTE_APROBACION_ADMIN = {pedidos_pendientes.count()}") # <<<< PRINT
    
    context = {
        'pedidos_list': pedidos_pendientes,
        'titulo': 'Pedidos Pendientes de Aprobación por Administración',
        'etapa_actual': 'admin',
    }
    return render(request, 'pedidos/lista_aprobacion_etapa.html', context)

@login_required
@user_passes_test(lambda u: es_vendedor(u) or es_admin_sistema_app(u) or u.is_superuser, login_url='core:acceso_denegado')
@require_POST
def aprobar_pedido_admin(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk, estado='PENDIENTE_APROBACION_ADMIN')
    motivo = request.POST.get('motivo', '')
    try:
        with transaction.atomic():
            pedido.estado = 'APROBADO_ADMIN'
            pedido.usuario_decision_admin = request.user
            pedido.fecha_decision_admin = timezone.now()
            if motivo:
                pedido.motivo_admin = motivo
            pedido.save()
            # No hay movimiento de stock aquí según la nueva lógica
            messages.success(request, f"Pedido #{pedido.pk} aprobado por Administración y enviado a Bodega.")
    except Exception as e:
        messages.error(request, f"Error al aprobar el pedido #{pedido.pk} por Administración: {e}")
        
    return redirect('pedidos:lista_aprobacion_admin')

@login_required
@user_passes_test(es_admin_sistema or es_factura, login_url='core:acceso_denegado')
@require_POST
def rechazar_pedido_admin(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk, estado='PENDIENTE_APROBACION_ADMIN')
    motivo = request.POST.get('motivo', '')

    if not motivo or not motivo.strip():
        messages.error(request, "Se requiere un motivo para rechazar el pedido por Administración.")
        return redirect('pedidos:lista_aprobacion_admin')
    
    try:
        with transaction.atomic():
            pedido.estado = 'RECHAZADO_ADMIN'
            pedido.motivo_admin = motivo
            pedido.usuario_decision_admin = request.user
            pedido.fecha_decision_admin = timezone.now()
            pedido.save()

            # Reintegro de Stock
            for detalle_rechazado in pedido.detalles.all():
                MovimientoInventario.objects.create(
                    producto=detalle_rechazado.producto,
                    cantidad=detalle_rechazado.cantidad, # Positivo
                    tipo_movimiento='ENTRADA_RECHAZO_ADMIN',
                    documento_referencia=f'Pedido #{pedido.pk} (Rechazo Admin)',
                    usuario=request.user,
                    notas=f'Reintegro por rechazo Admin. Pedido #{pedido.pk}. Motivo: {motivo}'
                )
            messages.warning(request, f"Pedido #{pedido.pk} rechazado por Administración. Stock reintegrado.")
    except Exception as e:
        messages.error(request, f"Error al rechazar el pedido #{pedido.pk} por Administración: {e}")
        
    return redirect('pedidos:lista_aprobacion_admin')

@login_required
def generar_pedido_pdf(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)
    # (Lógica de permisos para el PDF)
    # ...
    
    detalles_originales = pedido.detalles.select_related('producto').all()
    items_dama, items_caballero, items_unisex = [], [], []
    for detalle in detalles_originales:
        genero_producto = None
        try:
            genero_producto = detalle.producto.get_genero_display()
            if genero_producto not in ['Dama', 'Caballero', 'Unisex']: genero_producto = None
        except AttributeError: pass
        if genero_producto == 'Dama': items_dama.append(detalle)
        elif genero_producto == 'Caballero': items_caballero.append(detalle)
        else: items_unisex.append(detalle) # Incluir sin género o 'Unisex' aquí

    tallas_col_dama = ['3', '5', '7', '9', '11', '16', '18', '20', '22']
    tallas_col_caballero = [str(t) for t in range(28, 45, 2)]
    tallas_col_unisex = sorted(list(set(d.producto.talla for d in items_unisex if d.producto.talla))) # Tallas reales de unisex
    if not tallas_col_unisex: tallas_col_unisex = ['ÚNICA'] # Fallback

    grupos_dama, cols_dama = preparar_datos_seccion(items_dama, tallas_col_dama)
    grupos_caballero, cols_caballero = preparar_datos_seccion(items_caballero, tallas_col_caballero)
    grupos_unisex, cols_unisex = preparar_datos_seccion(items_unisex, tallas_col_unisex)

    logo_para_pdf = None
    try:
        logo_para_pdf = get_logo_base_64_despacho()
        if not logo_para_pdf: print("Advertencia PDF: get_logo_base_64_despacho() devolvió None.")
    except Exception as e: print(f"Advertencia PDF: Excepción al llamar get_logo_base_64_despacho(): {e}")
        
    context = {
        'pedido': pedido,
        'logo_base64': logo_para_pdf,
        'fecha_generacion': timezone.now(),
        'tasa_iva_pct': int(pedido.IVA_RATE * 100) if hasattr(pedido, 'IVA_RATE') else 19,
        'grupos_dama': grupos_dama, 'tallas_cols_dama': cols_dama,
        'grupos_caballero': grupos_caballero, 'tallas_cols_caballero': cols_caballero,
        'grupos_unisex': grupos_unisex, 'tallas_cols_unisex': cols_unisex,
        'incluir_color': True, 'incluir_vr_unit': True,
        'enlace_descarga_fotos_pdf': pedido.get_enlace_descarga_fotos(request),
    }
    template_path = 'pedidos/pedido_pdf.html'
    template = get_template(template_path)
    html_string = template.render(context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="pedido_{pedido.pk}_{timezone.now():%Y%m%d}.pdf"'
    try:
        base_url = request.build_absolute_uri('/')
        HTML(string=html_string, base_url=base_url).write_pdf(response)
        return response
    except Exception as e:
        print(f"Error generando PDF con WeasyPrint para Pedido {pk}: {e}")
        import traceback
        traceback.print_exc()
        messages.error(request, f"Error inesperado al generar el PDF del pedido #{pedido.pk}.")
        return HttpResponse(f'Error interno del servidor al generar el PDF.', status=500)

@login_required
def vista_pedido_exito(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)
    whatsapp_url = None
    if pedido.cliente and pedido.cliente.telefono:
        telefono_crudo = pedido.cliente.telefono
        telefono_limpio = re.sub(r'\D', '', telefono_crudo)
        if len(telefono_limpio) == 10: telefono_cliente_limpio = f"57{telefono_limpio}"
        elif len(telefono_limpio) > 10 and telefono_limpio.startswith('57'): telefono_cliente_limpio = telefono_limpio
        else: telefono_cliente_limpio = None # No se pudo normalizar

        if telefono_cliente_limpio:
            mensaje_texto = (
                f"Hola {pedido.cliente.nombre_completo if pedido.cliente else ''}, "
                f"te comparto el pedido #{pedido.pk}. " # Mensaje ajustado
                f"Adjunta el PDF descargado para confirmar. Gracias."
            )
            mensaje_encoded = quote(mensaje_texto)
            whatsapp_url = f"https://wa.me/{telefono_cliente_limpio}?text={mensaje_encoded}"
    context = {'pedido': pedido, 'whatsapp_url': whatsapp_url, 'titulo': f'Pedido #{pedido.pk} Creado'}
    return render(request, 'pedidos/pedido_exito.html', context)

def _prepare_crear_pedido_context(pedido_instance=None, detalles_existentes=None, pedido_form=None):
    if pedido_form is None:
        pedido_form = PedidoForm(instance=pedido_instance)
    referencias_qs = Producto.objects.filter(activo=True).values_list('referencia', flat=True).distinct().order_by('referencia')
    detalles_agrupados_json, linea_counter_init = None, 0
    if detalles_existentes:
        grupos, linea_counter_init = {}, 0
        for detalle in detalles_existentes:
            producto = detalle.producto
            ref = producto.referencia
            color_val = producto.color           
            
            color_slug = '-' if not color_val else color_val
            color_display = 'Sin Color' if color_slug == '-' else color_val
            grupo_key = (ref, color_slug)
            if grupo_key not in grupos:
                linea_counter_init += 1
                grupos[grupo_key] = {'lineaId': f'linea-{linea_counter_init}', 'ref': ref, 'color_slug': color_slug,
                                     'color_display': color_display, 'precio_unitario': float(detalle.precio_unitario),
                                     'total_qty': 0, 'total_value': 0.0, 'variants': [], 'quantities_obj': {}}
            grupos[grupo_key]['variants'].append({'id': producto.id, 'talla': producto.talla, 'cantidad': detalle.cantidad})
            grupos[grupo_key]['quantities_obj'][producto.id] = detalle.cantidad
            grupos[grupo_key]['total_qty'] += detalle.cantidad
            try: grupos[grupo_key]['total_value'] += float(detalle.subtotal)
            except: pass
        lista_grupos_final = []
        for grupo_data in grupos.values():
            grupo_data['variants'].sort(key=lambda x: x['talla'] or '')
            grupo_data['tallas_string'] = ", ".join([f"{v['talla']}: {v['cantidad']}" for v in grupo_data['variants']])
            grupo_data['quantities_json'] = json.dumps(grupo_data['quantities_obj'])
            lista_grupos_final.append(grupo_data)
        lista_grupos_final.sort(key=lambda g: (g['ref'], g['color_display']))
        detalles_agrupados_json = json.dumps(lista_grupos_final)
    context = {
        'pedido_form': pedido_form, 'referencias': list(referencias_qs),
        'titulo': f'Editar Pedido Borrador #{pedido_instance.pk}' if pedido_instance else 'Crear Nuevo Pedido',
        'pedido_instance': pedido_instance,
        'detalles_agrupados_json_data': detalles_agrupados_json,
        'linea_counter_init': linea_counter_init
    }
    return context

@login_required
@permission_required('pedidos.view_pedido', login_url='core:acceso_denegado')
def vista_lista_pedidos_borrador(request):
    user, search_query = request.user, request.GET.get('q', None)
    queryset, titulo = Pedido.objects.none(), 'Mis Pedidos Borrador'
    es_admin_sistema_general = user.is_staff or user.is_superuser or es_admin_sistema_app(user)
    if es_admin_sistema_general:
        queryset, titulo = Pedido.objects.filter(estado='BORRADOR'), 'Todos los Pedidos Borrador'
    elif es_vendedor(user):
        try: queryset = Pedido.objects.filter(vendedor__user=user, estado='BORRADOR')
        except AttributeError: messages.error(request, "Error: Perfil de vendedor no encontrado.")
    if search_query:
        queryset = queryset.filter(Q(pk__icontains=search_query) | Q(cliente__nombre_completo__icontains=search_query)).distinct()
    pedidos_list = queryset.select_related('cliente').order_by('-fecha_hora')
    context = {'pedidos_list': pedidos_list, 'titulo': titulo, 'search_query': search_query}
    return render(request, 'pedidos/lista_pedidos_borrador.html', context)

@login_required
@require_POST
@user_passes_test(lambda u: not es_bodega(u) or es_admin_sistema_app(u), login_url='core:acceso_denegado')
def vista_eliminar_pedido_borrador(request, pk):
    try:
        vendedor = Vendedor.objects.get(user=request.user)
        pedido = get_object_or_404(Pedido, pk=pk, vendedor=vendedor, estado='BORRADOR')
        pedido_id = pedido.pk
        pedido.delete()
        messages.success(request, f"El pedido borrador #{pedido_id} ha sido eliminado exitosamente.")
    except Vendedor.DoesNotExist: messages.error(request, "No tienes permiso de vendedor para eliminar borradores.")
    except Pedido.DoesNotExist: messages.error(request, "El pedido borrador que intentas eliminar no existe o no te pertenece.")
    except Exception as e: messages.error(request, f"Ocurrió un error inesperado al eliminar el borrador: {e}")
    return redirect('pedidos:lista_pedidos_borrador') # Ajustado para usar el name de la URL

@login_required
def vista_detalle_pedido(request, pk):
    pedido = get_object_or_404(Pedido.objects.prefetch_related('detalles__producto', 'cliente', 'vendedor__user'), pk=pk)
    iva_porcentaje = Decimal('0.00')
    if hasattr(pedido, 'IVA_RATE') and pedido.IVA_RATE is not None:
        try: iva_porcentaje = Decimal(pedido.IVA_RATE) * Decimal('100.00')
        except (TypeError, ValueError): pass
    context = {'pedido': pedido, 'detalles_pedido': pedido.detalles.all(),
               'titulo': f'Detalle del Pedido #{pedido.pk}', 'iva_porcentaje': iva_porcentaje}
    return render(request, 'pedidos/detalle_pedido_template.html', context)

class DescargarFotosPedidoView(View):
    template_name = 'pedidos/pagina_descarga_fotos.html'
    def get(self, request, token_pedido):
        pedido = get_object_or_404(Pedido, token_descarga_fotos=token_pedido)
        fotos_del_pedido, urls_fotos_ya_agregadas = [], set()
        if hasattr(pedido, 'detalles'):
            detalles_del_pedido = pedido.detalles.select_related('producto__articulo_color_fotos') \
                                               .prefetch_related('producto__articulo_color_fotos__fotos_agrupadas')
            for detalle in detalles_del_pedido:
                if detalle.producto and detalle.producto.articulo_color_fotos:
                    for foto in detalle.producto.articulo_color_fotos.fotos_agrupadas.all():
                        if foto.imagen and hasattr(foto.imagen, 'url') and foto.imagen.url not in urls_fotos_ya_agregadas:
                            fotos_del_pedido.append(foto)
                            urls_fotos_ya_agregadas.add(foto.imagen.url)
        context = {'pedido': pedido, 'fotos_del_pedido': fotos_del_pedido, 'titulo': f"Fotos del Pedido #{pedido.pk}"}
        return render(request, self.template_name, context)