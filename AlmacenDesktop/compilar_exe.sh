#!/bin/bash
# Script para compilar AlmacenDesktop en Mac/Linux
# Requiere: Python 3.10+ y PyInstaller

echo "============================================"
echo "  Compilando AlmacenDesktop"
echo "============================================"
echo ""

# Verificar si Python está instalado
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 no está instalado"
    echo "Instálalo con: brew install python3 (Mac) o apt install python3 (Linux)"
    exit 1
fi

# Verificar si PyInstaller está instalado
if ! python3 -m pip show pyinstaller &> /dev/null; then
    echo "PyInstaller no está instalado. Instalando..."
    python3 -m pip install pyinstaller --upgrade
fi

# Limpiar compilaciones anteriores
echo "Limpiando compilaciones anteriores..."
rm -rf build dist AlmacenDesktop.spec

# Ejecutar compilación
echo ""
echo "Iniciando compilación (esto puede tomar 2-3 minutos)..."
echo ""
pyinstaller build_exe.spec

# Verificar resultado
if [ $? -eq 0 ]; then
    echo ""
    echo "============================================"
    echo "✅ COMPILACIÓN EXITOSA"
    echo "============================================"
    echo ""
    echo "El ejecutable está en: dist/AlmacenDesktop/AlmacenDesktop"
    echo ""
    echo "Para ejecutar:"
    echo "  ./dist/AlmacenDesktop/AlmacenDesktop"
    echo ""
else
    echo ""
    echo "============================================"
    echo "❌ ERROR EN LA COMPILACIÓN"
    echo "============================================"
    exit 1
fi
