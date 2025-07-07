# core/utils.py
import os
import base64
from django.contrib.staticfiles import finders # Para encontrar archivos estáticos de forma robusta
from django.conf import settings # Para acceder a STATIC_ROOT en producción si es necesario
from django.template.loader import get_template
from weasyprint import HTML
from django.http import HttpResponse
from django.contrib import messages
from django.utils import timezone


def get_logo_base_64_despacho(empresa):
    """
    Retorna el logo en base64 para una empresa dada, si tiene uno.
    """
    if not empresa or not empresa.logo:
        print("DEBUG: Empresa no tiene logo asignado.")
        return None

    try:
        with empresa.logo.open('rb') as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

        filename_lower = empresa.logo.name.lower()
        if filename_lower.endswith((".jpg", ".jpeg")):
            image_type = "image/jpeg"
        elif filename_lower.endswith(".png"):
            image_type = "image/png"
        else:
            image_type = "image/jpeg" 

        print(f"DEBUG: Logo cargado dinámicamente para empresa '{empresa.nombre}'")
        return f"data:{image_type};base64,{encoded_string}"
    except Exception as e:
        print(f"Error al leer el logo para la empresa '{empresa.nombre}': {e}")
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

