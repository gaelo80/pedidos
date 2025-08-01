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
from collections import defaultdict
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
from core.auth_utils import es_administracion, es_bodega, es_vendedor, es_cartera, es_administracion, es_factura
from core.utils import get_logo_base_64_despacho
from .utils import preparar_datos_seccion
from core.mixins import TenantAwareMixin
import logging

logger = logging.getLogger(__name__)

class PedidoViewSet(TenantAwareMixin, viewsets.ModelViewSet):
    """
    API endpoint que permite ver y crear pedidos.
    """
    serializer_class = PedidoSerializer
    permission_classes = [IsAuthenticatedOrReadOnly] # O los permisos que prefieras

    def get_queryset(self):
        """
        - CORRECCIÓN DE SEGURIDAD -
        Filtra los pedidos para mostrar:
        - A los administradores: Todos los pedidos DE SU EMPRESA.
        - A los vendedores: Solo los pedidos creados por ellos DENTRO DE SU EMPRESA.
        """   
        queryset = super().get_queryset().order_by('-fecha_hora')
        
        user = self.request.user
        
        if not user.is_authenticated:
            return queryset.none()
        
        if user.is_staff or user.is_superuser:
            return queryset.filter(empresa=self.request.tenant)
        
        try:
            vendedor = Vendedor.objects.get(user=user, empresa=self.request.tenant)
            return queryset.filter(vendedor=vendedor)
        except Vendedor.DoesNotExist:
            return queryset.none()
        
        
        
        
        
        

    def perform_create(self, serializer):
        try:
            vendedor = Vendedor.objects.get(user=self.request.user, empresa=self.request.tenant)
            serializer.save(
                empresa=self.request.tenant, 
                vendedor=vendedor, 
                estado='PENDIENTE_APROBACION_CARTERA'
            )
        except Vendedor.DoesNotExist:
            raise serializers.ValidationError(
                "El usuario que realiza la solicitud no tiene un perfil de vendedor asociado en esta empresa."
            )



