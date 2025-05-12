# En algún lugar de tu código (ej: utils.py o views.py)
import base64
import os
from django.conf import settings
from django.contrib.staticfiles import finders # Para encontrar el archivo estático

def image_to_base64(static_path):
    """
    Encuentra un archivo estático, lo lee y lo codifica en Base64
    para usarlo directamente en un src de <img> en HTML para PDFs.
    """
    try:
        # Encuentra la ruta completa del archivo estático
        # 'static_path' debe ser relativa a las carpetas static (ej: 'img/logo.jpg')
        file_path = finders.find(static_path)
        if not file_path:
            print(f"Error: No se encontró el archivo estático '{static_path}'")
            return None

        # Lee el archivo en modo binario
        with open(file_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

        # Determina el tipo MIME (simple)
        ext = os.path.splitext(static_path)[1].lower()
        if ext in ['.jpg', '.jpeg']:
            mime_type = 'image/jpeg'
        elif ext == '.png':
            mime_type = 'image/png'
        elif ext == '.gif':
             mime_type = 'image/gif'
        # Agrega más tipos si los necesitas (svg, webp, etc.)
        else:
            print(f"Error: Tipo de imagen no soportado '{ext}' para '{static_path}'")
            return None

        return f"data:{mime_type};base64,{encoded_string}"

    except Exception as e:
        print(f"Error al codificar la imagen '{static_path}' a Base64: {e}")
        return None