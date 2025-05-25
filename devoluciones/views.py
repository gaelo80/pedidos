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
                    return redirect('devoluciones:detalle_devolucion', pk=devolucion_header.pk) # Redirige a la misma vista para limpiar

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
    return render(request, 'devoluciones/crear_devolucion.html', context)


# Create your views here.
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
            logo_b64 = get_logo_base_64_despacho()
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
    return render(request, 'devoluciones/devolucion_detalle.html', context)