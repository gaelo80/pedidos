# factura/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin 
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.db.models import Q, Exists, OuterRef, Prefetch
from django.views import View
from django.db import transaction
from decimal import Decimal
from collections import defaultdict
from bodega.models import ComprobanteDespacho
from clientes.models import Cliente
from pedidos.models import Pedido
from .models import EstadoFacturaDespacho
from .forms import InformeDespachosPorClienteForm, InformeDespachosPorEstadoForm, InformeDespachosPorPedidoForm, InformeFacturadosFechaForm, MarcarFacturadoForm
from core.mixins import TenantAwareMixin


class ListaDespachosAFacturarView(TenantAwareMixin, LoginRequiredMixin, PermissionRequiredMixin, ListView):

    model = ComprobanteDespacho
    template_name = 'factura/lista_despachos_a_facturar.html' 
    context_object_name = 'despachos_por_facturar' 
    paginate_by = 25
    
    permission_required = 'factura.view_despachos_a_facturar' 
    login_url = reverse_lazy('core:acceso_denegado') 

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para ver los despachos por facturar.")
        return redirect(self.login_url) 
        
    def get_queryset(self):

        empresa_actual = self.request.tenant
        
        
        despachos_ya_facturados_ids = EstadoFacturaDespacho.objects.filter(
            empresa=empresa_actual,
            estado='FACTURADO'
        ).values_list('despacho_id', flat=True)

        queryset = ComprobanteDespacho.objects.filter(
            pedido__empresa=empresa_actual
        ).select_related(
            'pedido', 
            'pedido__cliente', 
            'usuario_responsable' 
        ).exclude(
            pk__in=despachos_ya_facturados_ids
        ).order_by('fecha_hora_despacho')

        pedido_id_query = self.request.GET.get('pedido_id')
        if pedido_id_query:
            try:
                queryset = queryset.filter(pedido_id=int(pedido_id_query))
            except ValueError:
                pass
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = "Despachos Pendientes de Facturar"
        context['pedido_id_query'] = self.request.GET.get('pedido_id', '')
        return context

class DetalleDespachoFacturaView(TenantAwareMixin, LoginRequiredMixin, PermissionRequiredMixin, View):

    template_name = 'factura/detalle_despacho_factura.html'
    form_class = MarcarFacturadoForm
    
    permission_required = 'factura.view_estadofacturadespacho' # Permiso para ver el detalle
    login_url = reverse_lazy('core:acceso_denegado')

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para ver este detalle de despacho.")
        return redirect(self.login_url)

    def get_object(self, pk_despacho):

        return get_object_or_404(
            ComprobanteDespacho.objects.select_related(
                'pedido',
                'pedido__cliente',
                'pedido__vendedor',
                'usuario_responsable'
            ).prefetch_related(
                'detalles__producto', # Detalles del ComprobanteDespacho y sus productos
                'estado_facturacion_info'
            ),
            pk=pk_despacho,
            empresa=self.request.tenant
        )

    def get_estado_factura_despacho(self, comprobante_despacho):

        try:
            estado_factura, created = EstadoFacturaDespacho.objects.get_or_create(
                despacho=comprobante_despacho,
                empresa=self.request.tenant, # <-- FILTRO DE SEGURIDAD
                defaults={
                    'estado': 'POR_FACTURAR',
                    'usuario_responsable': self.request.user
                }
            )
            if created:
                print(f"EstadoFacturaDespacho CREADO para Despacho ID: {comprobante_despacho.pk}")
            return estado_factura
        except Exception as e:
            print(f"Error obteniendo o creando EstadoFacturaDespacho: {e}")
            messages.error(self.request, "Error crítico al acceder al estado de facturación.")
            return None


    def get(self, request, pk_despacho):

        comprobante_despacho = self.get_object(pk_despacho)
        estado_factura_obj = self.get_estado_factura_despacho(comprobante_despacho)

        if estado_factura_obj is None:
            return redirect('factura:lista_despachos_a_facturar')

        form = self.form_class(instance=estado_factura_obj)



