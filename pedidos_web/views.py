import json
import hmac
import hashlib
import base64
import logging
import os
import threading
from urllib.parse import urlencode
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.db import transaction, IntegrityError
from django.conf import settings
from clientes.models import Empresa, Ciudad
from pedidos_online.models import ClienteOnline
from pedidos.models import Pedido, DetallePedido
from productos.models import Producto, ReferenciaColor
from bodega.models import MovimientoInventario, Bodega
from vendedores.models import Vendedor
from core.auth_utils import es_administracion
from decouple import config
import requests
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from . import shopify_api



logger = logging.getLogger(__name__)
SHOPIFY_SECRET = config('SHOPIFY_SECRET')

@csrf_exempt
def webhook_nuevo_pedido_shopify(request):
    if request.method != 'POST':
        return HttpResponse(status=405)

    # 1. Validación de seguridad
    hmac_header = request.META.get('HTTP_X_SHOPIFY_HMAC_SHA256')
    if not hmac_header:
        return HttpResponseForbidden("Falta la firma")

    data = request.body
    digest = hmac.new(SHOPIFY_SECRET.encode('utf-8'), data, hashlib.sha256).digest()
    if not hmac.compare_digest(base64.b64encode(digest).decode('utf-8'), hmac_header):
        return HttpResponseForbidden("Firma inválida")

    try:
        orden = json.loads(data)
        
        # ---> EL ATRAPADOR DE DATOS (NUEVO) <---
        # Esto creará un archivo llamado 'pedido_shopify_ejemplo.json' en la raíz de tu proyecto
        ruta_archivo = os.path.join(settings.BASE_DIR, 'pedido_shopify_ejemplo.json')
        with open(ruta_archivo, 'w', encoding='utf-8') as f:
            json.dump(orden, f, indent=4, ensure_ascii=False)
        print(f"📦 ¡ATRAPADO! Todo el JSON de Shopify se guardó en: {ruta_archivo}")
        # ----------------------------------------

        # La empresa se resuelve por el dominio al que Shopify le pega el webhook
        # (el mismo TenantMiddleware que usa el resto del sistema) -- NUNCA la
        # primera empresa de la base de datos, o los webhooks de una tienda
        # terminarían mezclados con los pedidos de otra empresa.
        empresa_actual = getattr(request, 'tenant', None)
        if not empresa_actual:
            logger.error("Webhook de pedido Shopify recibido en un dominio sin empresa asociada (Host: %s)", request.get_host())
            return HttpResponse(status=200)

        vendedor_shopify = Vendedor.objects.filter(user__username='bot.shopify').first()

        if not vendedor_shopify:
            print("⚠️ Cuidado: No has creado el vendedor 'bot.shopify' en el admin.")

