# core/utils.py (o donde tengas definida get_logo_base64_despacho)
import os
import base64
from django.contrib.staticfiles import finders # Para encontrar archivos estáticos de forma robusta
from django.conf import settings # Para acceder a STATIC_ROOT en producción si es necesario
from django.template.loader import get_template
from weasyprint import HTML
from django.http import HttpResponse
from django.contrib import messages
from django.utils import timezone


def get_logo_base_64_despacho():
    # Ajusta esta ruta para que sea relativa a una carpeta 'static' de tu app 'core'
    # Por ejemplo, si tu logo está en 'core/static/core/img/logo.jpg',
    # la ruta para finders.find sería 'core/img/logo.jpg'.
    path_relativo_a_static = 'core/img/logo.jpg' # ¡¡¡AJUSTA ESTO!!!
    print(f"DEBUG (get_logo_base64): Buscando logo con path_relativo_a_static: '{path_relativo_a_static}'")

    logo_path_abs = finders.find(path_relativo_a_static)

    if not logo_path_abs:
        print(f"ERROR (get_logo_base_64): Logo NO ENCONTRADO usando staticfiles finders para '{path_relativo_a_static}'.")
        print("Verifica que la app 'core' esté en INSTALLED_APPS y la ruta al logo sea correcta dentro de 'core/static/'.")
        # Puedes añadir un fallback si es absolutamente necesario, pero finders es lo preferido.
        return None

    if not os.path.exists(logo_path_abs):
        print(f"ERROR (get_logo_base_64): El archivo de logo NO EXISTE en la ruta absoluta resuelta: {logo_path_abs}")
        return None
    try:
        with open(logo_path_abs, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

        filename_lower = logo_path_abs.lower()
        if filename_lower.endswith((".jpg", ".jpeg")):
            image_type = "image/jpeg"
        elif filename_lower.endswith(".png"):
            image_type = "image/png"
        # ... (otros tipos si es necesario) ...
        else:
            print(f"Advertencia (get_logo_base_64): Tipo de imagen desconocido. Usando image/jpeg.")
            image_type = "image/jpeg" 

        print(f"DEBUG (get_logo_base_64): Logo cargado desde {logo_path_abs}, tipo: {image_type}")
        return f"data:{image_type};base64,{encoded_string}"
    except Exception as e:
        print(f"Excepción al procesar el logo en get_logo_base_64_despacho: {e}")
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

