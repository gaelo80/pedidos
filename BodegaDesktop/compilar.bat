@echo off
REM BodegaDesktop/compilar.bat
REM Script para compilar el .exe en Windows

echo =====================================================
echo Bodega Desktop - Compilador
echo =====================================================
echo.

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no esta instalado o no esta en PATH
    pause
    exit /b 1
)

echo [1/3] Instalando dependencias...
pip install -q customtkinter Pillow requests urllib3 pyinstaller PyInstaller-Hooks-Contrib CTkMessagebox

if errorlevel 1 (
    echo ERROR: No se pudieron instalar las dependencias
    pause
    exit /b 1
)

echo [2/3] Limpiando builds anteriores...
rmdir /s /q build dist 2>nul
del /f /q *.spec 2>nul

echo [3/3] Compilando con PyInstaller...
python build_exe.py

if errorlevel 1 (
    echo.
    echo ERROR: La compilacion fallo
    pause
    exit /b 1
)

echo.
echo =====================================================
echo Compilacion completada!
echo Archivo: dist\BodegaDesktop.exe
echo =====================================================
echo.

REM Preguntar si abrir la carpeta
set /p abrir="Deseas abrir la carpeta dist? (S/N): "
if /i "%abrir%"=="S" (
    explorer dist
)

pause
