#!/usr/bin/env python3
"""
Script para compilar AlmacenDesktop en un único .exe empaquetado.

Requisitos previos:
  pip install pyinstaller

Uso:
  python build_exe.py

Resultado:
  dist/AlmacenDesktop.exe (archivo único, ~80-120 MB)
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

# Colores para terminal
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'

def log(msg, color=GREEN):
    print(f"{color}{'='*70}")
    print(f"{msg}")
    print(f"{'='*70}{RESET}")

def error(msg):
    print(f"{RED}ERROR: {msg}{RESET}")
    sys.exit(1)

def check_dependencies():
    """Verifica que PyInstaller esté instalado."""
    try:
        import PyInstaller
        log(f"✓ PyInstaller encontrado: {PyInstaller.__version__}", GREEN)
    except ImportError:
        error("PyInstaller no está instalado.\n"
              "Instala con: pip install pyinstaller")

def clean_build():
    """Limpia compilaciones anteriores."""
    log("Limpiando compilaciones anteriores...", YELLOW)
    dirs_to_remove = ['build', 'dist', 'AlmacenDesktop.spec']
    for d in dirs_to_remove:
        if os.path.exists(d):
            if os.path.isdir(d):
                shutil.rmtree(d)
                print(f"  ✓ Removido: {d}")
            else:
                os.remove(d)
                print(f"  ✓ Removido: {d}")

def build_exe():
    """Compila el .exe con PyInstaller."""
    log("Compilando AlmacenDesktop.exe...", YELLOW)

    cmd = [
        'pyinstaller',
        '--onefile',  # ← Un único ejecutable
        '--windowed',  # Sin consola
        '--name=AlmacenDesktop',
        '--icon=icon.ico' if os.path.exists('icon.ico') else '',  # Icono opcional
        '--add-data=modulos:modulos',  # Incluir carpeta modulos
        '--add-data=repositories:repositories',  # Incluir repositories
        '--collect-all=customtkinter',  # Incluir customtkinter
        '--collect-all=PIL',  # Incluir Pillow
        '--hidden-import=sqlite3',
        '--hidden-import=json',
        '--hidden-import=threading',
        '--hidden-import=requests',
        '--hidden-import=database',
        '--hidden-import=auth',
        '--hidden-import=repositories',
        '--hidden-import=modulos',
        '--distpath=dist',
        '--buildpath=build',
        '--specpath=.',
        'main.py',
    ]

    # Eliminar strings vacíos
    cmd = [c for c in cmd if c]

    print(f"\nComando: {' '.join(cmd)}\n")

    result = subprocess.run(cmd, capture_output=False)

    if result.returncode != 0:
        error(f"PyInstaller falló con código {result.returncode}")

    log("✓ Compilación completada", GREEN)

def verify_exe():
    """Verifica que el .exe fue creado."""
    exe_path = os.path.join('dist', 'AlmacenDesktop.exe')

    if not os.path.exists(exe_path):
        error(f"El archivo {exe_path} no fue creado")

    size_mb = os.path.getsize(exe_path) / (1024 * 1024)
    log(f"✓ {exe_path} creado exitosamente\n"
        f"  Tamaño: {size_mb:.1f} MB", GREEN)

def main():
    """Ejecuta el proceso completo de compilación."""
    print(f"\n{GREEN}{'='*70}")
    print(f"COMPILADOR DE AlmacenDesktop -> Unico Ejecutable (.exe)")
    print(f"{'='*70}{RESET}\n")

    # Cambiar al directorio del script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    print(f"Directorio de trabajo: {os.getcwd()}\n")

    try:
        check_dependencies()
        clean_build()
        build_exe()
        verify_exe()

        print(f"\n{GREEN}✓ ¡ÉXITO! El ejecutable está listo en: dist/AlmacenDesktop.exe{RESET}")
        print(f"\n{YELLOW}Próximos pasos:{RESET}")
        print(f"  1. Copia dist/AlmacenDesktop.exe a la máquina del almacén")
        print(f"  2. Ejecuta AlmacenDesktop.exe")
        print(f"  3. Ve a Configuración → Red y Sincronización")
        print(f"  4. Ingresa la URL: https://tu-dominio.com/api")
        print(f"  5. Click 'Guardar' → 'Probar Conexión'\n")

    except KeyboardInterrupt:
        print(f"\n{RED}✗ Compilación cancelada por el usuario{RESET}")
        sys.exit(1)
    except Exception as e:
        error(str(e))

if __name__ == '__main__':
    main()