# --- A. Guardar Cliente ---
        cliente_data = orden.get('customer') or {}
        direccion_data = orden.get('shipping_address') or {}

        if cliente_data:
            # En el checkout de Shopify no existe un campo nativo de "Identificación" (cédula/NIT),
            # así que en esta tienda se captura reutilizando el campo "Company" de la dirección de envío.
            identificacion_real = (direccion_data.get('company') or '').strip()
            if not identificacion_real:
                # Sin cédula capturada: usamos el ID de cliente de Shopify para no romper la unicidad.
                identificacion_real = f"SHOPIFY-{cliente_data.get('id')}"

            # Dirección completa = calle/carrera (address1) + complemento (apto/interior, address2)
            partes_direccion = [p for p in [direccion_data.get('address1'), direccion_data.get('address2')] if p]
            direccion_completa = ", ".join(partes_direccion) or 'Sin dirección'

            ciudad_obj = None
            nombre_ciudad = (direccion_data.get('city') or '').strip()
            if nombre_ciudad:
                ciudad_obj = Ciudad.objects.filter(nombre__iexact=nombre_ciudad).first()
                if not ciudad_obj:
                    ciudad_obj = Ciudad.objects.create(nombre=nombre_ciudad)

            cliente_online, _ = ClienteOnline.objects.update_or_create(
                identificacion=identificacion_real,
                empresa=empresa_actual,
                defaults={
                    'nombre_completo': f"{cliente_data.get('first_name', '')} {cliente_data.get('last_name', '')}".strip(),
                    # Si viene null, lo cambiamos por un string vacío ''
                    'email': cliente_data.get('email') or '',
                    'telefono': direccion_data.get('phone') or cliente_data.get('phone') or 'Sin teléfono',
                    'direccion': direccion_completa,
                    'ciudad': ciudad_obj,
                    'tipo_cliente': 'DETAL'
                }
            )

        else:
            cliente_online = None

        # --- B. Lógica de Pago y Estados ---
        estado_financiero_ingles = orden.get('financial_status')
        es_pago_confirmado = (estado_financiero_ingles == 'paid')
        estado_django = 'LISTO_BODEGA_DIRECTO' if es_pago_confirmado else 'BORRADOR'
        
        # 1. Diccionario traductor de estados financieros
        traductor_estados = {
            'paid': 'Pagado',
            'pending': 'Pendiente',
            'authorized': 'Autorizado',
            'partially_paid': 'Pago Parcial',
            'refunded': 'Reembolsado',
            'partially_refunded': 'Reembolso Parcial',
            'voided': 'Anulado'
        }
        estado_espanol = traductor_estados.get(estado_financiero_ingles, estado_financiero_ingles)

        # 2. Extraer el método de pago de Shopify
        nombres_pasarelas = orden.get('payment_gateway_names', [])
        medio_pago_shopify = ", ".join(nombres_pasarelas) if nombres_pasarelas else "No especificado"
        
        # 3. Lógica para Forma de Pago Nativa (Mapeo a models.py)
        pasarelas_lower = medio_pago_shopify.lower()
        if 'addi' in pasarelas_lower:
            forma_pago_django = 'ADDI'
        else:
            forma_pago_django = 'OTRO_ONLINE'
        
        # 4. Preparar la nota final
        numero_shopify = orden.get('order_number')
        texto_nota = f"Orden Shopify #{numero_shopify} | Estado: {estado_espanol} | Pasarela: {medio_pago_shopify}"

        with transaction.atomic():
            # Escudo antiduplicados
            if Pedido.objects.filter(empresa=empresa_actual, notas__icontains=f"Orden Shopify #{numero_shopify}").exists():
                print(f"🛑 ATENCIÓN: La orden #{numero_shopify} ya estaba registrada. Se aborta.")
                return HttpResponse(status=200)

            print("✅ Pasó el escudo antiduplicados. Intentando guardar en la base de datos...")
            
            # Creamos el pedido asignando la forma de pago exacta
            pedido = Pedido.objects.create(
                empresa=empresa_actual,
                cliente_online=cliente_online,
                vendedor=vendedor_shopify,
                tipo_pedido='ONLINE',
                estado=estado_django,
                forma_pago=forma_pago_django,
                notas=texto_nota,
                fecha_hora=parse_datetime(orden.get('created_at'))
            )
            print(f"🎉 ¡PEDIDO CREADO! Consecutivo asignado: {pedido.numero_pedido_empresa}")

        # --- D. Procesar Detalles ---
        doc_ref_base = f'Pedido #{pedido.numero_pedido_empresa} (Shopify)'

        for item in (orden.get('line_items') or []):
            variant_id = str(item.get('variant_id'))
            cantidad_comprada = int(item.get('quantity', 0))
            
            producto_interno = Producto.objects.filter(shopify_variant_id=variant_id, empresa=empresa_actual).first()
            
            if producto_interno:
                DetallePedido.objects.create(
                    pedido=pedido,
                    producto=producto_interno,
                    cantidad=cantidad_comprada,
                    precio_unitario=item.get('price')
                )

                if es_pago_confirmado:
                    MovimientoInventario.objects.create(
                        empresa=empresa_actual,
                        producto=producto_interno,
                        bodega=Bodega.objects.principal(empresa_actual),
                        tipo_movimiento='SALIDA_VENTA_PENDIENTE',
                        documento_referencia=doc_ref_base,
                        cantidad=-cantidad_comprada,
                        usuario=vendedor_shopify.user if vendedor_shopify else None
                    )
                    print(f"✅ Activado en Bodega: {producto_interno.referencia}")
                else:
                    print(f"⏳ Guardado como borrador: Pago {estado_espanol}")
            else:
                print(f"⚠️ Variante {variant_id} no enlazada en Django.")

        return HttpResponse(status=200)

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ Error CRÍTICO al guardar en DB: {str(e)}")
        return HttpResponse(status=200)
    