# --- INICIO: Lógica para agrupar ítems del despacho (Estilo PDF) ---
        items_despachados_originales = comprobante_despacho.detalles.select_related('producto').all()
        
        # --- INICIO: Cargar Mapeo de Tallas (PASO 8) ---
        empresa_obj = self.request.tenant
        TALLAS_MAPEO = empresa_obj.talla_mapeo if empresa_obj else {}
        # --- FIN: Cargar Mapeo de Tallas ---
        
        tallas_unicas_set = set()
        for detalle in items_despachados_originales:
            # --- Aplicar Mapeo de Talla (PASO 8) ---
            talla_original = detalle.producto.talla or 'N/A'
            talla_como_texto = str(talla_original).strip()
            talla_display = TALLAS_MAPEO.get(talla_como_texto, talla_como_texto)
            # --- Fin Mapeo ---
            tallas_unicas_set.add(talla_display)
        
        # Intentamos un ordenado inteligente (primero números, luego texto)
        try:
            # Forzamos la conversión a int para ordenar numéricamente
            tallas_header_ordenadas = sorted(list(tallas_unicas_set), key=int)
        except ValueError:
            # Si falla (ej. si una talla es 'N/A'), usa el ordenado alfabético
            tallas_header_ordenadas = sorted(list(tallas_unicas_set))

        # 2. Agrupar ítems y crear un dict de tallas
        items_agrupados_dict = defaultdict(lambda: {
            'referencia': '',
            'nombre': '',
            'color': '',
            'tallas_dict': defaultdict(int), # Usar un dict para conteo
            'cantidad_total': 0
        })

        for detalle_item in items_despachados_originales:
            producto_obj = detalle_item.producto
            clave_agrupacion = (producto_obj.referencia, producto_obj.color or '-')
            grupo = items_agrupados_dict[clave_agrupacion]

            if not grupo['referencia']:
                grupo['referencia'] = producto_obj.referencia
                grupo['nombre'] = producto_obj.nombre
                grupo['color'] = producto_obj.color or '-'

# --- Aplicar Mapeo de Talla (PASO 8) ---
            talla_original = producto_obj.talla or 'N/A'
            talla_como_texto = str(talla_original).strip()
            talla_display = TALLAS_MAPEO.get(talla_como_texto, talla_como_texto)
            # --- Fin Mapeo ---

            grupo['tallas_dict'][talla_display] += detalle_item.cantidad_despachada
            grupo['cantidad_total'] += detalle_item.cantidad_despachada

        # 3. Post-procesar: Convertir el tallas_dict en una lista ordenada que coincida con el header
        lista_items_final = []
        for grupo_dict in items_agrupados_dict.values():
            tallas_ordenadas_para_template = []
            for talla_header in tallas_header_ordenadas:
                cantidad = grupo_dict['tallas_dict'].get(talla_header, 0) # 0 si no tiene esa talla
                tallas_ordenadas_para_template.append(cantidad)
            
            grupo_dict['tallas_ordenadas'] = tallas_ordenadas_para_template
            lista_items_final.append(grupo_dict)

        # 4. Ordenar la lista final para la plantilla
        lista_items_agrupados = sorted(
            lista_items_final, 
            key=lambda x: (x['referencia'], x['color'])
        )
        # --- FIN: Lógica para agrupar ítems ---


        context = {
            'titulo': f"Detalle Despacho #{comprobante_despacho.pk} para Facturación",
            'comprobante_despacho': comprobante_despacho,
            'estado_factura_obj': estado_factura_obj,
            'form': form,
            'pedido': comprobante_despacho.pedido,
            'cliente': comprobante_despacho.pedido.cliente,
            # 'detalles_comprobante': items_despachados_originales, # Ya no pasamos los originales directamente para la tabla principal
            'items_despachados_agrupados': lista_items_agrupados, # Pasamos los agrupados
            'tallas_header': tallas_header_ordenadas,
        }
        return render(request, self.template_name, context)

    def post(self, request, pk_despacho):

        comprobante_despacho = self.get_object(pk_despacho)
        estado_factura_obj = self.get_estado_factura_despacho(comprobante_despacho)

        if estado_factura_obj is None:
            return redirect('factura:lista_despachos_a_facturar')

        form = self.form_class(request.POST, instance=estado_factura_obj)

        if form.is_valid():
            try:
                with transaction.atomic():
                    action = request.POST.get("action")

                    if action == "marcar_facturado":
                        if estado_factura_obj.estado == 'FACTURADO':
                            messages.warning(request, f"El Despacho #{comprobante_despacho.pk} ya está marcado como FACTURADO.")
                        else:
                            estado_factura_obj_actualizado_por_form = form.save(commit=False)
                            estado_factura_obj.estado = 'FACTURADO'
                            estado_factura_obj.fecha_hora_facturado_sistema = timezone.now()
                            estado_factura_obj.usuario_responsable = request.user
                            estado_factura_obj_actualizado_por_form.save()
                            messages.success(request, f"Despacho #{comprobante_despacho.pk} marcado como FACTURADO exitosamente.")
                            return redirect('factura:lista_despachos_a_facturar')
                    
                    elif action == "actualizar_info":
                        form.save()
                        messages.success(request, f"Información de facturación para Despacho #{comprobante_despacho.pk} actualizada.")
                        return redirect('factura:detalle_despacho_factura', pk_despacho=pk_despacho)

                    elif action == "marcar_por_facturar":
                        if estado_factura_obj.estado == 'POR_FACTURAR':
                            messages.info(request, f"El Despacho #{comprobante_despacho.pk} ya está como 'Por Facturar'.")
                        else:
                            estado_factura_obj_actualizado_por_form = form.save(commit=False)
                            estado_factura_obj_actualizado_por_form.estado = 'POR_FACTURAR'
                            
                            
                            estado_factura_obj_actualizado_por_form.usuario_responsable = request.user                            
                            estado_factura_obj_actualizado_por_form.save()
                            
                            messages.info(request, f"Despacho #{comprobante_despacho.pk} regresado a estado 'Por Facturar'.")
                        return redirect('factura:lista_despachos_a_facturar')
                    else:
                        if form.has_changed():
                            form.save()
                            messages.info(request, f"Cambios guardados para Despacho #{comprobante_despacho.pk}.")
                        else:
                            messages.info(request, f"No se detectaron cambios para guardar en Despacho #{comprobante_despacho.pk}.")
                        return redirect('factura:detalle_despacho_factura', pk_despacho=pk_despacho)
            except Exception as e:
                messages.error(request, f"Error al procesar la facturación: {e}")
                
                
                
