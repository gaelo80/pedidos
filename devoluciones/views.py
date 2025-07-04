from django.shortcuts import render
from django.contrib.auth.decorators import login_required, permission_required
from devoluciones.forms import DevolucionClienteForm, DetalleDevolucionFormSet, DevolucionCliente
from bodega.models import MovimientoInventario
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.db import transaction
from django.contrib import messages
from django.db.models import Sum
from django.template.loader import get_template
from core.utils import get_logo_base_64_despacho
from django.http import HttpResponse
from weasyprint import HTML



@login_required
@permission_required('devoluciones.add_devolucioncliente', login_url='core:acceso_denegado')
def vista_crear_devolucion(request):
    """
    Maneja la creación de una nueva Devolución de Cliente con sus detalles.
    """
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:index')
    
    if request.method == 'POST':
        form = DevolucionClienteForm(request.POST, empresa=empresa_actual)
        formset = DetalleDevolucionFormSet(request.POST, prefix='detalles', form_kwargs={'empresa': empresa_actual})


        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():

                    devolucion_header = form.save(commit=False)
                    devolucion_header.usuario = request.user
                    devolucion_header.fecha_hora = timezone.now()
                    devolucion_header.empresa = empresa_actual
                    devolucion_header.save()


                    formset.instance = devolucion_header
                    formset.save() 


                    print(f"Procesando stock para Devolución #{devolucion_header.pk}...")
                    detalles_guardados = devolucion_header.detalles.all() 
                    for detalle in detalles_guardados:
                       
                        if detalle.estado_producto == 'BUENO' and detalle.cantidad > 0:
                            MovimientoInventario.objects.create(
                                empresa=empresa_actual,
                                producto=detalle.producto,
                                cantidad=detalle.cantidad, 
                                tipo_movimiento='ENTRADA_DEVOLUCION', 
                                documento_referencia=f'Devolución #{devolucion_header.pk}',
                                usuario=request.user,
                                notas=f'Entrada por devolución cliente {devolucion_header.cliente} (Estado: Bueno)'
                            )
                            print(f" + Stock actualizado para {detalle.producto}: +{detalle.cantidad}")

                    return redirect('devoluciones:detalle_devolucion', pk=devolucion_header.pk) # Redirige a la misma vista para limpiar

            except Exception as e:
                messages.error(request, f"Error al guardar la devolución: {e}")


        else:
            messages.error(request, "Por favor corrige los errores en el formulario.")
    else: 

        form = DevolucionClienteForm(empresa=empresa_actual)
        formset = DetalleDevolucionFormSet(prefix='detalles', form_kwargs={'empresa': empresa_actual})

    context = {
        'form': form,
        'formset': formset,
        'titulo': f'Registrar Devolución ({empresa_actual.nombre})'
    }

    return render(request, 'devoluciones/crear_devolucion.html', context)



@login_required
def imprimir_comprobante_devolucion(request, devolucion_id): # Mantenemos el nombre original o cámbialo a generar_devolucion_pdf
    """
    Genera un comprobante de devolución en formato PDF usando WeasyPrint.
    """
    
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        return HttpResponse("Acceso no válido. Empresa no identificada.", status=403)
    
    try:
        
        devolucion = get_object_or_404(DevolucionCliente, pk=devolucion_id, empresa=empresa_actual)
        detalles = devolucion.detalles.select_related('producto').all()
        total_cantidad_devuelta = detalles.aggregate(total=Sum('cantidad'))['total'] or 0


        logo_b64 = None
        try:
            
            logo_b64 = get_logo_base_64_despacho(empresa=empresa_actual)
        except Exception as e:
            print(f"Advertencia PDF Devolución: No se pudo cargar el logo: {e}")

        # 4. Preparar Contexto (¡SIMPLIFICADO!)
        context = {
            'empresa': empresa_actual,
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
        template_path = 'devoluciones/devolucion_comprobante.html'
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


@login_required # O AÑADE UN @permission_required si es necesario
def vista_detalle_devolucion(request, pk):
    """
    Muestra el detalle de una devolución específica, asegurando
    que pertenezca al inquilino actual.
    """
    # 1. OBTENER EL INQUILINO ACTUAL
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. Empresa no identificada.")
        return redirect('core:index')

    # 2. OBTENER DEVOLUCIÓN DE FORMA SEGURA
    devolucion = get_object_or_404(DevolucionCliente, pk=pk, empresa=empresa_actual)
    
    # 3. CARGAR LOS DETALLES DE FORMA EFICIENTE
    detalles_devolucion = devolucion.detalles.select_related('producto').all()

    # 4. PREPARAR EL CONTEXTO
    context = {
        'devolucion': devolucion,
        'detalles': detalles_devolucion,
        'empresa': empresa_actual,
        'titulo': f"Detalle Devolución #{devolucion.pk} ({empresa_actual.nombre})"
    }
    
    return render(request, 'devoluciones/devolucion_detalle.html', context)

def vista_mi_template(request):
    empresa = request.user.empresa  # la empresa del usuario autenticado
    return render(request, 'mi_template.html', {'empresa': empresa})
