# pedidos_web/shopify_api.py
"""
Helper reutilizable para hablar con la API de Administración de Shopify.

Un ReferenciaColor (referencia + color) equivale a UN producto de Shopify;
cada Producto (variante = talla) es una variante de ese producto. El SKU y
el código de barras de cada variante SIEMPRE son el 'codigo_barras' interno
(fijo, nunca se edita desde acá), porque de esa coincidencia dependen los
webhooks que enlazan pedidos y productos entre Shopify y este sistema.

Las fotos se suben como adjunto en base64 (no por URL): en producción los
archivos de medios usan URLs firmadas y privadas (core.storages.PrivateMediaStorage),
así que la única forma robusta de subirlas es leyendo los bytes directamente
desde el storage configurado y mandándolos codificados en el payload.
"""
import base64
import logging

import requests
from decouple import config

logger = logging.getLogger(__name__)

SHOPIFY_API_VERSION = '2026-07'


def _shop_url():
    raw_url = config('SHOPIFY_URL')
    return raw_url.replace('https://', '').replace('http://', '').strip('/')


def obtener_token_temporal():
    shop_url = _shop_url()
    client_id = config('SHOPIFY_CLIENT_ID')
    client_secret = config('SHOPIFY_CLIENT_SECRET')
    url = f"https://{shop_url}/admin/oauth/access_token"
    payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'client_credentials',
    }
    response = requests.post(url, data=payload, timeout=20)
    response.raise_for_status()
    return response.json().get('access_token')


def obtener_headers():
    token = obtener_token_temporal()
    return {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json",
    }


def obtener_location_id():
    return config('SHOPIFY_LOCATION_ID', default='')


def _url_admin(recurso):
    return f"https://{_shop_url()}/admin/api/{SHOPIFY_API_VERSION}/{recurso}"


def _url_graphql():
    return f"https://{_shop_url()}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"


