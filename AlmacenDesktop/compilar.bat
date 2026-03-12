@echo off
REM Script para compilar AlmacenDesktop en un único .exe empaquetado
REM Requisitos: Python 3.9+ y pip install pyinstaller

echo ╔════════════════════════════════════════════════════════════════════╗
echo ║         COMPILADOR: AlmacenDesktop → Único Ejecutable (.exe)      ║
echo ╚════════════════════════════════════════════════════════════════════╝
echo.

REM Verificar que Python esté instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no está instalado o no está en PATH
    pause
    exit /b 1
)

REM Instalar PyInstaller si no está presente
echo [1/3] Verificando PyInstaller...
pip list | findstr /i "pyinstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo        PyInstaller no encontrado. Instalando...
    pip install pyinstaller
)

REM Cambiar al directorio del script
cd /d "%~dp0"

echo.
echo [2/3] Instalando dependencias necesarias...
pip install -r requirements.txt -q

echo.
echo [3/3] Compilando AlmacenDesktop.exe...
python build_exe.py

if %errorlevel% equ 0 (
    echo.
    echo ✓ ¡COMPILACIÓN EXITOSA!
    echo.
    echo El archivo está en: %cd%\dist\AlmacenDesktop.exe
    echo.
    pause
) else (
    echo.
    echo ✗ Error durante la compilación
    pause
    exit /b 1
)