@csrf_exempt
def webhook_producto_shopify(request):
    if request.method != 'POST':
        return HttpResponse(status=405)

    # 1. Validación de seguridad (La misma de los pedidos)
    hmac_header = request.META.get('HTTP_X_SHOPIFY_HMAC_SHA256')
    if not hmac_header:
        return HttpResponseForbidden("Falta la firma")

    data = request.body
    digest = hmac.new(SHOPIFY_SECRET.encode('utf-8'), data, hashlib.sha256).digest()
    if not hmac.compare_digest(base64.b64encode(digest).decode('utf-8'), hmac_header):
        return HttpResponseForbidden("Firma inválida")

    try:
        producto_shopify = json.loads(data)
        empresa_actual = getattr(request, 'tenant', None)
        if not empresa_actual:
            logger.error("Webhook de producto Shopify recibido en un dominio sin empresa asociada (Host: %s)", request.get_host())
            return HttpResponse(status=200)

        # 2. Recorrer las variantes (tallas/colores) que crearon en Shopify
        for variant in producto_shopify.get('variants', []):
            variant_id = str(variant.get('id'))
            
            # Extraemos el SKU (o el barcode, dependiendo de qué campo usen en Shopify)
            sku_shopify = variant.get('sku') or variant.get('barcode')
            
            if not sku_shopify:
                continue # Si no le pusieron SKU en Shopify, lo ignoramos

            # 3. Buscamos el producto en TU base de datos usando el código de barras
            # Asumo que tu campo se llama 'codigo_barras', cámbialo si se llama distinto
            producto_local = Producto.objects.filter(
                codigo_barras__iexact=sku_shopify.strip(), 
                empresa=empresa_actual
            ).first()

            if producto_local:
                # 4. ¡Hacemos la magia del enlace automático!
                producto_local.shopify_variant_id = variant_id
                producto_local.save()
                print(f"🔗 AUTO-ENLACE EXITOSO: Producto {producto_local.referencia} ahora está conectado con Shopify.")
            else:
                print(f"⚠️ El encargado creó el producto con SKU {sku_shopify} en Shopify, pero ese código no existe en Django.")

        return HttpResponse(status=200)

    except Exception as e:
        print(f"❌ Error en Webhook de Producto: {str(e)}")
        return HttpResponse(status=200)
    

def obtener_token_temporal(shop_url, client_id, client_secret):
    url = f"https://{shop_url}/admin/oauth/access_token"
    payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'client_credentials'
    }
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        return response.json().get('access_token'), None
    except requests.exceptions.HTTPError as e:
        mensaje_error = f"Shopify rechazó la conexión (HTTP {response.status_code}). Detalle: {response.text}"
        return None, mensaje_error
    except Exception as e:
        mensaje_error = f"Error interno: {str(e)}"
        return None, mensaje_error
    
def _obtener_todos_los_productos_shopify(headers, shop_url):
    """Recorre TODAS las páginas de productos (no solo los primeros 250)."""
    url = f"https://{shop_url}/admin/api/{shopify_api.SHOPIFY_API_VERSION}/products.json?limit=250"
    productos = []
    while url:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        productos.extend(response.json().get('products', []))
        url = response.links.get('next', {}).get('url')
    return productos


def _actualizar_progreso_sync(empresa_id, procesados, exitosos, errores, mensaje, total=None):
    campos = {
        'shopify_sync_procesados': procesados,
        'shopify_sync_exitosos': exitosos,
        'shopify_sync_errores': errores,
        'shopify_sync_mensaje': mensaje,
        'shopify_sync_actualizado_en': timezone.now(),
    }
    if total is not None:
        campos['shopify_sync_total'] = total
    Empresa.objects.filter(pk=empresa_id).update(**campos)


def _finalizar_sync(empresa_id, mensaje):
    Empresa.objects.filter(pk=empresa_id).update(
        shopify_sync_activo=False, shopify_sync_mensaje=mensaje, shopify_sync_actualizado_en=timezone.now(),
    )


def _hilo_enlazar_productos(empresa_id, headers, shop_url):
    """Corre en un hilo aparte para no bloquear la petición (evita el timeout de nginx)."""
    try:
        productos_shopify = _obtener_todos_los_productos_shopify(headers, shop_url)
        variantes = [(item, v) for item in productos_shopify for v in item.get('variants', [])]
        total = len(variantes)
        exitosos = 0
        errores = 0

        for indice, (item, variant) in enumerate(variantes, start=1):
            # Se prefiere 'barcode' sobre 'sku': es el campo que este sistema
            # controla de forma consistente; el 'sku' puede haber quedado
            # desactualizado por una edición manual o un error histórico.
            sku_shopify = variant.get('barcode') or variant.get('sku')
            if sku_shopify:
                producto_local = Producto.objects.filter(
                    empresa_id=empresa_id, activo=True, codigo_barras__iexact=sku_shopify.strip()
                ).first()
                if producto_local:
                    if not producto_local.shopify_variant_id:
                        try:
                            producto_local.shopify_variant_id = str(variant.get('id'))
                            producto_local.save(update_fields=['shopify_variant_id'])
                            exitosos += 1
                        except IntegrityError:
                            # Ese shopify_variant_id ya está en uso por otro producto
                            # (dato inconsistente en Shopify: dos variantes con el
                            # mismo código). Se registra como error y se sigue con
                            # el resto, en vez de abortar todo el enlace.
                            errores += 1
                            logger.error(
                                f"No se pudo enlazar {producto_local.referencia} talla "
                                f"{producto_local.talla}: shopify_variant_id "
                                f"{variant.get('id')} ya está en uso por otro producto."
                            )
                elif not Producto.objects.filter(codigo_barras__iexact=sku_shopify.strip()).exists():
                    errores += 1

            if indice % 5 == 0 or indice == total:
                _actualizar_progreso_sync(empresa_id, indice, exitosos, errores, f"Procesando {indice} de {total}...", total=total)

        _finalizar_sync(empresa_id, f"Enlace terminado: {exitosos} producto(s) enlazado(s), {errores} sin coincidencia.")
    except Exception as e:
        _finalizar_sync(empresa_id, f"Error: {str(e)}")


