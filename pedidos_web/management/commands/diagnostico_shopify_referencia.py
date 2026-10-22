"""
Diagnóstico del enlace entre una referencia local y Shopify.

Uso:
    python manage.py diagnostico_shopify_referencia 1926            # solo lectura
    python manage.py diagnostico_shopify_referencia 1926 --reparar  # desenlaza lo no confiable

Muestra, para cada talla/color local de la referencia, a qué variante de
Shopify quedó enlazada, y para cada variante de Shopify relacionada, qué SKU y
código de barras tiene. Marca los enlaces cruzados (una talla local apuntando
a una variante cuyo código de barras es de otro producto) y las variantes con
SKU y código de barras distintos. Sin --reparar no modifica nada; nunca toca Shopify.
"""
from django.core.management.base import BaseCommand

from pedidos_web import shopify_api
from pedidos_web.views import _obtener_todos_los_productos_shopify
from productos.models import Producto, ReferenciaColor


class Command(BaseCommand):
    help = "Diagnóstico de solo lectura del enlace de una referencia con Shopify."

    def add_arguments(self, parser):
        parser.add_argument('referencia')
        parser.add_argument(
            '--reparar', action='store_true',
            help="Desenlaza las tallas locales cuyo enlace no es confiable (variante inexistente, "
                 "SKU y código de barras distintos, o ninguno de los dos es el de la talla). "
                 "Después hay que correr 'Sincronizar Referencias' para volver a enlazarlas.",
        )

    def handle(self, *args, **options):
        ref = options['referencia'].strip()
        locales = list(
            Producto.objects.filter(referencia__iexact=ref)
            .select_related('color', 'empresa').order_by('empresa_id', 'color__nombre', 'talla')
        )
        if not locales:
            self.stdout.write(f"No hay productos locales con referencia {ref}.")
            return

        por_codigo = {(p.codigo_barras or '').strip().upper(): p for p in locales if p.codigo_barras}
        por_variant = {str(p.shopify_variant_id): p for p in Producto.objects.filter(shopify_variant_id__isnull=False)}

        def etiqueta(p):
            if not p:
                return '-'
            return f"#{p.pk} {p.referencia} {p.color or 'SIN COLOR'} T{p.talla}"

        self.stdout.write("Consultando Shopify...")
        productos_shopify = _obtener_todos_los_productos_shopify(shopify_api.obtener_headers(), shopify_api._shop_url())
        variantes_por_id = {}
        relacionadas = []
        for prod in productos_shopify:
            for v in prod.get('variants', []):
                variantes_por_id[str(v.get('id'))] = (prod, v)
                sku = (v.get('sku') or '').strip().upper()
                barcode = (v.get('barcode') or '').strip().upper()
                if sku in por_codigo or barcode in por_codigo or ref.upper() in (prod.get('title') or '').upper():
                    relacionadas.append((prod, v))

        problemas = 0
        a_desenlazar = []
        self.stdout.write("\n=== TALLAS LOCALES Y SU ENLACE ===")
        for p in locales:
            linea = f"{etiqueta(p)} | empresa {p.empresa_id} | codigo {p.codigo_barras} | {'activo' if p.activo else 'INACTIVO'} | variante {p.shopify_variant_id or '-'}"
            if p.shopify_variant_id:
                prod_v = variantes_por_id.get(str(p.shopify_variant_id))
                if not prod_v:
                    linea += "  <-- la variante ya NO existe en Shopify"
                    problemas += 1
                    a_desenlazar.append(p)
                else:
                    prod, v = prod_v
                    codigo = (p.codigo_barras or '').strip().upper()
                    sku = (v.get('sku') or '').strip().upper()
                    barcode = (v.get('barcode') or '').strip().upper()
                    linea += f" -> Shopify '{prod.get('title')}' talla {v.get('option1')} (sku {v.get('sku')}, barcode {v.get('barcode')})"
                    if shopify_api.sku_y_barcode_en_conflicto(v):
                        linea += "  <-- ENLACE NO CONFIABLE: esa variante tiene SKU y código de barras distintos"
                        problemas += 1
                        a_desenlazar.append(p)
                    elif codigo not in (sku, barcode):
                        linea += "  <-- ENLACE CRUZADO: el código de esa variante no es el de esta talla"
                        problemas += 1
                        a_desenlazar.append(p)
            self.stdout.write(linea)

        self.stdout.write("\n=== VARIANTES DE SHOPIFY RELACIONADAS ===")
        for prod, v in relacionadas:
            sku = (v.get('sku') or '').strip().upper()
            barcode = (v.get('barcode') or '').strip().upper()
            linea = (
                f"Shopify producto {prod.get('id')} '{prod.get('title')}' [{prod.get('status')}] talla {v.get('option1')} "
                f"| variante {v.get('id')} | sku {v.get('sku') or '-'} | barcode {v.get('barcode') or '-'}"
                f"\n    enlazada a: {etiqueta(por_variant.get(str(v.get('id'))))}"
                f" | sku es de: {etiqueta(por_codigo.get(sku))} | barcode es de: {etiqueta(por_codigo.get(barcode))}"
            )
            if sku and barcode and sku != barcode:
                linea += "\n    <-- SKU y código de barras DISTINTOS"
                problemas += 1
            self.stdout.write(linea)

        # Enlace a nivel de producto (referencia+color -> producto de Shopify).
        productos_por_id = {str(prod['id']): prod for prod in productos_shopify}
        rc_a_desenlazar = []
        self.stdout.write("\n=== REFERENCIA+COLOR Y SU PRODUCTO DE SHOPIFY ===")
        for rc in ReferenciaColor.objects.filter(referencia_base__iexact=ref).order_by('empresa_id', 'color'):
            linea = f"{rc.referencia_base} {rc.color} | empresa {rc.empresa_id} | producto {rc.shopify_product_id or '-'}"
            if rc.shopify_product_id:
                prod = productos_por_id.get(str(rc.shopify_product_id))
                codigos_rc = {(c or '').strip().upper() for c in rc.variantes.values_list('codigo_barras', flat=True) if c}
                codigos_prod = set()
                for v in (prod or {}).get('variants', []):
                    codigos_prod |= {(c or '').strip().upper() for c in (v.get('sku'), v.get('barcode')) if c}
                if not prod:
                    linea += "  <-- ese producto ya NO existe en Shopify"
                    rc_a_desenlazar.append(rc)
                elif not codigos_rc & codigos_prod:
                    linea += f" -> '{prod.get('title')}'  <-- ENLACE CRUZADO: ninguno de sus códigos está en ese producto"
                    rc_a_desenlazar.append(rc)
                else:
                    linea += f" -> '{prod.get('title')}'"
            self.stdout.write(linea)
        problemas += len(rc_a_desenlazar)

        self.stdout.write(f"\nProblemas encontrados: {problemas}")

        if options['reparar']:
            for p in a_desenlazar:
                p.shopify_variant_id = None
                p.shopify_inventory_item_id = None
                p.save(update_fields=['shopify_variant_id', 'shopify_inventory_item_id'])
                self.stdout.write(f"Desenlazado: {etiqueta(p)}")
            for rc in rc_a_desenlazar:
                rc.shopify_product_id = None
                rc.save(update_fields=['shopify_product_id'])
                self.stdout.write(f"Desenlazado producto: {rc.referencia_base} {rc.color}")
            self.stdout.write(
                f"{len(a_desenlazar)} talla(s) y {len(rc_a_desenlazar)} producto(s) desenlazado(s). Corrige "
                "SKU/código de barras en Shopify y luego usa 'Sincronizar Referencias' en el Panel de Sincronización Web."
            )
        elif a_desenlazar or rc_a_desenlazar:
            self.stdout.write("Ejecuta de nuevo con --reparar para desenlazar lo marcado.")
