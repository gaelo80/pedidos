"""
Repositorio de Movimientos (Devoluciones, Ventas manuales, Cambios).
"""
import json
from contextlib import contextmanager
from datetime import datetime
from typing import List, Tuple

from database import obtener_conexion

MovimientoRow = Tuple[int, str, str, str]  # id, fecha, tipo, detalles


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


class MovimientoRepository:

    @staticmethod
    def guardar(tipo: str, cliente: str, items: dict) -> int:
        """
        Persiste el movimiento y ajusta stock en una sola transacción.
        Retorna el id generado.
        """
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        descripcion = f"{tipo} - {cliente}"

        with _transaccion() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO devoluciones_pendientes (fecha, tipo, detalles) "
                "VALUES (?, ?, ?)",
                (fecha, descripcion, json.dumps(items, ensure_ascii=False))
            )
            id_mov = cursor.lastrowid

            for v in items.values():
                op = "+" if v["accion"] == "ENTRA" else "-"
                cursor.execute(
                    f"UPDATE productos_local "
                    f"SET stock_local = stock_local {op} ? WHERE id_producto = ?",
                    (v["cant"], v["id"])
                )

        return id_mov

    @staticmethod
    def historial(limite: int = 200) -> List[MovimientoRow]:
        with _transaccion() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id_devolucion, fecha, tipo, detalles "
                "FROM devoluciones_pendientes "
                "ORDER BY id_devolucion DESC LIMIT ?",
                (limite,)
            )
            return cursor.fetchall()