def graphql(query, variables=None):
    """Ejecuta una consulta/mutación GraphQL contra el Admin API de Shopify."""
    headers = obtener_headers()
    response = requests.post(
        _url_graphql(), headers=headers,
        json={'query': query, 'variables': variables or {}}, timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if data.get('errors'):
        raise ValueError(f"Shopify GraphQL rechazó la consulta: {data['errors']}")
    return data['data']


# Límite de páginas al recorrer el catálogo existente para extraer tipos y
# categorías en uso -- una tienda de este tamaño no necesita más, y evita
# quedar en un bucle largo si el catálogo de Shopify creciera mucho.
_MAX_PAGINAS_EXTRACCION = 20


def obtener_tipos_existentes():
    """
    Recorre los productos ya existentes en Shopify y devuelve la lista de
    valores distintos de 'product_type' (Tipo) que ya están en uso, para
    ofrecerlos en un selector en vez de que el usuario tenga que adivinar
    cómo los ha estado nombrando.
    """
    headers = obtener_headers()
    tipos = set()
    url = _url_admin('products.json') + '?limit=250&fields=product_type'

    for _ in range(_MAX_PAGINAS_EXTRACCION):
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        for producto in response.json().get('products', []):
            tipo = (producto.get('product_type') or '').strip()
            if tipo:
                tipos.add(tipo)

        siguiente = response.links.get('next', {}).get('url')
        if not siguiente:
            break
        url = siguiente

    return sorted(tipos)


_QUERY_CATEGORIAS_EXISTENTES = """
query($cursor: String) {
  products(first: 250, after: $cursor) {
    edges {
      node {
        category { id fullName }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""


def obtener_categorias_existentes():
    """
    Recorre los productos ya existentes en Shopify (vía GraphQL, la única API
    que expone la categoría oficial de la taxonomía de Shopify) y devuelve
    las categorías distintas que ya están en uso, con su id y nombre completo.
    """
    categorias = {}
    cursor = None

    for _ in range(_MAX_PAGINAS_EXTRACCION):
        datos = graphql(_QUERY_CATEGORIAS_EXISTENTES, {'cursor': cursor})
        productos = datos['products']
        for edge in productos['edges']:
            categoria = edge['node'].get('category')
            if categoria:
                categorias[categoria['id']] = categoria['fullName']

        if not productos['pageInfo']['hasNextPage']:
            break
        cursor = productos['pageInfo']['endCursor']

    return [{'id': cid, 'nombre': nombre} for cid, nombre in sorted(categorias.items(), key=lambda x: x[1])]


_MUTATION_ASIGNAR_CATEGORIA = """
mutation($input: ProductInput!) {
  productUpdate(input: $input) {
    product { id category { id fullName } }
    userErrors { field message }
  }
}
"""


def asignar_categoria(producto_shopify_id, categoria_id):
    """
    Asigna la categoría oficial de la taxonomía de Shopify a un producto ya
    creado. Es una llamada aparte porque la API REST (usada para crear y
    actualizar el resto del producto) no admite este campo -- solo GraphQL.
    """
    variables = {
        'input': {
            'id': f"gid://shopify/Product/{producto_shopify_id}",
            'category': categoria_id,
        }
    }
    datos = graphql(_MUTATION_ASIGNAR_CATEGORIA, variables)
    errores = datos['productUpdate']['userErrors']
    if errores:
        raise ValueError(f"Shopify rechazó la categoría: {errores}")
    return datos['productUpdate']['product']


def obtener_etiquetas_existentes():
    """
    Recorre los productos ya existentes en Shopify y devuelve las etiquetas
    (tags) distintas que ya están en uso, para ofrecerlas en un selector.
    """
    headers = obtener_headers()
    etiquetas = set()
    url = _url_admin('products.json') + '?limit=250&fields=tags'

    for _ in range(_MAX_PAGINAS_EXTRACCION):
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        for producto in response.json().get('products', []):
            for etiqueta in (producto.get('tags') or '').split(','):
                etiqueta = etiqueta.strip()
                if etiqueta:
                    etiquetas.add(etiqueta)

        siguiente = response.links.get('next', {}).get('url')
        if not siguiente:
            break
        url = siguiente

    return sorted(etiquetas)


_QUERY_COLECCIONES_EXISTENTES = """
query($cursor: String) {
  collections(first: 250, after: $cursor) {
    edges {
      node { id title }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""


def obtener_colecciones_existentes():
    """Devuelve todas las colecciones (manuales y automáticas) ya creadas en Shopify."""
    colecciones = []
    cursor = None

    for _ in range(_MAX_PAGINAS_EXTRACCION):
        datos = graphql(_QUERY_COLECCIONES_EXISTENTES, {'cursor': cursor})
        bloque = datos['collections']
        for edge in bloque['edges']:
            colecciones.append({'id': edge['node']['id'], 'nombre': edge['node']['title']})

        if not bloque['pageInfo']['hasNextPage']:
            break
        cursor = bloque['pageInfo']['endCursor']

    return sorted(colecciones, key=lambda c: c['nombre'])


_MUTATION_COLECCION_AGREGAR = """
mutation($id: ID!, $productIds: [ID!]!) {
  collectionAddProducts(id: $id, productIds: $productIds) {
    userErrors { field message }
  }
}
"""

_MUTATION_COLECCION_QUITAR = """
mutation($id: ID!, $productIds: [ID!]!) {
  collectionRemoveProducts(id: $id, productIds: $productIds) {
    job { id }
    userErrors { field message }
  }
}
"""


def sincronizar_colecciones(producto_shopify_id, ids_nuevos, ids_anteriores):
    """
    Agrega el producto a las colecciones recién seleccionadas y lo quita de
    las que estaban antes pero ya no. 'ids_nuevos'/'ids_anteriores' son listas
    de GIDs de colección (['gid://shopify/Collection/123', ...]).
    """
    producto_gid = f"gid://shopify/Product/{producto_shopify_id}"
    nuevos = set(filter(None, ids_nuevos))
    anteriores = set(filter(None, ids_anteriores))

    for coleccion_id in (nuevos - anteriores):
        datos = graphql(_MUTATION_COLECCION_AGREGAR, {'id': coleccion_id, 'productIds': [producto_gid]})
        errores = datos['collectionAddProducts']['userErrors']
        if errores:
            raise ValueError(f"Shopify rechazó agregar a la colección {coleccion_id}: {errores}")

    for coleccion_id in (anteriores - nuevos):
        datos = graphql(_MUTATION_COLECCION_QUITAR, {'id': coleccion_id, 'productIds': [producto_gid]})
        errores = datos['collectionRemoveProducts']['userErrors']
        if errores:
            raise ValueError(f"Shopify rechazó quitar de la colección {coleccion_id}: {errores}")


def _titulo_y_descripcion(referencia_color, variantes):
    primera = variantes[0] if variantes else None
    nombre_base = primera.nombre if primera else referencia_color.referencia_base
    # Cada color es un producto SEPARADO en Shopify (no una variante dentro
    # del mismo producto), así que el color va en el título por defecto:
    # si no fuera así, dos colores de una misma referencia se verían en la
    # tienda con el mismo nombre y no se podrían distinguir.
    if referencia_color.color:
        nombre_base = f"{nombre_base} - {referencia_color.color.title()}"
    titulo = referencia_color.shopify_titulo or nombre_base
    descripcion = referencia_color.shopify_descripcion or (primera.descripcion if primera else '') or ''
    return titulo, descripcion


def _construir_tags(referencia_color):
    """El color siempre se manda como etiqueta automática, además de las que
    el usuario haya agregado a mano en 'shopify_etiquetas'."""
    partes = []
    if referencia_color.color:
        partes.append(referencia_color.color)
    if referencia_color.shopify_etiquetas:
        partes.extend(e.strip() for e in referencia_color.shopify_etiquetas.split(',') if e.strip())
    return ', '.join(partes)


def _construir_imagenes_payload(referencia_color):
    imagenes = []
    for foto in referencia_color.fotos_agrupadas.all().order_by('orden'):
        try:
            foto.imagen.open('rb')
            contenido = foto.imagen.read()
        finally:
            foto.imagen.close()
        imagenes.append({
            'attachment': base64.b64encode(contenido).decode('ascii'),
            'filename': foto.imagen.name.split('/')[-1],
        })
    return imagenes


def _construir_variantes_payload_creacion(referencia_color, variantes):
    """Payload de variantes para la creación inicial del producto."""
    precio_override = referencia_color.shopify_precio
    payload = []
    for producto in variantes:
        precio = precio_override or producto.precio_venta
        payload.append({
            'option1': str(producto.talla) if producto.talla is not None else 'Única',
            'price': str(precio),
            'sku': producto.codigo_barras or '',
            'barcode': producto.codigo_barras or '',
            'inventory_management': 'shopify',
            'inventory_policy': 'deny',
        })
    return payload


def crear_producto(referencia_color, variantes, estado='active'):
    """
    Crea el producto en Shopify con todas sus variantes (tallas) y fotos.
    Devuelve el dict 'product' que responde Shopify (incluye los IDs nuevos
    de producto/variantes/inventory_item que hay que guardar localmente).

    'estado' por defecto es 'active' (lo que usa el botón "Subir" en
    producción); se puede forzar a 'draft' para pruebas puntuales contra la
    tienda real sin que el producto quede visible para clientes.
    """
    headers = obtener_headers()
    titulo, descripcion = _titulo_y_descripcion(referencia_color, variantes)

    payload = {
        'product': {
            'title': titulo,
            'body_html': descripcion,
            'vendor': referencia_color.empresa.nombre if referencia_color.empresa_id else '',
            'product_type': referencia_color.shopify_tipo or '',
            'status': estado,
            'tags': _construir_tags(referencia_color),
            'options': [{'name': 'Talla'}],
            'variants': _construir_variantes_payload_creacion(referencia_color, variantes),
            'images': _construir_imagenes_payload(referencia_color),
        }
    }
    response = requests.post(_url_admin('products.json'), json=payload, headers=headers, timeout=60)
    response.raise_for_status()
    producto_creado = response.json()['product']

    # La categoría oficial de la taxonomía solo se puede asignar por GraphQL,
    # en una llamada aparte (la API REST usada arriba no admite este campo).
    if referencia_color.shopify_categoria_id:
        asignar_categoria(producto_creado['id'], referencia_color.shopify_categoria_id)

    # Un producto nuevo no estaba en ninguna colección todavía, así que solo
    # hay que agregarlo a las que se hayan seleccionado (no hay que quitar nada).
    ids_colecciones = [i.strip() for i in (referencia_color.shopify_colecciones_ids or '').split(',') if i.strip()]
    if ids_colecciones:
        sincronizar_colecciones(producto_creado['id'], ids_colecciones, [])

    return producto_creado


def actualizar_producto(referencia_color, variantes):
    """
    Actualiza título/descripción y precios en Shopify. El SKU/barcode de cada
    variante (fijado en la creación) nunca se toca acá.
    """
    headers = obtener_headers()
    titulo, descripcion = _titulo_y_descripcion(referencia_color, variantes)
    precio_override = referencia_color.shopify_precio

    payload_variantes = []
    for producto in variantes:
        if not producto.shopify_variant_id:
            continue  # variante nueva que todavía no se ha subido a Shopify
        precio = precio_override or producto.precio_venta
        payload_variantes.append({
            'id': int(producto.shopify_variant_id),
            'price': str(precio),
        })

    payload = {
        'product': {
            'id': int(referencia_color.shopify_product_id),
            'title': titulo,
            'body_html': descripcion,
            'product_type': referencia_color.shopify_tipo or '',
            'tags': _construir_tags(referencia_color),
            'variants': payload_variantes,
        }
    }
    response = requests.put(
        _url_admin(f'products/{referencia_color.shopify_product_id}.json'),
        json=payload, headers=headers, timeout=60,
    )
    response.raise_for_status()
    producto_actualizado = response.json()['product']

    if referencia_color.shopify_categoria_id:
        asignar_categoria(referencia_color.shopify_product_id, referencia_color.shopify_categoria_id)

    return producto_actualizado


def archivar_producto(referencia_color):
    """Pasa el producto a 'draft' en Shopify (se oculta de la tienda, no se borra)."""
    return _cambiar_estado_producto(referencia_color, 'draft')


def reactivar_producto(referencia_color):
    """Vuelve a publicar ('active') un producto que estaba en borrador."""
    return _cambiar_estado_producto(referencia_color, 'active')


def _cambiar_estado_producto(referencia_color, estado):
    headers = obtener_headers()
    payload = {'product': {'id': int(referencia_color.shopify_product_id), 'status': estado}}
    response = requests.put(
        _url_admin(f'products/{referencia_color.shopify_product_id}.json'),
        json=payload, headers=headers, timeout=30,
    )
    response.raise_for_status()
    return response.json()['product']


def sincronizar_inventario(headers, location_id, producto):
    """Empuja el stock real (stock_actual) de una variante ya enlazada."""
    if not producto.shopify_inventory_item_id:
        return
    cantidad_real = max(producto.stock_actual, 0)
    payload = {
        'location_id': location_id,
        'inventory_item_id': producto.shopify_inventory_item_id,
        'available': cantidad_real,
    }
    response = requests.post(_url_admin('inventory_levels/set.json'), json=payload, headers=headers, timeout=30)
    response.raise_for_status()