def _hilo_subir_inventario(empresa_id, headers, shop_url, location_id):
    """
    Corre en un hilo aparte para no bloquear la petición (evita el timeout de
    nginx). Empuja el inventario en LOTES por GraphQL (en vez de una llamada
    REST por variante), lo que reduce cientos de llamadas a un puñado. Solo
    cuenta el stock de las bodegas habilitadas para venta web
    ('disponible_venta_web'), no el de toda la empresa.
    """
    try:
        productos_shopify = _obtener_todos_los_productos_shopify(headers, shop_url)

        empresa = Empresa.objects.filter(pk=empresa_id).first()
        _actualizar_progreso_sync(empresa_id, 0, 0, 0, "Revisando y corrigiendo el catálogo...", total=0)
        reporte_auditoria = shopify_api.auditar_y_corregir_catalogo(empresa, productos_shopify)

        variant_ids_shopify = {
            str(v.get('id')) for item in productos_shopify for v in item.get('variants', [])
        }

        productos_a_sincronizar = list(
            Producto.objects.filter(
                empresa_id=empresa_id, activo=True, shopify_variant_id__in=variant_ids_shopify
            )
        )
        total = len(productos_a_sincronizar)
        _actualizar_progreso_sync(empresa_id, 0, 0, 0, f"Sincronizando {total} variante(s) en lotes...", total=total)

        exitosos_total = 0
        errores_total = 0
        tamano_lote = shopify_api._TAMANO_LOTE_INVENTARIO
        for inicio in range(0, total, tamano_lote):
            lote = productos_a_sincronizar[inicio:inicio + tamano_lote]
            exitosos_lote, errores_lote = shopify_api.sincronizar_inventario_lote(lote, location_id)
            exitosos_total += exitosos_lote
            errores_total += errores_lote
            procesados = min(inicio + tamano_lote, total)
            _actualizar_progreso_sync(
                empresa_id, procesados, exitosos_total, errores_total,
                f"Procesando {procesados} de {total}...", total=total,
            )

        mensaje = f"Inventario actualizado: {exitosos_total} exitoso(s), {errores_total} con error."
        if reporte_auditoria['titulos_corregidos']:
            mensaje += f" Títulos corregidos automáticamente: {len(reporte_auditoria['titulos_corregidos'])}."
        if reporte_auditoria['pendientes_revision_manual']:
            mensaje += (
                f" {len(reporte_auditoria['pendientes_revision_manual'])} color(es) siguen sin subir "
                "a Shopify (revisar en Catálogo Shopify)."
            )
        _finalizar_sync(empresa_id, mensaje)
    except Exception as e:
        _finalizar_sync(empresa_id, f"Error: {str(e)}")


