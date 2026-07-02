import logging
import traceback
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseRedirect
from clientes.models import Dominio

# CONECTAMOS EL MIDDLEWARE A TU LOGGER EXISTENTE
logger = logging.getLogger('django')

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        hostname = request.get_host().split(':')[0].lower()
        try:
            dominio_obj = Dominio.objects.select_related('empresa').get(nombre_dominio=hostname)
            # USAMOS 'request.tenant' COMO ESTÁNDAR EN TODO EL PROYECTO
            request.tenant = dominio_obj.empresa
        except Dominio.DoesNotExist:
            request.tenant = None
        
        response = self.get_response(request)
        return response

class GlobalExceptionMiddleware:
    """
    Middleware global para capturar excepciones no controladas (Error 500).
    Evita la pantalla de error de Django, notifica al usuario y registra el error en django.log.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        # 1. Registrar el error técnico en logs/django.log (Tu configuración actual)
        logger.error(f"💥 Error Global Capturado: {str(exception)}")
        logger.error(traceback.format_exc())

        # 2. Obtener la página desde donde venía el usuario (para regresarlo allí de forma segura)
        referer = request.META.get('HTTP_REFERER')

        # 3. Preparar el mensaje amigable para la interfaz
        mensaje_error = f"Ocurrió un error inesperado procesando la solicitud: {str(exception)}"
        
        # 4. Enviar la notificación al sistema de 'messages' de Django
        messages.error(request, mensaje_error)

        # 5. Redirigir para evitar la pantalla 500
        if referer:
            return HttpResponseRedirect(referer)
        
        # Si no hay página anterior, enviarlo al inicio
        return redirect('/')