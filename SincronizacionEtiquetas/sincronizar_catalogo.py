"""
Sincroniza el catálogo de etiquetas (referencia, nombre, color, talla y
código de barras) desde el servidor hacia un archivo Excel local, para que
el programa de impresión de etiquetas siempre tenga los datos al día.

Pensado para ejecutarse periódicamente vía el Programador de Tareas de
Windows (Task Scheduler) -- ver instrucciones en README.md.
"""
import json
import logging
import os
import sys
from pathlib import Path

import requests

CARPETA_SCRIPT = Path(__file__).resolve().parent
RUTA_CONFIG = CARPETA_SCRIPT / 'config.json'
RUTA_LOG = CARPETA_SCRIPT / 'sincronizacion.log'

CONFIG_EJEMPLO = {
    "servidor_url": "https://pedidoslouisferry.online",
    "usuario": "usuario_del_sistema",
    "password": "contraseña_del_sistema",
    "carpeta_destino": str(Path.home() / "Documents" / "CatalogoEtiquetas"),
    "nombre_archivo": "catalogo_etiquetas.xlsx",
    "verificar_ssl": True
}

logging.basicConfig(
    filename=str(RUTA_LOG),
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    encoding='utf-8',
)


def cargar_configuracion():
    if not RUTA_CONFIG.exists():
        with open(RUTA_CONFIG, 'w', encoding='utf-8') as f:
            json.dump(CONFIG_EJEMPLO, f, indent=4, ensure_ascii=False)
        mensaje = (
            f"No existía config.json, se creó uno de ejemplo en {RUTA_CONFIG}. "
            "Complétalo con los datos reales (servidor, usuario, contraseña) "
            "y vuelve a ejecutar el script."
        )
        logging.error(mensaje)
        print(mensaje)
        sys.exit(1)

    with open(RUTA_CONFIG, 'r', encoding='utf-8') as f:
        return json.load(f)


def obtener_token(servidor_url, usuario, password, verificar_ssl):
    url = servidor_url.rstrip('/') + '/api/token/'
    respuesta = requests.post(
        url,
        json={'username': usuario, 'password': password},
        timeout=15,
        verify=verificar_ssl,
    )
    respuesta.raise_for_status()
    return respuesta.json()['access']


def descargar_catalogo(servidor_url, token, verificar_ssl):
    url = servidor_url.rstrip('/') + '/productos/api/exportar-catalogo-etiquetas/'
    respuesta = requests.get(
        url,
        headers={'Authorization': f'Bearer {token}'},
        timeout=60,
        verify=verificar_ssl,
    )
    respuesta.raise_for_status()
    return respuesta.content


def guardar_archivo_atomico(contenido, carpeta_destino, nombre_archivo):
    carpeta_destino = Path(carpeta_destino)
    carpeta_destino.mkdir(parents=True, exist_ok=True)

    ruta_final = carpeta_destino / nombre_archivo
    ruta_temporal = carpeta_destino / f".{nombre_archivo}.tmp"

    with open(ruta_temporal, 'wb') as f:
        f.write(contenido)

    # Reemplazo atómico: el programa de etiquetas nunca ve el archivo "a medias".
    os.replace(ruta_temporal, ruta_final)
    return ruta_final


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass  # stdout redirigido a algo que no soporta reconfigure (ej. Task Scheduler)

    config = cargar_configuracion()
    verificar_ssl = config.get('verificar_ssl', True)
    try:
        token = obtener_token(
            config['servidor_url'], config['usuario'], config['password'], verificar_ssl
        )
        contenido = descargar_catalogo(config['servidor_url'], token, verificar_ssl)
        ruta = guardar_archivo_atomico(contenido, config['carpeta_destino'], config['nombre_archivo'])
        logging.info(f"Sincronización exitosa: {ruta} ({len(contenido)} bytes)")
        print(f"OK: catálogo actualizado en {ruta}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error de conexión/autenticación: {e}")
        print(f"ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error inesperado: {e}")
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