@login_required
def panel_sincronizacion_shopify(request):
    # --- LÓGICA MULTI-EMPRESA ESTANDARIZADA ---
    empresa_actual = getattr(request, 'tenant', None)

    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:acceso_denegado')

    # Creamos una base de consulta filtrada dinámicamente por la empresa actual del usuario.
    productos_base = Producto.objects.filter(activo=True, empresa=empresa_actual)
    total_productos = productos_base.count()
    sincronizados = productos_base.filter(shopify_variant_id__isnull=False).count()

    if request.method == 'POST':
        accion = request.POST.get('accion')

        empresa_actual.refresh_from_db()
        if empresa_actual.shopify_sync_activo:
            messages.warning(request, "Ya hay una sincronización en curso — espera a que termine (ver la barra de progreso abajo).")
            return redirect('pedidos_web:panel_sincronizacion')

        raw_url = config('SHOPIFY_URL')
        shop_url = raw_url.replace('https://', '').replace('http://', '').strip('/')
        client_id = config('SHOPIFY_CLIENT_ID')
        client_secret = config('SHOPIFY_CLIENT_SECRET')

        token, mensaje_de_error = obtener_token_temporal(shop_url, client_id, client_secret)

        if not token:
            messages.error(request, f"Fallo de autenticación: {mensaje_de_error}")
        elif accion == 'enlazar_productos':
            headers = {"X-Shopify-Access-Token": token, "Content-Type": "application/json"}
            empresa_actual.shopify_sync_activo = True
            empresa_actual.shopify_sync_accion = 'enlazar_productos'
            empresa_actual.shopify_sync_mensaje = 'Consultando productos en Shopify...'
            empresa_actual.shopify_sync_total = 0
            empresa_actual.shopify_sync_procesados = 0
            empresa_actual.shopify_sync_exitosos = 0
            empresa_actual.shopify_sync_errores = 0
            empresa_actual.save(update_fields=[
                'shopify_sync_activo', 'shopify_sync_accion', 'shopify_sync_mensaje',
                'shopify_sync_total', 'shopify_sync_procesados', 'shopify_sync_exitosos', 'shopify_sync_errores',
            ])
            threading.Thread(target=_hilo_enlazar_productos, args=(empresa_actual.pk, headers, shop_url), daemon=True).start()
            messages.success(request, "Se inició el enlace de productos en segundo plano — sigue el progreso abajo.")
        elif accion == 'subir_inventario':
            location_id = config('SHOPIFY_LOCATION_ID', default='')
            if not location_id:
                messages.error(request, "Falta configurar el SHOPIFY_LOCATION_ID en el archivo .env")
            else:
                headers = {"X-Shopify-Access-Token": token, "Content-Type": "application/json"}
                empresa_actual.shopify_sync_activo = True
                empresa_actual.shopify_sync_accion = 'subir_inventario'
                empresa_actual.shopify_sync_mensaje = 'Consultando productos en Shopify...'
                empresa_actual.shopify_sync_total = 0
                empresa_actual.shopify_sync_procesados = 0
                empresa_actual.shopify_sync_exitosos = 0
                empresa_actual.shopify_sync_errores = 0
                empresa_actual.save(update_fields=[
                    'shopify_sync_activo', 'shopify_sync_accion', 'shopify_sync_mensaje',
                    'shopify_sync_total', 'shopify_sync_procesados', 'shopify_sync_exitosos', 'shopify_sync_errores',
                ])
                threading.Thread(target=_hilo_subir_inventario, args=(empresa_actual.pk, headers, shop_url, location_id), daemon=True).start()
                messages.success(request, "Se inició la actualización de inventario en segundo plano — sigue el progreso abajo.")

        return redirect('pedidos_web:panel_sincronizacion')

    search_query = request.GET.get('q', '').strip()
    huerfanos = productos_base.filter(shopify_variant_id__isnull=True)

    if search_query:
        huerfanos = huerfanos.filter(
            Q(referencia__icontains=search_query) |
            Q(codigo_barras__icontains=search_query)
        )

    empresa_actual.refresh_from_db()
    context = {
        'total_productos': total_productos,
        'sincronizados': sincronizados,
        'pendientes': total_productos - sincronizados,
        'huerfanos': huerfanos,
        'search_query': search_query,
        'sync_activo': empresa_actual.shopify_sync_activo,
        'sync_accion': empresa_actual.shopify_sync_accion,
        'sync_total': empresa_actual.shopify_sync_total,
        'sync_procesados': empresa_actual.shopify_sync_procesados,
        'sync_exitosos': empresa_actual.shopify_sync_exitosos,
        'sync_errores': empresa_actual.shopify_sync_errores,
        'sync_mensaje': empresa_actual.shopify_sync_mensaje,
    }
    return render(request, 'pedidos_web/sincronizacion_shopify.html', context)


@login_required
def api_shopify_sync_progreso(request):
    """Consulta AJAX del progreso de la sincronización en curso (para la barra de progreso)."""
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        return JsonResponse({'error': 'No se pudo identificar la empresa.'}, status=403)

    empresa_actual.refresh_from_db()
    return JsonResponse({
        'activo': empresa_actual.shopify_sync_activo,
        'accion': empresa_actual.shopify_sync_accion,
        'total': empresa_actual.shopify_sync_total,
        'procesados': empresa_actual.shopify_sync_procesados,
        'exitosos': empresa_actual.shopify_sync_exitosos,
        'errores': empresa_actual.shopify_sync_errores,
        'mensaje': empresa_actual.shopify_sync_mensaje,
    })


# =========================================================================
# GESTIÓN DE CATÁLOGO POR REFERENCIA (subir / actualizar / bajar de Shopify)
# =========================================================================

