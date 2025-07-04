# core/middleware.py

from clientes.models import Dominio

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