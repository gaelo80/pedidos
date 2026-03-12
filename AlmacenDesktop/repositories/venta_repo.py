"""
Repositorio de Ventas.
Persiste la venta y descuenta stock en una sola transacción atómica.
"""
import json
from contextlib import contextmanager
from datetime import datetime
from typing import List, Tuple

from database import obtener_conexion
from modulos.carrito import Carrito

VentaRow = Tuple[int, str, float, str]  # id, fecha, total, metodo


@contextmanager
def _transaccion():
    conn = obtener_conexion()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


class VentaRepository:

    @staticmethod
    def guardar(carrito: Carrito, metodo_pago: str, datos_cliente: dict) -> int:
        """
        Persiste la venta y descuenta stock en una sola transacción.
        Retorna el id de la venta creada.
        """
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        detalles = {
            "items": carrito.to_dict(),
            "cliente": datos_cliente,
        }

        with _transaccion() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "INSERT INTO ventas_pendientes_sincronizar "
                "(fecha, total, metodo_pago, detalles) VALUES (?, ?, ?, ?)",
                (fecha, carrito.total, metodo_pago,
                 json.dumps(detalles, ensure_ascii=False))
            )
            id_venta = cursor.lastrowid

            for item in carrito.items.values():
                cursor.execute(
                    "UPDATE productos_local "
                    "SET stock_local = stock_local - ? WHERE id_producto = ?",
                    (item.cantidad, item.id_producto)
                )

        return id_venta

    @staticmethod
    def historial(limite: int = 100) -> List[VentaRow]:
        with _transaccion() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id_venta, fecha, total, metodo_pago "
                "FROM ventas_pendientes_sincronizar "
                "ORDER BY id_venta DESC LIMIT ?",
                (limite,)
            )
            return cursor.fetchall()