@login_required
@user_passes_test(es_administracion, login_url='core:acceso_denegado')
def gestion_catalogo_shopify(request):
    """
    Lista una fila por Referencia+Color (mismo agrupador que ya usa el
    catálogo de fotos: ReferenciaColor) con toda su información y el estado
    de sincronización con Shopify, para subir/actualizar/bajar cada una.
    """
    empresa_actual = getattr(request, 'tenant', None)
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:acceso_denegado')

    if not empresa_actual.usa_shopify:
        messages.error(request, "Esta empresa no tiene activada la integración con Shopify.")
        return redirect('core:index')

    search_query = request.GET.get('q', '').strip()

    referencias_qs = ReferenciaColor.objects.filter(
        empresa=empresa_actual
    ).order_by('referencia_base', 'color')

    if search_query:
        referencias_qs = referencias_qs.filter(
            Q(referencia_base__icontains=search_query) |
            Q(variantes__codigo_barras__icontains=search_query)
        ).distinct()

    referencias_qs = referencias_qs.prefetch_related('fotos_agrupadas', 'variantes')
    paginator = Paginator(referencias_qs, 100)
    page_obj = paginator.get_page(request.GET.get('page'))

    filas = []
    for rc in page_obj.object_list:
        variantes = [v for v in rc.variantes.all() if v.activo]
        if not variantes:
            continue
        variantes.sort(key=lambda p: (p.talla if p.talla is not None else 0))
        primera_foto = next(iter(rc.fotos_agrupadas.all()), None)
        filas.append({
            'referencia_color': rc,
            'variantes': variantes,
            'foto': primera_foto,
            'nombre': variantes[0].nombre,
            'genero': variantes[0].get_genero_display() if variantes[0].genero else '',
            'costo': variantes[0].costo,
            'precio_venta': variantes[0].precio_venta,
            'stock_total': sum(v.stock_disponible_para_canal('WEB') for v in variantes),
            'esta_subido': bool(rc.shopify_product_id),
        })

    context = {
        'titulo': f'Catálogo Shopify ({empresa_actual.nombre})',
        'filas': filas,
        'page_obj': page_obj,
        'search_query': search_query,
    }
    return render(request, 'pedidos_web/gestion_catalogo_shopify.html', context)


@login_required
@user_passes_test(es_administracion, login_url='core:acceso_denegado')
def api_shopify_tipos_y_categorias(request):
    """
    Devuelve 'Tipo', 'Categoría' (taxonomía oficial), 'Etiquetas' y
    'Colecciones' ya existentes en Shopify, para ofrecerlos en los selectores
    en vez de que el usuario tenga que escribirlos/adivinarlos a ciegas.
    Se consulta a Shopify en el momento (no se guarda copia local) porque es
    una pantalla de uso ocasional, no una de alto tráfico.
    """
    try:
        tipos = shopify_api.obtener_tipos_existentes()
        categorias = shopify_api.obtener_categorias_existentes()
        etiquetas = shopify_api.obtener_etiquetas_existentes()
        colecciones = shopify_api.obtener_colecciones_existentes()
        return JsonResponse({
            'tipos': tipos, 'categorias': categorias,
            'etiquetas': etiquetas, 'colecciones': colecciones,
        })
    except requests.exceptions.RequestException as e:
        detalle = getattr(e.response, 'text', str(e)) if getattr(e, 'response', None) is not None else str(e)
        return JsonResponse({'error': f"Shopify rechazó la consulta: {detalle[:300]}"}, status=502)
    except Exception as e:
        return JsonResponse({'error': f"Error inesperado: {str(e)}"}, status=500)


def _obtener_referencia_color_de_empresa(request, referencia_color_id):
    empresa_actual = getattr(request, 'tenant', None)
    return get_object_or_404(ReferenciaColor, pk=referencia_color_id, empresa=empresa_actual)


@login_required
@user_passes_test(es_administracion, login_url='core:acceso_denegado')
def api_shopify_producto_detalle(request, referencia_color_id):
    """
    Trae del catálogo REAL de Shopify (no de lo guardado localmente) el
    título, descripción, precio y clasificación actuales de una referencia
    ya subida, para mostrarlos al abrir su panel de Detalles.
    """
    referencia_color = _obtener_referencia_color_de_empresa(request, referencia_color_id)
    if not referencia_color.shopify_product_id:
        return JsonResponse({'error': 'Esta referencia todavía no se ha subido a Shopify.'}, status=400)

    try:
        detalle = shopify_api.obtener_producto_detalle(
            referencia_color.shopify_product_id, referencia_color.color
        )
        return JsonResponse(detalle)
    except requests.exceptions.RequestException as e:
        detalle_error = getattr(e.response, 'text', str(e)) if getattr(e, 'response', None) is not None else str(e)
        return JsonResponse({'error': f"Shopify rechazó la consulta: {detalle_error[:300]}"}, status=502)
    except Exception as e:
        return JsonResponse({'error': f"Error inesperado: {str(e)}"}, status=500)


