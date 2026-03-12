"""
Repositorio de Productos.
Toda consulta SQL relacionada con productos vive aquí.
"""
from contextlib import contextmanager
from typing import List, Tuple

from database import obtener_conexion

# id, codigo, nombre, precio, stock
ProductoRow = Tuple[int, str, str, float, int]


@contextmanager
def _conexion():
    """Context manager que garantiza cierre aunque haya excepciones."""
    conn = obtener_conexion()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


class ProductoRepository:

    @staticmethod
    def buscar(termino: str) -> List[ProductoRow]:
        """
        Busca por código exacto primero; si no hay resultado,
        hace búsqueda parcial por nombre o código.
        """
        with _conexion() as conn:
            cursor = conn.cursor()
            # Coincidencia exacta de código de barras
            cursor.execute(
                "SELECT id_producto, codigo_barras, nombre, precio_detal, stock_local "
                "FROM productos_local WHERE codigo_barras = ?",
                (termino,)
            )
            exactos = cursor.fetchall()
            if exactos:
                return exactos
            # Búsqueda parcial
            cursor.execute(
                "SELECT id_producto, codigo_barras, nombre, precio_detal, stock_local "
                "FROM productos_local "
                "WHERE nombre LIKE ? OR codigo_barras LIKE ? "
                "ORDER BY nombre LIMIT 50",
                (f"%{termino}%", f"%{termino}%")
            )
            return cursor.fetchall()

    @staticmethod
    def listar(termino: str = "", limite: int = 200) -> List[ProductoRow]:
        """Lista productos para la pestaña de consulta de stock."""
        with _conexion() as conn:
            cursor = conn.cursor()
            if termino:
                cursor.execute(
                    "SELECT id_producto, codigo_barras, nombre, precio_detal, stock_local "
                    "FROM productos_local "
                    "WHERE nombre LIKE ? OR codigo_barras LIKE ? "
                    "ORDER BY nombre LIMIT ?",
                    (f"%{termino}%", f"%{termino}%", limite)
                )
            else:
                cursor.execute(
                    "SELECT id_producto, codigo_barras, nombre, precio_detal, stock_local "
                    "FROM productos_local ORDER BY nombre LIMIT ?",
                    (limite,)
                )
            return cursor.fetchall()