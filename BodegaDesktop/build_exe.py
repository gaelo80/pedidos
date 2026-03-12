# BodegaDesktop/build_exe.py
"""
Script para compilar BodegaDesktop.exe con PyInstaller
Ejecutar con: python build_exe.py
"""
import subprocess
import sys
import os

print("=" * 70)
print("Compilando BodegaDesktop.exe")
print("=" * 70)

# Comando PyInstaller
cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--windowed",
    "--name=BodegaDesktop",
    "--icon=assets/despacho.png" if os.path.exists("assets/despacho.png") else "",
    "--collect-all=customtkinter",
    "--collect-all=PIL",
    "--collect-all=urllib3",
    "--hidden-import=sqlite3",
    "--hidden-import=requests",
    "--hidden-import=threading",
    "--hidden-import=json",
    "--hidden-import=webbrowser",
    "--hidden-import=database",
    "--add-data=modulos:modulos",
    "--add-data=assets:assets" if os.path.exists("assets") else "",
    "main.py"
]

# Limpiar comandos vacíos
cmd = [c for c in cmd if c]

print("\nEjecutando:")
print(" ".join(cmd))
print()

try:
    result = subprocess.run(cmd, check=True)
    print("\n" + "=" * 70)
    print("[OK] Compilacion exitosa")
    print("[ARCHIVO] Ubicacion: dist/BodegaDesktop.exe")
    print("=" * 70)
except subprocess.CalledProcessError as e:
    print("\n" + "=" * 70)
    print(f"[ERROR] Error en compilacion: {e}")
    print("=" * 70)
    sys.exit(1)