def _variantes_activas(referencia_color):
    return list(
        Producto.objects.filter(
            articulo_color_fotos=referencia_color, activo=True
        ).order_by('talla')
    )


def _redirect_catalogo_shopify(request, referencia_color_id):
    """
    Vuelve a la misma página y búsqueda en las que estaba la administradora
    (en vez de reiniciar siempre en la página 1), con un ancla a la fila que
    acaba de editar/subir/bajar para que quede a la vista de inmediato.
    """
    params = {}
    pagina = request.POST.get('pagina_actual', '').strip()
    busqueda = request.POST.get('busqueda_actual', '').strip()
    if pagina and pagina != '1':
        params['page'] = pagina
    if busqueda:
        params['q'] = busqueda

    url = reverse('pedidos_web:gestion_catalogo_shopify')
    if params:
        url += '?' + urlencode(params)
    url += f'#fila-{referencia_color_id}'
    return redirect(url)


@login_required
@user_passes_test(es_administracion, login_url='core:acceso_denegado')
@require_POST
def api_shopify_subir(request, referencia_color_id):
    """Publica (crea, o reactiva si estaba en borrador) el producto en Shopify."""
    referencia_color = _obtener_referencia_color_de_empresa(request, referencia_color_id)
    variantes = _variantes_activas(referencia_color)

    if not variantes:
        messages.error(request, "Esta referencia no tiene tallas activas para subir.")
        return _redirect_catalogo_shopify(request, referencia_color_id)

    try:
        if referencia_color.shopify_product_id:
            # Ya existía (probablemente en borrador tras un "Bajar") -> reactivar.
            shopify_api.reactivar_producto(referencia_color)
            referencia_color.shopify_borrador_por_agotado = False
            messages.success(request, f"'{referencia_color}' se reactivó en Shopify.")
        else:
            producto_shopify = shopify_api.crear_producto(referencia_color, variantes)
            referencia_color.shopify_product_id = str(producto_shopify['id'])

            variantes_por_sku = {v.codigo_barras: v for v in variantes if v.codigo_barras}
            for variant_data in producto_shopify.get('variants', []):
                variante_local = variantes_por_sku.get(variant_data.get('sku'))
                if variante_local:
                    variante_local.shopify_variant_id = str(variant_data.get('id'))
                    variante_local.shopify_inventory_item_id = str(variant_data.get('inventory_item_id'))
                    variante_local.save(update_fields=['shopify_variant_id', 'shopify_inventory_item_id'])

            messages.success(request, f"'{referencia_color}' se subió a Shopify con {len(variantes)} talla(s).")

        # Sincronizar el stock real de cada variante recién enlazada.
        location_id = shopify_api.obtener_location_id()
        if location_id:
            headers = shopify_api.obtener_headers()
            for variante in variantes:
                variante.refresh_from_db(fields=['shopify_inventory_item_id'])
                shopify_api.sincronizar_inventario(headers, location_id, variante)

        referencia_color.shopify_ultima_sincronizacion = timezone.now()
        referencia_color.save(update_fields=[
            'shopify_product_id', 'shopify_ultima_sincronizacion', 'shopify_borrador_por_agotado',
        ])

    except requests.exceptions.RequestException as e:
        detalle = getattr(e.response, 'text', str(e)) if getattr(e, 'response', None) is not None else str(e)
        messages.error(request, f"Shopify rechazó la operación: {detalle[:300]}")
    except Exception as e:
        messages.error(request, f"Error inesperado subiendo a Shopify: {str(e)}")

    return _redirect_catalogo_shopify(request, referencia_color_id)