# --- INICIO: Lógica para agrupar ítems del despacho (Estilo PDF) ---
        items_despachados_originales = comprobante_despacho.detalles.select_related('producto').all()
        
        # --- INICIO: Cargar Mapeo de Tallas (PASO 8) ---
        empresa_obj = self.request.tenant
        TALLAS_MAPEO = empresa_obj.talla_mapeo if empresa_obj else {}
        # --- FIN: Cargar Mapeo de Tallas ---
        
        # 1. Obtener todas las tallas únicas de este despacho y ordenarlas
        tallas_unicas_set = set()
        for detalle in items_despachados_originales:
            # --- Aplicar Mapeo de Talla (PASO 8) ---
            talla_original = detalle.producto.talla or 'N/A'
            talla_como_texto = str(talla_original).strip()
            talla_display = TALLAS_MAPEO.get(talla_como_texto, talla_como_texto)
            # --- Fin Mapeo ---
            tallas_unicas_set.add(talla_display)
        
        try:
            # Forzamos la conversión a int para ordenar numéricamente
            tallas_header_ordenadas = sorted(list(tallas_unicas_set), key=int)
        except ValueError:
            # Si falla (ej. si una talla es 'N/A'), usa el ordenado alfabético
            tallas_header_ordenadas = sorted(list(tallas_unicas_set))

        # 2. Agrupar ítems y crear un dict de tallas
        items_agrupados_dict = defaultdict(lambda: {
            'referencia': '',
            'nombre': '',
            'color': '',
            'tallas_dict': defaultdict(int),
            'cantidad_total': 0
        })

        for detalle_item in items_despachados_originales:
            producto_obj = detalle_item.producto
            clave_agrupacion = (producto_obj.referencia, producto_obj.color or '-')
            grupo = items_agrupados_dict[clave_agrupacion]

            if not grupo['referencia']:
                grupo['referencia'] = producto_obj.referencia
                grupo['nombre'] = producto_obj.nombre
                grupo['color'] = producto_obj.color or '-'

# --- Aplicar Mapeo de Talla (PASO 8) ---
            talla_original = producto_obj.talla or 'N/A'
            talla_como_texto = str(talla_original).strip()
            talla_display = TALLAS_MAPEO.get(talla_como_texto, talla_como_texto)
            # --- Fin Mapeo ---

            grupo['tallas_dict'][talla_display] += detalle_item.cantidad_despachada
            grupo['cantidad_total'] += detalle_item.cantidad_despachada

        # 3. Post-procesar
        lista_items_final = []
        for grupo_dict in items_agrupados_dict.values():
            tallas_ordenadas_para_template = []
            for talla_header in tallas_header_ordenadas:
                cantidad = grupo_dict['tallas_dict'].get(talla_header, 0)
                tallas_ordenadas_para_template.append(cantidad)
            
            grupo_dict['tallas_ordenadas'] = tallas_ordenadas_para_template
            lista_items_final.append(grupo_dict)

        # 4. Ordenar la lista final
        lista_items_agrupados = sorted(
            lista_items_final, 
            key=lambda x: (x['referencia'], x['color'])
        )
        # --- FIN: Lógica para agrupar ítems ---



        context = {
            'titulo': f"Detalle Despacho #{comprobante_despacho.pk} para Facturación",
            'comprobante_despacho': comprobante_despacho,
            'estado_factura_obj': estado_factura_obj,
            'form': form, 
            'pedido': comprobante_despacho.pedido,
            'cliente': comprobante_despacho.pedido.cliente,
            'items_despachados_agrupados': lista_items_agrupados, # Usar los agrupados también aquí
            'tallas_header': tallas_header_ordenadas,
        }
        return render(request, self.template_name, context)


