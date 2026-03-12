# database.py
import sqlite3

DB_PATH = "almacen_local.db"

def obtener_conexion():
    """Retorna una conexión a la base de datos local."""
    return sqlite3.connect(DB_PATH)

def inicializar_db():
    """Crea las tablas si no existen."""
    conexion = obtener_conexion()
    cursor = conexion.cursor()

    # Tabla de productos (Catálogo)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS productos_local (
            id_producto INTEGER PRIMARY KEY,
            codigo_barras TEXT UNIQUE,
            nombre TEXT,
            precio_detal REAL,
            stock_local INTEGER
        )
    ''')

    # Tabla de ventas (Agregamos la columna 'detalles' para guardar los items)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ventas_pendientes_sincronizar (
            id_venta INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            total REAL,
            metodo_pago TEXT,
            detalles TEXT,
            estado_sincronizacion INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS devoluciones_pendientes (
            id_devolucion INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            tipo TEXT,
            detalles TEXT,
            estado_sincronizacion INTEGER DEFAULT 0
        )
    ''')

    # Tabla para contraseña maestra de configuración
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS maestro_config (
            id INTEGER PRIMARY KEY,
            clave TEXT UNIQUE,
            valor TEXT
        )
    ''')

    conexion.commit()
    conexion.close()