@login_required
@user_passes_test(es_administracion, login_url='core:acceso_denegado')
@require_POST
def api_shopify_actualizar(request, referencia_color_id):
    """
    Guarda los campos editables (título/descripción/precio para Shopify) y,
    si ya estaba subido, empuja esos cambios y el stock real a Shopify.
    El EAN y las tallas nunca se tocan acá.
    """
    referencia_color = _obtener_referencia_color_de_empresa(request, referencia_color_id)
    ids_colecciones_anteriores = referencia_color.shopify_colecciones_ids  # antes de sobreescribir, para el diff

    # DEBUG TEMPORAL: diagnosticar por qué precio/categoría no llegan desde el navegador.
    logger.warning(f"DEBUG api_shopify_actualizar POST recibido para rc={referencia_color_id}: {dict(request.POST)}")

    referencia_color.shopify_titulo = request.POST.get('shopify_titulo', '').strip() or None
    referencia_color.shopify_descripcion = request.POST.get('shopify_descripcion', '').strip() or None
    precio_raw = request.POST.get('shopify_precio', '').strip()
    referencia_color.shopify_precio = precio_raw or None
    referencia_color.shopify_tipo = request.POST.get('shopify_tipo', '').strip() or None
    referencia_color.shopify_categoria_id = request.POST.get('shopify_categoria_id', '').strip() or None
    referencia_color.shopify_categoria_nombre = request.POST.get('shopify_categoria_nombre', '').strip() or None
    referencia_color.shopify_etiquetas = ', '.join(
        e.strip() for e in request.POST.getlist('shopify_etiquetas') if e.strip()
    ) or None
    referencia_color.shopify_colecciones_ids = ', '.join(request.POST.getlist('shopify_colecciones_ids')) or None
    referencia_color.shopify_colecciones_nombres = ', '.join(request.POST.getlist('shopify_colecciones_nombres')) or None
    referencia_color.save(update_fields=[
        'shopify_titulo', 'shopify_descripcion', 'shopify_precio',
        'shopify_tipo', 'shopify_categoria_id', 'shopify_categoria_nombre',
        'shopify_etiquetas', 'shopify_colecciones_ids', 'shopify_colecciones_nombres',
    ])

    if not referencia_color.shopify_product_id:
        messages.success(request, "Cambios guardados. Todavía no se ha subido a Shopify — usa 'Subir' para publicarlo.")
        return _redirect_catalogo_shopify(request, referencia_color_id)

    variantes = _variantes_activas(referencia_color)
    try:
        shopify_api.actualizar_producto(referencia_color, variantes)

        ids_nuevos = [i.strip() for i in (referencia_color.shopify_colecciones_ids or '').split(',') if i.strip()]
        ids_anteriores = [i.strip() for i in (ids_colecciones_anteriores or '').split(',') if i.strip()]
        if ids_nuevos != ids_anteriores:
            shopify_api.sincronizar_colecciones(referencia_color.shopify_product_id, ids_nuevos, ids_anteriores)

        location_id = shopify_api.obtener_location_id()
        if location_id:
            headers = shopify_api.obtener_headers()
            for variante in variantes:
                shopify_api.sincronizar_inventario(headers, location_id, variante)

        referencia_color.shopify_ultima_sincronizacion = timezone.now()
        referencia_color.save(update_fields=['shopify_ultima_sincronizacion'])
        messages.success(request, f"'{referencia_color}' se actualizó en Shopify.")
    except requests.exceptions.RequestException as e:
        detalle = getattr(e.response, 'text', str(e)) if getattr(e, 'response', None) is not None else str(e)
        messages.error(request, f"Shopify rechazó la actualización: {detalle[:300]}")
    except Exception as e:
        messages.error(request, f"Error inesperado actualizando en Shopify: {str(e)}")

    return _redirect_catalogo_shopify(request, referencia_color_id)


@login_required
@user_passes_test(es_administracion, login_url='core:acceso_denegado')
@require_POST
def api_shopify_bajar(request, referencia_color_id):
    """Pasa el producto a borrador en Shopify (se oculta, no se borra)."""
    referencia_color = _obtener_referencia_color_de_empresa(request, referencia_color_id)

    if not referencia_color.shopify_product_id:
        messages.error(request, "Esta referencia todavía no se ha subido a Shopify.")
        return _redirect_catalogo_shopify(request, referencia_color_id)

    try:
        shopify_api.archivar_producto(referencia_color)
        referencia_color.shopify_ultima_sincronizacion = timezone.now()
        # Se resetea a False: este borrador lo pidió la administradora, no la
        # automatización por falta de stock, así que no debe reactivarse solo.
        referencia_color.shopify_borrador_por_agotado = False
        referencia_color.save(update_fields=['shopify_ultima_sincronizacion', 'shopify_borrador_por_agotado'])
        messages.success(request, f"'{referencia_color}' se pasó a borrador en Shopify (ya no se ve en la tienda).")
    except requests.exceptions.RequestException as e:
        detalle = getattr(e.response, 'text', str(e)) if getattr(e, 'response', None) is not None else str(e)
        messages.error(request, f"Shopify rechazó la operación: {detalle[:300]}")
    except Exception as e:
        messages.error(request, f"Error inesperado bajando de Shopify: {str(e)}")

    return _redirect_catalogo_shopify(request, referencia_color_id)