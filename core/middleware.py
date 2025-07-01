# core/middleware.py

from clientes.models import Dominio

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Obtenemos el hostname (ej: 'empresa-prueba.localhost') desde la petición
        hostname = request.get_host().split(':')[0].lower()
        
        try:
            # Buscamos en la base de datos si este dominio está registrado
            dominio_obj = Dominio.objects.select_related('empresa').get(nombre_dominio=hostname)
            
            # ¡La magia sucede aquí! Adjuntamos la empresa a la petición
            request.tenant = dominio_obj.empresa
            
        except Dominio.DoesNotExist:
            # Si el dominio no se encuentra, adjuntamos None
            # Podrías redirigir a una página de error o a un dominio principal
            request.tenant = None

        response = self.get_response(request)
        return response