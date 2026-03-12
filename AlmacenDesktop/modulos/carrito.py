"""
Modelo de Carrito de Compras.
Encapsula toda la lógica del estado del carrito, desacoplada de la UI.
"""
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ItemCarrito:
    id_producto: int
    ref: str
    nombre: str
    precio: float
    cantidad: int
    stock_max: int

    @property
    def subtotal(self) -> float:
        return self.precio * self.cantidad


class Carrito:
    """Carrito de compras con validación de stock y cálculo de totales."""

    def __init__(self):
        self._items: Dict[str, ItemCarrito] = {}

    # ── Consultas ──────────────────────────────────────────────────────────────

    @property
    def items(self) -> Dict[str, ItemCarrito]:
        return dict(self._items)

    @property
    def total(self) -> float:
        return sum(i.subtotal for i in self._items.values())

    @property
    def cantidad_lineas(self) -> int:
        return len(self._items)

    @property
    def vacio(self) -> bool:
        return len(self._items) == 0

    # ── Mutaciones ─────────────────────────────────────────────────────────────

    def agregar(self, id_producto: int, ref: str, nombre: str,
                precio: float, stock_max: int, cantidad: int = 1) -> str:
        """Agrega o incrementa un item. Retorna mensaje de estado."""
        ref = str(ref)
        if ref in self._items:
            nuevo = self._items[ref].cantidad + cantidad
            if nuevo > stock_max:
                return f"⚠ Stock máximo: {stock_max} unidades"
            self._items[ref].cantidad = nuevo
        else:
            if cantidad > stock_max:
                return f"⚠ Stock máximo: {stock_max} unidades"
            self._items[ref] = ItemCarrito(id_producto, ref, nombre,
                                           precio, cantidad, stock_max)
        return f"✓ {nombre}"

    def actualizar_cantidad(self, ref: str, nueva_cantidad: int) -> Optional[str]:
        """Actualiza cantidad. Retorna mensaje de error o None si OK."""
        if ref not in self._items:
            return "Producto no encontrado en carrito"
        if nueva_cantidad <= 0:
            self.eliminar(ref)
            return None
        if nueva_cantidad > self._items[ref].stock_max:
            return f"Stock insuficiente. Máx: {self._items[ref].stock_max}"
        self._items[ref].cantidad = nueva_cantidad
        return None

    def eliminar(self, ref: str) -> bool:
        if ref in self._items:
            del self._items[ref]
            return True
        return False

    def vaciar(self):
        self._items.clear()

    def to_dict(self) -> dict:
        return {
            ref: {
                "id_producto": i.id_producto,
                "nombre": i.nombre,
                "precio": i.precio,
                "cant": i.cantidad,
                "subtotal": i.subtotal,
            }
            for ref, i in self._items.items()
        }