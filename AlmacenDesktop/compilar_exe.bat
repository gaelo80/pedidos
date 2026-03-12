@echo off
REM Script para compilar AlmacenDesktop.exe en Windows
REM Requiere: Python 3.10+ y PyInstaller instalado

echo ============================================
echo  Compilando AlmacenDesktop.exe
echo ============================================
echo.

REM Verificar si Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no está instalado o no está en PATH
    echo Descárgalo desde: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Verificar si PyInstaller está instalado
python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller no está instalado. Instalando...
    python -m pip install pyinstaller --upgrade
)

REM Limpiar compilaciones anteriores
echo Limpiando compilaciones anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist AlmacenDesktop.spec del AlmacenDesktop.spec

REM Ejecutar compilación
echo.
echo Iniciando compilación (esto puede tomar 2-3 minutos)...
echo.
pyinstaller build_exe.spec

REM Verificar resultado
if %errorlevel% equ 0 (
    echo.
    echo ============================================
    echo ✅ COMPILACIÓN EXITOSA
    echo ============================================
    echo.
    echo El ejecutable está en: dist\AlmacenDesktop\AlmacenDesktop.exe
    echo.
    echo Instrucciones de instalación:
    echo 1. Copiar la carpeta "dist\AlmacenDesktop" a Program Files
    echo 2. Crear acceso directo del .exe en Desktop
    echo 3. Ejecutar AlmacenDesktop.exe
    echo.
    pause
) else (
    echo.
    echo ============================================
    echo ❌ ERROR EN LA COMPILACIÓN
    echo ============================================
    echo.
    echo Revisa los errores arriba
    pause
    exit /b 1
)
