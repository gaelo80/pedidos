# BodegaDesktop/database.py
import sqlite3
from contextlib import contextmanager

DB_PATH = "bodega_local.db"


def obtener_conexion():
    """Retorna una conexión a la base de datos local."""
    return sqlite3.connect(DB_PATH)


def inicializar_db():
    """Crea las tablas si no existen."""
    conexion = obtener_conexion()
    cursor = conexion.cursor()

    # Tabla de configuración
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS configuracion (
            id INTEGER PRIMARY KEY,
            clave TEXT UNIQUE,
            valor TEXT
        )
    ''')

    # Tabla de borradores locales (caché de despacho en progreso)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS borradores_locales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id INTEGER UNIQUE,
            datos_json TEXT,
            fecha_creacion TEXT,
            fecha_modificacion TEXT
        )
    ''')

    conexion.commit()
    conexion.close()


@contextmanager
def transaccion():
    """Context manager para transacciones"""
    conn = obtener_conexion()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def guardar_configuracion(clave: str, valor: str):
    """Guarda un valor de configuración"""
    with transaccion() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO configuracion (clave, valor) VALUES (?, ?)",
            (clave, valor)
        )


def obtener_configuracion(clave: str, default=None):
    """Obtiene un valor de configuración"""
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute("SELECT valor FROM configuracion WHERE clave = ?", (clave,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] if resultado else default