@login_required
@permission_required('pedidos.add_pedido', login_url='core:acceso_denegado')
def vista_crear_pedido_web(request, pk=None):
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:acceso_denegado')
        
        
    vendedor = None
    try:
        if hasattr(request.user, 'perfil_vendedor'):
             vendedor = request.user.perfil_vendedor
        elif request.user.is_staff or es_administracion(request.user):
            pass
        
        else:
            messages.error(request, "Perfil de vendedor no encontrado y no es usuario administrador.")
            return redirect('core:acceso_denegado')
        
        vendedor = Vendedor.objects.filter(user=request.user, user__empresa=empresa_actual).first()
        
    except Vendedor.DoesNotExist:
        if not (request.user.is_staff or es_administracion(request.user)) and not vendedor:
            messages.error(request, "Perfil de vendedor no encontrado para esta empresa.")
            return redirect('core:acceso_denegado')
    except AttributeError:
        if not (request.user.is_staff or es_administracion(request.user)):
            messages.error(request, "Atributo de perfil de vendedor no encontrado.")
            return redirect('core:acceso_denegado')
        
    pedido_instance = None
    detalles_existentes = None
    if pk is not None:
        query_params = {'pk': pk, 'estado': 'BORRADOR', 'empresa': empresa_actual}
        if vendedor and not (request.user.is_staff or es_administracion(request.user)):
            query_params['vendedor'] = vendedor
        pedido_instance = get_object_or_404(Pedido, **query_params)
        
    detalles_existentes = pedido_instance.detalles.select_related('producto').all() if pedido_instance else None

    if request.method == 'POST':
        form_instance = pedido_instance
        pedido_form = PedidoForm(request.POST, instance=pedido_instance, empresa=empresa_actual)
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
                            producto_variante = Producto.objects.get(pk=producto_id, activo=True, empresa=empresa_actual)
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
                
                
                stock_suficiente_para_crear = True
                if not al_menos_un_detalle:
                    messages.error(request, "Debes agregar al menos un producto para crear el pedido.")
                    stock_suficiente_para_crear = False
                else:
                    for detalle_data_check in detalles_para_crear:
                        if detalle_data_check['cantidad'] > detalle_data_check['producto'].stock_actual:
                            stock_suficiente_para_crear = False
                            errores_stock.append(f"Stock insuficiente para '{detalle_data_check['producto']}'. Pedido: {detalle_data_check['cantidad']}, Disp: {detalle_data_check['producto'].stock_actual}")
                
                if not stock_suficiente_para_crear:
                    for error in errores_stock: messages.error(request, error)

                
                if not errores_generales and stock_suficiente_para_crear: # Condición combinada

                    try:
                        with transaction.atomic():
                            pedido = pedido_form.save(commit=False)
                            pedido.empresa = empresa_actual
                            if vendedor:
                                pedido.vendedor = vendedor
                            elif request.user.is_staff or es_administracion(request.user):
 
                                pass

                            if not pedido.vendedor:
                                messages.error(request, "El vendedor es obligatorio para crear el pedido.")
                                raise Exception("Vendedor no asignado y es obligatorio.")                                
                                       
                            if pedido.prospecto:

                                pedido.estado = 'PENDIENTE_CLIENTE'
                            else:

                                pedido.estado = 'PENDIENTE_APROBACION_CARTERA'

                            pedido.save()
                            
                            
                            
                            

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
                                    empresa=empresa_actual,
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
                        pedido.empresa = empresa_actual
                        if vendedor:
                            pedido.vendedor = vendedor
                        elif not pedido.vendedor and (request.user.is_staff or es_administracion(request.user)):
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
            request=request,                      # <-- Argumento añadido
            empresa_actual=empresa_actual,
            pedido_instance=pedido_instance,
            detalles_existentes=detalles_existentes,
            pedido_form=pedido_form
        )
        return render(request, 'pedidos/crear_pedido_web_matriz.html', context)

    else: # request.method == 'GET'
        pedido_form = PedidoForm(instance=pedido_instance, empresa=empresa_actual)
        context = _prepare_crear_pedido_context(request, empresa_actual, pedido_instance, detalles_existentes, pedido_form)
        return render(request, 'pedidos/crear_pedido_web_matriz.html', context)

#////////////////////////////////////////////////////////////////////////////////////


@login_required
@user_passes_test(lambda u: es_cartera(u) or u.is_superuser or es_administracion(u), login_url='core:acceso_denegado')
def lista_pedidos_para_aprobacion_cartera(request):
    
    """
    Lista los pedidos pendientes de aprobación por cartera, filtrando por la empresa
    del inquilino actual.
    """
    # Lógica de obtención de inquilino robusta
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:acceso_denegado')
    
    
    pedidos_pendientes = Pedido.objects.filter(
        empresa=empresa_actual,
        estado='PENDIENTE_APROBACION_CARTERA'
    ).order_by('fecha_hora')
    
    context = {
        'pedidos_list': pedidos_pendientes,
        'titulo': 'Pedidos Pendientes de Aprobación por Cartera',
        'etapa_actual': 'cartera',
    }
    return render(request, 'pedidos/lista_aprobacion_etapa.html', context)



@login_required
@user_passes_test(lambda u: es_cartera(u) or u.is_superuser or es_administracion(u), login_url='core:acceso_denegado')
@require_POST
def aprobar_pedido_cartera(request, pk):
    
    """
    Aprueba un pedido específico desde la etapa de cartera, asegurando que el pedido
    pertenezca al inquilino actual.
    """
    # Lógica de obtención de inquilino robusta
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('pedidos:lista_aprobacion_cartera') # Redirige a la lista para no perder contexto
    
    
    
    pedido = get_object_or_404(
        Pedido, 
        pk=pk, 
        empresa=empresa_actual,        
        estado='PENDIENTE_APROBACION_CARTERA'
    )
    
    motivo = request.POST.get('motivo', '')
    try:
        with transaction.atomic(): # Añadido por si acaso, aunque aquí es simple
            pedido.estado = 'PENDIENTE_APROBACION_ADMIN'
            pedido.usuario_decision_cartera = request.user
            pedido.fecha_decision_cartera = timezone.now()
            if motivo:
                pedido.motivo_cartera = motivo
            pedido.save()
            print(f"DEBUG APROB-CARTERA: Pedido #{pedido.pk} guardado con estado {pedido.estado}")
            messages.success(request, f"Pedido #{pedido.pk} aprobado por Cartera y enviado a Administración.")
    except Exception as e:
        print(f"DEBUG APROB-CARTERA: Excepción al aprobar: {e}")
        messages.error(request, f"Error al aprobar el pedido #{pedido.pk} por Cartera: {e}")
        
    return redirect('pedidos:lista_aprobacion_cartera')




