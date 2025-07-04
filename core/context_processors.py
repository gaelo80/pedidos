# core/context_processors.py

def empresa_context(request):
    # BUSCAMOS LA VARIABLE 'request.tenant'
    if hasattr(request, 'tenant') and request.tenant:
        return {
            'titulo_web': request.tenant.titulo_web,
            'nombre_empresa': request.tenant.nombre
        }
    return {}