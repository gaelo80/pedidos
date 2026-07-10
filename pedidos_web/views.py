import json
import hmac
import hashlib
import base64
import logging
import os
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.utils.dateparse import parse_datetime
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction
from django.conf import settings
from clientes.models import Empresa
from pedidos_online.models import ClienteOnline
from pedidos.models import Pedido, DetallePedido
from productos.models import Producto
from bodega.models import MovimientoInventario
from vendedores.models import Vendedor
from decouple import config
import requests
from django.shortcuts import render
from django.contrib.auth.decorators import login_required



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

        # Buscamos a tu Bot (Asegúrate de crearlo en el admin con este username)
        empresa_actual = Empresa.objects.first() 
        vendedor_shopify = Vendedor.objects.filter(user__username='bot.shopify').first()

        if not vendedor_shopify:
            print("⚠️ Cuidado: No has creado el vendedor 'bot.shopify' en el admin.")

# --- A. Guardar Cliente ---
        cliente_data = orden.get('customer') or {}
        direccion_data = orden.get('shipping_address') or {}
        
        if cliente_data:
            cliente_online, _ = ClienteOnline.objects.update_or_create(
                identificacion=str(cliente_data.get('id')),
                empresa=empresa_actual,
                defaults={
                    'nombre_completo': f"{cliente_data.get('first_name', '')} {cliente_data.get('last_name', '')}".strip(),
                    # Si viene null, lo cambiamos por un string vacío ''
                    'email': cliente_data.get('email') or '',
                    'telefono': direccion_data.get('phone') or cliente_data.get('phone') or 'Sin teléfono', 
                    'direccion': direccion_data.get('address1') or 'Sin dirección',
                    'tipo_cliente': 'DETAL'
                }
            )
        else:
            cliente_online = None

        # --- B. Lógica de Pago y Estados ---
        estado_financiero = orden.get('financial_status')
        es_pago_confirmado = (estado_financiero == 'paid')
        estado_django = 'LISTO_BODEGA_DIRECTO' if es_pago_confirmado else 'BORRADOR'

        with transaction.atomic():
            # --- C. Crear Pedido ---
            pedido, pedido_creado = Pedido.objects.get_or_create(
                numero_pedido_empresa=orden.get('order_number'),
                empresa=empresa_actual,
                defaults={
                    'cliente_online': cliente_online,
                    'vendedor': vendedor_shopify,
                    'tipo_pedido': 'ONLINE',
                    'estado': estado_django,
                    'notas': f"Importado de Shopify. Pago: {estado_financiero}",
                    'fecha_hora': parse_datetime(orden.get('created_at'))
                }
            )

            if not pedido_creado:
                return HttpResponse(status=200)

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
                            tipo_movimiento='SALIDA_VENTA_PENDIENTE',
                            documento_referencia=doc_ref_base,
                            cantidad=-cantidad_comprada,
                            usuario=vendedor_shopify.user if vendedor_shopify else None
                        )
                        print(f"✅ Activado en Bodega: {producto_interno.referencia}")
                    else:
                        print(f"⏳ Guardado como borrador: Pago {estado_financiero}")
                else:
                    print(f"⚠️ Variante {variant_id} no enlazada en Django.")

        return HttpResponse(status=200)

    except Exception as e:
        print(f"❌ Error en Webhook: {str(e)}")
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
        empresa_actual = Empresa.objects.first()

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
        response.raise_for_status() # Esto lanza un error si Shopify no devuelve 200 OK
        return response.json().get('access_token')
    except requests.exceptions.HTTPError as e:
        print(f"❌ Error de Shopify al pedir token: HTTP {response.status_code}")
        print(f"Detalle del rechazo: {response.text}")
        return None
    except Exception as e:
        print(f"❌ Error interno de conexión: {str(e)}")
        return None
    