@login_required
@user_passes_test(lambda u: es_cartera(u) or u.is_superuser or es_administracion(u), login_url='core:acceso_denegado')
@require_POST
def rechazar_pedido_cartera(request, pk):
    
    """
    Rechaza un pedido específico desde la etapa de cartera, asegurando que tanto el pedido
    como el movimiento de inventario resultante pertenezcan al inquilino actual.
    """
    # Lógica de obtención de inquilino robusta
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('pedidos:lista_aprobacion_cartera')
    
    
    pedido = get_object_or_404(
        Pedido, 
        pk=pk, 
        empresa=empresa_actual,
        estado='PENDIENTE_APROBACION_CARTERA'
    )
    motivo = request.POST.get('motivo', '')

    if not motivo or not motivo.strip():
        messages.error(request, "Se requiere un motivo para rechazar el pedido por Cartera.")
        return redirect('pedidos:lista_aprobacion_cartera')
    
    try:
        with transaction.atomic():
            pedido.estado = 'RECHAZADO_CARTERA'
            pedido.motivo_cartera = motivo
            pedido.usuario_decision_cartera = request.user
            pedido.fecha_decision_cartera = timezone.now()
            pedido.save()
            
            for detalle_rechazado in pedido.detalles.all():
                MovimientoInventario.objects.create(
                    empresa=empresa_actual,
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

#88888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888


@login_required
@user_passes_test(es_administracion, login_url='core:acceso_denegado')
def lista_pedidos_para_aprobacion_admin(request):
    
    """
    Lista los pedidos pendientes de aprobación por administración, filtrando por
    la empresa del inquilino actual.
    """
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:acceso_denegado')


    pedidos_pendientes = Pedido.objects.filter(
        empresa=empresa_actual,
        estado='PENDIENTE_APROBACION_ADMIN'
    ).order_by('fecha_hora')
           
    context = {
        'pedidos_list': pedidos_pendientes,
        'titulo': 'Pedidos Pendientes de Aprobación por Administración',
        'etapa_actual': 'admin',
    }
    return render(request, 'pedidos/lista_aprobacion_etapa.html', context)



@login_required
@user_passes_test(es_administracion, login_url='core:acceso_denegado')
@require_POST
def aprobar_pedido_admin(request, pk):
    
    """
    Aprueba un pedido específico desde la etapa de administración, asegurando que
    pertenezca al inquilino actual.
    """
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('pedidos:lista_aprobacion_admin')
    
    pedido = get_object_or_404(
        Pedido, 
        pk=pk, 
        empresa=empresa_actual,
        estado='PENDIENTE_APROBACION_ADMIN'
    )
    
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
@user_passes_test(lambda u: es_administracion(u) or es_factura(u), login_url='core:acceso_denegado')
@require_POST
def rechazar_pedido_admin(request, pk):
    
    """
    Rechaza un pedido específico desde la etapa de administración, asegurando que
    pertenezca al inquilino actual y que el reintegro de stock se asocie a él.
    """
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('pedidos:lista_aprobacion_admin')
    
    pedido = get_object_or_404(
        Pedido, 
        pk=pk, 
        empresa=empresa_actual,
        estado='PENDIENTE_APROBACION_ADMIN'
    )
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
                    empresa=empresa_actual,
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
    
    """
    Genera un PDF para un pedido específico, asegurando que el pedido pertenezca
    al inquilino actual y que el usuario tenga permisos para verlo.
    """
    empresa_actual = getattr(request, 'tenant', None)
    
    # --- LÓGICA DE ACCESO CORREGIDA ---
    query_params = {'pk': pk}
    # Si el usuario NO es superusuario, forzamos el filtro por su empresa.
    if not request.user.is_superuser:
        if not empresa_actual:
            messages.error(request, "Acceso no válido. Su usuario no está asociado a ninguna empresa.")
            return redirect('core:acceso_denegado')
        query_params['empresa'] = empresa_actual
    
    
    pedido = get_object_or_404(
        Pedido.objects.select_related('cliente', 'cliente_online', 'prospecto', 'vendedor__user', 'empresa'), 
        **query_params
    )
    
    es_su_pedido = (hasattr(request.user, 'perfil_vendedor') and pedido.vendedor == request.user.perfil_vendedor)
    es_admin_o_staff = request.user.is_superuser or es_administracion(request.user)
    grupos_autorizados = ['Bodega', 'Cartera', 'Factura', 'Administracion']
    pertenece_a_grupo_autorizado = request.user.groups.filter(name__in=grupos_autorizados).exists()
    
    if not (es_su_pedido or es_admin_o_staff or pertenece_a_grupo_autorizado):
        messages.error(request, "No tienes permiso para ver este pedido.")
        return redirect('core:acceso_denegado')

    detalles_originales = pedido.detalles.select_related('producto').all()
    items_dama, items_caballero, items_unisex = [], [], []
    
    TALLAS_DAMA = ['3', '5', '7', '9', '11', '13'] # Ajusta si son diferentes
    TALLAS_CABALLERO = ['28', '30', '32', '34', '36', '38'] # Ajusta si son diferentes
    TALLAS_UNISEX = ['S', 'M', 'L', 'XL'] # Ajusta si son diferentes
    
    
    
    for detalle in detalles_originales:
        # Asumiendo que el modelo Producto tiene un campo 'genero'
        genero_producto = getattr(detalle.producto, 'genero', 'UNISEX').upper()
        if genero_producto == 'DAMA':
            items_dama.append(detalle)
        elif genero_producto == 'CABALLERO':
            items_caballero.append(detalle)
        else:
            items_unisex.append(detalle)       

    grupos_dama, cols_dama = preparar_datos_seccion(items_dama, TALLAS_DAMA)
    grupos_caballero, cols_caballero = preparar_datos_seccion(items_caballero, TALLAS_CABALLERO)
    grupos_unisex, cols_unisex = preparar_datos_seccion(items_unisex, TALLAS_UNISEX)


    logo_para_pdf = None
    try:
        logo_para_pdf = get_logo_base_64_despacho(empresa_actual)
        if not logo_para_pdf: print("Advertencia PDF: get_logo_base_64_despacho() devolvió None.")
    except Exception as e: print(f"Advertencia PDF: Excepción al llamar get_logo_base_64_despacho(): {e}")
        
    context = {
        'pedido': pedido,
        'empresa_actual': empresa_actual,
        'logo_base64': get_logo_base_64_despacho(empresa_actual),
        'tasa_iva_pct': int(pedido.IVA_RATE * 100),
        'grupos_dama': grupos_dama, 'tallas_cols_dama': cols_dama,
        'grupos_caballero': grupos_caballero, 'tallas_cols_caballero': cols_caballero,
        'grupos_unisex': grupos_unisex, 'tallas_cols_unisex': cols_unisex,
        'incluir_color': True,
        'incluir_vr_unit': pedido.mostrar_precios_pdf,
        'enlace_descarga_fotos_pdf': pedido.get_enlace_descarga_fotos(request),
    }
    
    template = get_template('pedidos/pedido_pdf.html')
    html = template.render(context)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="pedido_{pedido.pk}.pdf"'
    
    from xhtml2pdf import pisa
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
       return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response

@login_required
def vista_pedido_exito(request, pk):
    
    """
    Muestra la página de éxito después de crear un pedido, asegurando que el pedido
    pertenezca al inquilino actual.
    """
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:acceso_denegado')

    try: # Inicia el bloque try
        pedido = get_object_or_404(Pedido, pk=pk, empresa=empresa_actual)
        
        whatsapp_url = None
        # Se usa pedido.destinatario para obtener el teléfono, que puede ser Cliente o ClienteOnline
        if pedido.destinatario and pedido.destinatario.telefono:
            telefono_crudo = pedido.destinatario.telefono
            telefono_limpio = re.sub(r'\D', '', telefono_crudo)
            # Asumiendo que los números de teléfono en Colombia tienen 10 dígitos y se les añade el prefijo 57
            if len(telefono_limpio) == 10: 
                telefono_cliente_limpio = f"57{telefono_limpio}"
            elif len(telefono_limpio) > 10 and telefono_limpio.startswith('57'): 
                telefono_cliente_limpio = telefono_limpio
            else: 
                telefono_cliente_limpio = None # No se pudo normalizar

            if telefono_cliente_limpio:
                mensaje_texto = (
                    f"Hola {pedido.destinatario.nombre_completo if pedido.destinatario else ''}, "
                    f"te comparto el pedido #{pedido.pk}. " 
                    f"Adjunta el PDF descargado para confirmar. Gracias."
                )
                mensaje_encoded = quote(mensaje_texto)
                whatsapp_url = f"https://wa.me/{telefono_cliente_limpio}?text={mensaje_encoded}"

        # Determinar la URL para el botón "Crear Nuevo Pedido"
        if pedido.tipo_pedido == 'ONLINE':
            crear_nuevo_pedido_url = 'pedidos_online:crear_pedido_online'
        else: # 'ESTANDAR' o cualquier otro tipo
            crear_nuevo_pedido_url = 'pedidos:crear_pedido_web'

        context = {
            'pedido': pedido, 
            'whatsapp_url': whatsapp_url, 
            'titulo': f'Pedido #{pedido.pk} Creado',
            'crear_nuevo_pedido_url': crear_nuevo_pedido_url, # Pasa la URL al contexto
        }
        return render(request, 'pedidos/pedido_exito.html', context)
    
    except Exception as e: # Captura cualquier excepción inesperada
        messages.error(request, f"Ocurrió un error inesperado al cargar la página de éxito del pedido: {e}")
        logger.exception("Error en vista_pedido_exito para pedido %s:", pk) # Registra la excepción completa
        return redirect('core:index') # Redirige a una página segura si hay un error


def _prepare_crear_pedido_context(request, empresa_actual, pedido_instance=None, detalles_existentes=None, pedido_form=None):
    
    """
    Función auxiliar para preparar el contexto del formulario de creación/edición de pedidos.
    """
    
    if pedido_form is None:
        pedido_form = PedidoForm(instance=pedido_instance, empresa=empresa_actual)
        
    referencias_qs = Producto.objects.filter(
        empresa=empresa_actual,        
        activo=True
    ).values_list('referencia', flat=True).distinct().order_by('referencia')
    
    
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
    
    """
    Lista los pedidos en estado de borrador, filtrando por la empresa actual y
    por el vendedor si corresponde.
    """
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:acceso_denegado')
    
    
    user, search_query = request.user, request.GET.get('q', None)
    queryset, titulo = Pedido.objects.none(), 'Mis Pedidos Borrador'
    es_admin = es_administracion(user) or user.is_superuser
    
    base_queryset = Pedido.objects.filter(empresa=empresa_actual, estado='BORRADOR')
    
    if es_admin:
        queryset, titulo = base_queryset, 'Todos los Pedidos Borrador'
    elif es_vendedor(user):
        queryset = base_queryset.filter(vendedor__user=user)
    
    if search_query:
        queryset = queryset.filter(Q(pk__icontains=search_query) | Q(cliente__nombre_completo__icontains=search_query)).distinct()
        
    pedidos_list = queryset.select_related('cliente').order_by('-fecha_hora')
    context = {'pedidos_list': pedidos_list, 'titulo': titulo, 'search_query': search_query}
    return render(request, 'pedidos/lista_pedidos_borrador.html', context)



@login_required
@require_POST
@user_passes_test(lambda u: not es_bodega(u) or es_administracion(u), login_url='core:acceso_denegado')
def vista_eliminar_pedido_borrador(request, pk):
    
    """
    Elimina un pedido en estado de borrador, asegurando que pertenezca al vendedor
    y a la empresa actual.
    """
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('pedidos:lista_pedidos_borrador')
    
    
    
    try:
        vendedor = Vendedor.objects.get(user=request.user, empresa=empresa_actual)
        pedido = get_object_or_404(Pedido, pk=pk, vendedor=vendedor, estado='BORRADOR', empresa=empresa_actual)
        pedido_id = pedido.pk
        pedido.delete()
        messages.success(request, f"El pedido borrador #{pedido_id} ha sido eliminado exitosamente.")
    except Vendedor.DoesNotExist:
        messages.error(request, "No tienes un perfil de vendedor en esta empresa para realizar esta acción.")
    except Pedido.DoesNotExist:
        messages.error(request, "El pedido borrador que intentas eliminar no existe o no te pertenece.")
    except Exception as e:
        messages.error(request, f"Ocurrió un error inesperado al eliminar el borrador: {e}")
        
    return redirect('pedidos:lista_pedidos_borrador')



@login_required
def vista_detalle_pedido(request, pk):
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:acceso_denegado')

    query = Pedido.objects.prefetch_related('detalles__producto', 'cliente', 'vendedor__user')
    pedido = get_object_or_404(query, pk=pk, empresa=empresa_actual)

    # --- Reglas de acceso (mantener igual) ---
    es_superuser = request.user.is_superuser
    es_admin = es_administracion(request.user)
    es_vendedor_y_su_pedido = hasattr(request.user, 'perfil_vendedor') and pedido.vendedor == request.user.perfil_vendedor
    estado_borrador = pedido.estado == 'BORRADOR'

    if estado_borrador:
        if not es_vendedor_y_su_pedido and not es_superuser and not es_admin:
            messages.error(request, "No tienes permisos para ver este pedido en estado borrador.")
            return redirect('pedidos:lista_pedidos_borrador')
    else:
        if not es_superuser and not es_admin:
            # Aquí permitimos que usuarios normales (ej. bodega) puedan ver pedidos NO borrador
            pass  # Permitido

    # --- Cálculo del IVA (mantener igual) ---
    iva_porcentaje = Decimal('0.00')
    if hasattr(pedido, 'IVA_RATE') and pedido.IVA_RATE is not None:
        try:
            iva_porcentaje = Decimal(pedido.IVA_RATE) * Decimal('100.00')
        except (TypeError, ValueError):
            pass

    # --- LÓGICA DE AGRUPAMIENTO DE PRODUCTOS PARA LA TABLA ---
    detalles_pedido = pedido.detalles.all() # Obtener todos los detalles del pedido

    items_agrupados_por_referencia_color = defaultdict(lambda: {
        'referencia': '',
        'descripcion': '', # Campo para el nombre/descripción del producto
        'color': '',
        'tallas': {}, # Para almacenar 'talla_nombre': cantidad
        'total_cantidad': 0,
        'precio_unitario': Decimal('0.00'), # Para el valor numérico del precio
        'precio_unitario_display': '', # Para mostrar el precio unitario formateado
        'subtotal_display': '', # Para mostrar el subtotal del grupo formateado
    })

    todas_las_tallas_pedidas = set() # Para los encabezados de columna de las tallas

    for detalle in detalles_pedido:
        producto_obj = detalle.producto
        referencia_str = producto_obj.referencia or ""
        color_str = producto_obj.color or ""
        # Asegura que la talla sea un string para usarla como clave de diccionario y en el set
        talla_str = str(producto_obj.talla) if producto_obj.talla else "N/A"

        clave_agrupacion = (referencia_str, color_str)
        grupo = items_agrupados_por_referencia_color[clave_agrupacion]

        # Rellenar datos generales del grupo (solo una vez)
        if not grupo['referencia']:
            grupo['referencia'] = referencia_str
            grupo['descripcion'] = producto_obj.nombre or "" # Usar nombre del producto como descripción
            grupo['color'] = color_str
            grupo['precio_unitario'] = detalle.precio_unitario # Asumimos que es el mismo por referencia/color
            # Formato colombiano para display del precio unitario
            grupo['precio_unitario_display'] = f"${detalle.precio_unitario:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        # Asignar la cantidad a la talla correspondiente dentro del grupo
        grupo['tallas'][talla_str] = (grupo['tallas'].get(talla_str, 0) + detalle.cantidad)
        grupo['total_cantidad'] += detalle.cantidad

        # Registrar la talla para la lista de encabezados de columna de la tabla
        todas_las_tallas_pedidas.add(talla_str)

    items_para_tabla_html = []
    for clave_agrupacion, data in items_agrupados_por_referencia_color.items():
        # Calcular el subtotal del grupo
        subtotal_grupo = data['total_cantidad'] * data['precio_unitario']
        data['subtotal_display'] = f"${subtotal_grupo:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        items_para_tabla_html.append(data)

    # Ordenar las tallas para los encabezados de columna de la tabla (numéricamente para números, alfabéticamente para otros)
    todas_las_tallas_ordenadas = sorted(list(todas_las_tallas_pedidas), key=lambda x: (int(x) if x.isdigit() else float('inf'), x))

    # Ordenar los grupos para la tabla (por referencia, luego por color)
    items_para_tabla_html.sort(key=lambda x: (x['referencia'], x['color']))
    # --- FIN DE LA LÓGICA DE AGRUPAMIENTO DE PRODUCTOS PARA LA TABLA ---

    context = {
        'titulo': f'Detalle del Pedido #{pedido.pk}',
        'pedido': pedido,
        # 'detalles_pedido': detalles_pedido, # Ya no necesitas esto para la tabla de productos
        'items_agrupados_para_tabla': items_para_tabla_html, # <-- NUEVOS DATOS PARA LA TABLA
        'todas_las_tallas_ordenadas': todas_las_tallas_ordenadas, # <-- NUEVOS ENCABEZADOS DE TALLAS
        'iva_porcentaje': iva_porcentaje # Porcentaje de IVA ya calculado
    }

    return render(request, 'pedidos/detalle_pedido_template.html', context)


class DescargarFotosPedidoView(TenantAwareMixin, View):
    template_name = 'pedidos/pagina_descarga_fotos.html'
    
    def get(self, request, token_pedido):
        empresa_actual = getattr(self.request, 'tenant', None)
        if not empresa_actual:
            return HttpResponse("Acceso no válido.", status=404)
        
        pedido = get_object_or_404(Pedido, token_descarga_fotos=token_pedido, empresa=empresa_actual)
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
    
@login_required
@permission_required('pedidos.view_pedido', login_url='core:acceso_denegado') # Se mantiene el permiso de ver pedido
def generar_borrador_pdf(request, pk):
    """
    Genera un PDF para un pedido en estado BORRADOR específico,
    asegurando que pertenezca al inquilino actual y que el usuario
    tenga permisos para verlo.
    """
    empresa_actual = getattr(request, 'tenant', None)
    
    # Lógica de acceso: Superusuario puede ver todos los borradores,
    # Vendedor solo los suyos, Administración puede ver todos los de su empresa.
    query_params = {'pk': pk, 'estado': 'BORRADOR'}
    
    # Filtro por empresa para todos los usuarios NO superusuario
    if not request.user.is_superuser:
        if not empresa_actual:
            messages.error(request, "Acceso no válido. Su usuario no está asociado a ninguna empresa.")
            return redirect('core:acceso_denegado')
        query_params['empresa'] = empresa_actual
    
    # Filtro adicional para vendedores (solo pueden ver sus borradores)
    if es_vendedor(request.user) and not (request.user.is_superuser or es_administracion(request.user)):
        try:
            vendedor_obj = Vendedor.objects.get(user=request.user, user__empresa=empresa_actual)
            query_params['vendedor'] = vendedor_obj
        except Vendedor.DoesNotExist:
            messages.error(request, "Su perfil de vendedor no está asociado a esta empresa.")
            return redirect('core:acceso_denegado')
            
    # Obtener el pedido borrador
    pedido = get_object_or_404(
        Pedido.objects.select_related('cliente', 'cliente_online', 'prospecto', 'vendedor__user', 'empresa'), 
        **query_params
    )

    # --- Los datos que se pasan a la plantilla PDF son los mismos que en generar_pedido_pdf ---
    detalles_originales = pedido.detalles.select_related('producto').all()
    items_dama, items_caballero, items_unisex = [], [], []
    
    # Asegúrate de que TALLAS_DAMA, TALLAS_CABALLERO, TALLAS_UNISEX y preparar_datos_seccion
    # estén definidos o importados en este archivo (asumo que ya lo están).
    # Estas variables y la función están en generar_pedido_pdf.
    # Puedes definirlas globalmente en views.py o copiarlas si solo las usas aquí.
    TALLAS_DAMA = ['3', '5', '7', '9', '11', '13'] # Ajusta si son diferentes
    TALLAS_CABALLERO = ['28', '30', '32', '34', '36', '38'] # Ajusta si son diferentes
    TALLAS_UNISEX = ['S', 'M', 'L', 'XL'] # Ajusta si son diferentes
    
    for detalle in detalles_originales:
        genero_producto = getattr(detalle.producto, 'genero', 'UNISEX').upper()
        if genero_producto == 'DAMA':
            items_dama.append(detalle)
        elif genero_producto == 'CABALLERO':
            items_caballero.append(detalle)
        else:
            items_unisex.append(detalle)       

    grupos_dama, cols_dama = preparar_datos_seccion(items_dama, TALLAS_DAMA)
    grupos_caballero, cols_caballero = preparar_datos_seccion(items_caballero, TALLAS_CABALLERO)
    grupos_unisex, cols_unisex = preparar_datos_seccion(items_unisex, TALLAS_UNISEX)

    logo_para_pdf = None
    try:
        logo_para_pdf = get_logo_base_64_despacho(empresa_actual)
    except Exception as e: 
        logger.warning(f"Advertencia PDF Borrador: Excepción al llamar get_logo_base_64_despacho(): {e}")
        
    context = {
        'pedido': pedido,
        'empresa_actual': empresa_actual,
        'logo_base64': logo_para_pdf, # Usar la variable logo_para_pdf
        'tasa_iva_pct': int(pedido.IVA_RATE * 100), # Puedes tomarlo del pedido mismo
        'grupos_dama': grupos_dama, 'tallas_cols_dama': cols_dama,
        'grupos_caballero': grupos_caballero, 'tallas_cols_caballero': cols_caballero,
        'grupos_unisex': grupos_unisex, 'tallas_cols_unisex': cols_unisex,
        'incluir_color': True,
        'incluir_vr_unit': pedido.mostrar_precios_pdf,
        'enlace_descarga_fotos_pdf': pedido.get_enlace_descarga_fotos(request), # Obtener el enlace de descarga de fotos
    }
    
    template = get_template('pedidos/pedido_pdf.html') # Reutilizamos la misma plantilla PDF
    html = template.render(context)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="pedido_borrador_{pedido.pk}.pdf"'
    
    # Uso de xhtml2pdf (si no tienes WeasyPrint configurado)
    from xhtml2pdf import pisa
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
       logger.error(f"Error al generar PDF de borrador para pedido #{pedido.pk}: {pisa_status.err}")
       return HttpResponse('Ocurrió un error al generar el PDF.', status=500)
    return response