class InformeFacturadosPorFechaView(TenantAwareMixin, LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = 'factura/informe_facturados_fecha.html'
    form_class = InformeFacturadosFechaForm
    permission_required = 'factura.view_informe_facturados_fecha'
    login_url = reverse_lazy('core:acceso_denegado')

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para ver el informe de facturados por fecha.")
        return redirect(self.login_url)

    def get(self, request, *args, **kwargs):
        form = self.form_class(request.GET or None) 
        resultados = None
        total_general_facturado = Decimal('0.00') 


        if form.is_valid():
            fecha_inicio = form.cleaned_data['fecha_inicio']
            fecha_fin = form.cleaned_data['fecha_fin']

            fecha_fin_ajustada = timezone.make_aware(
                timezone.datetime.combine(fecha_fin, timezone.datetime.max.time()),
                timezone.get_current_timezone()
            )
            fecha_inicio_ajustada = timezone.make_aware(
                timezone.datetime.combine(fecha_inicio, timezone.datetime.min.time()),
                timezone.get_current_timezone()
            )

            resultados = EstadoFacturaDespacho.objects.filter(
                empresa=self.request.tenant,
                estado='FACTURADO',
                fecha_hora_facturado_sistema__gte=fecha_inicio_ajustada,
                fecha_hora_facturado_sistema__lte=fecha_fin_ajustada
            ).select_related(
                'despacho', 
                'despacho__pedido', 
                'despacho__pedido__cliente', 
                'usuario_responsable' 
            ).order_by('fecha_hora_facturado_sistema', 'despacho__pk')

        context = {
            'titulo': "Informe de Despachos Facturados por Fecha",
            'form': form,
            'resultados': resultados,
            'total_general_facturado': total_general_facturado, 
            'fecha_inicio_filtro': request.GET.get('fecha_inicio', ''), 
            'fecha_fin_filtro': request.GET.get('fecha_fin', ''),  
        }
        return render(request, self.template_name, context)
    
    
class InformeDespachosPorClienteView(TenantAwareMixin, LoginRequiredMixin, PermissionRequiredMixin, View):

    template_name = 'factura/informe_despachos_cliente.html'
    form_class = InformeDespachosPorClienteForm
    
    permission_required = 'factura.view_informe_despachos_cliente'
    login_url = reverse_lazy('core:acceso_denegado')

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para ver el informe de despachos por cliente.")
        return redirect(self.login_url)

    def get(self, request, *args, **kwargs):
        
        form = self.form_class(request.GET or None, empresa=self.request.tenant)
        clientes_encontrados = None 
        cliente_seleccionado = None
        despachos_cliente = None

        if form.is_valid():
            termino_busqueda = form.cleaned_data['termino_busqueda_cliente']

            # Buscar clientes que coincidan con el término de búsqueda
            query_cliente = Q(nombre_completo__icontains=termino_busqueda) | \
                            Q(identificacion__icontains=termino_busqueda)
            
            clientes_qs = Cliente.objects.filter(query_cliente, empresa=self.request.tenant)

            if clientes_qs.count() == 1:
                cliente_seleccionado = clientes_qs.first()
                # Obtener todos los ComprobanteDespacho para este cliente
                # y pre-cargar la información de EstadoFacturaDespacho
                despachos_cliente = ComprobanteDespacho.objects.filter(
                    pedido__cliente=cliente_seleccionado
                ).select_related(
                    'pedido',
                    'pedido__cliente', # Ya lo tenemos, pero por consistencia
                    'usuario_responsable' # Usuario de bodega
                ).prefetch_related(
                    Prefetch(
                        'estado_facturacion_info', # El related_name de OneToOneField en EstadoFacturaDespacho                       
                        queryset=EstadoFacturaDespacho.objects.filter(empresa=self.request.tenant),
                        to_attr='estado_factura_cached'
                    ),
                    'detalles__producto' # Para contar ítems o mostrar info si es necesario
                ).order_by('-fecha_hora_despacho')

            elif clientes_qs.count() > 1:
                clientes_encontrados = clientes_qs
                messages.info(request, f"Se encontraron {clientes_qs.count()} clientes. Por favor, seleccione uno de la lista o refine su búsqueda.")
            else:
                messages.warning(request, f"No se encontraron clientes que coincidan con '{termino_busqueda}'.")

        context = {
            'titulo': "Informe de Despachos por Cliente",
            'form': form,
            'clientes_encontrados': clientes_encontrados,
            'cliente_seleccionado': cliente_seleccionado,
            'despachos_cliente': despachos_cliente,
            'termino_busqueda_cliente_filtro': request.GET.get('termino_busqueda_cliente', ''),
        }
        return render(request, self.template_name, context)


class InformeDespachosPorEstadoView(TenantAwareMixin, LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = 'factura/informe_despachos_estado.html'
    form_class = InformeDespachosPorEstadoForm
    
    permission_required = 'factura.view_informe_despachos_estado'
    login_url = reverse_lazy('core:acceso_denegado')

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para ver el informe de despachos por estado.")
        return redirect(self.login_url)

    def get(self, request, *args, **kwargs):
        form = self.form_class(request.GET or None)
        resultados = None
        estado_seleccionado_display = None

        if form.is_valid():
            estado_query = form.cleaned_data['estado']
            
            # Obtener el nombre legible del estado para mostrarlo en el título
            for valor, nombre in EstadoFacturaDespacho.ESTADO_CHOICES:
                if valor == estado_query:
                    estado_seleccionado_display = nombre
                    break

            # Filtrar los EstadoFacturaDespacho por el estado seleccionado
            resultados = EstadoFacturaDespacho.objects.filter(
                empresa=self.request.tenant,
                estado=estado_query
            ).select_related(
                'despacho',
                'despacho__pedido',
                'despacho__pedido__cliente',
                'usuario_responsable'
            ).order_by('-despacho__fecha_hora_despacho') # Más recientes primero

        context = {
            'titulo': "Informe de Despachos por Estado de Facturación",
            'form': form,
            'resultados': resultados,
            'estado_seleccionado_display': estado_seleccionado_display,
            'estado_query_filtro': request.GET.get('estado', ''), # Para mantener en el form
        }
        return render(request, self.template_name, context)
    
class InformeDespachosPorPedidoView(TenantAwareMixin, LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Muestra un informe de todos los Comprobantes de Despacho asociados a un
    ID de Pedido específico, junto con su estado de facturación.
    """
    template_name = 'factura/informe_despachos_pedido.html'
    form_class = InformeDespachosPorPedidoForm
    
    permission_required = 'factura.view_informe_despachos_pedido'
    login_url = reverse_lazy('core:acceso_denegado')

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para ver el informe de despachos por pedido.")
        return redirect(self.login_url)

    def get(self, request, *args, **kwargs):
        form = self.form_class(request.GET or None, empresa=self.request.tenant)
        pedido_obj = None
        despachos_del_pedido = None

        if form.is_valid():
            pedido_id_query = form.cleaned_data['pedido_id']
            try:
                pedido_obj = Pedido.objects.select_related('cliente').get(
                    numero_pedido_empresa=pedido_id_query,
                    empresa=self.request.tenant # <-- FILTRO DE SEGURIDAD
                )
                
                # Obtener todos los ComprobanteDespacho para este pedido
                # y pre-cargar la información de EstadoFacturaDespacho
                despachos_del_pedido = ComprobanteDespacho.objects.filter(
                    pedido=pedido_obj
                ).select_related(
                    'usuario_responsable' # Usuario de bodega
                ).prefetch_related(
                    Prefetch(
                        'estado_facturacion_info',
                        queryset=EstadoFacturaDespacho.objects.filter(empresa=self.request.tenant),
                        to_attr='estado_factura_cached'
                    ),
                    'detalles__producto' # Para contar ítems o mostrar info si es necesario
                ).order_by('fecha_hora_despacho') # Más antiguos primero

                if not despachos_del_pedido.exists():
                    messages.info(request, f"El Pedido #{pedido_id_query} existe pero no tiene comprobantes de despacho registrados.")

            except Pedido.DoesNotExist:
                messages.error(request, f"El Pedido con ID #{pedido_id_query} no fue encontrado.")
            except Exception as e:
                messages.error(request, f"Ocurrió un error al buscar el pedido: {e}")


        context = {
            'titulo': "Informe de Despachos por Pedido",
            'form': form,
            'pedido_obj': pedido_obj,
            'despachos_del_pedido': despachos_del_pedido,
            'pedido_id_query_filtro': request.GET.get('pedido_id', ''), 
        }
        return render(request, self.template_name, context)