@login_required
def panel_sincronizacion_shopify(request):
    # --- LÓGICA MULTI-EMPRESA ESTANDARIZADA ---
    empresa_actual = getattr(request, 'tenant', None)
    
    if not empresa_actual:
        messages.error(request, "Acceso no válido. No se pudo identificar la empresa.")
        return redirect('core:acceso_denegado')

    # Creamos una base de consulta filtrada dinámicamente por la empresa actual del usuario.
    productos_base = Producto.objects.filter(activo=True, empresa=empresa_actual)
    
    # 1. Variables base (Ahora usamos productos_base en vez de Producto.objects)
    total_productos = productos_base.count()
    sincronizados = productos_base.filter(shopify_variant_id__isnull=False).count()
    huerfanos = productos_base.filter(shopify_variant_id__isnull=True)
    
    context = {
        'total_productos': total_productos,
        'sincronizados': sincronizados,
        'pendientes': total_productos - sincronizados,
        'huerfanos': huerfanos,
        'resultado_sync': None,
        'resultado_inventario': None,
        'error_api': None
    }

    if request.method == 'POST':
        accion = request.POST.get('accion')
        
        # 2. Leemos tus credenciales desde el .env
        raw_url = config('SHOPIFY_URL')
        shop_url = raw_url.replace('https://', '').replace('http://', '').strip('/')
        client_id = config('SHOPIFY_CLIENT_ID')
        client_secret = config('SHOPIFY_CLIENT_SECRET') # El Secreto de tu captura de pantalla
        
        # 3. Canjeamos las credenciales por el token dinámico válido
        token = obtener_token_temporal(shop_url, client_id, client_secret)
        
        if not token:
            context['error_api'] = "Fallo de Autenticación: Verifica que el ID de cliente y el Secreto sean exactos a tu captura."
        else:
            # Si Shopify nos autoriza, armamos la cabecera permitida
            headers = {
                "X-Shopify-Access-Token": token,
                "Content-Type": "application/json"
            }
            
            # =========================================================
            # BOTÓN 1: ENLAZAR PRODUCTOS
            # =========================================================
            if accion == 'enlazar_productos':
                productos_actualizados = []
                errores_shopify = []
                url_productos = f"https://{shop_url}/admin/api/2024-01/products.json?limit=250"
                
                try:
                    response = requests.get(url_productos, headers=headers)
                    if response.status_code == 200:
                        data_shopify = response.json()
                        for item in data_shopify.get('products', []):
                            for variant in item.get('variants', []):
                                variant_id = str(variant.get('id'))
                                sku_shopify = variant.get('sku') or variant.get('barcode')
                                
                                if not sku_shopify:
                                    continue
                                    
                                # 1. Buscamos PRIMERO dentro del catálogo de ESTA empresa (Louisferry)
                                producto_local = productos_base.filter(codigo_barras__iexact=sku_shopify.strip()).first()
                                
                                if producto_local:
                                    if not producto_local.shopify_variant_id:
                                        producto_local.shopify_variant_id = variant_id
                                        producto_local.save()
                                        productos_actualizados.append(producto_local)
                                else:
                                    # --- CORRECCIÓN DE LA FUGA DE DATOS MULTI-TENANT ---
                                    # Si no está en esta empresa, verificamos globalmente si le pertenece a OTRA empresa
                                    existe_en_otra_empresa = Producto.objects.filter(codigo_barras__iexact=sku_shopify.strip()).exists()
                                    
                                    # Solo lo marcamos como error si NO existe en NINGUNA empresa de la base de datos
                                    if not existe_en_otra_empresa:
                                        errores_shopify.append({
                                            'titulo': item.get('title'),
                                            'sku': sku_shopify,
                                            'motivo': 'Código no existe en el sistema local'
                                        })
                                        
                        context['resultado_sync'] = {'exitosos': productos_actualizados, 'errores': errores_shopify}
                    else:
                        context['error_api'] = f"Error conectando a Shopify: {response.status_code}"
                except Exception as e:
                    context['error_api'] = f"Error al enlazar: {str(e)}"
                    
            # =========================================================
            # BOTÓN 2: SUBIR INVENTARIO REAL A SHOPIFY
            # =========================================================
            elif accion == 'subir_inventario':
                location_id = config('SHOPIFY_LOCATION_ID', default='') 
                
                if not location_id:
                    context['error_api'] = "Falta configurar el SHOPIFY_LOCATION_ID en el archivo .env"
                else:
                    inventario_actualizado = 0
                    errores_inventario = []
                    url_productos = f"https://{shop_url}/admin/api/2024-01/products.json?limit=250"
                    url_set_inventory = f"https://{shop_url}/admin/api/2024-01/inventory_levels/set.json"
                    
                    try:
                        response = requests.get(url_productos, headers=headers)
                        if response.status_code == 200:
                            data_shopify = response.json()
                            for item in data_shopify.get('products', []):
                                for variant in item.get('variants', []):
                                    variant_id = str(variant.get('id'))
                                    inventory_item_id = variant.get('inventory_item_id')
                                    
                                    # Buscar solo dentro del catálogo filtrado de esta empresa
                                    producto_local = productos_base.filter(shopify_variant_id=variant_id).first()
                                    
                                    if producto_local and inventory_item_id:
                                        cantidad_real = producto_local.stock 
                                        payload_inventario = {
                                            "location_id": location_id,
                                            "inventory_item_id": inventory_item_id,
                                            "available": cantidad_real
                                        }
                                        inv_response = requests.post(url_set_inventory, json=payload_inventario, headers=headers)
                                        if inv_response.status_code == 200:
                                            inventario_actualizado += 1
                                        else:
                                            errores_inventario.append(f"Fallo al actualizar stock de {producto_local.referencia}")
                            context['resultado_inventario'] = {'exitosos': inventario_actualizado, 'errores': errores_inventario}
                        else:
                            context['error_api'] = f"Error al leer productos: {response.status_code}"
                    except Exception as e:
                        context['error_api'] = f"Error actualizando inventario: {str(e)}"

    # Recalculamos los totales al final usando la misma base filtrada
    context['sincronizados'] = productos_base.filter(shopify_variant_id__isnull=False).count()
    context['pendientes'] = total_productos - context['sincronizados']
    context['huerfanos'] = productos_base.filter(shopify_variant_id__isnull=True)

    return render(request, 'pedidos_web/sincronizacion_shopify.html', context)