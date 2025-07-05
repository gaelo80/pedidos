# prospectos/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import CreateView, ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db import transaction, IntegrityError

from .models import Prospecto
from .forms import ProspectoForm, DocumentoFormSet, RechazoForm
from clientes.models import Cliente
from pedidos.models import Pedido # <-- 1. IMPORTAMOS EL MODELO PEDIDO
from core.mixins import TenantAwareMixin

class SolicitudCrearView(LoginRequiredMixin, PermissionRequiredMixin, TenantAwareMixin, CreateView):
    model = Prospecto
    form_class = ProspectoForm # <-- Usa el nuevo ProspectoForm
    template_name = 'prospectos/solicitud_crear_mejorada.html' # <-- Apunta a la nueva plantilla
    success_url = reverse_lazy('prospectos:lista_solicitudes')
    permission_required = 'prospectos.add_prospecto'

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            # Usa el nuevo DocumentoFormSet
            data['documentos_formset'] = DocumentoFormSet(self.request.POST, self.request.FILES, instance=self.object, prefix='documentos')
        else:
            # Usa el nuevo DocumentoFormSet
            data['documentos_formset'] = DocumentoFormSet(instance=self.object, prefix='documentos')
        data['titulo_pagina'] = "Crear Solicitud de Cliente Nuevo"
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        documentos_formset = context['documentos_formset']
        
        # Validación crucial: revisa que el formset también sea válido
        if documentos_formset.is_valid():
            with transaction.atomic():
                form.instance.empresa = self.request.tenant
                form.instance.vendedor_asignado = self.request.user
                self.object = form.save()

                documentos_formset.instance = self.object
                documentos_formset.save()
                
                messages.success(self.request, f"Solicitud para '{self.object.nombre_completo}' creada exitosamente.")
                # El super().form_valid(form) se encarga de la redirección
                return super().form_valid(form)
        else:
            # Si el formset no es válido, vuelve a renderizar el formulario con los errores
            messages.error(self.request, "Por favor, corrija los errores en los documentos adjuntos.")
            return self.form_invalid(form)

class SolicitudListView(LoginRequiredMixin, PermissionRequiredMixin, TenantAwareMixin, ListView):
    model = Prospecto
    template_name = 'prospectos/solicitud_lista.html'
    context_object_name = 'solicitudes'
    permission_required = 'prospectos.view_prospecto'
    paginate_by = 25
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.order_by('-fecha_solicitud')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Solicitudes de Clientes Nuevos"
        return context

class SolicitudDetailView(LoginRequiredMixin, PermissionRequiredMixin, TenantAwareMixin, DetailView):
    model = Prospecto
    template_name = 'prospectos/solicitud_detalle.html'
    context_object_name = 'solicitud'
    permission_required = 'prospectos.view_prospecto'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f"Detalle Solicitud #{self.object.pk}"
        context['rechazo_form'] = RechazoForm()
        return context


@require_POST
@login_required
@permission_required('prospectos.change_prospecto', raise_exception=True)
def aprobar_solicitud(request, pk):
    """
    Aprueba una solicitud, crea el cliente y activa los pedidos pendientes.
    """
    solicitud = get_object_or_404(Prospecto, pk=pk, empresa=request.tenant)

    if solicitud.estado not in ['PENDIENTE', 'EN_ESTUDIO']:
        messages.warning(request, f"La solicitud de '{solicitud.nombre_completo}' ya ha sido procesada.")
        return redirect('prospectos:detalle_solicitud', pk=solicitud.pk)

    try:
        with transaction.atomic():
            # Paso 1: Crear el nuevo cliente (sin cambios)
            nuevo_cliente = Cliente.objects.create(
                empresa=solicitud.empresa,
                nombre_completo=solicitud.nombre_completo,
                identificacion=solicitud.identificacion,
                ciudad=solicitud.ciudad,
                direccion=solicitud.direccion,
                telefono=solicitud.telefono,
                email=solicitud.email
            )
            
            # Paso 2: Actualizar el estado del prospecto (sin cambios)
            solicitud.estado = 'APROBADO'
            solicitud.save()
            
            # --- INICIO DE LA NUEVA LÓGICA ---
            # Paso 3: Buscar y actualizar los pedidos pendientes asociados a este prospecto.
            pedidos_pendientes = Pedido.objects.filter(
                prospecto=solicitud, 
                estado='PENDIENTE_CLIENTE'
            )
            
            pedidos_actualizados_count = 0
            for pedido in pedidos_pendientes:
                pedido.cliente = nuevo_cliente
                pedido.prospecto = None # Desvinculamos el prospecto
                pedido.estado = 'PENDIENTE_APROBACION_CARTERA' # Lo enviamos al flujo normal
                pedido.save()
                pedidos_actualizados_count += 1
            # --- FIN DE LA NUEVA LÓGICA ---

            # Mensaje de éxito mejorado
            success_message = f"¡Prospecto '{solicitud.nombre_completo}' aprobado! Se ha creado el cliente #{nuevo_cliente.pk} exitosamente."
            if pedidos_actualizados_count > 0:
                success_message += f" Además, {pedidos_actualizados_count} pedido(s) que estaban en espera han sido enviados a aprobación de cartera."

            messages.success(request, success_message)

    except IntegrityError:
        messages.error(request, f"Error: Ya existe un cliente con la identificación '{solicitud.identificacion}' en la base de datos.")
    except Exception as e:
        messages.error(request, f"Ocurrió un error inesperado al aprobar la solicitud: {e}")

    return redirect('prospectos:detalle_solicitud', pk=solicitud.pk)


@require_POST
@login_required
@permission_required('prospectos.change_prospecto', raise_exception=True)
def rechazar_solicitud(request, pk):
    # (Esta función se mantiene sin cambios)
    solicitud = get_object_or_404(Prospecto, pk=pk, empresa=request.tenant)
    if solicitud.estado not in ['PENDIENTE', 'EN_ESTUDIO']:
        messages.warning(request, f"La solicitud de '{solicitud.nombre_completo}' ya ha sido procesada.")
        return redirect('prospectos:detalle_solicitud', pk=solicitud.pk)
    form = RechazoForm(request.POST)
    if form.is_valid():
        solicitud.estado = 'RECHAZADO'
        solicitud.notas_evaluacion = form.cleaned_data['notas_evaluacion']
        solicitud.save()
        messages.info(request, f"La solicitud de '{solicitud.nombre_completo}' ha sido rechazada.")
    else:
        messages.error(request, "Error al procesar el rechazo. El motivo es obligatorio.")
    return redirect('prospectos:detalle_solicitud', pk=solicitud.pk)